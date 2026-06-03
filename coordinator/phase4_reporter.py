#!/usr/bin/env python3
"""
MACRS Phase 4: Report Generator
Reads Phase 1-3 JSON results and generates a human-readable Markdown report.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


# ── Configuration ──────────────────────────────────────────────────────────

# Will be set from command line argument
REPORT_DIR = None
COORDINATOR_DIR = Path("C:/Users/Administrator/Claude-Code/cc-tools/MACRS/coordinator")

# Severity ordering (lower number = higher priority)
SEVERITY_ORDER = {
    "P0 BLOCKING": 0,
    "P1 CRITICAL": 1,
    "P2 HIGH": 2,
    "P2 MEDIUM": 2,
    "P3 LOW": 3,
    "P3 MEDIUM": 3,
}

# Chinese labels for severity groups
SEVERITY_LABELS = {
    "P0": "P0 阻断 -- 必须立即修复",
    "P1": "P1 严重 -- 合并前应修复",
    "P2": "P2 重要 -- 下个迭代修复",
    "P3": "P3 建议 -- 有空可改",
}


# ── Helpers ────────────────────────────────────────────────────────────────

def load_json(path: Path) -> dict | list:
    """Load a JSON file and return parsed content."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def severity_group(severity: str) -> str:
    """Extract the P-level group from a severity string like 'P0 BLOCKING' -> 'P0'."""
    return severity.split()[0] if severity else "P3"


def severity_sort_key(finding: dict) -> tuple:
    """Sort key for findings: (severity_order, -confidence, merged_id)."""
    sev = finding.get("canonical_severity", "P3 LOW")
    order = SEVERITY_ORDER.get(sev, 99)
    conf = finding.get("confidence_after_verification") or finding.get("consensus", {}).get("final_confidence", 0)
    mid = finding.get("merged_id", "M-999")
    num = int(mid.split("-")[1]) if "-" in mid else 999
    return (order, -conf, num)


def format_confidence(val: float | None) -> str:
    """Format a confidence float as '0.XX'."""
    if val is None:
        return "N/A"
    return f"{val:.2f}"


def get_confidence(finding: dict) -> float | None:
    """Get the best available confidence value for a finding."""
    return finding.get("confidence_after_verification") or finding.get("consensus", {}).get("final_confidence")


def get_source_agents(finding: dict) -> str:
    """Return comma-separated agent names from sources."""
    sources = finding.get("sources", [])
    agents = sorted(set(s.get("agent", "?") for s in sources))
    return ", ".join(f"Agent {a}" for a in agents)


def get_verdict_label(verdict: str) -> str:
    """Map verdict string to a display label."""
    labels = {
        "CONFIRM": "CONFIRM",
        "DOWNGRADE": "DOWNGRADE",
        "REFUTE": "REFUTE",
        "NEEDS_HUMAN": "NEEDS_HUMAN",
        "NOT_CHECKED": "NOT_CHECKED",
    }
    return labels.get(verdict, verdict)


# ── Data Loading ───────────────────────────────────────────────────────────

def load_all_data() -> dict:
    """Load all Phase 1-3 data and return a unified data dict."""
    # Phase 1 (some agents may have failed)
    review_a = load_json(REPORT_DIR / "review-a.json") if (REPORT_DIR / "review-a.json").exists() else {"findings": []}
    review_b = load_json(REPORT_DIR / "review-b.json") if (REPORT_DIR / "review-b.json").exists() else {"findings": []}
    review_c = load_json(REPORT_DIR / "review-c.json") if (REPORT_DIR / "review-c.json").exists() else {"findings": []}
    phase1_summary = load_json(REPORT_DIR / "phase-1-summary.json")

    # Phase 2
    merged_findings = load_json(REPORT_DIR / "phase2" / "merged-findings.json")
    phase2_summary = load_json(REPORT_DIR / "phase2" / "phase2-summary.json")

    # Phase 3 (optional - may not exist if skeptic failed)
    phase3_dir = REPORT_DIR / "phase3"
    if (phase3_dir / "skeptic-verification.json").exists():
        skeptic_verification = load_json(phase3_dir / "skeptic-verification.json")
        phase3_summary = load_json(phase3_dir / "phase3-summary.json")
    else:
        print("[Phase 4] Phase 3 data not found, skipping adversarial verification")
        skeptic_verification = {"verifications": []}
        phase3_summary = {"verdicts": {}}

    return {
        "review_a": review_a,
        "review_b": review_b,
        "review_c": review_c,
        "phase1_summary": phase1_summary,
        "merged_findings": merged_findings,
        "phase2_summary": phase2_summary,
        "skeptic_verification": skeptic_verification,
        "phase3_summary": phase3_summary,
    }


# ── Categorize Findings ───────────────────────────────────────────────────

def categorize_findings(data: dict) -> dict:
    """
    Split findings into:
    - active: CONFIRM / NOT_CHECKED (displayed in severity sections)
    - downgraded: DOWNGRADE (displayed in severity sections at adjusted level)
    - refuted: REFUTE (appendix)
    - needs_human: NEEDS_HUMAN (appendix)
    """
    # Use phase3-summary verified_findings as primary source (most complete)
    verified = data["phase3_summary"].get("verified_findings", [])

    # If Phase 3 didn't run, use phase2 merged_findings directly
    if not verified:
        print("[Phase 4] No Phase 3 verification data, using Phase 2 findings directly")
        merged = data.get("merged_findings", [])
        active = []
        for f in merged:
            # Add default verdict fields
            f["skeptic_verdict"] = "NOT_CHECKED"
            f["confidence_after_verification"] = f.get("confidence", 0.8)
            active.append(f)
        active.sort(key=severity_sort_key)
        return {
            "active": active,
            "refuted": [],
            "needs_human": [],
        }

    active = []      # CONFIRM, NOT_CHECKED, DOWNGRADE (they have adjusted severity)
    refuted = []
    needs_human = []

    for f in verified:
        verdict = f.get("skeptic_verdict", "NOT_CHECKED")
        if verdict == "REFUTE":
            refuted.append(f)
        elif verdict == "NEEDS_HUMAN":
            needs_human.append(f)
        else:
            # CONFIRM, DOWNGRADE, NOT_CHECKED all go to active
            active.append(f)

    # Sort active findings by severity
    active.sort(key=severity_sort_key)

    return {
        "active": active,
        "refuted": refuted,
        "needs_human": needs_human,
    }


# ── Severity Counts ───────────────────────────────────────────────────────

def count_severities(findings: list) -> dict:
    """Count findings by severity group (P0, P1, P2, P3)."""
    counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for f in findings:
        sev = f.get("canonical_severity", "P3 LOW")
        grp = severity_group(sev)
        counts[grp] = counts.get(grp, 0) + 1
    return counts


# ── Markdown Generation ───────────────────────────────────────────────────

def generate_report(data: dict) -> str:
    """Generate the full Markdown report."""
    lines = []

    # Collect all metadata
    phase1 = data["phase1_summary"]
    phase3 = data["phase3_summary"]
    review_a = data["review_a"]
    review_b = data["review_b"]

    total_files = review_a.get("review_scope", {}).get("files", [])
    lines_total = review_a.get("review_scope", {}).get("lines_total", 0)
    total_elapsed = phase1.get("total_elapsed_seconds", 0)

    cats = categorize_findings(data)
    active = cats["active"]
    refuted = cats["refuted"]
    needs_human = cats["needs_human"]

    all_active_count = len(active)
    sev_counts = count_severities(active)

    # Phase 3 verdict stats
    total_verified = phase3.get("total_findings", 0)
    confirmed_count = sum(1 for f in active if f.get("skeptic_verdict") == "CONFIRM")
    downgraded_count = sum(1 for f in active if f.get("skeptic_verdict") == "DOWNGRADE")
    not_checked_count = sum(1 for f in active if f.get("skeptic_verdict") == "NOT_CHECKED")

    # ── Header ──
    lines.append("# MACRS 代码审查报告")
    lines.append("")
    lines.append(f"> **审查时间**: 2026-06-01")
    lines.append(f"> **审查范围**: Xun-CC-Panel/server/ ({len(total_files)}个文件, {lines_total}行)")
    lines.append(f"> **总耗时**: {total_elapsed:.1f} 秒")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Executive Summary ──
    lines.append("## 执行摘要")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|------|------|")
    lines.append(f"| 发现问题总数 | {all_active_count} |")
    lines.append(f"| ┣ P0 阻断 | {sev_counts.get('P0', 0)} |")
    lines.append(f"| ┣ P1 严重 | {sev_counts.get('P1', 0)} |")
    lines.append(f"| ┣ P2 重要 | {sev_counts.get('P2', 0)} |")
    lines.append(f"| ┣ P3 建议 | {sev_counts.get('P3', 0)} |")
    lines.append(f"| 对抗验证通过 | {confirmed_count + downgraded_count} ({(confirmed_count + downgraded_count) / max(total_verified, 1) * 100:.0f}%) |")
    lines.append(f"| 对抗验证驳斥 | {len(refuted)} |")
    lines.append(f"| 需人工裁决 | {len(needs_human)} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Group active findings by severity ──
    grouped = {"P0": [], "P1": [], "P2": [], "P3": [], "P4": []}
    for f in active:
        grp = severity_group(f.get("canonical_severity", "P3 LOW"))
        if grp not in grouped:
            grp = "P3"  # fallback
        grouped[grp].append(f)

    counter = 1

    for p_level in ["P0", "P1", "P2", "P3"]:
        findings_in_group = grouped[p_level]
        if not findings_in_group:
            continue

        lines.append(f"## {SEVERITY_LABELS[p_level]}")
        lines.append("")

        for f in findings_in_group:
            mid = f.get("merged_id", "M-???")
            title = f.get("canonical_title", "Untitled")
            sev = f.get("canonical_severity", "N/A")
            file_path = f.get("file", "unknown")
            line_range = f.get("line_range", [0, 0])
            desc = f.get("canonical_description", "No description.")
            suggestion = f.get("suggestion", "")
            code_bad = f.get("code_snippet_bad", "")
            code_good = f.get("code_snippet_good", "")
            confidence = get_confidence(f)
            sources = get_source_agents(f)
            verdict = f.get("skeptic_verdict", "NOT_CHECKED")
            rationale = f.get("skeptic_rationale", "")
            categories = f.get("category", [])
            if isinstance(categories, str):
                categories = [categories]

            # Counter label
            label = f"P0-{counter:03d}" if p_level == "P0" else \
                    f"P1-{counter:03d}" if p_level == "P1" else \
                    f"P2-{counter:03d}" if p_level == "P2" else \
                    f"P3-{counter:03d}"
            counter += 1

            lines.append(f"### {label}: {title}")
            lines.append("")
            lines.append("| 属性 | 值 |")
            lines.append("|------|-----|")
            lines.append(f"| **文件** | `{file_path}:{line_range[0]}-{line_range[1]}` |")
            lines.append(f"| **来源** | {sources} |")
            lines.append(f"| **分类** | {', '.join(categories)} |")
            lines.append(f"| **置信度** | {format_confidence(confidence)} |")
            lines.append(f"| **对抗验证** | {get_verdict_label(verdict)} |")
            if f.get("original_severity") and f.get("original_severity") != sev:
                lines.append(f"| **原始等级** | {f['original_severity']} (已降级) |")
            lines.append("")

            lines.append(f"**问题描述**：{desc}")
            lines.append("")

            if code_bad:
                lines.append("**问题代码**：")
                lines.append("```javascript")
                lines.append(code_bad)
                lines.append("```")
                lines.append("")

            if suggestion:
                lines.append(f"**修复建议**：{suggestion}")
                lines.append("")

            if code_good:
                lines.append("**修复后代码**：")
                lines.append("```javascript")
                lines.append(code_good)
                lines.append("```")
                lines.append("")

            if rationale:
                lines.append(f"**对抗验证备注**：{rationale}")
                lines.append("")

            lines.append("---")
            lines.append("")

    # ── Refuted Findings ──
    if refuted:
        lines.append("## 已驳斥发现")
        lines.append("")
        lines.append("| # | 原始发现 | 来源 | 原始等级 | 驳斥理由 |")
        lines.append("|---|---------|------|----------|----------|")
        for i, f in enumerate(refuted, 1):
            mid = f.get("merged_id", "M-???")
            title = f.get("canonical_title", "Untitled")
            sources = get_source_agents(f)
            orig_sev = f.get("original_severity", f.get("canonical_severity", "N/A"))
            rationale = f.get("skeptic_rationale", "N/A")
            # Truncate rationale for table
            short_rationale = rationale[:120] + "..." if len(rationale) > 120 else rationale
            lines.append(f"| {i} | {mid}: {title} | {sources} | {orig_sev} | {short_rationale} |")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── Needs Human Decision ──
    if needs_human:
        lines.append("## 需人工裁决")
        lines.append("")
        lines.append("| # | 发现 | 来源 | 原始等级 | 理由 |")
        lines.append("|---|------|------|----------|------|")
        for i, f in enumerate(needs_human, 1):
            mid = f.get("merged_id", "M-???")
            title = f.get("canonical_title", "Untitled")
            sources = get_source_agents(f)
            sev = f.get("canonical_severity", "N/A")
            rationale = f.get("skeptic_rationale", "N/A")
            short_rationale = rationale[:120] + "..." if len(rationale) > 120 else rationale
            lines.append(f"| {i} | {mid}: {title} | {sources} | {sev} | {short_rationale} |")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── Review Statistics ──
    lines.append("## 审查统计")
    lines.append("")
    lines.append("| Agent | 技能 | 发现数 | 状态 |")
    lines.append("|-------|------|--------|------|")

    agent_info = phase1.get("agents", {})
    agent_skills = {
        "A": data["review_a"].get("skill", "unknown"),
        "B": data["review_b"].get("skill", "unknown"),
        "C": data["review_c"].get("skill", "unknown"),
    }
    agent_names = {
        "A": "Agent A",
        "B": "Agent B",
        "C": "Agent C",
    }

    for agent_id in ["A", "B", "C"]:
        info = agent_info.get(agent_id, {})
        name = agent_names.get(agent_id, f"Agent {agent_id}")
        skill = agent_skills.get(agent_id, "unknown")
        count = info.get("findings_count", 0)
        status = "OK" if info.get("status") == "OK" else f"FAILED ({', '.join(info.get('validation_errors', []))})"
        elapsed = info.get("elapsed_seconds", 0) or 0
        lines.append(f"| {name} | {skill} | {count} | {status} ({elapsed:.1f}s) |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Footer ──
    lines.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
    lines.append(f"*Phase 2 去重后发现数: {data['phase2_summary'].get('total_findings_after_dedup', 'N/A')}*")
    lines.append(f"*Phase 3 对抗验证: {confirmed_count} CONFIRM, {downgraded_count} DOWNGRADE, {len(refuted)} REFUTE, {len(needs_human)} NEEDS_HUMAN*")
    lines.append("")

    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    global REPORT_DIR

    # Parse command line argument
    if len(sys.argv) > 1:
        REPORT_DIR = Path(sys.argv[1])
    else:
        REPORT_DIR = Path("C:/Users/Administrator/Claude-Code/cc-tools/MACRS/reports/review-20260601-172405")

    if not REPORT_DIR.exists():
        print(f"Error: Report directory not found: {REPORT_DIR}")
        sys.exit(1)

    print(f"[Phase 4] Loading Phase 1-3 data from: {REPORT_DIR}")
    data = load_all_data()

    print("[Phase 4] Generating Markdown report...")
    report = generate_report(data)

    output_path = REPORT_DIR / "report.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"[Phase 4] Report written to: {output_path}")
    print(f"[Phase 4] Report size: {len(report)} chars, {report.count(chr(10))} lines")

    # Quick summary
    cats = categorize_findings(data)
    print(f"[Phase 4] Active findings: {len(cats['active'])}")
    print(f"[Phase 4] Refuted findings: {len(cats['refuted'])}")
    print(f"[Phase 4] Needs human: {len(cats['needs_human'])}")


if __name__ == "__main__":
    main()
