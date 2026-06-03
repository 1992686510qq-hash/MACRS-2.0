# Crucible Architecture Analysis

> Source: `Bambushu/crucible` — commit `52607e9` (May 4, 2026), 84% Python, 16% Shell
> 51 stars, 7 forks, MIT license

## 1. Overview

Crucible is a **Claude Code slash-command skill** that performs codebase-level adversarial review using a panel of 4 structurally-different frontier models, followed by a Claude verification pass. It is NOT a standalone CLI — it runs inside Claude Code, which provides the verification intelligence and full source access.

The core insight: single-model review has correlated blind spots. Models from the same training lineage (GPT-class, Claude-class) tend to miss the same things. A panel drawn from genuinely different vendor families (DeepSeek, Google, Moonshot, MiniMax) produces uncorrelated findings. But since OS models can hallucinate convergently, Claude reads every finding back against the actual source code before the user sees it.

**Repo structure (8 files + 2 dirs):**
```
crucible/
├── skill.md              # Canonical Claude Code skill spec (the "brain")
├── review-prompts.md     # 4 prompt templates (pass 1/2/3 + meta)
├── scripts/
│   ├── crucible-run.sh        # One-shot end-to-end CI wrapper
│   ├── orchestrate.py         # Per-file dispatch engine, OpenRouter calls
│   ├── build_report.py        # Aggregates findings to report.md
│   ├── compare-reports.py     # Diff two run caches side-by-side
│   ├── chunk-file.py          # Language-aware splitter (>1500 lines)
│   └── discover-premium.sh    # Populates ~/.crucible/models.json
├── assets/hero.png
├── LICENSE (MIT)
└── README.md
```

---

## 2. Multi-Model Adversarial Design

### 2.1 Panel Composition

The default panel comprises 4 models from 4 different vendor families, discovered and health-checked by `discover-premium.sh`:

| Priority | Family | Primary Model | Fallbacks |
|----------|--------|--------------|-----------|
| 1 | DeepSeek | `deepseek-v4-pro` | v4-flash, v3.2-speciale, v3.2-exp, r1-0528 |
| 2 | Google | `gemini-3.1-pro-preview` | gemini-2.5-pro, gemini-2.5-pro-preview |
| 3 | Moonshot (Kimi) | `kimi-k2.6` | k2-thinking, k2.5, k2-0905, k2 |
| 4 | MiniMax | `minimax-m2.7` | m2.5, m2.1, m2 |
| 5+ | Qwen (fallback) | `qwen3-coder-plus` | qwen3-max-thinking, qwen3.6-plus |
| 6+ | GLM (fallback) | `glm-5.1` | glm-5, glm-4.7 |
| 7+ | Llama-4 (western) | `llama-4-maverick` | llama-4-scout |
| 8+ | Mistral (western) | `mistral-small-2603` | — |

**Family diversity is strict**: at most 1 model per vendor family. The discovery script walks preferences in order, and refuses to add a second model from a family already represented. Only when all distinct families are exhausted would duplicates be allowed (but the script currently caps at PANEL_SIZE=4).

**Model health tracking**: orchestrate.py uses a 3-consecutive-failure threshold (not 2, to avoid dropping on a transient rate-limit). Any successful pass resets the counter. This is implemented in `update_health()` which mutates a shared `healthy` dict. The self-test in the script verifies this logic.

**Health verification**: Each candidate model is pinged with a "Say OK" request (max_tokens=16) during discovery. Response time and context window are recorded in the cache.

**Cache TTL**: 72 hours. After that, `discover-premium.sh` re-fetches the model list and re-pings candidates.

### 2.2 Review Modes: Sequential vs Blind

#### Sequential (default)

Files are reviewed in a **chain**. Each model sees the previous model's output:

```
File -> [DeepSeek: Pass 1 (base adversarial)]
     -> [Gemini: Pass 2 (validate + add)]
     -> [Kimi: Pass 2 (validate + add)]
     -> [MiniMax: Pass 2 (validate + add)]
```

- **Pass 1** (first model in chain, or any model in blind mode): Independent adversarial review. Output is a JSON object with `findings[]` array.
- **Pass 2** (every subsequent model): Receives the `{file, prior_findings, code}`. Independently reviews the code first (explicitly told "do not anchor on prior findings"), then for each prior finding returns `validate: {verdict: agree|disagree|refine, note, revised_severity}`, plus `new_findings[]` for anything missed.
- **Pass 3** (only in `--deep` mode): A consolidator model receives BOTH prior reviewers' full output, merges them, eliminates duplicates, re-calibrates severity, and emits the single final `findings[]` with `flagged_by[]` attribution.

#### Blind (parallel-independent)

All models receive ONLY the Pass 1 prompt — no model sees any other's output. After all reviews complete, `build_report.py` runs **consensus deduplication**: findings within 3 lines on the same file with >=70% Jaccard title-word overlap are merged into one finding with accumulated `flagged_by[]`. The merged finding takes the highest severity among the cluster.

**Key difference**: Sequential mode builds findings incrementally with cross-validation built in. Blind mode gets more independent samples but requires post-hoc dedup. The README notes that findings flagged by 2+ models in blind mode become "consensus" findings ranked higher.

**Combining modes**: `/crucible --all --deep --blind` runs the full repo with 3 models per file independently, then consensus-dedups.

### 2.3 Cross-File Meta-Pass

After all per-file reviews, one model does an architectural sweep looking for:
1. **Repeated anti-patterns** — same problem in 3+ files suggests missing abstraction
2. **Inconsistencies** — some files validate, others don't; mixed error handling; different loggers
3. **Coupling smells** — import cycles, leaky abstractions, modules that know internals
4. **Missing layers** — API handlers talking directly to DB
5. **Test coverage gaps** — files with logic but no test sibling
6. **Entry-point exposure** — threat surface analysis

The meta-pass receives: the project tree (from `git ls-files`), aggregated per-file finding titles (not full text, to keep the prompt small), and the file list. It outputs `findings/_meta.json`.

### 2.4 Per-File Pipeline Details

For each file, the orchestrator:
1. Reads the file and prepends line numbers (`1: import jwt`, etc.)
2. Infers language by extension (`.ts` -> TypeScript, `.py` -> Python, etc.)
3. Splices deployment context block before the code
4. Builds prompt from template + interpolated variables
5. Calls each healthy model with 8-second delay between calls
6. Extracts JSON from response (strips ```json fences, finds first `{...}`)
7. If JSON parse fails -> increments model's consecutive failure counter
8. If 3 consecutive failures -> drops model from panel
9. Persists: `findings/<safe_filename>.json`, appends to `progress.jsonl`, saves `transcripts/<file>.<model>.txt`
10. Streams progress: `OK [i/N] path.ts (N findings: Cc Hh Mm Ll) — X.Xs`

**Resume support**: The orchestrator checks if `findings/<sanitized_path>.json` already exists and skips completed files. A network blip mid-run just requires re-running the same command.

---

## 3. Claude as Verifier

### 3.1 What Claude Verifies

The verification phase is the **critical differentiator** — and it is NOT implemented in the Python scripts. It lives in `skill.md` as part of the Claude Code slash-command flow. The Python orchestrator handles the OS panel; Claude handles verification.

Claude's verification scope:
- **Every CRITICAL finding** — read the actual source at the cited line
- **Every HIGH finding** — read the actual source at the cited line
- MEDIUM and LOW findings are NOT verified (implicit trust)

Claude categorizes each finding into one of four verdicts:

| Verdict | Meaning |
|---------|---------|
| **Confirmed** | The finding is real, the cited line has the described issue, the suggested fix is sound |
| **Refined** | The bug is real but severity/category/line is wrong. Claude adjusts it. |
| **Disputed / False Positive** | The cited code does NOT have the described issue (model hallucinated or misread) |
| **Needs human judgment** | Claude cannot determine definitively (edge case, needs domain knowledge) |

Additionally, Claude adds **up to three findings the panel missed** — leveraging its own reasoning to catch what 4 different OS models collectively overlooked.

### 3.2 Verification Prompt Structure

The verification prompt (from `skill.md`, inferred from the sample report structure) instructs Claude to:

1. For each CRITICAL and HIGH finding:
   - Read the actual source file at the cited line
   - Determine: does the code actually do what the finding claims?
   - Categorize: confirmed / refined / disputed / needs-human
   - Provide evidence: quote the relevant source lines
2. After reviewing all findings:
   - Scan for anything the panel clearly missed
   - Add up to 3 additional findings with the same severity+category format
3. Append the verification section to the report

### 3.3 Verification in CI Mode (crucible-run.sh)

The one-shot CI wrapper **skips verification**. From the README:
> The verification phase is skipped in this mode (it requires Claude); you get the panel's raw output.

This means the verification phase is inherently tied to Claude Code's interactive session. It cannot be automated in a pipeline without a Claude model available. This is both a limitation (no CI verification) and a design choice (verification requires genuine understanding, not scripted rules).

### 3.4 Evidence of Verification Quality

The sample report in the README shows specific, actionable verification:
- `src/api/auth/session.ts:48` -> "matched code at line; fix is sound" (confirmed)
- `src/db/migrations/0042.sql:1` -> "table size is in fact ~50M rows per ANALYZE" (confirmed)
- `src/api/upload.ts:112` -> "bug is real but severity should be MEDIUM not HIGH (only triggers under multipart, not the current ingest path)" (refined)
- `src/utils/redact.ts:23` -> "panel flagged unsanitized regex, but the input already passes through sanitizeUserInput at line 8 of the calling site" (disputed)
- Additional: `src/api/auth/session.ts:71` (refresh-token rotation missing), `src/db/repo.ts:88` (missing FOR UPDATE)

This demonstrates that Claude reads **beyond the cited line** — it traces the call site in `redact.ts:23` back to `sanitizeUserInput` at line 8 of the caller, which no single-file review could do.

---

## 4. Review Modes Deep-Dive

### 4.1 Scope Selection

| Flag | Behavior | Example |
|------|----------|---------|
| *(default)* | Current branch's diff against base | `/crucible` |
| `--all` | Whole repo (excludes tests, node_modules, etc.) | `/crucible --all` |
| `--paths "<glob>"` | Shell glob pattern | `/crucible --paths "src/api/**/*.ts"` |
| `--diff <range>` | Specific git range | `/crucible --diff main...HEAD` |
| `--files <list>` | Explicit file list | `/crucible --files src/auth.ts src/db.ts` |

### 4.2 Mode Flags

| Flag | Effect |
|------|--------|
| `--deep` | Adds a 3rd pass (consolidator) to sequential chain |
| `--blind` | All models review independently (Pass 1 only). Consensus dedup after. |
| `--models N` | Use only the first N models from the panel (1-4) |
| `--no-meta` | Skip the cross-file architectural meta-pass |
| `--include-tests` | Don't skip `*.test.*` / `*.spec.*` files |
| `--resume <run-id>` | Resume an interrupted run from `.crucible-cache/<run-id>/` |
| `--deployment-context "..."` | Free-text scoping injected before code in every prompt |

### 4.3 Sequential vs Blind vs Deep — Confidence Tradeoffs

| Mode | Independence | Cross-Validation | Calls (per file) | Best For |
|------|-------------|-----------------|------------------|----------|
| Sequential (default) | Low (later models see prior) | Inline — each model validates/disputes | 4 | Reducing duplicates, building consensus |
| Sequential + Deep | Low | Inline + consolidator rechecks | 5 (3 deep + 2 chain) | Maximum thoroughness |
| Blind | High (no model sees others) | Post-hoc consensus dedup | 4 | Independent sampling, catching consensus misses |
| Blind + Deep | High | Post-hoc consensus dedup | 4 | Maximum independence |

### 4.4 Deployment Context — The False-Positive Reducer

This flag is described as "the highest-leverage flag" in the README. It solves a real problem: models default to "this code could run anywhere" and flag multi-worker auth, multi-region race conditions, and public-internet hardening even when the code is a desktop sidecar bound to localhost.

The context block is spliced into every per-file prompt BEFORE the code, wrapped in clear delimiters:
```
=== DEPLOYMENT CONTEXT (read before reviewing the code below) ===
Desktop Tauri sidecar bound to 127.0.0.1, single-process.
Multi-worker uvicorn / deployed-service findings are out of scope.
=== END DEPLOYMENT CONTEXT ===
```

This is a clever alternative to editing prompt templates — it keeps templates generic while scoping review context per-run.

---

## 5. Cost Control

### 5.1 Cost Model

Costs come from OpenRouter's `usage.cost` field returned in every chat completion response. The orchestrator accumulates these into `cost.json`:

```json
{
  "total_cost_usd": 0.1842,
  "total_calls": 83,
  "by_model": {
    "deepseek/deepseek-v4-pro": {"calls": 21, "cost_usd": 0.0321, "total_tokens": 245000},
    "google/gemini-3.1-pro-preview": {"calls": 21, "cost_usd": 0.0892, "total_tokens": 198000}
  },
  "calls": []
}
```

### 5.2 Pre-Flight Estimation

The pre-flight check (handled by the Claude Code skill, not Python) estimates:
- Files x Models = base calls (+1 for meta-pass)
- Cost thresholds that pause for confirmation:
  - >10 files
  - >30 calls
  - any single file >2000 lines
  - family-diversity warning (<4 distinct families for 4 models)

Under those thresholds, it runs without confirmation.

### 5.3 Estimated Costs (from README)

| Scope | Files | Calls | Wall Clock | Approx Cost |
|-------|-------|-------|------------|-------------|
| Small diff | 5 | 20 | ~3 min | $0.01-$0.05 |
| Typical PR | 20 | 80 | ~10 min | $0.10-$0.20 |
| Full feature branch | 50 | 200 | ~25 min | $0.30-$0.50 |
| Whole-repo deep audit | 100 | 400 | ~60 min | $0.50-$0.75 |

### 5.4 Rate Limiting Mitigation

- 8-second delay between calls to the same file (configurable via `--delay-between-calls`)
- Exponential backoff on 429/502/503/504: initial 4s, doubles each retry
- Honours `Retry-After` header from OpenRouter
- Max 2 retries per call (tightened from 4 to "fail fast on flaky models")
- 90-second request timeout (tightened from 180s — "most healthy calls finish in 30-60s")

### 5.5 Free-Tier Fallback

Deleting `~/.crucible/models.json` causes Crucible to fall back to free-tier models (same panel as `/rival`). It warns "running in degraded mode."

---

## 6. Finding Format & Conflict Handling

### 6.1 Per-File Finding JSON

Each file produces a JSON document with per-pass results and final consolidated findings:
```json
{
  "file": "src/api/auth/session.ts",
  "duration_s": 45.2,
  "passes": [
    {
      "model": "deepseek/deepseek-v4-pro",
      "status": "ok",
      "findings": [
        {
          "line": 48,
          "severity": "critical",
          "category": "security",
          "title": "Session token comparison uses ==, vulnerable to timing attack",
          "explanation": "An attacker who can measure response timing can recover the session token byte-by-byte.",
          "suggestion": "Replace with crypto.timingSafeEqual(Buffer.from(token), Buffer.from(expected))"
        }
      ]
    },
    {
      "model": "google/gemini-3.1-pro-preview",
      "status": "ok",
      "validates": [
        {
          "prior_finding_index": 0,
          "verdict": "agree",
          "note": "Confirmed -- timing attack is real.",
          "revised_severity": "critical"
        }
      ],
      "new_findings": [
        {
          "line": 71,
          "severity": "high",
          "category": "security",
          "title": "Missing refresh-token rotation",
          "explanation": "...",
          "suggestion": "..."
        }
      ]
    }
  ],
  "findings": []
}
```

### 6.2 Severity Guide (applied by models, from prompt template)

| Severity | Criteria |
|----------|----------|
| **critical** | Data loss, security breach, or production outage |
| **high** | Significant bug affecting core behavior or security |
| **medium** | Edge case, reliability concern, or maintainability hazard with real cost |
| **low** | Minor improvement, easy win |

Categories: `security`, `bug`, `performance`, `correctness`, `maintainability`

### 6.3 Inter-Model Conflict Handling

**In sequential mode**: Conflicts are handled inline by Pass 2. A model can `disagree` with a prior finding with reasoning. The disagreement is recorded in the pass result but does NOT remove the finding from the aggregated list — it stays with the validator's note. Disputes are preserved for Claude's verification pass to adjudicate.

**In blind mode**: Consensus dedup merges findings that AGREE (same file, within 3 lines, >=70% Jaccard title similarity). Conflicting findings (same line but different diagnoses) are NOT merged — they remain as separate findings, creating an explicit conflict for the user/Claude to resolve.

**Claude's verification role**: Claude is the ultimate arbiter. When it reads a disputed finding against the source, its verified/disputed/refined verdict overrides the panel. The report shows both the panel's raw finding AND Claude's adjudication.

### 6.4 Finding Attribution

Findings carry a `flagged_by` field listing which models caught each issue. In sequential mode, this is derived from pass-level data. In blind mode, consensus dedup merges attribution across models. The `build_report.py` attribution logic cross-references top-level findings against per-pass `findings[]` and `new_findings[]` arrays using line proximity (within 3 lines) and title-word overlap (Jaccard >=0.7).

### 6.5 Report Structure

The final `report.md` has 6 sections:
1. **Header**: run ID, scope, files reviewed, models, mode, total findings with severity breakdown
2. **CRITICAL/HIGH/MEDIUM/LOW sections**: Each finding with `file:line`, title, flagged models, category, explanation, suggested fix
3. **Verification Pass (Claude)**: Confirmed/Refined/Disputed/Additional findings
4. **Architectural / Cross-File**: Meta-pass findings with files_involved
5. **Per-File Summary**: Table with severity counts per file
6. **Models Used**: Per-model pass statistics (ok/empty/malformed/dropped counts)

---

## 7. Integration Surface

### 7.1 Crucible as a Claude Code Skill

Crucible is NOT a standalone CLI — it's a Claude Code slash command. Installation:
```bash
git clone https://github.com/Bambushu/crucible.git ~/.claude/skills/crucible
export OPENROUTER_API_KEY=sk-or-...
```
Then in any Claude Code session: `/crucible --diff main...HEAD`

The skill.md file defines the slash command's behavior within Claude Code. Claude handles:
- Scope resolution (parsing `--diff`, `--paths`, `--all`, etc.)
- Pre-flight estimation and confirmation
- Calling `orchestrate.py` for the OS panel
- The verification pass (reading findings against source)
- Calling `build_report.py` for final report generation

### 7.2 CI Integration

The `crucible-run.sh` wrapper is a standalone CI entry point that:
1. Runs `discover-premium.sh` if model cache is stale
2. Orchestrates per-file review + meta-pass
3. Builds the report
4. Outputs total cost

The verification phase is SKIPPED in CI mode. The report in CI mode contains only the raw panel findings without Claude's adjudication.

### 7.3 Adaptation for Our Multi-Agent System

Crucible maps naturally onto our Coordinator pattern:

| Crucible Component | Our Equivalent |
|-------------------|----------------|
| Claude Code skill (scope resolution) | Coordinator Agent (task decomposition) |
| orchestrate.py (panel dispatch) | Sub-Agent dispatch with `run_in_background: true` |
| Per-model passes | Parallel sub-Agents (blind mode) or serial pipeline (sequential) |
| build_report.py | Result aggregation in Coordinator |
| Claude verification | Dedicated verification Agent or Coordinator inline |
| crucible-run.sh | CI pipeline step |

**What we could reuse directly:**
- `orchestrate.py`: The OpenRouter dispatch engine is provider-agnostic and could serve as our model-calling backend
- `build_report.py`: The finding aggregation, severity sort, consensus dedup, and markdown rendering
- `review-prompts.md`: The prompt templates are well-designed and could be injected into our sub-Agent prompts
- `chunk-file.py`: Language-aware file splitting for large files

**What we would need to build:**
- A Coordinator skill that dispatches review sub-Agents instead of calling OpenRouter directly
- Hooking Claude verification into our existing Agent workflow
- Adapting the persistence model (`.crucible-cache/`) to our `D:/Claude Code/` output convention
- Adding our own model registry (we may not use OpenRouter for all models)

### 7.4 Key Integration Decisions

1. **Keep orchestrate.py as is?** Yes — it's battle-tested for OpenRouter calls. But we'd want to ADD an Anthropic SDK path for calling Claude models as panel members (not just verifier).

2. **Use OpenRouter or native APIs?** The README defends OpenRouter: "One key, one billing, one rate-limit story." For us in China: DeepSeek, Kimi, MiniMax, Qwen, GLM might be accessible via their native Chinese APIs with lower latency and cost than OpenRouter.

3. **Verification model?** Crucible uses Claude for verification only. In our system, we could use the Coordinator model for verification OR delegate to a dedicated verification sub-Agent.

---

## 8. Model Substitution

### 8.1 Difficulty Assessment

| Substitution | Difficulty | What to Change |
|-------------|-----------|----------------|
| Swap within OpenRouter | **Trivial** | Edit `~/.crucible/models.json` or `PREFERENCES[]` in discover-premium.sh |
| Add a new OpenRouter model | **Trivial** | Add to `PREFERENCES[]` array; discovery picks it up automatically |
| Replace MiniMax with Claude (via Anthropic SDK) | **Medium** | Add new `call_anthropic()` function to orchestrate.py; add prompt caching; handle different response format |
| Add local model (Ollama, vLLM) | **Medium** | Add `call_local()` function; OpenAI-compatible API if supported; handle context window limits |
| Change panel size (more than 4) | **Medium** | Sequential: prompt templates exist for up to pass 3; beyond that, Pass 2 template re-used. Blind: no limits. |
| Use Chinese-native APIs | **Medium-High** | Replace `call_openrouter()` with provider-specific SDKs (DashScope for Qwen, DeepSeek API, Moonshot API, MiniMax API) |
| Run fully offline | **High** | Replace all OpenRouter calls with local endpoints; model diversity becomes a challenge |

### 8.2 Provider Dependency Map

The system currently has one hard dependency: **OpenRouter**. All model calls go through `call_openrouter()` in `orchestrate.py` using the OpenAI-compatible chat completions endpoint. The function is self-contained (~40 lines), making it the single point of change for adding new backends.

The response parsing (`extract_model_output`, `extract_json_object`) is provider-agnostic — it handles standard `.choices[0].message.content`, reasoning models' `.reasoning_content`, and markdown fence stripping.

### 8.3 What's Hard-Coded vs Configurable

**Hard-coded:**
- OpenRouter URL and headers in `orchestrate.py`
- Max tokens (16384)
- Request timeout (90s)
- Max retries (2)
- Initial backoff (4s)
- Drop threshold (3 consecutive failures)
- Default delay between calls (8s)
- Prompt templates (4 specific H2 sections in `review-prompts.md`)

**Configurable:**
- Model list (`~/.crucible/models.json` or `--models` flag)
- Panel size (`--panel-size` or `--models N`)
- Review mode (`--mode sequential|blind`, `--deep`)
- Meta-pass inclusion (`--no-meta`)
- Delay between calls (`--delay-between-calls`)
- Deployment context (`--deployment-context`)
- Prompt templates (edit `review-prompts.md` directly)

---

## 9. Strengths & Weaknesses

### 9.1 Strengths

**1. True Multi-Family Diversity**
Not "4 personas of the same model" (like RaadSmid) but 4 genuinely different models from different training runs. The README explicitly contrasts with RaadSmid: "every persona is the same model. Crucible spins up four genuinely different models from four different vendor families."

**2. Verification as a First-Class Citizen**
The Claude verification pass is not an afterthought — it's the core value proposition. Reading findings against actual source code catches convergent hallucinations that 4 models could collectively produce. The sample report shows Claude doing sophisticated verification: tracing call sites, checking table sizes via ANALYZE, adjusting severity based on actual ingest paths.

**3. Resume Architecture**
Per-file persistence means a network blip doesn't lose work. The orchestrator checks for existing findings JSON before reviewing each file. Progress is written to `progress.jsonl` for monitoring. Transcripts are saved for audit.

**4. Aggressive Health Tracking**
The 3-consecutive-failure threshold is well-calibrated (not 2, which would drop on transient rate limits; not infinite, which would stall on broken models). The self-test in orchestrate.py verifies this logic: 2 fails + 1 success + 2 fails should NOT drop.

**5. Deployment Context**
A simple but high-leverage flag that reduces false positives. Models default to "this code could run anywhere" — scoping to "Desktop sidecar bound to localhost" eliminates an entire class of invalid findings.

**6. Self-Contained CI Mode**
Single bash command produces a report. No Claude Code session needed. Costs and model health tracked per run.

**7. Prompt Engineering is Sound**
- "Do not anchor on prior findings" (Pass 2)
- "Do not inflate to look thorough" (severity calibration instruction)
- "If you find nothing of substance, return an empty findings array. Do not invent issues."
- JSON-only output format with explicit instruction: "no prose, no markdown fences"
- File contents with line numbers prepended

**8. Cost Transparency**
Every call's cost is tracked via OpenRouter's `usage.cost`. Per-model breakdown. Pre-flight estimate before spending. Confirmation gate for larger scopes.

**9. Transcript Audit Trail**
Both prompts AND responses are saved. The deployment context block in transcripts lets verification grep confirm it was injected.

### 9.2 Weaknesses

**1. Verification is Claude-Only and Interactive-Only**
The most valuable feature (verification) requires a Claude Code session and cannot run in CI. This limits adoption to interactive workflows. A CI-able verification pass (perhaps using a cheaper Claude model via API) would expand use cases.

**2. Very Early Stage**
3 commits total. No releases. No tests beyond the single self-test in orchestrate.py. No evidence of production usage beyond the author's own projects. Edge cases around model output parsing are handled with "log to transcripts/ and continue" — reasonable for a v0 but fragile.

**3. Sequential Anchoring Risk**
In sequential mode, later models see prior findings. The Pass 2 prompt says "do not anchor on prior findings" but anchoring bias is a well-known LLM failure mode. There's no mechanism to detect or measure anchoring — no comparison of "would this model have found this independently?"

**4. No Prompt Caching**
The same file content is sent to every model in the panel. OpenRouter supports prompt caching (Anthropic-style), but orchestrate.py doesn't use it. For the 4-model panel, this means 4x the token cost for identical prefixes.

**5. Language Support is Extension-Based Only**
Language inference maps file extensions to language names. No detection of framework-specific patterns (React vs Vue, Flask vs FastAPI, etc.). The models might produce framework-inappropriate findings.

**6. JSON Parsing Resilience is Basic**
The `extract_json_object` function strips markdown fences and searches for `{...}`. If a model returns JSON with a trailing comma or unescaped character, it fails silently. No retry with "your JSON was malformed, please fix" — the call is treated as a failure, incrementing the model's failure counter.

**7. No Incremental Review**
Re-running Crucible on the same codebase re-reviews every file. There's no caching of "this file hasn't changed since the last run." For whole-repo audits on large codebases, this wastes time and money.

**8. Meta-Pass Depends on Tree Completeness**
The meta-pass needs a project tree. It tries `git ls-files` first, falls back to os.walk with a 200-entry cap. For very large repos, the tree is truncated and architectural findings may miss cross-module patterns.

**9. Model Quality is Not Monitored**
Health tracking only checks "did we get valid JSON?" — not "were the findings reasonable?" A model could return valid JSON with 50 low-quality findings and the system would accept them all. There's no finding quality scoring or anomaly detection (e.g., "this model flagged 100 findings on a 50-line file — suspicious").

**10. No Custom Exclusion Rules**
Files are included/excluded by test-pattern matching only. There's no `.crucibleignore` or configurable exclusion list. Third-party code, generated files, and vendored dependencies would all be reviewed unless explicitly excluded by scope.

### 9.3 Innovation Scorecard

| Aspect | Innovation Level | Notes |
|--------|-----------------|-------|
| Multi-model panel | **Medium** | Inspired by ensemble methods in ML; `/rival` did single-model adversarial first |
| Vendor-family diversity enforcement | **High** | The discover-premium.sh family constraint is genuinely novel in the code-review space |
| Claude verification pass | **High** | No other tool has a separate verification model that reads findings against source |
| Deployment context injection | **Medium** | Simple but effective; rarely seen in code-review tools |
| Consensus dedup in blind mode | **Low** | Standard deduplication with title similarity matching |
| Per-file persistence + resume | **Low** | Well-implemented but not novel |
| Consecutive-failure model dropping | **Medium** | Good engineering; the 3-consecutive threshold is well-tuned |

---

## 10. Architecture Diagram

```
CLAUDE CODE SESSION
+----------------------------------------------------------+
|                                                           |
|  User: /crucible --diff main...HEAD --deep                |
|                                                           |
|  +----------------------------------------------------+  |
|  | SKILL.md (Canonical Spec)                           |  |
|  |  1. Resolve scope (git diff, glob, files)           |  |
|  |  2. Pre-flight: count files, estimate cost, confirm |  |
|  |  3. Call orchestrate.py -- files, models, mode      |  |
|  |  4. Call build_report.py -- renders report.md       |  |
|  |  5. VERIFICATION: Claude reads CRITICAL+HIGH        |  |
|  |     findings against source code                    |  |
|  |  6. Present report.md to user                       |  |
|  +----------------------------------------------------+  |
+----------------------------------------------------------+

orchestrate.py
+----------------------------------------------------------+
|                                                           |
|  For each file:                                           |
|  +----------------------------------------------------+  |
|  | File -> [DeepSeek: Pass 1]                          |  |
|  |      -> [Gemini: Pass 2] -- sees Pass 1 findings    |  |
|  |      -> [Kimi: Pass 2]    -- sees merged prior      |  |
|  |      -> [MiniMax: Pass 2] -- sees merged prior      |  |
|  |                                                      |  |
|  |      OR (--blind): all models get Pass 1 independently |  |
|  |      OR (--deep): Pass 3 consolidator after 2 passes |  |
|  +----------------------------------------------------+  |
|                                                           |
|  Meta-Pass: one model reviews all finding titles          |
|  + project tree -> architectural findings (_meta.json)    |
|                                                           |
|  Persists: findings/*.json, progress.jsonl, transcripts/* |
|  cost.json, run.log                                       |
+----------------------------------------------------------+

build_report.py
+----------------------------------------------------------+
|                                                           |
|  1. Load per-file findings + meta findings                 |
|  2. Reconstruct run state from cache (if no manifest)      |
|  3. Build attribution map (which model flagged each)       |
|  4. If --blind: consensus dedup (line proximity + overlap) |
|  5. Sort: severity -> file -> line                        |
|  6. Render report.md                                      |
+----------------------------------------------------------+
```

---

## 11. Recommendations for Our Adaptation

### 11.1 What to Adopt Directly

1. **Prompt templates** (`review-prompts.md`): The 3-tier pass structure (independent review -> validation + addition -> consolidation) is well-designed. Inject these into sub-Agent system prompts.

2. **Finding JSON schema**: Standardize our findings format on Crucible's structure. It's clean, machine-parseable, and supports multi-model attribution.

3. **Verification pattern**: The "read finding against source -> confirm/refine/dispute/missed" pattern is the right interface between review Agents and verification Agents.

4. **Consecutive-failure threshold**: Adopt the 3-consecutive (not total) failure threshold for model health in our Agent dispatch.

5. **Deployment context injection**: Add a `--context` flag to our review orchestrator for scoping findings.

### 11.2 What to Extend

1. **Add Anthropic SDK path to orchestrate.py**: For using Claude as a panel member, not just verifier. This would benefit from prompt caching.

2. **CI-able verification**: Implement a lightweight verification pass that doesn't require an interactive Claude Code session. Could use a small Claude model via API with structured output.

3. **Chinese API backends**: Add native API paths for DeepSeek, Moonshot/Kimi, MiniMax, Qwen, GLM — lower latency and cost for models hosted in China.

4. **Incremental review**: Cache per-file findings with content hashes. Only re-review changed files.

5. **Custom exclusion rules**: Add `.crucibleignore` support for excluding vendored code, generated files, and third-party dependencies.

### 11.3 What to Rethink

1. **Sequential anchoring**: Consider adding an "anchoring check" where after sequential review completes, one model from blind mode re-reviews the same file to catch anchoring artifacts.

2. **Meta-pass model selection**: Currently uses "next healthy model." Consider using a model selection strategy based on the meta-pass task (architectural reasoning benefits from different capabilities than per-file bug finding).

3. **Severity calibration**: The 4-tier severity system relies on model self-calibration. Consider adding a severity normalization step where Claude (or another model) re-calibrates all findings on a common scale before the final report.

---

## 12. Key Files Reference

| File | Lines | Purpose |
|------|-------|---------|
| `skill.md` | — | Canonical Claude Code skill spec (the "brain"). Defines slash command behavior, verification flow, pre-flight logic. |
| `review-prompts.md` | ~200 | 4 prompt templates (Pass 1, Pass 2 sequential, Pass 3 consolidator, Meta-pass) with output format specs and chunking instructions. |
| `scripts/orchestrate.py` | ~450 | Core engine: OpenRouter calls, model health tracking, JSON extraction, persistence, resume support, meta-pass dispatch. |
| `scripts/build_report.py` | ~350 | Report builder: loads findings, reconstructs run state, builds attribution maps, consensus dedup for blind mode, renders markdown. |
| `scripts/compare-reports.py` | ~200 | Diff tool for two Crucible run caches. Shows only-left, only-right, and shared findings with severity comparison. |
| `scripts/discover-premium.sh` | ~200 | Model discovery: fetches OpenRouter model list, picks first available per family, health-checks with ping, writes to ~/.crucible/models.json. |
| `scripts/crucible-run.sh` | ~120 | One-shot CI wrapper: discover models -> orchestrate -> build report. Skips verification. |
| `scripts/chunk-file.py` | ~120 | Language-aware file splitter for files >1500 lines. Uses function/class boundaries as split points. |
