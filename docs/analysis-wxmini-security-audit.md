# wxmini-security-audit: Deep Architecture Analysis

> Source: https://github.com/sssmmmwww/wxmini-security-audit
> Analyzed: 2026-06-01
> Purpose: Feed into general code-review agent architecture design session

---

## 1. Executive Summary

wxmini-security-audit is a WeChat Mini Program (wxapkg) automated security audit Skill built on Claude Code Agent Teams. It orchestrates 7 specialized agents through a 6-phase pipeline (0 through 3, with 2.5 conditional). The project's defining innovation is a dual-layer architecture where deterministic Python regex scripts guarantee exhaustive coverage and LLM agents guarantee contextual accuracy. This pattern has clear generalization potential beyond the WeChat Mini Program domain to any static code security audit.

Scale: 2 Python scripts (~930 lines each), 7 agent prompt files (~200-400 lines each), 1 orchestrator SKILL.md (~450 lines). Total: approximately 5,000 lines of prompt + script code.

---

## 2. The 7-Agent Architecture

### 2.1 Agent Roster

| # | Agent Name | Phase | Input Source | Analysis Type | Output |
|---|-----------|-------|-------------|---------------|--------|
| 01 | Decompiler | Phase 1 | Raw wxapkg files | Binary reverse engineering | file_inventory.json |
| 02 | SecretScanner | Phase 2 | raw_secrets.json (script) | Script-informed LLM analysis | secrets_report.json |
| 03 | EndpointMiner | Phase 2 | raw_endpoints.json (script) | Script-informed LLM analysis | api_endpoints.json + endpoints_fuzz.txt |
| 04 | CryptoAnalyzer | Phase 2 | file_inventory.json only | Pure LLM analysis | crypto_analysis.json |
| 05 | VulnAnalyzer | Phase 2 | file_inventory.json only | Pure LLM analysis | vuln_analysis.json |
| 06 | Reporter | Phase 3 | All Phase 2 JSON outputs | Aggregation + formatting | security_report.md + 5 auxiliary files |
| 07 | CustomAnalyzer | Phase 2.5 (conditional) | Phase 2 JSONs + user requirements | Deep-dive LLM analysis | custom_analysis.json |

### 2.2 Responsibility Boundaries (Critical Design Decision)

Each agent has hard-coded responsibility boundaries enforced via prompt engineering. The most notable boundary is between Agent 04 (CryptoAnalyzer) and Agent 07 (CustomAnalyzer):

- Agent 04 is forbidden from analyzing any user-specified specific API endpoint. Its domain is strictly universal global crypto analysis across all JS files.
- Agent 07 owns all user-directed deep-dive analysis (specific endpoints, parameters, Burp Suite correlations).
- The orchestrator must not inject user-specific requirements into Agent 04's prompt -- this is an explicit isolation rule in SKILL.md.

This boundary pattern prevents scope creep within agents and ensures the parallel Phase 2 agents remain purely generic, while user-specific concerns are handled in the sequential Phase 2.5.

### 2.3 Parallel vs Sequential Execution

```
Phase 0: Orchestrator (no sub-agent)                [sequential]
Phase 1: Agent-01 (decompile)                       [sequential, blocking]
Phase 1.5: Python scripts (orchestrator runs)       [sequential, blocking]
Phase 2: Agents 02,03,04,05 (4-way parallel)        [parallel, blocking gate]
Phase 2.5: Agent-07 (conditional)                   [sequential, blocking]
Phase 3: Agent-06 (report)                          [sequential, blocking]
```

The key parallelism insight: Agents 02-05 have no data dependencies on each other. Two (02, 03) depend on Phase 1.5 scripts; two (04, 05) depend only on Phase 1's file inventory. This allows all four to launch simultaneously, reducing wall-clock time by approximately 4x for the most compute-intensive phase.


---

## 3. The Dual-Layer Architecture (Script + LLM)

### 3.1 The Core Insight

This is the project's defining architectural contribution. It solves a fundamental tension in automated code review:

- Regex/scripts: Exhaustive, deterministic, fast, zero false negatives on defined patterns. But: high false positive rate, zero semantic understanding, cannot handle contextual patterns.
- LLMs: Semantic understanding, contextual reasoning, false positive filtering. But: non-deterministic, can miss things (coverage gaps), expensive at scale.

The solution: Use both in a pipelined manner, each doing what it does best.

### 3.2 How It Works Mechanically

**Layer 1 -- Python Script Layer (Phase 1.5)**:

Two scripts run sequentially on the orchestrator's machine (not as sub-agents):

1. endpoint_extractor.py (~930 lines): 28 distinct regex patterns covering:
   - Full HTTP/HTTPS URLs, WebSocket URLs
   - API path fragments (/api/..., /v1/..., etc.)
   - wx.request / wx.uploadFile / wx.downloadFile calls
   - BaseURL variable definitions
   - Cloud function calls, database collections
   - Third-party HTTP library calls (axios, fetch, jQuery)
   - Request wrapper function definitions
   - Template string URL construction
   - XMLHttpRequest, WebView src, GraphQL endpoints
   - Route configuration objects
   - Miniprogram navigation targets
   - And 13 more pattern categories

2. secret_scanner.py (~930 lines): ~70 regex rules organized in 8 categories:
   - WeChat credentials (AppID, AppSecret, MchID, PayKey, SessionKey)
   - Cloud service keys (AWS, Aliyun, Tencent, Huawei, Baidu, Qiniu, Volcengine, GCP/Firebase, Azure, Cloudflare, DigitalOcean, Heroku, Oracle)
   - Third-party service tokens (GitHub, GitLab, Slack, DingTalk, Feishu, WeCom, SendGrid, Stripe, Sentry, Twilio, Telegram, npm, Docker Hub, Netlify, Vercel)
   - Chinese service credentials (WeCom, DingTalk, Feishu, Alipay, Amap, Tencent Map, Baidu Map)
   - Database connection strings (MySQL, MongoDB, Redis, PostgreSQL, JDBC, FTP, SMTP, LDAP, RabbitMQ)
   - Tokens and keys (JWT, private keys, SSH keys, hardcoded passwords, bearer tokens, certificates)
   - Internal network infrastructure (IP addresses, internal domains)
   - Certificate/key file extensions

Each rule optionally defines context_keywords -- a list of keywords that must appear nearby for the match to be considered valid (e.g., Huawei AK requires huaweicloud in context). This is the script's basic attempt at false-positive reduction.

Both scripts output raw_*.json with by_file grouping (hits organized by source file) and metadata (file size, hit count, severity statistics, category statistics).

**Layer 2 -- LLM Agent Layer (Phase 2)**:

Agents 02 and 03 receive the raw_*.json files as input. Their core task is NOT to re-scan, but to:

- Filter false positives: Identify placeholder values, commented-out code, test fixtures, SDK examples
- Add semantic context: For Agent 03, this means BaseURL-to-path-fragment association (the script extracts fragments and BaseURLs separately; the LLM must connect them)
- Risk-rate findings: Apply nuanced severity assessment that regex cannot do
- Supplement missed findings: The LLM can identify semantic patterns the regex missed (e.g., an SMS config block using an API key from 3 lines above)

The key architectural principle: the script guarantees nothing is missed on defined patterns; the LLM guarantees what is reported is real and prioritized correctly.

### 3.3 Degradation Strategy

If Python is unavailable (script execution fails), Agents 02 and 03 automatically fall back to pure LLM mode (using grep to re-implement the regex scanning). This means:
- Coverage may drop (LLM grep is less exhaustive than Python regex)
- But the audit pipeline does not halt
- The degradation is explicit -- agents record their analysis method in output

This is a pragmatic graceful degradation pattern that prioritizes pipeline completion over perfection.

### 3.4 Why Not Pure LLM?

The design implicitly answers this question:
- Pure LLM scanning would require reading every file into context, which is prohibitively expensive for large codebases
- Pure LLM is non-deterministic -- run the same audit twice, get different hit counts
- Pure regex has too many false positives -- a security team would drown in noise
- The combination gives determinism where it matters (coverage) and intelligence where it matters (accuracy)

---

## 4. Agent Communication and Data Flow

### 4.1 File-Based Handoff (No Message Passing)

All inter-agent communication occurs through the filesystem. The output_dir directory (typically ./wxaudit-output/) serves as the shared state. There is no direct agent-to-agent message passing, no shared memory, no event bus.

Data flow diagram (artifacts):

```
Phase 1:  agent-01 --> file_inventory.json
Phase 1.5: python   --> raw_endpoints.json, raw_secrets.json
Phase 2:  agent-02 --> secrets_report.json   (reads raw_secrets.json + file_inventory.json)
          agent-03 --> api_endpoints.json     (reads raw_endpoints.json + file_inventory.json)
                        + endpoints_fuzz.txt
          agent-04 --> crypto_analysis.json   (reads file_inventory.json only)
          agent-05 --> vuln_analysis.json     (reads file_inventory.json only)
Phase 2.5: agent-07 --> custom_analysis.json  (reads all Phase 2 JSONs + file_inventory.json)
Phase 3:  agent-06 --> security_report.md     (reads all above JSON files)
                        api_endpoints_full.md
                        secrets_full.md
                        findings.json
                        domains.txt
                        endpoints_fuzz.txt (verifies)
```

### 4.2 The Orchestrator as Gating Mechanism

The orchestrator (SKILL.md executed by the main Claude Code session) does NOT perform analysis. Its sole responsibilities:

1. Parse user intent (Phase 0): Extract target directory, parse custom requirements
2. Create output directory: CWD/wxaudit-output/
3. Launch agents in correct order: Sequential for Phase 1, parallel for Phase 2, conditional for Phase 2.5
4. Verify phase gates: After each phase, check that expected output files exist and are valid before proceeding
5. Pass data between phases: Replace template variables ({target_dir}, {output_dir}, {skill_dir}) in agent prompts

Crucially, SKILL.md contains hard prohibitions (called iron rules) on the orchestrator:
- Must not create any analysis output files directly (only agents can)
- Must not skip phases
- Must not withhold user data from agents (e.g., Burp Suite information must be passed to Agent 07)
- Must not analyze code during the Phase 2 waiting period

### 4.3 Verification Gates

Each phase has explicit verification criteria. Examples:

- Phase 1 gate: file_inventory.json exists AND total_files > 0 AND JS file list is non-empty
- Phase 1.5 gate: Both raw_*.json files exist AND total_files_scanned > 0
- Phase 2 gate: At least 3 of 4 expected JSON files exist and are valid JSON
- Phase 3 gate: All 6 output files exist and security_report.md > 1KB

If a gate fails, the pipeline either retries (with a limit of 1 retry for Phase 3), degrades gracefully (Phase 1.5 failure -> Phase 2 agents in pure LLM mode), or terminates with an error report.


---

## 5. Coverage Model

### 5.1 How Coverage Is Defined

Coverage is defined at two levels:

Script-level coverage (guaranteed by Python):
- Every scannable file (.js, .json, .wxml, .html, .ts) is processed by both scripts
- Every regex rule is applied to every file
- Coverage = files_scanned / total_scannable_files (target: >= 95% for JS, 100% for JSON configs)
- The total_files_scanned field in raw_*.json records actual coverage

Agent-level coverage (best-effort by LLM):
- Agent 02 must analyze every non-placeholder hit in raw_secrets.json
- Agent 03 must attempt BaseURL association for every path fragment
- Agent 05 must check all 7 vulnerability dimensions (even if a dimension yields zero findings)
- Agent 06 must include every finding from every input JSON in the output files

### 5.2 Large File Handling

All agents share a tiered large-file strategy:

| File Size | Strategy |
|-----------|----------|
| <= 200KB | Read full file, complete analysis |
| 200KB - 500KB | grep for patterns, read context around hits |
| 500KB - 1MB | grep only, no full reads |
| > 1MB | grep only Critical/High priority patterns |
| > 2MB | Python scripts skip entirely, logged in skipped_large_files |

This preserves coverage of high-severity findings even in webpack-bundled monolith files (common in WeChat Mini Programs, where app-service.js can be many megabytes).

### 5.3 What Coverage Does NOT Mean

The project is explicit that coverage means pattern matching coverage, not semantic understanding coverage. The LLM agents may miss things that require deep semantic reasoning. The design acknowledges this limitation by:
- Labeling findings as confirmed vs requires backend verification
- Clearly separating what can be determined from static frontend code alone
- Not claiming to find vulnerabilities that require runtime behavior analysis

---

## 6. Integration Surface: Generalizing Beyond WeChat Mini Programs

### 6.1 What Is WeChat-Specific

- unveilr.exe reverse compilation tool (wxapkg format)
- wx.request, wx.cloud, wx.setStorageSync API patterns
- WXML/WXSS file formats
- WeChat-specific credential patterns (AppID, AppSecret, MchID, PayKey)
- app.json / project.config.json config structures
- Mini-program subpackage architecture

### 6.2 What Is Domain-Agnostic (Generalizable)

The architecture pattern generalizes cleanly:

1. Phase pipeline: Decompile/Prepare -> Script Pre-scan -> Parallel Analysis -> Custom Deep-Dive -> Report
2. Dual-layer: Deterministic regex layer + LLM intelligence layer, applicable to any code audit
3. Agent specialization by concern: Secret scanning, endpoint/API discovery, crypto analysis, vulnerability analysis are universal security concerns
4. File-based artifact handoff: JSON intermediate format, no tight coupling between agents
5. Verification gates between phases: Each phase produces verifiable artifacts before the next begins
6. Graceful degradation: If a tool is unavailable, fall back to less efficient but functional alternatives
7. Large file triage: Tiered analysis depth based on file size

### 6.3 Generalization Recipe

To adapt this architecture to general code review (e.g., a Node.js/React web app):

1. Replace Agent 01 (Decompiler): With a project parser that generates a file inventory, dependency tree, and configuration summary (e.g., package.json parsing, ESLint config detection, framework identification)

2. Replace the Python scripts' rule sets: The secret_scanner.py rules are already ~80% universal (cloud keys, tokens, database URLs, JWT, private keys). Add framework-specific patterns. The endpoint_extractor.py would need to target Express routes, React Router paths, Next.js API routes, etc. instead of wx.request.

3. Keep Agents 02-07 structurally identical: Change the prompt context from WeChat Mini Program to the target framework. The analysis methodology (filter false positives, associate routes, trace data flow, assess risk) is identical.

4. Add new specialized agents: For example, a Dependency Vulnerability Agent that cross-references package.json against CVE databases (read-only, static), or a Configuration Hardening Agent for Docker/Kubernetes configs.

5. The orchestrator SKILL.md pattern is universal: Any multi-agent pipeline can use the same phase-gate-parallel-conditional structure.


---

## 7. Strengths Analysis

### 7.1 Architectural Strengths

**A. Separation of Coverage and Accuracy Concerns**
The dual-layer design is the project's most brilliant insight. It recognizes that finding everything and being right about what you find are fundamentally different problems requiring different tools. This is a reusable architectural pattern.

**B. File-Based Loose Coupling**
Agents communicate only through JSON files in a shared directory. This means:
- Agents can be developed, tested, and debugged independently
- An agent failure does not corrupt another agent's state
- Results are auditable at every intermediate step
- The pipeline is replayable from any phase

**C. Parallelism Without Complexity**
Phase 2's 4-way parallel execution is possible because the agents have zero mutual data dependencies. This is a deliberate design choice: Agents 02-05 are designed to NOT need each other's output. The cost is some duplicated work (e.g., multiple agents may read the same source files), but the benefit is a 4x wall-clock speedup with no synchronization complexity.

**D. Explicit Verification Gates**
Every phase has a concrete, machine-checkable completion criterion. This eliminates the ambiguity common in LLM pipelines (did the agent actually finish?). The gates are simple file-existence and JSON-validity checks -- cheap to verify, hard to fake.

**E. Prompt-Level Isolation**
The strict boundary between Agent 04 (universal crypto) and Agent 07 (targeted analysis) prevents the common multi-agent failure mode where agents' scopes blur and they duplicate or contradict each other's work.

**F. Graceful Degradation**
The pipeline has two explicit degradation paths: Python failure -> pure LLM fallback, and individual agent failure -> continue with reduced coverage. This is production-grade thinking for LLM systems where failures are probabilistic.

### 7.2 Engineering Strengths

**G. Python Scripts Use Only Standard Library**
No pip install required. The scripts are self-contained and portable. This is a deliberate constraint that reduces setup friction.

**H. Comprehensive Rule Coverage**
The secret_scanner.py has ~70 regex rules covering 8 categories. The endpoint_extractor.py has 28 extraction patterns. This is an unusually thorough rule set for a project of this size, reflecting real security auditing expertise.

**I. Context-Aware Regex**
The context_keywords mechanism in secret_scanner.py is a pragmatic middle ground between pure regex (too many false positives) and pure LLM (too slow/expensive). It pre-filters obvious noise before the LLM sees the data.

**J. Report Architecture**
The split between security_report.md (key findings only, human-readable) and *_full.md (complete data, machine-readable) is a well-considered UX decision. Security auditors need both: the executive summary for decision-making and the full data for verification.

---

## 8. Weaknesses and Limitations

### 8.1 Architectural Limitations

**A. No Shared Semantic Model**
Agents 02-05 may analyze the same code independently without knowledge of each other's findings during analysis. For example, Agent 02 might find a hardcoded AES key, and Agent 04 might find the same key in its crypto analysis -- but neither knows the other found it. The deduplication burden falls entirely on Agent 06 (Reporter), which can only correlate by ID references, not by semantic overlap. A shared findings registry (even a simple in-memory set of unique findings with cross-references) could reduce duplicate work and improve cross-agent insight.

**B. Phase 2 Agents Cannot Cross-Reference**
Because Agents 02-05 run in parallel with no communication, an Agent 05 (VulnAnalyzer) finding of hardcoded test account cannot be immediately cross-referenced with Agent 02's hardcoded password finding to produce a combined test account with known password critical finding. This cross-referencing only happens in Phase 3 (report), and the Reporter agent may not have the context to make these connections.

**C. No Incremental Analysis**
The pipeline always runs from scratch. For a codebase that changes incrementally (e.g., a new version of the mini-program), there is no mechanism to re-audit only the changed files. This limits utility in CI/CD scenarios.

**D. Prompt Files Contain Duplication**
The large-file handling strategy, safety boundaries, and input descriptions are copy-pasted across all 7 agent prompts. This is a maintainability concern -- changing one rule requires editing 7+ files. A template system with shared agent preamble files would reduce this.

**E. Single Platform Dependency**
The requirement for unveilr.exe (Windows only) limits the pipeline to Windows. While the analysis agents themselves are platform-agnostic, Phase 1 is Windows-locked.

### 8.2 Coverage Limitations

**F. Scripts Skip Files Larger Than 2MB**
While pragmatically necessary, this creates a coverage gap for large bundled files. A webpack bundle with secrets in it that exceeds 2MB will be silently skipped. The degradation is explicit (logged in skipped_large_files) but the gap is real.

**G. No Dynamic Analysis**
The project explicitly constrains itself to static analysis (zero network requests). This is a safety feature, but it means runtime behaviors (e.g., dynamically constructed eval strings, runtime API generation) are invisible.

**H. Regex-Defined Coverage Is Only As Good As Its Rules**
If a new type of secret (e.g., a new cloud provider's key format) is not in the regex rules, the script guarantees 100% coverage of known patterns but 0% coverage of unknown patterns. The LLM layer can partially compensate, but only for patterns it encounters during its supplemental scanning.

### 8.3 Operational Limitations

**I. No Cost Model**
There is no mechanism to estimate or cap token usage. A large codebase could consume significant API costs in Phase 2 (4 agents running in parallel, each potentially reading many files).

**J. Orchestrator Is a Single Point of Failure**
If the main Claude Code session (running SKILL.md) crashes or times out during Phase 2 (waiting for 4 background agents), the entire pipeline state is lost. There is no checkpoint/resume mechanism.

**K. Verification Gate Rigidity**
Phase 2 requires at least 3 of 4 JSON files to proceed. If exactly 2 agents succeed, the pipeline terminates even though partial results might be valuable. The all-or-mostly-nothing gating could be more nuanced.


---

## 9. Key Design Decisions Worth Emulating

1. Script+LLM pipelining -- Use deterministic tools for coverage, LLM for accuracy. This pattern applies to virtually any automated analysis task.

2. File-based agent handoff -- Loose coupling via JSON artifacts. Each agent is independently testable, debuggable, and replaceable.

3. Phase gates with explicit verification -- Never trust that an LLM agent probably finished. Always check for concrete output files.

4. Parallelism through dependency analysis -- Identify which agents have no mutual data dependencies and run them simultaneously.

5. Conditional phase triggering -- Phase 2.5 only executes if the user expressed specific requirements. This avoids unnecessary computation while still supporting deep-dive analysis.

6. Graceful degradation paths -- Always have a fallback. If a tool fails, continue with reduced capability rather than halting entirely.

7. Split reporting -- Human-readable summary for decision-makers, machine-readable complete data for verifiers. Never try to serve both audiences with one document.

8. Explicit responsibility boundaries -- Each agent's scope is strictly defined with negative constraints (what it must NOT do). This is as important as the positive constraints (what it must do).

---

## 10. Comparison to Other Multi-Agent Architectures

### 10.1 vs. CrewAI / AutoGen
Those frameworks emphasize dynamic agent-to-agent dialogue. wxmini-security-audit uses a static DAG (Directed Acyclic Graph) with file-based handoff. The static approach trades flexibility for reliability -- there is no risk of agents getting stuck in negotiation loops or hallucinating conversations.

### 10.2 vs. Single-Agent Monolith
A single all-in-one audit agent would have lower orchestration complexity but would:
- Be limited by context window (cannot fit all files + all analysis simultaneously)
- Have no parallelism (sequential analysis only)
- Risk attention dilution (trying to do everything at once reduces quality on each dimension)

### 10.3 vs. Microservice Security Scanners (e.g., Snyk, SonarQube)
Those tools use hardcoded rules with minimal AI. The wxmini pattern adds an LLM layer for semantic understanding while keeping the deterministic rule layer for coverage -- a hybrid that traditional tools lack.

---

## 11. Recommendations for Generalization

If this architecture were to be adapted into a general-purpose code review agent framework:

1. Create a project parser agent that auto-detects project type (Node.js, Python, Go, etc.) and generates appropriate file inventories, dependency lists, and framework-specific configuration summaries.

2. Make the Python script layer pluggable: Allow rule packs for different languages/frameworks. The script interface (input: directory + inventory, output: raw_*.json with by_file grouping) is clean enough to be an extension point.

3. Add a shared findings registry: A single JSON file that all Phase 2 agents can read and append to (with agent-ID tagging). This would enable cross-agent deduplication and correlation without requiring inter-agent communication.

4. Add incremental analysis support: Hash files and compare against a previous run's manifest. Only re-analyze changed files. This makes CI/CD integration feasible.

5. Implement cost estimation: Each agent prompt should include a rough token budget, and the orchestrator should estimate total cost before launching Phase 2.

6. Add checkpoint/resume: After each phase, write a pipeline_state.json that allows resuming from the last completed phase if the orchestrator crashes.

7. Template the agent prompts: Extract shared sections (safety rules, large file strategy, input parameters) into a shared preamble to reduce duplication and maintenance burden.

---

## Appendix A: File Inventory

```
wxmini-security-audit/
├── SKILL.md                              # Orchestrator (450+ lines)
├── README.md                             # Public documentation
├── .gitignore
├── agents/
│   ├── agent-01-decompiler.md            # Phase 1: Decompile + file inventory
│   ├── agent-02-secret-scanner.md        # Phase 2: Sensitive info analysis (script-informed)
│   ├── agent-03-endpoint-miner.md        # Phase 2: API endpoint analysis (script-informed)
│   ├── agent-04-crypto-analyzer.md       # Phase 2: Crypto analysis (pure LLM)
│   ├── agent-05-vuln-analyzer.md         # Phase 2: Vulnerability analysis (7 dimensions, pure LLM)
│   ├── agent-06-reporter.md              # Phase 3: Report generation
│   └── agent-07-custom-analyzer.md       # Phase 2.5: Custom deep-dive (conditional)
└── tools/
    ├── unveilr.exe                       # Third-party wxapkg decompiler (not included)
    └── scripts/
        ├── endpoint_extractor.py         # ~930 lines, 28 regex patterns
        └── secret_scanner.py             # ~930 lines, ~70 regex rules, 8 categories
```

## Appendix B: Vulnerability Analysis Dimensions (Agent 05)

The VulnAnalyzer covers 7 dimensions, each with multiple sub-checks:

| # | Dimension | Sub-Checks |
|---|-----------|-----------|
| 1 | Configuration Security | Hidden/admin pages, debug mode, domain validation off, HTTP plaintext |
| 2 | Authentication and Authorization | Login state management, frontend auth bypass, hardcoded test accounts, sensitive API over-collection |
| 3 | Data Security | Storage of sensitive data, clipboard leaks, console.log leaks, logout data cleanup |
| 4 | Business Logic | Frontend price tampering, SMS bombing, IDOR, file upload restrictions, coupon/discount frontend control |
| 5 | WebView Security | HTTP WebView src, postMessage safety, navigateToMiniProgram hijacking |
| 6 | Third-Party Components | SDK identification (~15 known SDKs), npm package vulnerabilities, mini-program plugin audit |
| 7 | Cloud Development Security | Cloud function enumeration, database collection enumeration, cloud storage operations, environment ID leaks |

## Appendix C: Endpoint Extractor Coverage (28 Pattern Categories)

The endpoint_extractor.py extracts these endpoint types:

1. Full HTTP URLs
2. WebSocket URLs
3. API path fragments (prefixed with /api/, /v1/, etc.)
4. Generic path fragments (multi-segment paths)
5. BaseURL variable definitions
6. Environment-specific URLs (dev/test/prod)
7. wx.request calls with URL extraction
8. wx.uploadFile / wx.downloadFile calls
9. wx.connectSocket calls
10. Cloud function calls (wx.cloud.callFunction)
11. Cloud database collections
12. Third-party HTTP libraries (axios, fetch, jQuery)
13. Request wrapper function definitions
14. WebView src attributes (WXML)
15. Ad unit IDs and contact-button session data (WXML)
16. Route configuration objects
17. Method-style wrapper calls (request.get('/api/...'))
18. Function-style wrapper calls (request('/api/...'))
19. Protocol-relative URLs (//api.example.com/...)
20. Path fragments without leading slash
21. Business-specific paths (/login, /order, /pay, etc.)
22. Miniprogram jump targets (navigateToMiniProgram)
23. Internal route navigations (navigateTo, redirectTo, etc.)
24. Cloud file operations (upload, download, temp URL)
25. GraphQL endpoints
26. WebSocket URL variables
27. Service market invocations
28. Plugin requirements
