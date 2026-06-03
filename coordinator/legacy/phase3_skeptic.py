"""MACRS Phase 3 - Skeptic Agent (Adversarial Verification).

Reads Phase 2 merged findings, filters P0/P1, sends each to a Skeptic Agent
that tries to refute them. Outputs verification results.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

PHASE2_DIR = None  # Set at runtime
PHASE3_DIR = None
SOURCE_DIR = None
TIMEOUT = 600


def load_merged_findings(phase2_dir: Path) -> list[dict]:
    """Load merged findings from Phase 2."""
    f = phase2_dir / "merged-findings.json"
    if not f.exists():
        print(f"Error: {f} not found")
        sys.exit(1)
    return json.loads(f.read_text(encoding="utf-8"))


def filter_for_verification(findings: list[dict]) -> list[dict]:
    """Only verify P0 BLOCKING and P1 CRITICAL findings."""
    return [f for f in findings if f.get("canonical_severity", "").startswith(("P0", "P1"))]


def read_source_file(file_path: str, source_dir: Path) -> str:
    """Read the actual source file content."""
    full_path = source_dir / file_path
    if full_path.exists():
        return full_path.read_text(encoding="utf-8", errors="replace")[:5000]
    return "(file not found)"


def build_skeptic_prompt(findings: list[dict], source_dir: Path) -> str:
    """Build the Skeptic Agent prompt with all findings and source code."""
    findings_text = []
    for f in findings:
        file_content = read_source_file(f.get("file", ""), source_dir)
        findings_text.append(f"""### {f.get('merged_id', 'N/A')} - {f.get('canonical_title', 'N/A')}
- Severity: {f.get('canonical_severity', 'N/A')}
- File: {f.get('file', 'N/A')} lines {f.get('line_range', 'N/A')}
- Description: {f.get('description', 'N/A')[:500]}
- Suggestion: {f.get('suggestion', 'N/A')[:300]}

Source code context:
```
{file_content}
```
""")

    prompt = f"""你是代码审查的"魔鬼代言人"。你的唯一任务是：
仔细阅读每一个发现，对照实际源代码，尽最大努力证明它是误报。

## 你可以使用的反驳角度：
1. 上下文反驳：这段代码的调用上下文使"漏洞"不可利用
2. 防护反驳：上游已有验证/过滤/转义，攻击向量被阻断
3. 范围反驳：问题代码在测试文件/已废弃代码/非生产路径中
4. 替代解释：Agent 误解了代码意图，实际行为是正确的
5. 严重降级：问题存在但严重等级被高估

## 你必须对每一个发现做出裁决：
- CONFIRM：确认，发现正确
- REFUTE：驳斥，提供反驳证据
- DOWNGRADE：降级，问题存在但严重等级过高，给出正确等级
- NEEDS_HUMAN：无法确定，需要人类判断

## 待验证的发现：

{"".join(findings_text)}

## 输出格式要求
**只输出 JSON，不要输出任何 JSON 以外的文本。**

```json
{{
  "verifications": [
    {{
      "merged_id": "M-001",
      "verdict": "CONFIRM | REFUTE | DOWNGRADE | NEEDS_HUMAN",
      "adjusted_severity": "如果DOWNGRADE填新等级，否则null",
      "rationale": "详细理由",
      "confidence_after_verification": 0.9
    }}
  ],
  "summary": {{
    "total_verified": 0,
    "confirmed": 0,
    "refuted": 0,
    "downgraded": 0,
    "needs_human": 0
  }}
}}
```"""
    return prompt


def run_skeptic(prompt: str, phase3_dir: Path) -> dict | None:
    """Run Skeptic Agent via claude CLI."""
    prompt_file = phase3_dir / "skeptic-prompt.md"
    prompt_file.write_text(prompt, encoding="utf-8")

    print("[Skeptic] Running adversarial verification...")
    start = time.time()

    try:
        import os
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["LANG"] = "en_US.UTF-8"
        cmd = f'cat "{prompt_file}" | claude -p --model sonnet --output-format text'
        result = subprocess.run(
            cmd, capture_output=True,
            timeout=TIMEOUT, shell=True, env=env,
        )
        elapsed = time.time() - start
        print(f"[Skeptic] Completed in {elapsed:.1f}s")

        stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
        stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""

        if result.returncode != 0:
            print(f"[Skeptic] Error: {stderr[:500]}")
            return None

        return _extract_json(stdout)
    except subprocess.TimeoutExpired:
        print(f"[Skeptic] Timeout after {TIMEOUT}s")
        return None


def _extract_json(text: str) -> dict | None:
    """Extract JSON from text."""
    import re
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    blocks = re.findall(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    for block in blocks:
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            continue

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


def apply_verifications(findings: list[dict], verification: dict) -> list[dict]:
    """Apply skeptic verdicts to findings."""
    ver_map = {v["merged_id"]: v for v in verification.get("verifications", [])}

    for f in findings:
        vid = f.get("merged_id")
        if vid in ver_map:
            v = ver_map[vid]
            f["skeptic_verdict"] = v.get("verdict", "PENDING")
            f["skeptic_rationale"] = v.get("rationale", "")
            f["confidence_after_verification"] = v.get("confidence_after_verification", f.get("confidence", 0.8))
            if v.get("verdict") == "DOWNGRADE" and v.get("adjusted_severity"):
                f["original_severity"] = f.get("canonical_severity")
                f["canonical_severity"] = v["adjusted_severity"]
        else:
            f["skeptic_verdict"] = "NOT_CHECKED"

    return findings


def main():
    global PHASE2_DIR, PHASE3_DIR, SOURCE_DIR

    if len(sys.argv) > 1:
        report_dir = Path(sys.argv[1])
    else:
        report_dir = Path("C:/Users/Administrator/Claude-Code/cc-tools/MACRS/reports/review-20260601-172405")

    if not report_dir.exists():
        print(f"Error: Report directory not found: {report_dir}")
        sys.exit(1)

    PHASE2_DIR = report_dir / "phase2"
    PHASE3_DIR = report_dir / "phase3"
    SOURCE_DIR = Path("C:/Users/Administrator/Claude-Code/cc-tools/Xun-CC-Panel/server")

    PHASE3_DIR.mkdir(parents=True, exist_ok=True)

    # Load and filter
    findings = load_merged_findings(PHASE2_DIR)
    to_verify = filter_for_verification(findings)
    print(f"[Phase 3] {len(findings)} total findings, {len(to_verify)} P0/P1 for verification")

    if not to_verify:
        print("[Phase 3] No P0/P1 findings to verify. Done.")
        return

    # Build and run skeptic
    prompt = build_skeptic_prompt(to_verify, SOURCE_DIR)
    verification = run_skeptic(prompt, PHASE3_DIR)

    if verification is None:
        print("[Phase 3] Skeptic failed. Skipping verification.")
        return

    # Save raw verification
    (PHASE3_DIR / "skeptic-verification.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Apply to findings
    verified_findings = apply_verifications(to_verify, verification)

    # Summary
    verdicts = {}
    for f in verified_findings:
        v = f.get("skeptic_verdict", "PENDING")
        verdicts[v] = verdicts.get(v, 0) + 1

    summary = {
        "phase": 3,
        "total_findings": len(findings),
        "p0_p1_for_verification": len(to_verify),
        "verdicts": verdicts,
        "verified_findings": verified_findings,
    }

    (PHASE3_DIR / "phase3-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n[Phase 3] Results:")
    for k, v in verdicts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
