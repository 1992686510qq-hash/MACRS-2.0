"""MACRS Coordinator - Result Collector.

Validates agent outputs and collects results into a summary.
"""

import json
from pathlib import Path

from config import REQUIRED_FINDING_FIELDS, REQUIRED_REPORT_FIELDS


def validate_agent_output(data: dict) -> list[str]:
    """Validate an agent's JSON output against the expected schema.
    Returns a list of validation errors (empty = valid).
    """
    errors = []

    # Check top-level fields
    for field in REQUIRED_REPORT_FIELDS:
        if field not in data:
            errors.append(f"Missing top-level field: {field}")

    # Check findings array
    findings = data.get("findings", [])
    if not isinstance(findings, list):
        errors.append("'findings' must be an array")
        return errors

    for i, finding in enumerate(findings):
        for field in REQUIRED_FINDING_FIELDS:
            if field not in finding:
                errors.append(f"Finding[{i}] missing field: {field}")

        # Validate confidence range (0-100 scale, consistent with system)
        conf = finding.get("confidence")
        if conf is not None and (conf < 0 or conf > 100):
            errors.append(f"Finding[{i}] confidence out of range [0,100]: {conf}")

        # Validate line_range format
        lr = finding.get("line_range")
        if lr is not None:
            if not isinstance(lr, list) or len(lr) != 2:
                errors.append(f"Finding[{i}] line_range must be [start, end]")

    # Check metrics
    metrics = data.get("metrics", {})
    if "total_findings" in metrics and metrics["total_findings"] != len(findings):
        errors.append(
            f"metrics.total_findings ({metrics['total_findings']}) "
            f"!= actual findings count ({len(findings)})"
        )

    return errors


def collect_results(
    agent_results: dict[str, dict], output_dir: Path
) -> dict:
    """Collect and summarize all agent results.

    Returns a summary dict with:
      - status: "OK" | "PARTIAL" | "FAILED"
      - agents: per-agent status and finding counts
      - total_findings: across all agents
      - output_files: paths to saved JSON files
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "status": "OK",
        "agents": {},
        "total_findings": 0,
        "total_praise": 0,
        "output_files": [],
    }

    ok_count = 0

    for agent_id in ("A", "B", "C"):
        result = agent_results.get(agent_id, {"status": "MISSING"})

        agent_summary = {
            "name": f"Agent {agent_id}",
            "status": result.get("status", "MISSING"),
            "elapsed_seconds": result.get("elapsed_seconds"),
            "findings_count": 0,
            "validation_errors": [],
        }

        if result.get("status") == "OK":
            ok_count += 1
            data = result["data"]

            # Validate
            errors = validate_agent_output(data)
            agent_summary["validation_errors"] = errors

            if errors:
                print(f"[ResultCollector] Agent {agent_id} validation warnings:")
                for err in errors:
                    print(f"  - {err}")

            # Count findings
            findings = data.get("findings", [])
            agent_summary["findings_count"] = len(findings)
            summary["total_findings"] += len(findings)

            # Count praise
            praise = data.get("praise", [])
            agent_summary["praise_count"] = len(praise)
            summary["total_praise"] += len(praise)

            # Track output file
            output_file = result.get("output_file")
            if output_file:
                summary["output_files"].append(output_file)

        else:
            agent_summary["error"] = result.get("error", "Unknown error")

        summary["agents"][agent_id] = agent_summary

    # Determine overall status
    if ok_count == 3:
        summary["status"] = "OK"
    elif ok_count >= 1:
        summary["status"] = "PARTIAL"
    else:
        summary["status"] = "FAILED"

    # Save summary
    summary_file = output_dir / "phase-1-summary.json"
    summary_file.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary["summary_file"] = str(summary_file)

    return summary


def print_summary(summary: dict) -> None:
    """Print a human-readable summary to console."""
    status = summary["status"]
    print("\n" + "=" * 60)
    print(f"  MACRS Phase 1 Results: {status}")
    print("=" * 60)

    for agent_id in ("A", "B", "C"):
        agent = summary["agents"].get(agent_id, {})
        name = agent.get("name", f"Agent {agent_id}")
        agent_status = agent.get("status", "MISSING")
        count = agent.get("findings_count", 0)
        elapsed = agent.get("elapsed_seconds")

        icon = "OK" if agent_status == "OK" else "FAIL"
        time_str = f" ({elapsed}s)" if elapsed else ""
        print(f"  [{icon}] {name}: {count} findings{time_str}")

        if agent.get("error"):
            print(f"       Error: {agent['error']}")
        if agent.get("validation_errors"):
            for err in agent["validation_errors"][:3]:
                print(f"       Warning: {err}")

    print("-" * 60)
    print(f"  Total findings: {summary['total_findings']}")
    print(f"  Total praise:   {summary['total_praise']}")
    print(f"  Output files:   {len(summary.get('output_files', []))}")
    if summary.get("summary_file"):
        print(f"  Summary:        {summary['summary_file']}")
    print("=" * 60)
