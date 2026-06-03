"""MACRS Coordinator - Main Entry Point (7-Phase Architecture).

Orchestrates a complete code review pipeline through 7 phases:
  Phase 1: Context Discovery   - Analyze changes, identify type, select lenses
  Phase 2: Parallel Reviews    - Run applicable lenses in parallel (L1-L7)
  Phase 3: Cheap Scoring       - Sonnet batch-scores findings (gate filter)
  Phase 4: Deep Validation     - Opus/Sonnet validates high-value candidates
  Phase 5: Discourse           - Reviewers react to each other's findings
  Phase 6: Synthesis           - Generate final report
  Phase 7: Auto-Fix (optional) - Generate and apply fixes for confirmed issues

Usage:
    python main.py <target_path> [--output-dir <dir>] [--autofix] [--change-type <type>]
    python main.py <target_path> --lens L1,L2,L6    # Force specific lenses
    python main.py <target_path> --team-config team.yaml  # Multi-model team

Examples:
    python main.py D:/myproject/src/auth/
    python main.py D:/myproject/app.py --output-dir C:/Users/Administrator/Claude-Code/cc-tools/MACRS/reports/my-review/
    python main.py D:/myproject/src/ --autofix --change-type security
"""

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Add coordinator dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    REPORTS_DIR, LENS_CONFIG, VALIDATION_GATE, DISCOURSE, AUTOFIX,
    MACRS_ROOT, TEAM_CONFIG_PATH,
)
from prompt_builder import read_target_files
from lens_manager import LensManager, LensDefinition, LensResult
from team_config import load_team_config, TeamConfig
from validation_gate import ValidationGate
from phase5_discourse import DiscoursePhase, DiscourseResult, apply_discourse_result
from phase5_autofix import AutoFixPhase
from artifact_manager import ArtifactManager
from llm_client import call_claude
from json_utils import extract_json as _extract_lens_json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("MACRS")


# ============================================================
# Lens Execution
# ============================================================

def run_lens(
    lens: LensDefinition,
    context: dict,
    lens_manager: LensManager,
    output_dir: Path,
) -> LensResult:
    """Run a single lens against the target code.

    Args:
        lens: The lens definition to execute.
        context: Phase 1 context (files, change_type, etc.).
        lens_manager: LensManager instance for prompt building.
        output_dir: Directory to save lens output.

    Returns:
        LensResult with findings or error info.
    """
    start_time = time.time()
    code_files = context["files"]

    # Build the prompt for this lens
    prompt = lens_manager.build_lens_prompt(
        lens=lens,
        code_files=code_files,
        project_context=context.get("project_context", ""),
        other_lens_findings=context.get("other_lens_findings", []),
    )

    # Save prompt for debugging
    prompt_file = output_dir / f"prompt-{lens.id.lower()}.md"
    prompt_file.write_text(prompt, encoding="utf-8")

    logger.info("Running lens %s (%s) - model=%s", lens.id, lens.name, lens.model)

    try:
        stdout = call_claude(prompt, model=lens.model, timeout=lens.timeout_seconds)

        elapsed = time.time() - start_time

        if stdout is None:
            logger.error("Lens %s failed", lens.id)
            return LensResult(
                lens_id=lens.id,
                status="FAILED",
                error="claude CLI returned no output",
                elapsed_seconds=round(elapsed, 1),
            )

        # Parse JSON from output
        parsed = _extract_lens_json(stdout)
        if parsed is None:
            logger.warning("Lens %s: could not parse JSON output", lens.id)
            return LensResult(
                lens_id=lens.id,
                status="FAILED",
                raw_output=stdout[:2000],
                error="Could not extract valid JSON from lens output",
                elapsed_seconds=round(elapsed, 1),
            )

        # Save lens result
        output_file = output_dir / f"lens-{lens.id.lower()}.json"
        output_file.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")

        findings = parsed.get("findings", [])
        logger.info("Lens %s completed: %d findings in %.1fs", lens.id, len(findings), elapsed)

        return LensResult(
            lens_id=lens.id,
            status="OK",
            findings=findings,
            raw_output=stdout[:2000],
            elapsed_seconds=round(elapsed, 1),
        )

    except FileNotFoundError:
        return LensResult(
            lens_id=lens.id,
            status="FAILED",
            error="claude CLI not found. Install: npm install -g @anthropic-ai/claude-code",
            elapsed_seconds=0.0,
        )
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error("Lens %s exception: %s", lens.id, e)
        return LensResult(
            lens_id=lens.id,
            status="FAILED",
            error=str(e),
            elapsed_seconds=round(elapsed, 1),
        )


# ============================================================
# Phase 1: Context Discovery
# ============================================================

def phase1_context_discovery(args) -> dict:
    """Analyze changes, identify type, and prepare context for review.

    Returns:
        Context dict with keys:
          - files: dict of {relative_path: content}
          - change_type: str (bugfix/feature/refactor/security/unknown)
          - is_trivial: bool (True if small change)
          - is_user_facing: bool (True if affects UI/UX)
          - project_context: str (additional context)
          - target_path: str
    """
    logger.info("Phase 1: Context Discovery")

    target_path = Path(args.target).resolve()
    if not target_path.exists():
        logger.error("Target path does not exist: %s", target_path)
        sys.exit(1)

    # Read target files
    files = read_target_files(str(target_path))
    if not files:
        logger.error("No code files found at: %s", target_path)
        sys.exit(1)

    logger.info("  Files found: %d", len(files))

    # Calculate total lines
    total_lines = sum(len(content.split("\n")) for content in files.values())
    logger.info("  Total lines: %d", total_lines)

    # Determine change type
    change_type = getattr(args, "change_type", None) or _detect_change_type(files)
    logger.info("  Change type: %s", change_type)

    # Determine triviality
    trivial_threshold = LENS_CONFIG.get("trivial_threshold", 50)
    is_trivial = total_lines < trivial_threshold
    logger.info("  Trivial: %s (threshold=%d, lines=%d)", is_trivial, trivial_threshold, total_lines)

    # Determine if user-facing
    is_user_facing = _detect_user_facing(files, args)
    logger.info("  User-facing: %s", is_user_facing)

    # Load project context (CLAUDE.md if exists)
    project_context = _load_project_context(target_path)

    return {
        "files": files,
        "change_type": change_type,
        "is_trivial": is_trivial,
        "is_user_facing": is_user_facing,
        "project_context": project_context,
        "target_path": str(target_path),
        "total_lines": total_lines,
    }


def _detect_change_type(files: dict[str, str]) -> str:
    """Heuristic detection of change type based on file patterns and content."""
    import re

    all_content = "\n".join(files.values())
    file_names = " ".join(files.keys()).lower()

    # Security indicators
    security_patterns = [
        r"password", r"secret", r"token", r"auth", r"crypto",
        r"sql.*query", r"exec\(", r"eval\(", r"__import__",
    ]
    if any(re.search(p, all_content, re.IGNORECASE) for p in security_patterns):
        # Check if files are auth/security related
        if any(kw in file_names for kw in ("auth", "security", "login", "token", "crypto")):
            return "security"

    # Feature indicators
    if any(kw in file_names for kw in ("feat", "feature", "new", "add")):
        return "feature"

    # Bugfix indicators
    if any(kw in file_names for kw in ("fix", "bug", "hotfix", "patch")):
        return "bugfix"

    # Refactor indicators
    if any(kw in file_names for kw in ("refactor", "clean", "reorganize")):
        return "refactor"

    # Test files
    if any(kw in file_names for kw in ("test", "spec", "__test__")):
        return "test"

    # Config files
    if any(kw in file_names for kw in ("config", "settings", ".env", "yaml", "toml")):
        return "config"

    # Docs
    if any(kw in file_names for kw in ("readme", "doc", ".md", ".rst")):
        return "docs"

    return "unknown"


def _detect_user_facing(files: dict[str, str], args) -> bool:
    """Detect if changes affect user-facing components."""
    user_facing_patterns = LENS_CONFIG.get("user_facing_patterns", [
        "*.ui", "*.vue", "*.tsx", "*.jsx", "*.html", "*.css",
        "*.scss", "*.less", "*.svelte", "*.astro",
    ])

    file_names = list(files.keys())
    for pattern in user_facing_patterns:
        # Simple glob-like matching
        ext = pattern.replace("*", "")
        if any(f.endswith(ext) for f in file_names):
            return True

    # Check for CLI/API patterns in content
    all_content = "\n".join(files.values())
    cli_patterns = ["argparse", "click", "typer", "fastapi", "flask", "django", "express"]
    if any(p in all_content.lower() for p in cli_patterns):
        return True

    return False


def _load_project_context(target_path: Path) -> str:
    """Load project context from CLAUDE.md and other config files."""
    context_parts = []

    # Check for CLAUDE.md in target dir and parents
    for parent in [target_path] + list(target_path.parents):
        claude_md = parent / "CLAUDE.md"
        if claude_md.exists():
            content = claude_md.read_text(encoding="utf-8", errors="replace")
            context_parts.append(f"### CLAUDE.md ({claude_md})\n{content[:3000]}")
            break

    # Check for README
    for parent in [target_path] + list(target_path.parents):
        readme = parent / "README.md"
        if readme.exists():
            content = readme.read_text(encoding="utf-8", errors="replace")
            context_parts.append(f"### README.md\n{content[:2000]}")
            break

    return "\n\n".join(context_parts) if context_parts else ""


# ============================================================
# Phase 2: Parallel Reviews (7 Lens)
# ============================================================

def phase2_parallel_reviews(context: dict, lens_manager: LensManager, output_dir: Path) -> list[dict]:
    """Run applicable lenses in parallel and collect findings.

    Args:
        context: Phase 1 context dict.
        lens_manager: LensManager instance.
        output_dir: Directory to save results.

    Returns:
        List of all findings from all lenses.
    """
    logger.info("Phase 2: Parallel Reviews (7 Lens)")

    # Get applicable lenses (pass custom lens IDs from --lens CLI arg)
    applicable_lenses = lens_manager.get_applicable_lenses(
        change_type=context["change_type"],
        is_trivial=context["is_trivial"],
        is_user_facing=context["is_user_facing"],
        custom_lens_ids=context.get("_custom_lens_ids"),
    )

    if not applicable_lenses:
        logger.warning("No applicable lenses found for context")
        return []

    logger.info("  Applicable lenses: %s", [l.id for l in applicable_lenses])
    logger.info("  Models: %s", {l.id: l.model for l in applicable_lenses})

    # Run lenses in parallel
    all_findings = []
    lens_results = {}

    phase2_dir = output_dir / "phase2"
    phase2_dir.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(max_workers=len(applicable_lenses)) as executor:
        futures = {
            executor.submit(run_lens, lens, context, lens_manager, phase2_dir): lens
            for lens in applicable_lenses
        }

        for future in as_completed(futures):
            lens = futures[future]
            try:
                result = future.result()
                lens_results[lens.id] = result

                if result.status == "OK":
                    # Tag findings with lens source
                    for finding in result.findings:
                        finding["_lens_source"] = lens.id
                        finding["_lens_model"] = lens.model
                    all_findings.extend(result.findings)
                    logger.info("  %s: %d findings (%.1fs)", lens.id, len(result.findings), result.elapsed_seconds)
                else:
                    logger.warning("  %s: %s - %s", lens.id, result.status, result.error)
            except Exception as e:
                logger.error("  %s: exception - %s", lens.id, e)
                lens_results[lens.id] = LensResult(
                    lens_id=lens.id, status="FAILED", error=str(e)
                )

    # Save combined results
    _save_lens_summary(lens_results, all_findings, phase2_dir)

    logger.info("Phase 2 complete: %d total findings from %d lenses",
                len(all_findings), len([r for r in lens_results.values() if r.status == "OK"]))

    return all_findings


def _save_lens_summary(
    lens_results: dict[str, LensResult],
    all_findings: list[dict],
    output_dir: Path,
):
    """Save lens execution summary and combined findings."""
    summary = {
        "lenses": {
            lid: {
                "status": r.status,
                "findings_count": len(r.findings),
                "elapsed_seconds": r.elapsed_seconds,
                "error": r.error,
            }
            for lid, r in lens_results.items()
        },
        "total_findings": len(all_findings),
        "successful_lenses": sum(1 for r in lens_results.values() if r.status == "OK"),
    }

    (output_dir / "lens-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    (output_dir / "all-findings.json").write_text(
        json.dumps(all_findings, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ============================================================
# Phase 3: Cheap Scoring
# ============================================================

def phase3_cheap_scoring(findings: list[dict], validation_gate: ValidationGate, output_dir: Path) -> list:
    """Score findings with Sonnet batch processing.

    Args:
        findings: All findings from Phase 2.
        validation_gate: ValidationGate instance.
        output_dir: Directory to save results.

    Returns:
        List of ScoredFinding objects.
    """
    logger.info("Phase 3: Cheap Scoring")
    logger.info("  Input findings: %d", len(findings))

    if not findings:
        logger.info("  No findings to score")
        return []

    # Run cheap scoring
    scored = validation_gate.cheap_scoring(findings)
    logger.info("  Scored: %d findings", len(scored))

    # Auto-graduate cross-validated findings
    scored = validation_gate.auto_graduate(scored)
    graduated = sum(1 for s in scored if s.auto_graduated)
    logger.info("  Auto-graduated: %d findings", graduated)

    # Count dispositions
    from validation_gate import Disposition
    pending = sum(1 for s in scored if s.disposition == Disposition.PENDING_VALIDATION)
    below_gate = sum(1 for s in scored if s.disposition == Disposition.BELOW_GATE)
    logger.info("  Pending validation: %d, Below gate: %d", pending, below_gate)

    # Save results
    phase3_dir = output_dir / "phase3-scoring"
    phase3_dir.mkdir(parents=True, exist_ok=True)

    scored_data = []
    for sf in scored:
        scored_data.append({
            "finding_id": sf.finding.get("merged_id") or sf.finding.get("id", "unknown"),
            "score": sf.score,
            "source_families": sf.source_families,
            "disposition": sf.disposition.value,
            "auto_graduated": sf.auto_graduated,
            "chunk_index": sf.chunk_index,
        })

    (phase3_dir / "scored-findings.json").write_text(
        json.dumps(scored_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return scored


# ============================================================
# Phase 4: Deep Validation
# ============================================================

def phase4_deep_validation(scored, validation_gate: ValidationGate, output_dir: Path) -> list:
    """Validate high-value candidates with Opus/Sonnet.

    Args:
        scored: List of ScoredFinding objects from Phase 3.
        validation_gate: ValidationGate instance.
        output_dir: Directory to save results.

    Returns:
        List of ValidationResult objects.
    """
    logger.info("Phase 4: Deep Validation")

    if not scored:
        logger.info("  No candidates to validate")
        return []

    # Run deep validation
    validated = validation_gate.deep_validation(scored)
    logger.info("  Validated: %d findings", len(validated))

    # Count dispositions
    from validation_gate import Disposition
    confirmed = sum(1 for v in validated if v.disposition.value.startswith("confirmed"))
    disproven = sum(1 for v in validated if v.disposition == Disposition.DISPROVEN)
    uncertain = sum(1 for v in validated if v.disposition == Disposition.UNCERTAIN)
    logger.info("  Confirmed: %d, Disproven: %d, Uncertain: %d", confirmed, disproven, uncertain)

    # Save results
    phase4_dir = output_dir / "phase4-validation"
    phase4_dir.mkdir(parents=True, exist_ok=True)

    validated_data = []
    for vr in validated:
        validated_data.append({
            "finding_id": vr.finding.get("merged_id") or vr.finding.get("id", "unknown"),
            "disposition": vr.disposition.value,
            "confidence": vr.confidence,
            "reasoning": vr.reasoning,
            "lane": vr.lane,
            "adjusted_severity": vr.adjusted_severity,
        })

    (phase4_dir / "validated-findings.json").write_text(
        json.dumps(validated_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return validated


# ============================================================
# Phase 5: Discourse
# ============================================================

def phase5_discourse(
    findings: list[dict],
    discourse_phase: DiscoursePhase,
    output_dir: Path,
) -> DiscourseResult:
    """Run discourse round where reviewers react to each other's findings.

    Args:
        findings: All findings from Phase 2 (with scores/validations attached).
        discourse_phase: DiscoursePhase instance.
        output_dir: Directory to save results.

    Returns:
        DiscourseResult with responses and confidence adjustments.
    """
    logger.info("Phase 5: Discourse")
    logger.info("  Input findings: %d", len(findings))

    if not findings:
        logger.info("  No findings for discourse")
        return DiscourseResult()

    # Run discourse
    result = discourse_phase.run(findings)

    logger.info("  Responses: %d", len(result.responses))
    logger.info("  Confidence adjustments: %d", len(result.confidence_adjustments))
    logger.info("  New findings from discourse: %d", len(result.new_findings))

    # Save results
    phase5_dir = output_dir / "phase5-discourse"
    phase5_dir.mkdir(parents=True, exist_ok=True)

    discourse_data = {
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

    (phase5_dir / "discourse-result.json").write_text(
        json.dumps(discourse_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return result


# ============================================================
# Phase 6: Synthesis
# ============================================================

def phase6_synthesis(
    findings: list[dict],
    discourse_result: DiscourseResult,
    context: dict,
    validation_results: list,
    output_dir: Path,
) -> dict:
    """Generate final report combining all phases.

    Args:
        findings: All findings with discourse adjustments applied.
        discourse_result: Phase 5 discourse result.
        context: Phase 1 context.
        validation_results: Phase 4 validation results.
        output_dir: Directory to save report.

    Returns:
        Report dict.
    """
    logger.info("Phase 6: Synthesis")

    # Apply discourse adjustments to findings
    if discourse_result:
        findings = apply_discourse_result(findings, discourse_result)

    # Build validation map
    validation_map = {}
    from validation_gate import Disposition
    for vr in (validation_results or []):
        fid = vr.finding.get("merged_id") or vr.finding.get("id", "unknown")
        validation_map[fid] = {
            "disposition": vr.disposition.value,
            "confidence": vr.confidence,
            "reasoning": vr.reasoning,
        }

    # Classify findings by severity
    severity_groups = {"P0": [], "P1": [], "P2": [], "P3": []}
    confirmed_findings = []

    for f in findings:
        # Get severity
        severity = f.get("canonical_severity") or f.get("severity", "P3 LOW")
        sev_prefix = severity.split()[0] if severity else "P3"
        if sev_prefix not in severity_groups:
            sev_prefix = "P3"

        # Check validation status
        fid = f.get("merged_id") or f.get("id", "")
        validation = validation_map.get(fid)
        disposition = validation.get("disposition") if validation else None

        # Only include confirmed findings in report (or unvalidated ones)
        if disposition and disposition.startswith("confirmed"):
            f["_validation"] = validation
            severity_groups[sev_prefix].append(f)
            confirmed_findings.append(f)
        elif not disposition:
            # No validation (e.g., below gate) - include with note
            f["_validation"] = {"disposition": "unvalidated", "confidence": 0, "reasoning": ""}
            severity_groups[sev_prefix].append(f)

    # Build report
    report = {
        "metadata": {
            "target": context["target_path"],
            "change_type": context["change_type"],
            "is_trivial": context["is_trivial"],
            "is_user_facing": context["is_user_facing"],
            "total_files": len(context["files"]),
            "total_lines": context["total_lines"],
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "summary": {
            "total_findings": len(findings),
            "confirmed_findings": len(confirmed_findings),
            "by_severity": {
                sev: len(fs) for sev, fs in severity_groups.items()
            },
        },
        "findings": {
            "P0": _format_findings(severity_groups["P0"]),
            "P1": _format_findings(severity_groups["P1"]),
            "P2": _format_findings(severity_groups["P2"]),
            "P3": _format_findings(severity_groups["P3"]),
        },
        "discourse": {
            "responses_count": len(discourse_result.responses) if discourse_result else 0,
            "new_findings_count": len(discourse_result.new_findings) if discourse_result else 0,
            "adjustments": discourse_result.confidence_adjustments if discourse_result else {},
        },
    }

    # Save report
    phase6_dir = output_dir / "phase6-report"
    phase6_dir.mkdir(parents=True, exist_ok=True)

    (phase6_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Generate markdown report
    md_report = _generate_markdown_report(report)
    (phase6_dir / "report.md").write_text(md_report, encoding="utf-8")

    logger.info("Phase 6 complete: %d total findings, %d confirmed",
                len(findings), len(confirmed_findings))

    return report


def _format_findings(findings: list[dict]) -> list[dict]:
    """Format findings for the report."""
    formatted = []
    for f in findings:
        formatted.append({
            "id": f.get("merged_id") or f.get("id", "N/A"),
            "title": f.get("canonical_title") or f.get("title", "N/A"),
            "severity": f.get("canonical_severity") or f.get("severity", "N/A"),
            "file": f.get("file", "N/A"),
            "line": f.get("line") or f.get("line_range", "N/A"),
            "description": f.get("description", "")[:500],
            "suggestion": f.get("suggestion", "")[:300],
            "confidence": f.get("confidence_after_discourse") or f.get("confidence", 0),
            "lens_source": f.get("_lens_source", "N/A"),
            "validation": f.get("_validation", {}),
        })
    return formatted


def _generate_markdown_report(report: dict) -> str:
    """Generate a human-readable markdown report."""
    meta = report["metadata"]
    summary = report["summary"]

    lines = [
        "# MACRS Code Review Report",
        "",
        f"**Target:** `{meta['target']}`",
        f"**Date:** {meta['timestamp']}",
        f"**Change Type:** {meta['change_type']}",
        f"**Files:** {meta['total_files']} | **Lines:** {meta['total_lines']}",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total Findings | {summary['total_findings']} |",
        f"| Confirmed | {summary['confirmed_findings']} |",
        f"| P0 (Blocking) | {summary['by_severity'].get('P0', 0)} |",
        f"| P1 (Critical) | {summary['by_severity'].get('P1', 0)} |",
        f"| P2 (High) | {summary['by_severity'].get('P2', 0)} |",
        f"| P3 (Low) | {summary['by_severity'].get('P3', 0)} |",
        "",
    ]

    # Add findings by severity
    for sev, label in [("P0", "P0 - Blocking"), ("P1", "P1 - Critical"), ("P2", "P2 - High"), ("P3", "P3 - Low")]:
        findings = report["findings"].get(sev, [])
        if not findings:
            continue

        lines.append(f"## {label}")
        lines.append("")

        for f in findings:
            lines.append(f"### {f['id']}: {f['title']}")
            lines.append(f"- **File:** `{f['file']}:{f['line']}`")
            lines.append(f"- **Confidence:** {f['confidence']}/100")
            lines.append(f"- **Lens:** {f['lens_source']}")
            lines.append(f"- **Description:** {f['description']}")
            if f.get("suggestion"):
                lines.append(f"- **Suggestion:** {f['suggestion']}")
            lines.append("")

    # Add discourse summary
    discourse = report.get("discourse", {})
    if discourse.get("responses_count", 0) > 0:
        lines.extend([
            "## Discourse Summary",
            "",
            f"- Responses: {discourse['responses_count']}",
            f"- New findings from discourse: {discourse['new_findings_count']}",
            "",
        ])

    return "\n".join(lines)


# ============================================================
# Phase 7: Auto-Fix (Optional)
# ============================================================

def phase7_autofix(
    report: dict,
    autofix_phase: AutoFixPhase,
    artifact_manager: ArtifactManager,
    output_dir: Path,
) -> dict:
    """Generate and apply fixes for confirmed findings.

    Args:
        report: Phase 6 report dict.
        autofix_phase: AutoFixPhase instance.
        artifact_manager: ArtifactManager instance.
        output_dir: Directory to save results.

    Returns:
        Fix result dict.
    """
    logger.info("Phase 7: Auto-Fix")

    # Extract confirmed findings as fix candidates
    confirmed = []
    for sev_findings in report.get("findings", {}).values():
        for f in sev_findings:
            validation = f.get("validation", {})
            disposition = validation.get("disposition", "")
            if disposition.startswith("confirmed"):
                confirmed.append(f)

    if not confirmed:
        logger.info("  No confirmed findings to fix")
        return {"status": "no_candidates", "fixes": []}

    logger.info("  Fix candidates: %d", len(confirmed))

    # Save candidates to artifact for autofix module
    artifact_data = {
        "findings": [
            {
                "id": f["id"],
                "file_path": f["file"],
                "line": f["line"],
                "message": f.get("description", ""),
                "status": "open",
                "disposition": f.get("validation", {}).get("disposition", ""),
                "score": int(f.get("confidence", 0)),
                "category": f.get("category", ""),
            }
            for f in confirmed
        ]
    }

    artifact_path = output_dir / "phase7-autofix" / "candidates.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact_data, ensure_ascii=False, indent=2), encoding="utf-8")

    # Run autofix gate
    try:
        candidates = autofix_phase.load_and_gate(str(artifact_path))
        logger.info("  Passed gate: %d candidates", len(candidates))

        if not candidates:
            return {"status": "gate_filtered", "fixes": []}

        # Group and fix
        groups = autofix_phase.create_fix_groups(candidates)
        fixes = autofix_phase.apply_fixes(groups)

        # Post-fix review
        reviewed_fixes = autofix_phase.post_fix_review(fixes)

        # Save results
        fix_results = []
        for fix in reviewed_fixes:
            fix_results.append({
                "finding_id": fix.finding.get("id", "unknown"),
                "state": fix.state.value,
                "diff": fix.diff,
                "regression": fix.regression,
                "error": fix.error,
                "attempts": fix.attempts,
            })

        result = {
            "status": "completed",
            "candidates": len(candidates),
            "fixes": fix_results,
        }

        (output_dir / "phase7-autofix" / "fix-results.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        resolved = sum(1 for f in fix_results if f["state"] == "resolved")
        logger.info("Phase 7 complete: %d/%d fixes resolved", resolved, len(fix_results))

        return result

    except Exception as e:
        logger.error("Phase 7 failed: %s", e)
        return {"status": "error", "error": str(e), "fixes": []}


# ============================================================
# Main Entry Point
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="MACRS: Multi-Agent Adversarial Code Review System (7-Phase)"
    )
    parser.add_argument(
        "target",
        help="File or directory to review",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=None,
        help="Output directory for results",
    )
    parser.add_argument(
        "--change-type", "-t",
        default=None,
        choices=["bugfix", "feature", "refactor", "security", "hotfix", "patch",
                 "enhancement", "auth", "crypto", "ui", "ux", "api", "cli",
                 "docs", "config", "migration", "unknown"],
        help="Override automatic change type detection",
    )
    parser.add_argument(
        "--lens",
        default=None,
        help="Comma-separated lens IDs to use (e.g., L1,L2,L6). Overrides auto-detection.",
    )
    parser.add_argument(
        "--autofix",
        action="store_true",
        default=False,
        help="Enable Phase 7: Auto-Fix for confirmed findings",
    )
    parser.add_argument(
        "--team-config",
        default=None,
        help="Path to team config YAML for multi-model reviews",
    )
    parser.add_argument(
        "--skip-discourse",
        action="store_true",
        default=False,
        help="Skip Phase 5: Discourse",
    )
    parser.add_argument(
        "--cheap-threshold",
        type=int,
        default=VALIDATION_GATE.get("cheap_threshold", 45),
        help=f"Cheap scoring gate threshold (default: {VALIDATION_GATE.get('cheap_threshold', 45)})",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Setup output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        output_dir = REPORTS_DIR / f"review-{timestamp}"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Print banner
    print("=" * 70)
    print("  MACRS - Multi-Agent Adversarial Code Review System")
    print("  7-Phase Architecture")
    print("=" * 70)
    print(f"  Target:      {args.target}")
    print(f"  Output:      {output_dir}")
    print(f"  Auto-Fix:    {'ON' if args.autofix else 'OFF'}")
    print(f"  Discourse:   {'OFF' if args.skip_discourse else 'ON'}")
    print("=" * 70)

    start_time = time.time()

    # ── Phase 1: Context Discovery ──────────────────────────────────────
    context = phase1_context_discovery(args)

    # ── Initialize components ───────────────────────────────────────────

    # Load project rules for L3 lens
    project_rules = context.get("project_context", "")

    # Initialize LensManager
    lens_manager = LensManager(project_rules=project_rules)

    # Override lenses if specified
    if args.lens:
        custom_ids = [lid.strip().upper() for lid in args.lens.split(",")]
        context["_custom_lens_ids"] = custom_ids

    # Initialize ValidationGate
    validation_gate = ValidationGate(
        cheap_threshold=args.cheap_threshold,
        deep_threshold=VALIDATION_GATE.get("deep_threshold", 60),
        chunk_size=VALIDATION_GATE.get("chunk_size", 25),
        source_dir=Path(context["target_path"]),
        output_dir=output_dir,
    )

    # Initialize DiscoursePhase
    discourse_phase = DiscoursePhase(
        timeout=600,
    )

    # Initialize AutoFixPhase (if enabled)
    autofix_phase = None
    artifact_manager = None
    if args.autofix:
        from agent_runner import _run_single_agent
        class _AgentRunnerAdapter:
            """Adapter: wraps _run_single_agent(agent_id, prompt, output_dir)
            to match AutoFixPhase's expected agent_runner.run(prompt, source_dir) interface."""
            def __init__(self, fn):
                self._fn = fn
            def run(self, prompt: str, source_dir: str):
                result = self._fn("autofix", prompt, Path(source_dir))
                return result
        autofix_phase = AutoFixPhase(
            agent_runner=_AgentRunnerAdapter(_run_single_agent),
            source_dir=context["target_path"],
        )
        artifact_manager = ArtifactManager(
            artifact_path=str(output_dir / "artifacts" / "findings.json")
        )

    # ── Phase 2: Parallel Reviews (7 Lens) ──────────────────────────────
    all_findings = phase2_parallel_reviews(context, lens_manager, output_dir)

    # ── Phase 3: Cheap Scoring ──────────────────────────────────────────
    scored = phase3_cheap_scoring(all_findings, validation_gate, output_dir)

    # ── Phase 4: Deep Validation ────────────────────────────────────────
    validated = phase4_deep_validation(scored, validation_gate, output_dir)

    # ── Phase 5: Discourse ──────────────────────────────────────────────
    if args.skip_discourse:
        logger.info("Phase 5: Discourse (SKIPPED)")
        discourse_result = DiscourseResult()
    else:
        discourse_result = phase5_discourse(all_findings, discourse_phase, output_dir)

    # ── Phase 6: Synthesis ──────────────────────────────────────────────
    report = phase6_synthesis(all_findings, discourse_result, context, validated, output_dir)

    # ── Phase 7: Auto-Fix (optional) ────────────────────────────────────
    fix_result = None
    if args.autofix and autofix_phase:
        fix_result = phase7_autofix(report, autofix_phase, artifact_manager, output_dir)

    # ── Final Summary ───────────────────────────────────────────────────
    total_time = time.time() - start_time

    # Save overall summary
    summary = {
        "status": "COMPLETED",
        "target": context["target_path"],
        "change_type": context["change_type"],
        "total_elapsed_seconds": round(total_time, 1),
        "phases": {
            "phase1_context": {
                "files": len(context["files"]),
                "lines": context["total_lines"],
                "change_type": context["change_type"],
                "is_trivial": context["is_trivial"],
            },
            "phase2_reviews": {
                "total_findings": len(all_findings),
                "lenses_used": list(set(f.get("_lens_source") for f in all_findings)),
            },
            "phase3_scoring": {
                "scored_count": len(scored),
                "auto_graduated": sum(1 for s in scored if s.auto_graduated) if scored else 0,
            },
            "phase4_validation": {
                "validated_count": len(validated),
            },
            "phase5_discourse": {
                "responses": len(discourse_result.responses) if discourse_result else 0,
                "new_findings": len(discourse_result.new_findings) if discourse_result else 0,
            },
            "phase6_synthesis": {
                "total_findings": report["summary"]["total_findings"],
                "confirmed": report["summary"]["confirmed_findings"],
            },
            "phase7_autofix": fix_result if fix_result else {"status": "disabled"},
        },
    }

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # Print final summary
    print("\n" + "=" * 70)
    print("  REVIEW COMPLETE")
    print("=" * 70)
    print(f"  Total time:   {total_time:.1f}s")
    print(f"  Total findings: {report['summary']['total_findings']}")
    print(f"  Confirmed:    {report['summary']['confirmed_findings']}")
    print(f"  Output:       {output_dir}")
    print("=" * 70)

    # Print severity breakdown
    for sev in ["P0", "P1", "P2", "P3"]:
        count = report["summary"]["by_severity"].get(sev, 0)
        if count > 0:
            print(f"  {sev}: {count} findings")

    if fix_result and fix_result.get("fixes"):
        resolved = sum(1 for f in fix_result["fixes"] if f["state"] == "resolved")
        print(f"\n  Auto-Fix: {resolved}/{len(fix_result['fixes'])} fixes applied")

    print()

    # Exit code
    p0_count = report["summary"]["by_severity"].get("P0", 0)
    if p0_count > 0:
        print(f"BLOCKING: {p0_count} P0 findings require immediate attention.")
        sys.exit(2)
    elif report["summary"]["total_findings"] == 0:
        print("No issues found. Code looks clean!")
        sys.exit(0)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
