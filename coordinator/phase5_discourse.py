"""MACRS Phase 3 - Discourse Mechanism.

After individual reviewers produce findings, the Discourse phase lets each
reviewer react to the others' work.  Four response types are supported:

  AGREE   - Confirm another reviewer's finding  (confidence +1)
  CHALLENGE - Dispute a finding; author may defend (defend: +1, lose: -1)
  CONNECT - Link one of your findings to another reviewer's finding (confidence +1)
  SURFACE - Raise a new issue inspired by reading others' findings

Confidence is tracked on a -3..+3 integer scale (0 = neutral default).
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from json_utils import extract_json
from llm_client import call_claude


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class ResponseType(Enum):
    AGREE = "AGREE"
    CHALLENGE = "CHALLENGE"
    CONNECT = "CONNECT"
    SURFACE = "SURFACE"


@dataclass
class DiscourseResponse:
    """A single parsed discourse response line."""
    response_type: ResponseType
    reviewer: str
    finding_id: str
    target_reviewer: Optional[str] = None
    target_finding_id: Optional[str] = None
    reasoning: str = ""
    defended: Optional[bool] = None  # only meaningful for CHALLENGE


@dataclass
class DiscourseResult:
    """Aggregated result of the entire discourse phase."""
    responses: list[DiscourseResponse] = field(default_factory=list)
    confidence_adjustments: dict[str, int] = field(default_factory=dict)
    new_findings: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

DISCOURSE_PROMPT = """\
你之前以 **{reviewer_name}** 的身份审查了这段代码。
现在请你审视其他 reviewer 的发现，并做出建设性回应。

## 你的原始发现
{your_findings}

## 其他 reviewer 的发现
{other_findings}

## 你的任务
针对每一条"其他发现"，用以下格式**各写一行**回应（可多行）：

- **AGREE [reviewer] [finding_id]**: 你认同这条发现，附带简短理由。
- **CHALLENGE [reviewer] [finding_id]**: 你质疑这条发现，必须给出具体推理（不能空洞否定）。
- **CONNECT [your_finding_id] -> [reviewer:finding_id]**: 你发现你的某条发现与对方的发现相关联。
- **SURFACE [proposed_title]**: 阅读他人工作后，你发现了一个全新的、之前未被任何人提及的问题。

## 输出要求
1. 每条回应独占一行。
2. 先写回应行，之后空一行，再写 JSON 摘要。
3. JSON 摘要格式：

```json
{{
  "responses": [
    {{
      "type": "AGREE | CHALLENGE | CONNECT | SURFACE",
      "reviewer": "你的 reviewer id",
      "finding_id": "相关 finding id",
      "target_reviewer": "对方 reviewer id (AGREE/CHALLENGE/SURFACE 填 null)",
      "target_finding_id": "对方 finding id (SURFACE 填 null)",
      "reasoning": "你的理由",
      "new_finding": null
    }}
  ]
}}
```

SURFACE 类型如果提出了新发现，在 `new_finding` 中填入：
```json
{{
  "title": "...",
  "file": "...",
  "line": 0,
  "severity": "P2 | P3",
  "description": "...",
  "suggestion": "..."
}}
```

保持建设性。用推理质疑，而非否定。"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _finding_to_text(finding: dict) -> str:
    """Render a single finding dict to a compact text block."""
    fid = finding.get("id") or finding.get("merged_id", "N/A")
    title = finding.get("title") or finding.get("canonical_title", "N/A")
    severity = finding.get("severity") or finding.get("canonical_severity", "N/A")
    file_ = finding.get("file", "N/A")
    line = finding.get("line") or finding.get("line_range", "N/A")
    desc = (finding.get("description", "") or "")[:400]
    return (
        f"### {fid} - {title}\n"
        f"- severity: {severity}\n"
        f"- file: {file_} line {line}\n"
        f"- description: {desc}\n"
    )


def _group_by_reviewer(findings: list[dict]) -> dict[str, list[dict]]:
    """Group findings by their originating agent / reviewer id."""
    groups: dict[str, list[dict]] = {}
    for f in findings:
        reviewer = f.get("agent_id") or f.get("reviewer", "unknown")
        groups.setdefault(reviewer, []).append(f)
    return groups


# ---------------------------------------------------------------------------
# Response parser (line-level regex + JSON fallback)
# ---------------------------------------------------------------------------

_AGREE_RE = re.compile(
    r"AGREE\s+\[?(\w+)\]?\s+\[?([\w\-]+)\]?", re.IGNORECASE
)
_CHALLENGE_RE = re.compile(
    r"CHALLENGE\s+\[?(\w+)\]?\s+\[?([\w\-]+)\]?", re.IGNORECASE
)
_CONNECT_RE = re.compile(
    r"CONNECT\s+\[?([\w\-]+)\]?\s*->\s*\[?(\w+):([\w\-]+)\]?", re.IGNORECASE
)
_SURFACE_RE = re.compile(
    r"SURFACE\s+\[?(.+?)\]?\s*$", re.IGNORECASE
)


def parse_responses(raw_lines: list[str], reviewer: str) -> list[DiscourseResponse]:
    """Parse discourse response lines into structured objects.

    Tries line-level regex first; falls back to JSON block if present.
    """
    responses: list[DiscourseResponse] = []

    for line in raw_lines:
        line = line.strip()
        if not line:
            continue

        # AGREE
        m = _AGREE_RE.search(line)
        if m:
            responses.append(
                DiscourseResponse(
                    response_type=ResponseType.AGREE,
                    reviewer=reviewer,
                    finding_id=m.group(2),
                    target_reviewer=m.group(1),
                    reasoning=line[m.end() :].strip(" -:"),
                )
            )
            continue

        # CHALLENGE
        m = _CHALLENGE_RE.search(line)
        if m:
            responses.append(
                DiscourseResponse(
                    response_type=ResponseType.CHALLENGE,
                    reviewer=reviewer,
                    finding_id=m.group(2),
                    target_reviewer=m.group(1),
                    reasoning=line[m.end() :].strip(" -:"),
                )
            )
            continue

        # CONNECT
        m = _CONNECT_RE.search(line)
        if m:
            responses.append(
                DiscourseResponse(
                    response_type=ResponseType.CONNECT,
                    reviewer=reviewer,
                    finding_id=m.group(1),
                    target_reviewer=m.group(2),
                    target_finding_id=m.group(3),
                )
            )
            continue

        # SURFACE
        m = _SURFACE_RE.search(line)
        if m:
            responses.append(
                DiscourseResponse(
                    response_type=ResponseType.SURFACE,
                    reviewer=reviewer,
                    finding_id=f"SURFACE-{len(responses)+1}",
                    reasoning=m.group(1).strip(),
                )
            )
            continue

    return responses


def parse_json_responses(json_block: dict, reviewer: str) -> list[DiscourseResponse]:
    """Parse the JSON summary section that the LLM is asked to produce."""
    responses: list[DiscourseResponse] = []
    for entry in json_block.get("responses", []):
        rtype_str = entry.get("type", "").upper()
        try:
            rtype = ResponseType(rtype_str)
        except ValueError:
            continue

        resp = DiscourseResponse(
            response_type=rtype,
            reviewer=reviewer,
            finding_id=entry.get("finding_id", ""),
            target_reviewer=entry.get("target_reviewer"),
            target_finding_id=entry.get("target_finding_id"),
            reasoning=entry.get("reasoning", ""),
        )
        responses.append(resp)

        # If SURFACE includes a new_finding, record it
        new_f = entry.get("new_finding")
        if new_f and isinstance(new_f, dict):
            new_f["_source_reviewer"] = reviewer
            new_f["_discourse_type"] = "SURFACE"
            # will be collected later

    return responses


# ---------------------------------------------------------------------------
# Confidence adjustment
# ---------------------------------------------------------------------------

def adjust_confidence(
    findings: list[dict],
    responses: list[DiscourseResponse],
) -> dict[str, int]:
    """Compute net confidence adjustment for each finding.

    Rules:
      AGREE                    -> target finding +1
      CHALLENGE defended=True  -> challenged finding unchanged, challenger +1
      CHALLENGE defended=False -> challenged finding -1
      CONNECT                  -> both connected findings +1
      SURFACE                  -> no direct adjustment (generates new findings)

    Returns {finding_id: delta}.
    """
    adjustments: dict[str, int] = {}

    for resp in responses:
        if resp.response_type == ResponseType.AGREE:
            fid = resp.finding_id
            adjustments[fid] = adjustments.get(fid, 0) + 1

        elif resp.response_type == ResponseType.CHALLENGE:
            fid = resp.finding_id
            if resp.defended is True:
                # Defender keeps score; challenger earns +1 on their own finding
                pass  # no change to challenged finding
            elif resp.defended is False:
                adjustments[fid] = adjustments.get(fid, 0) - 1
            else:
                # Not yet adjudicated -- treat as pending (no change)
                pass

        elif resp.response_type == ResponseType.CONNECT:
            fid = resp.finding_id
            adjustments[fid] = adjustments.get(fid, 0) + 1
            if resp.target_finding_id:
                tfid = resp.target_finding_id
                adjustments[tfid] = adjustments.get(tfid, 0) + 1

        # SURFACE: no adjustment, may produce new findings

    return adjustments


# ---------------------------------------------------------------------------
# Discourse execution
# ---------------------------------------------------------------------------

class DiscoursePhase:
    """Orchestrates the discourse round across all reviewers."""

    DISCOURSE_PROMPT = DISCOURSE_PROMPT  # re-export for external use

    def __init__(self, agent_runner_fn=None, timeout: int = 600):
        """
        Parameters
        ----------
        agent_runner_fn : callable(prompt: str) -> str | None
            Function that sends a prompt to an LLM agent and returns raw text.
            If None, uses the default ``_default_agent_runner`` (claude CLI).
        timeout : int
            Per-agent timeout in seconds.
        """
        self.agent_runner_fn = agent_runner_fn or self._default_agent_runner
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, findings: list[dict]) -> DiscourseResult:
        """Execute the full discourse phase.

        Parameters
        ----------
        findings : list[dict]
            All findings from Phase 1/2, each must contain ``agent_id`` or
            ``reviewer`` to identify the originating reviewer.

        Returns
        -------
        DiscourseResult
        """
        grouped = _group_by_reviewer(findings)
        reviewer_ids = list(grouped.keys())

        if len(reviewer_ids) < 2:
            # Need at least 2 reviewers for discourse to make sense
            return DiscourseResult()

        # 1. Build tasks
        tasks: dict[str, str] = {}
        for reviewer in reviewer_ids:
            your = grouped[reviewer]
            others = [
                f
                for rid, fs in grouped.items()
                if rid != reviewer
                for f in fs
            ]
            tasks[reviewer] = self.create_discourse_task(
                reviewer, your, others
            )

        # 2. Run in parallel
        raw_outputs = self._run_parallel(tasks)

        # 3. Parse all responses
        all_responses: list[DiscourseResponse] = []
        new_findings: list[dict] = []

        for reviewer, raw in raw_outputs.items():
            if raw is None:
                continue
            responses, surf_findings = self._parse_single_output(raw, reviewer)
            all_responses.extend(responses)
            new_findings.extend(surf_findings)

        # 4. Adjust confidence
        adjustments = adjust_confidence(findings, all_responses)

        return DiscourseResult(
            responses=all_responses,
            confidence_adjustments=adjustments,
            new_findings=new_findings,
        )

    def create_discourse_task(
        self,
        reviewer: str,
        your_findings: list[dict],
        other_findings: list[dict],
    ) -> str:
        """Generate the discourse prompt for a single reviewer."""
        your_text = "\n".join(_finding_to_text(f) for f in your_findings)
        other_text = "\n".join(_finding_to_text(f) for f in other_findings)
        return self.DISCOURSE_PROMPT.format(
            reviewer_name=reviewer,
            your_findings=your_text or "(无)",
            other_findings=other_text or "(无)",
        )

    def parse_responses(
        self, raw_responses: list[str], reviewer: str
    ) -> list[DiscourseResponse]:
        """Parse raw response lines into DiscourseResponse objects.

        Delegates to line-level regex then JSON fallback.
        """
        line_parsed = parse_responses(raw_responses, reviewer)
        if line_parsed:
            return line_parsed

        # Try JSON block from the entire text
        joined = "\n".join(raw_responses)
        parsed_json = extract_json(joined)
        if parsed_json and "responses" in parsed_json:
            return parse_json_responses(parsed_json, reviewer)

        return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_parallel(self, tasks: dict[str, str]) -> dict[str, str | None]:
        """Run discourse tasks for all reviewers in parallel."""
        results: dict[str, str | None] = {}

        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            futures = {
                executor.submit(self.agent_runner_fn, prompt): reviewer
                for reviewer, prompt in tasks.items()
            }
            for future in as_completed(futures):
                reviewer = futures[future]
                try:
                    results[reviewer] = future.result()
                except Exception as exc:
                    print(f"[Discourse] {reviewer} failed: {exc}")
                    results[reviewer] = None

        return results

    def _parse_single_output(
        self, raw: str, reviewer: str
    ) -> tuple[list[DiscourseResponse], list[dict]]:
        """Parse one agent's output into responses + any SURFACE findings."""
        lines = raw.strip().splitlines()
        responses = self.parse_responses(lines, reviewer)

        # Extract new findings from SURFACE responses that carry new_finding
        new_findings: list[dict] = []
        parsed_json = extract_json(raw)
        if parsed_json:
            for entry in parsed_json.get("responses", []):
                nf = entry.get("new_finding")
                if nf and isinstance(nf, dict):
                    nf["_source_reviewer"] = reviewer
                    new_findings.append(nf)

        return responses, new_findings

    @staticmethod
    def _default_agent_runner(prompt: str) -> str | None:
        """Run a prompt through the claude CLI via shared llm_client."""
        try:
            return call_claude(prompt, model="sonnet", timeout=600)
        except FileNotFoundError:
            return None


# ---------------------------------------------------------------------------
# Convenience: apply adjustments back to findings list
# ---------------------------------------------------------------------------

def apply_discourse_result(
    findings: list[dict], result: DiscourseResult
) -> list[dict]:
    """Merge discourse adjustments and new findings into the findings list.

    - Updates ``confidence_discourse_delta`` on existing findings.
    - Appends SURFACE-generated new findings.
    """
    for f in findings:
        fid = f.get("id") or f.get("merged_id", "")
        delta = result.confidence_adjustments.get(fid, 0)
        f["confidence_discourse_delta"] = delta
        # Clamp final confidence to [0, 100]
        base = f.get("confidence", 50)
        f["confidence_after_discourse"] = max(0, min(100, int(base + delta * 10)))

    for nf in result.new_findings:
        nf["confidence"] = 60
        nf["confidence_after_discourse"] = 60
        findings.append(nf)

    return findings


# ---------------------------------------------------------------------------
# CLI entry point (for standalone testing)
# ---------------------------------------------------------------------------

def main():
    """Standalone test: load findings from phase2, run discourse."""
    import sys
    from pathlib import Path

    if len(sys.argv) > 1:
        report_dir = Path(sys.argv[1])
    else:
        print("Usage: python phase3_discourse.py <report_dir>")
        print("  report_dir should contain phase2/merged-findings.json")
        sys.exit(1)

    phase2_dir = report_dir / "phase2"
    phase3_dir = report_dir / "phase3-discourse"
    phase3_dir.mkdir(parents=True, exist_ok=True)

    merged_file = phase2_dir / "merged-findings.json"
    if not merged_file.exists():
        print(f"Error: {merged_file} not found")
        sys.exit(1)

    findings = json.loads(merged_file.read_text(encoding="utf-8"))
    print(f"[Discourse] Loaded {len(findings)} findings")

    grouped = _group_by_reviewer(findings)
    print(f"[Discourse] Reviewers: {list(grouped.keys())}")

    if len(grouped) < 2:
        print("[Discourse] Need at least 2 reviewers. Skipping.")
        return

    phase = DiscoursePhase()
    result = phase.run(findings)

    # Save raw result
    result_data = {
        "responses": [
            {
                "type": r.response_type.value,
                "reviewer": r.reviewer,
                "finding_id": r.finding_id,
                "target_reviewer": r.target_reviewer,
                "target_finding_id": r.target_finding_id,
                "reasoning": r.reasoning,
                "defended": r.defended,
            }
            for r in result.responses
        ],
        "confidence_adjustments": result.confidence_adjustments,
        "new_findings": result.new_findings,
    }
    out_file = phase3_dir / "discourse-result.json"
    out_file.write_text(
        json.dumps(result_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[Discourse] Saved to {out_file}")

    # Apply and save updated findings
    updated = apply_discourse_result(findings, result)
    updated_file = phase3_dir / "findings-after-discourse.json"
    updated_file.write_text(
        json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Print summary
    type_counts: dict[str, int] = {}
    for r in result.responses:
        type_counts[r.response_type.value] = (
            type_counts.get(r.response_type.value, 0) + 1
        )

    print(f"\n[Discourse] Summary:")
    print(f"  Total responses: {len(result.responses)}")
    for t, c in sorted(type_counts.items()):
        print(f"    {t}: {c}")
    print(f"  Confidence adjustments: {len(result.confidence_adjustments)}")
    print(f"  New findings from SURFACE: {len(result.new_findings)}")
    print(f"  Updated findings saved: {updated_file}")


if __name__ == "__main__":
    main()
