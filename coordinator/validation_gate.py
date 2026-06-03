"""MACRS Validation Gate - Two-Layer Finding Verification.

Implements the AdamsReview-style two-layer validation gate:
  Phase 3 (Cheap Scoring): Sonnet batch-scores findings in chunks (<=25 each),
    applies a 45-point gate, and auto-graduates candidates with >=2 source families.
  Phase 4 (Deep Validation): Opus deep-validates high-risk candidates individually;
    Sonnet batch-validates the rest. Produces final dispositions.

Usage:
    gate = ValidationGate(cheap_threshold=45, deep_threshold=60)
    scored = gate.cheap_scoring(findings)
    graduated = gate.auto_graduate(scored)
    results = gate.deep_validation(graduated)
"""

import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHEAP_CHUNK_SIZE = 25          # Max findings per Sonnet scoring batch
AUTO_GRADUATE_MIN_FAMILIES = 2 # Minimum source families for auto-graduation
DEEP_LANE_SCORE_THRESHOLD = 75 # Score >= this goes to Deep lane (Opus)
DEEP_LANE_SEVERITY = {"P0", "P1"}  # These severities always go Deep lane
AGENT_TIMEOUT = 600            # Seconds per agent call


# ---------------------------------------------------------------------------
# Enums & Data Classes
# ---------------------------------------------------------------------------

class Disposition(Enum):
    """Final disposition of a finding after the validation gate."""
    BELOW_GATE = "below_gate"                       # Phase 3 score below threshold
    PENDING_VALIDATION = "pending_validation"        # Awaiting Phase 4
    DISPROVEN = "disproven"                          # Refuted by deep validation
    UNCERTAIN = "uncertain"                          # Cannot determine, needs human
    CONFIRMED_MECHANICAL = "confirmed_mechanical"    # Confirmed: mechanical / bug
    CONFIRMED_PARTIAL = "confirmed_partial"          # Confirmed: partial / style
    CONFIRMED_REGRESSION = "confirmed_regression"    # Confirmed: regression risk


@dataclass
class ScoredFinding:
    """A finding enriched with its Phase 3 cheap score."""
    finding: dict                  # Original finding dict
    score: int                     # 0-100 cheap score
    source_families: list[str]     # Distinct agent/source families that reported it
    disposition: Disposition       # Current disposition
    auto_graduated: bool = False   # True if auto-graduated via source family rule
    chunk_index: int = -1          # Which scoring chunk it belonged to


@dataclass
class ValidationResult:
    """Final validation result from Phase 4."""
    finding: dict                  # Original finding dict
    disposition: Disposition       # Final disposition
    confidence: int                # 0-100
    reasoning: str                 # Explanation from the validator
    lane: str = ""                 # "deep" or "light"
    adjusted_severity: Optional[str] = None  # If severity was changed


# ---------------------------------------------------------------------------
# Prompt Templates
# ---------------------------------------------------------------------------

CHEAP_SCORING_PROMPT = """You are a code review triage specialist. Score each finding from 0-100 based on:
- Severity weight (P0=40, P1=30, P2=20, P3=10 base)
- Evidence strength (specific code cited = +20, vague = +5)
- Actionability (clear fix suggested = +10, no fix = +0)
- Cross-reference (multiple agents agree = +15, single source = +0)

Cap the total at 100.

## Findings to score:

{findings_text}

## Output format
**Output ONLY valid JSON, no other text.**

```json
{{
  "scores": [
    {{
      "finding_id": "M-001",
      "score": 75,
      "rationale": "Brief scoring explanation"
    }}
  ]
}}
```"""


DEEP_VALIDATION_PROMPT = """You are a senior code reviewer performing deep validation.
For each candidate, examine the actual source code context and determine if the finding is:
- CONFIRMED_MECHANICAL: Real bug, will cause failures
- CONFIRMED_PARTIAL: Real issue but lower severity than reported
- CONFIRMED_REGRESSION: Valid regression risk
- DISPROVEN: False positive - provide refutation evidence
- UNCERTAIN: Cannot determine from available context

## Candidates to validate:

{candidates_text}

## Source code context:

{source_context}

## Output format
**Output ONLY valid JSON, no other text.**

```json
{{
  "validations": [
    {{
      "finding_id": "M-001",
      "disposition": "CONFIRMED_MECHANICAL | CONFIRMED_PARTIAL | CONFIRMED_REGRESSION | DISPROVEN | UNCERTAIN",
      "confidence": 85,
      "reasoning": "Detailed explanation",
      "adjusted_severity": null
    }}
  ]
}}
```"""


LIGHT_VALIDATION_PROMPT = """You are a code review validator performing batch verification.
For each finding, quickly assess if it's plausible based on the description and severity.
Mark as:
- CONFIRMED_MECHANICAL: Clearly valid
- CONFIRMED_PARTIAL: Probably valid but less severe
- DISPROVEN: Clearly a false positive
- UNCERTAIN: Need more context

## Findings to validate:

{findings_text}

## Output format
**Output ONLY valid JSON, no other text.**

```json
{{
  "validations": [
    {{
      "finding_id": "M-001",
      "disposition": "CONFIRMED_MECHANICAL | CONFIRMED_PARTIAL | DISPROVEN | UNCERTAIN",
      "confidence": 70,
      "reasoning": "Brief explanation"
    }}
  ]
}}
```"""


# ---------------------------------------------------------------------------
# Utility Functions
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> Optional[dict]:
    """Extract a JSON object from potentially noisy text output."""
    if not text or len(text.strip()) < 10:
        return None

    # Strategy 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: fenced code block
    blocks = re.findall(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    for block in blocks:
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            continue

    # Strategy 3: first balanced { ... } block
    brace_depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if brace_depth == 0:
                start = i
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth == 0 and start >= 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = -1
    return None


def _call_llm(prompt: str, model: str = "sonnet", timeout: int = AGENT_TIMEOUT) -> Optional[dict]:
    """Call claude CLI with a prompt and return parsed JSON response."""
    import os
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["LANG"] = "en_US.UTF-8"

    # Write prompt to temp file to avoid shell escaping issues
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False,
                                      encoding="utf-8") as f:
        f.write(prompt)
        prompt_file = f.name

    try:
        cmd = f'cat "{prompt_file}" | claude -p --model {model} --output-format text'
        start = time.time()
        result = subprocess.run(
            cmd, capture_output=True, timeout=timeout, shell=True, env=env,
        )
        elapsed = time.time() - start
        logger.info("LLM call completed in %.1fs (model=%s)", elapsed, model)

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
            logger.error("LLM call failed (rc=%d): %s", result.returncode, stderr[:500])
            return None

        stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
        return _extract_json(stdout)

    except subprocess.TimeoutExpired:
        logger.error("LLM call timed out after %ds", timeout)
        return None
    except FileNotFoundError:
        logger.error("claude CLI not found. Install: npm install -g @anthropic-ai/claude-code")
        return None
    finally:
        Path(prompt_file).unlink(missing_ok=True)


def _chunk_list(items: list, chunk_size: int) -> list[list]:
    """Split a list into chunks of at most chunk_size items."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def _extract_source_families(finding: dict) -> list[str]:
    """Extract distinct source agent families from a finding.

    Returns a deduplicated list of agent identifiers (e.g., ["A", "B"]).
    A finding with >=2 families suggests cross-validated evidence.
    """
    families = set()

    # From "sources" array (Phase 2 merged format)
    for src in finding.get("sources", []):
        agent = src.get("agent") or src.get("agent_id") or src.get("source", "")
        if agent:
            families.add(str(agent))

    # From "agent_id" field (single-agent format)
    if finding.get("agent_id"):
        families.add(str(finding["agent_id"]))

    # From "reported_by" field
    for reporter in finding.get("reported_by", []):
        families.add(str(reporter))

    return sorted(families)


def _extract_severity(finding: dict) -> str:
    """Extract severity string from a finding dict."""
    return finding.get("canonical_severity") or finding.get("severity", "P3 LOW")


# ---------------------------------------------------------------------------
# ValidationGate
# ---------------------------------------------------------------------------

class ValidationGate:
    """Two-layer validation gate for code review findings.

    Layer 1 (Cheap Scoring): Fast, batch scoring with Sonnet to filter noise.
    Layer 2 (Deep Validation): Thorough validation with Opus (deep) or Sonnet (light).
    """

    def __init__(
        self,
        cheap_threshold: int = 45,
        deep_threshold: int = 60,
        chunk_size: int = CHEAP_CHUNK_SIZE,
        source_dir: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        self.cheap_threshold = cheap_threshold
        self.deep_threshold = deep_threshold
        self.chunk_size = chunk_size
        self.source_dir = source_dir
        self.output_dir = output_dir

    # ── Phase 3: Cheap Scoring ──────────────────────────────────────────

    def cheap_scoring(self, findings: list[dict]) -> list[ScoredFinding]:
        """Phase 3: Sonnet batch-scores findings in chunks.

        Each chunk contains at most self.chunk_size findings.
        Returns ScoredFinding objects with raw scores (gate not yet applied).
        """
        if not findings:
            return []

        chunks = _chunk_list(findings, self.chunk_size)
        logger.info("Cheap scoring: %d findings in %d chunks (size=%d)",
                     len(findings), len(chunks), self.chunk_size)

        all_scored: list[ScoredFinding] = []

        for chunk_idx, chunk in enumerate(chunks):
            scored_chunk = self._score_chunk(chunk, chunk_idx)
            all_scored.extend(scored_chunk)
            logger.info("Chunk %d/%d scored: %d findings",
                        chunk_idx + 1, len(chunks), len(scored_chunk))

        return all_scored

    def _score_chunk(self, findings: list[dict], chunk_index: int) -> list[ScoredFinding]:
        """Score a single chunk of findings via Sonnet."""
        # Build prompt
        findings_text = self._format_findings_for_prompt(findings)
        prompt = CHEAP_SCORING_PROMPT.format(findings_text=findings_text)

        # Call Sonnet
        response = _call_llm(prompt, model="sonnet")
        if response is None:
            logger.warning("Cheap scoring failed for chunk %d, assigning default score=0", chunk_index)
            return [
                ScoredFinding(
                    finding=f,
                    score=0,
                    source_families=_extract_source_families(f),
                    disposition=Disposition.BELOW_GATE,
                    chunk_index=chunk_index,
                )
                for f in findings
            ]

        # Parse scores
        score_map = {}
        for entry in response.get("scores", []):
            fid = entry.get("finding_id", "")
            score_map[fid] = {
                "score": min(100, max(0, int(entry.get("score", 0)))),
                "rationale": entry.get("rationale", ""),
            }

        # Build ScoredFinding objects
        scored = []
        for f in findings:
            fid = f.get("merged_id") or f.get("id", "unknown")
            info = score_map.get(fid, {"score": 0, "rationale": "Not scored"})
            families = _extract_source_families(f)
            disp = self._apply_gate(info["score"], families)

            scored.append(ScoredFinding(
                finding=f,
                score=info["score"],
                source_families=families,
                disposition=disp,
                chunk_index=chunk_index,
            ))

        return scored

    def _apply_gate(self, score: int, source_families: list[str]) -> Disposition:
        """Apply the cheap gate threshold to a score.

        Note: Auto-graduation is handled separately in auto_graduate().
        """
        if score >= self.cheap_threshold:
            return Disposition.PENDING_VALIDATION
        return Disposition.BELOW_GATE

    # ── Auto-Graduation ─────────────────────────────────────────────────

    def auto_graduate(self, scored: list[ScoredFinding]) -> list[ScoredFinding]:
        """Auto-graduate findings with >=2 source families.

        Even if a finding scored below the cheap threshold, if it was
        independently reported by >= AUTO_GRADUATE_MIN_FAMILIES distinct
        agents, it automatically advances to Phase 4 deep validation.
        This prevents high-signal but unusual findings from being filtered.
        """
        graduated_count = 0
        for sf in scored:
            if (sf.disposition == Disposition.BELOW_GATE
                    and len(sf.source_families) >= AUTO_GRADUATE_MIN_FAMILIES):
                sf.disposition = Disposition.PENDING_VALIDATION
                sf.auto_graduated = True
                graduated_count += 1
                logger.info("Auto-graduated %s (score=%d, families=%s)",
                            sf.finding.get("merged_id", "?"),
                            sf.score, sf.source_families)

        logger.info("Auto-graduation: %d/%d findings promoted", graduated_count, len(scored))
        return scored

    # ── Phase 4: Deep Validation ────────────────────────────────────────

    def deep_validation(self, candidates: list[ScoredFinding]) -> list[ValidationResult]:
        """Phase 4: Validate candidates that passed the cheap gate.

        Candidates are split into two lanes:
          - Deep lane (Opus): High-score or P0/P1 findings, validated individually.
          - Light lane (Sonnet): Lower-risk findings, batch-validated in chunks.

        Returns final ValidationResult objects with definitive dispositions.
        """
        pending = [sf for sf in candidates if sf.disposition == Disposition.PENDING_VALIDATION]
        if not pending:
            logger.info("Deep validation: no candidates to validate")
            return []

        deep_lane, light_lane = self._split_lanes(pending)
        logger.info("Deep validation: %d deep, %d light (total=%d)",
                     len(deep_lane), len(light_lane), len(pending))

        results: list[ValidationResult] = []

        # Deep lane: Opus individual validation
        if deep_lane:
            deep_results = self._validate_deep_lane(deep_lane)
            results.extend(deep_results)

        # Light lane: Sonnet batch validation
        if light_lane:
            light_results = self._validate_light_lane(light_lane)
            results.extend(light_results)

        return results

    def classify_lane(self, finding: ScoredFinding) -> str:
        """Classify a finding into Deep lane or Light lane.

        Deep lane criteria (any match):
          - Score >= DEEP_LANE_SCORE_THRESHOLD
          - Severity is P0 or P1
          - Auto-graduated (cross-validated by multiple agents)

        Everything else goes to Light lane.
        """
        if finding.score >= DEEP_LANE_SCORE_THRESHOLD:
            return "deep"
        if finding.auto_graduated:
            return "deep"
        sev = _extract_severity(finding.finding)
        sev_prefix = sev.split()[0] if sev else "P3"
        if sev_prefix in DEEP_LANE_SEVERITY:
            return "deep"
        return "light"

    def _split_lanes(
        self, candidates: list[ScoredFinding]
    ) -> tuple[list[ScoredFinding], list[ScoredFinding]]:
        """Split candidates into deep and light lane lists."""
        deep = []
        light = []
        for sf in candidates:
            if self.classify_lane(sf) == "deep":
                deep.append(sf)
            else:
                light.append(sf)
        return deep, light

    # ── Deep Lane (Opus) ────────────────────────────────────────────────

    def _validate_deep_lane(
        self, candidates: list[ScoredFinding]
    ) -> list[ValidationResult]:
        """Validate each candidate individually with Opus.

        High-cost but high-accuracy: each finding gets its own validation
        call with full source code context.
        """
        results: list[ValidationResult] = []

        for sf in candidates:
            fid = sf.finding.get("merged_id") or sf.finding.get("id", "?")
            logger.info("Deep validation: %s (score=%d)", fid, sf.score)

            # Load source context if available
            source_context = self._load_source_context(sf.finding)

            # Build prompt for single finding
            finding_text = self._format_single_finding(sf.finding)
            prompt = DEEP_VALIDATION_PROMPT.format(
                candidates_text=finding_text,
                source_context=source_context or "(source code not available)",
            )

            response = _call_llm(prompt, model="opus")
            vr = self._parse_deep_result(response, sf)
            results.append(vr)

            logger.info("  -> %s (confidence=%d)", vr.disposition.value, vr.confidence)

        return results

    def _parse_deep_result(self, response: Optional[dict], sf: ScoredFinding) -> ValidationResult:
        """Parse a deep validation response into a ValidationResult."""
        fid = sf.finding.get("merged_id") or sf.finding.get("id", "?")

        if response is None:
            return ValidationResult(
                finding=sf.finding,
                disposition=Disposition.UNCERTAIN,
                confidence=0,
                reasoning="Deep validation agent failed to respond",
                lane="deep",
            )

        validations = response.get("validations", [])
        if not validations:
            return ValidationResult(
                finding=sf.finding,
                disposition=Disposition.UNCERTAIN,
                confidence=0,
                reasoning="No validation entries in response",
                lane="deep",
            )

        # Find matching validation entry
        entry = None
        for v in validations:
            if v.get("finding_id") == fid:
                entry = v
                break
        if entry is None:
            entry = validations[0]  # Fallback to first entry

        # Map disposition string to enum
        disp_str = entry.get("disposition", "UNCERTAIN")
        disposition = self._parse_disposition(disp_str)

        return ValidationResult(
            finding=sf.finding,
            disposition=disposition,
            confidence=min(100, max(0, int(entry.get("confidence", 50)))),
            reasoning=entry.get("reasoning", ""),
            lane="deep",
            adjusted_severity=entry.get("adjusted_severity"),
        )

    # ── Light Lane (Sonnet Batch) ───────────────────────────────────────

    def _validate_light_lane(
        self, candidates: list[ScoredFinding]
    ) -> list[ValidationResult]:
        """Batch-validate candidates with Sonnet in chunks.

        Lower cost but less thorough: findings are validated in groups
        without individual source code context.
        """
        chunks = _chunk_list(candidates, self.chunk_size)
        logger.info("Light validation: %d candidates in %d chunks",
                     len(candidates), len(chunks))

        results: list[ValidationResult] = []

        for chunk_idx, chunk in enumerate(chunks):
            chunk_results = self._validate_light_chunk(chunk, chunk_idx)
            results.extend(chunk_results)
            logger.info("Light chunk %d/%d: %d results",
                        chunk_idx + 1, len(chunks), len(chunk_results))

        return results

    def _validate_light_chunk(
        self, candidates: list[ScoredFinding], chunk_index: int
    ) -> list[ValidationResult]:
        """Validate a single chunk of findings via Sonnet (light lane)."""
        findings_text = self._format_findings_for_prompt(
            [sf.finding for sf in candidates]
        )
        prompt = LIGHT_VALIDATION_PROMPT.format(findings_text=findings_text)

        response = _call_llm(prompt, model="sonnet")
        if response is None:
            logger.warning("Light validation failed for chunk %d", chunk_index)
            return [
                ValidationResult(
                    finding=sf.finding,
                    disposition=Disposition.UNCERTAIN,
                    confidence=0,
                    reasoning="Light validation agent failed",
                    lane="light",
                )
                for sf in candidates
            ]

        # Parse results
        validation_map = {}
        for entry in response.get("validations", []):
            fid = entry.get("finding_id", "")
            validation_map[fid] = entry

        results = []
        for sf in candidates:
            fid = sf.finding.get("merged_id") or sf.finding.get("id", "?")
            entry = validation_map.get(fid)

            if entry is None:
                results.append(ValidationResult(
                    finding=sf.finding,
                    disposition=Disposition.UNCERTAIN,
                    confidence=0,
                    reasoning="Not found in validation response",
                    lane="light",
                ))
                continue

            disp_str = entry.get("disposition", "UNCERTAIN")
            disposition = self._parse_disposition(disp_str)

            results.append(ValidationResult(
                finding=sf.finding,
                disposition=disposition,
                confidence=min(100, max(0, int(entry.get("confidence", 50)))),
                reasoning=entry.get("reasoning", ""),
                lane="light",
            ))

        return results

    # ── Formatting Helpers ──────────────────────────────────────────────

    def _format_findings_for_prompt(self, findings: list[dict]) -> str:
        """Format a list of findings into text for an LLM prompt."""
        parts = []
        for f in findings:
            fid = f.get("merged_id") or f.get("id", "N/A")
            title = f.get("canonical_title") or f.get("title", "Untitled")
            sev = _extract_severity(f)
            desc = (f.get("canonical_description") or f.get("description", ""))[:500]
            suggestion = (f.get("suggestion", ""))[:300]
            file_path = f.get("file", "unknown")
            line_range = f.get("line_range", [0, 0])
            code_bad = f.get("code_snippet_bad", "")[:300]

            parts.append(f"""### {fid} - {title}
- Severity: {sev}
- File: {file_path} lines {line_range}
- Description: {desc}
- Suggestion: {suggestion}
{f"- Problematic code:\n```\n{code_bad}\n```" if code_bad else ""}
""")
        return "\n".join(parts)

    def _format_single_finding(self, finding: dict) -> str:
        """Format a single finding for deep validation prompt."""
        return self._format_findings_for_prompt([finding])

    def _load_source_context(self, finding: dict) -> Optional[str]:
        """Load source code context for a finding if source_dir is set."""
        if self.source_dir is None:
            return None

        file_path = finding.get("file", "")
        if not file_path:
            return None

        full_path = self.source_dir / file_path
        if not full_path.exists():
            return None

        try:
            # Read with line range context (+/- 20 lines)
            content = full_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()

            line_range = finding.get("line_range", [0, 0])
            start = max(0, (line_range[0] if isinstance(line_range, list) else 0) - 20)
            end = min(len(lines), (line_range[1] if isinstance(line_range, list) else len(lines)) + 20)

            context_lines = lines[start:end]
            numbered = [f"{i + start + 1:4d} | {line}" for i, line in enumerate(context_lines)]
            return f"File: {file_path} (lines {start+1}-{end})\n```\n" + "\n".join(numbered) + "\n```"
        except Exception as e:
            logger.warning("Failed to read source %s: %s", file_path, e)
            return None

    # ── Disposition Parsing ─────────────────────────────────────────────

    @staticmethod
    def _parse_disposition(raw: str) -> Disposition:
        """Map a disposition string to the Disposition enum."""
        mapping = {
            "BELOW_GATE": Disposition.BELOW_GATE,
            "PENDING_VALIDATION": Disposition.PENDING_VALIDATION,
            "DISPROVEN": Disposition.DISPROVEN,
            "UNCERTAIN": Disposition.UNCERTAIN,
            "CONFIRMED_MECHANICAL": Disposition.CONFIRMED_MECHANICAL,
            "CONFIRMED_PARTIAL": Disposition.CONFIRMED_PARTIAL,
            "CONFIRMED_REGRESSION": Disposition.CONFIRMED_REGRESSION,
            # Legacy mappings from existing Phase 3 skeptic
            "CONFIRM": Disposition.CONFIRMED_MECHANICAL,
            "REFUTE": Disposition.DISPROVEN,
            "DOWNGRADE": Disposition.CONFIRMED_PARTIAL,
            "NEEDS_HUMAN": Disposition.UNCERTAIN,
        }
        return mapping.get(raw.upper().strip(), Disposition.UNCERTAIN)

    # ── Full Pipeline ───────────────────────────────────────────────────

    def run_pipeline(self, findings: list[dict]) -> dict:
        """Execute the full two-layer validation pipeline.

        Returns a summary dict with all scored findings, validation results,
        and statistics.
        """
        logger.info("=== Validation Gate Pipeline ===")
        logger.info("Input: %d findings", len(findings))

        # Phase 3: Cheap Scoring
        logger.info("--- Phase 3: Cheap Scoring ---")
        scored = self.cheap_scoring(findings)

        # Auto-Graduation
        logger.info("--- Auto-Graduation ---")
        scored = self.auto_graduate(scored)

        # Phase 4: Deep Validation
        logger.info("--- Phase 4: Deep Validation ---")
        validation_results = self.deep_validation(scored)

        # Build validation result lookup
        vr_map = {}
        for vr in validation_results:
            fid = vr.finding.get("merged_id") or vr.finding.get("id", "?")
            vr_map[fid] = vr

        # Merge validation results back into scored findings
        final_results = []
        for sf in scored:
            fid = sf.finding.get("merged_id") or sf.finding.get("id", "?")
            if fid in vr_map:
                vr = vr_map[fid]
                final_results.append(vr)
            elif sf.disposition == Disposition.BELOW_GATE:
                # Below gate and not auto-graduated: keep as-is
                final_results.append(ValidationResult(
                    finding=sf.finding,
                    disposition=Disposition.BELOW_GATE,
                    confidence=sf.score,
                    reasoning=f"Below cheap gate threshold (score={sf.score} < {self.cheap_threshold})",
                    lane="none",
                ))
            else:
                # Should not happen, but handle gracefully
                final_results.append(ValidationResult(
                    finding=sf.finding,
                    disposition=Disposition.UNCERTAIN,
                    confidence=0,
                    reasoning="No validation result produced",
                    lane="none",
                ))

        # Statistics
        stats = self._compute_stats(scored, final_results)

        # Save to disk if output_dir is set
        if self.output_dir:
            self._save_results(scored, final_results, stats)

        return {
            "scored_findings": scored,
            "validation_results": final_results,
            "stats": stats,
        }

    def _compute_stats(
        self, scored: list[ScoredFinding], results: list[ValidationResult]
    ) -> dict:
        """Compute pipeline statistics."""
        disp_counts = {}
        for vr in results:
            key = vr.disposition.value
            disp_counts[key] = disp_counts.get(key, 0) + 1

        below_gate = sum(1 for sf in scored if sf.disposition == Disposition.BELOW_GATE)
        auto_grad = sum(1 for sf in scored if sf.auto_graduated)
        deep_count = sum(1 for vr in results if vr.lane == "deep")
        light_count = sum(1 for vr in results if vr.lane == "light")

        confirmed = sum(
            disp_counts.get(d, 0)
            for d in ["confirmed_mechanical", "confirmed_partial", "confirmed_regression"]
        )

        return {
            "total_input": len(scored),
            "below_gate": below_gate,
            "auto_graduated": auto_grad,
            "deep_lane": deep_count,
            "light_lane": light_count,
            "confirmed": confirmed,
            "disproven": disp_counts.get("disproven", 0),
            "uncertain": disp_counts.get("uncertain", 0),
            "disposition_counts": disp_counts,
            "cheap_threshold": self.cheap_threshold,
            "deep_threshold": self.deep_threshold,
        }

    def _save_results(
        self,
        scored: list[ScoredFinding],
        results: list[ValidationResult],
        stats: dict,
    ) -> None:
        """Save pipeline results to disk."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Save scored findings
        scored_data = []
        for sf in scored:
            scored_data.append({
                "finding_id": sf.finding.get("merged_id") or sf.finding.get("id", "?"),
                "score": sf.score,
                "source_families": sf.source_families,
                "disposition": sf.disposition.value,
                "auto_graduated": sf.auto_graduated,
                "chunk_index": sf.chunk_index,
            })
        (self.output_dir / "scored-findings.json").write_text(
            json.dumps(scored_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Save validation results
        results_data = []
        for vr in results:
            results_data.append({
                "finding_id": vr.finding.get("merged_id") or vr.finding.get("id", "?"),
                "disposition": vr.disposition.value,
                "confidence": vr.confidence,
                "reasoning": vr.reasoning,
                "lane": vr.lane,
                "adjusted_severity": vr.adjusted_severity,
            })
        (self.output_dir / "validation-results.json").write_text(
            json.dumps(results_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Save stats
        (self.output_dir / "validation-gate-stats.json").write_text(
            json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        logger.info("Results saved to %s", self.output_dir)
