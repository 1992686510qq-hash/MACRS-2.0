"""
MACRS Phase 2: Cross-Validation Script
Performs deduplication, conflict detection, and consensus scoring
on 3 Agent review outputs.
"""

import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations


# ============================================================
# 1. Text Similarity (standard library only, no external deps)
# ============================================================

def tokenize(text):
    """Simple tokenizer: split on non-alphanumeric, lowercase, filter short tokens."""
    if not text:
        return set()
    tokens = re.split(r'[^a-zA-Z0-9一-鿿]+', text.lower())
    return {t for t in tokens if len(t) >= 2}


def text_similarity(a, b):
    """Jaccard similarity on token sets. Returns float [0, 1]."""
    t1, t2 = tokenize(a), tokenize(b)
    if not t1 and not t2:
        return 1.0
    if not t1 or not t2:
        return 0.0
    return len(t1 & t2) / len(t1 | t2)


# ============================================================
# 2. Line Range Overlap
# ============================================================

def line_range_overlap(r1, r2):
    """
    Calculate overlap ratio of two line ranges.
    overlap = intersection / union (as span)
    Returns float [0, 1].
    """
    if not r1 or not r2 or len(r1) < 2 or len(r2) < 2:
        return 0.0
    start1, end1 = r1[0], r1[1]
    start2, end2 = r2[0], r2[1]
    intersection = max(0, min(end1, end2) - max(start1, start2) + 1)
    union = max(end1, end2) - min(start1, start2) + 1
    return intersection / union if union > 0 else 0.0


# ============================================================
# 3. Union-Find
# ============================================================

class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x, y):
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1

    def components(self):
        groups = defaultdict(list)
        for i in range(len(self.parent)):
            groups[self.find(i)].append(i)
        return list(groups.values())


# ============================================================
# 4. Severity Mapping & Comparison
# ============================================================

# Unified severity order: higher index = less severe
SEVERITY_ORDER = {
    "blocking": 0,
    "critical": 0,
    "important": 1,
    "high": 1,
    "medium": 2,
    "nit": 2,
    "suggestion": 3,
    "low": 3,
    "learning": 4,
    "info": 4,
    "praise": 4,
    # L-level from pragmatic reviewer
    "l5": 0,
    "l4": 1,
    "l3": 2,
    "l2": 3,
    "l1": 4,
}

UNIFIED_LABELS = ["P0 BLOCKING", "P1 CRITICAL", "P2 HIGH", "P3 MEDIUM", "P4 LOW"]


def severity_rank(severity_str):
    """Map any known severity string to a 0-4 unified rank."""
    if not severity_str:
        return 2  # default to MEDIUM
    key = severity_str.strip().lower()
    return SEVERITY_ORDER.get(key, 2)


def unified_label(severity_str):
    return UNIFIED_LABELS[severity_rank(severity_str)]


def resolve_canonical_severity(sources):
    """Take the most severe (lowest rank number) among sources."""
    best_rank = 999
    best_raw = None
    for s in sources:
        r = severity_rank(s.get("severity", ""))
        if r < best_rank:
            best_rank = r
            best_raw = s.get("severity", "")
    return best_raw or "medium"


def max_severity_label(sources):
    """Return unified label for the most severe finding in sources."""
    best = min(severity_rank(s.get("severity", "")) for s in sources)
    return UNIFIED_LABELS[best]


# ============================================================
# 5. Core Data Structures
# ============================================================

def load_review(path):
    """Load a review JSON. Returns None if file missing or empty."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data or not data.get("findings"):
            return None
        return data
    except (json.JSONDecodeError, IOError):
        return None


def normalize_finding(finding, agent_id):
    """Ensure every finding has a consistent agent_id tag."""
    finding = dict(finding)
    finding["_agent_id"] = agent_id
    return finding


# ============================================================
# 6. Deduplication
# ============================================================

OVERLAP_THRESHOLD = 0.5
TITLE_SIM_THRESHOLD = 0.75


def deduplicate(all_findings):
    """
    Deduplicate findings using dual-key matching:
      1. Same file + line_range overlap > 50%
      2. Same file + title similarity > 0.75
    Returns (merged_groups, dedup_log_entries).
    """
    n = len(all_findings)
    uf = UnionFind(n)
    dedup_log = []

    # Group by file for efficiency
    by_file = defaultdict(list)
    for i, f in enumerate(all_findings):
        by_file[f.get("file", "")].append(i)

    # Within each file bucket, check all pairs
    for file_path, indices in by_file.items():
        for i, j in combinations(indices, 2):
            fi, fj = all_findings[i], all_findings[j]

            overlap = line_range_overlap(
                fi.get("line_range", []), fj.get("line_range", [])
            )
            title_sim = text_similarity(
                fi.get("title", ""), fj.get("title", "")
            )

            matched = False
            match_type = "none"
            rationale = ""

            if overlap > OVERLAP_THRESHOLD:
                matched = True
                match_type = "line_range_overlap"
                rationale = f"line_range_overlap {overlap:.2f} > {OVERLAP_THRESHOLD} threshold"
            elif title_sim > TITLE_SIM_THRESHOLD:
                matched = True
                match_type = "semantic"
                rationale = f"title_similarity {title_sim:.2f} > {TITLE_SIM_THRESHOLD} threshold"
            else:
                # Borderline detection for log
                if overlap > 0.3 or title_sim > 0.5:
                    match_type = "borderline"
                    rationale = (
                        f"Both metrics below threshold "
                        f"(overlap={overlap:.2f}, title_sim={title_sim:.2f}). "
                        f"Keeping separate."
                    )

            log_entry = {
                "pair": [fi.get("id", f"?{i}"), fj.get("id", f"?{j}")],
                "file": file_path,
                "match_type": match_type,
                "overlap_ratio": round(overlap, 4),
                "title_similarity": round(title_sim, 4),
                "decision": "MERGE" if matched else "KEEP_SEPARATE",
                "rationale": rationale,
            }
            dedup_log.append(log_entry)

            if matched:
                uf.union(i, j)

    return uf.components(), dedup_log


# ============================================================
# 7. Conflict Detection
# ============================================================

def detect_severity_conflict(sources):
    """Detect if agents disagree on severity by >= 2 ranks."""
    ranks = [severity_rank(s.get("severity", "")) for s in sources]
    if max(ranks) - min(ranks) >= 2:
        return True, max(ranks) - min(ranks)
    return False, max(ranks) - min(ranks)


def detect_existence_conflict(all_findings, merged_groups, reviews_by_agent):
    """
    Detect existence conflicts: one agent found an issue in a code region,
    but another agent reviewed the same file and did NOT report it there.
    """
    conflicts = []

    # Build a map: agent_id -> set of files they reviewed
    agent_files = {}
    for agent_id, review in reviews_by_agent.items():
        if review and review.get("review_scope", {}).get("files"):
            agent_files[agent_id] = set(review["review_scope"]["files"])

    for group_indices in merged_groups:
        group_findings = [all_findings[i] for i in group_indices]
        reporting_agents = {f["_agent_id"] for f in group_findings}
        group_file = group_findings[0].get("file", "")

        # Check which agents reviewed this file but didn't report
        for agent_id, files in agent_files.items():
            if agent_id in reporting_agents:
                continue
            if group_file in files:
                # This agent reviewed the same file but didn't find this issue
                # Only flag if the finding severity is high enough
                max_rank = min(severity_rank(f.get("severity", "")) for f in group_findings)
                if max_rank <= 1:  # P0 or P1 only
                    conflicts.append({
                        "type": "existence",
                        "file": group_file,
                        "missing_agent": agent_id,
                        "reported_by": list(reporting_agents),
                        "finding_ids": [f.get("id", "") for f in group_findings],
                        "max_severity": UNIFIED_LABELS[max_rank],
                    })

    return conflicts


def detect_category_conflict(sources):
    """Detect if agents categorize the same finding differently."""
    categories = {s.get("category", "") for s in sources}
    categories.discard("")
    return len(categories) > 1, list(categories)


# ============================================================
# 8. Consensus Scoring
# ============================================================

def calculate_consensus(sources):
    """
    Calculate consensus score for a merged finding.
    - 1 agent: base only
    - 2 agents: +0.15
    - 3 agents: +0.25
    """
    n = len(sources)
    base_confidence = sum(s.get("confidence", 0.5) for s in sources) / max(n, 1)

    # Consensus factor per architecture doc section 3.3.3
    if n >= 3:
        consensus_boost = 0.25
    elif n >= 2:
        consensus_boost = 0.15
    else:
        consensus_boost = 0.0

    final = min(1.0, base_confidence + consensus_boost)
    return {
        "base_confidence": round(base_confidence, 4),
        "consensus_boost": consensus_boost,
        "final_confidence": round(final, 4),
        "agent_count": n,
    }


# ============================================================
# 9. MergedFinding Builder
# ============================================================

def pick_canonical_title(sources):
    """Pick the longest (most detailed) title."""
    return max(sources, key=lambda s: len(s.get("title", ""))).get("title", "")


def pick_canonical_description(sources):
    """Pick the longest description."""
    return max(sources, key=lambda s: len(s.get("description", ""))).get("description", "")


def merge_line_ranges(sources):
    """Return the union line range across all sources."""
    starts, ends = [], []
    for s in sources:
        lr = s.get("line_range", [])
        if lr and len(lr) >= 2:
            starts.append(lr[0])
            ends.append(lr[1])
    if starts:
        return [min(starts), max(ends)]
    return [0, 0]


def build_merged_finding(merged_id, sources):
    """Build a MergedFinding dict from a list of source findings."""
    consensus = calculate_consensus(sources)
    sev_conflict, sev_gap = detect_severity_conflict(sources)
    cat_conflict, cat_list = detect_category_conflict(sources)

    # Determine status
    if len(sources) >= 2:
        status = "conflict" if sev_conflict else "consensus"
    else:
        status = "single_source"

    source_records = []
    for s in sources:
        source_records.append({
            "agent": s["_agent_id"],
            "finding_id": s.get("id", ""),
            "severity": s.get("severity", ""),
            "unified_severity": unified_label(s.get("severity", "")),
            "title": s.get("title", ""),
            "description": s.get("description", ""),
            "confidence": s.get("confidence", 0.5),
            "category": s.get("category", ""),
            "rule_reference": s.get("rule_reference", ""),
        })

    merged = {
        "merged_id": merged_id,
        "canonical_title": pick_canonical_title(sources),
        "canonical_severity": max_severity_label(sources),
        "canonical_description": pick_canonical_description(sources),
        "category": cat_list[0] if len(cat_list) == 1 else (cat_list or ["unknown"]),
        "file": sources[0].get("file", ""),
        "line_range": merge_line_ranges(sources),
        "sources": source_records,
        "consensus": consensus,
        "status": status,
        "conflicts": {
            "severity_conflict": sev_conflict,
            "severity_gap": sev_gap,
            "category_conflict": cat_conflict,
            "categories": cat_list,
        },
    }

    # Include code snippets from the first source that has them
    for s in sources:
        if s.get("code_snippet_bad"):
            merged["code_snippet_bad"] = s["code_snippet_bad"]
            break
    for s in sources:
        if s.get("code_snippet_good"):
            merged["code_snippet_good"] = s["code_snippet_good"]
            break

    # Include suggestion from the first source that has one
    for s in sources:
        if s.get("suggestion"):
            merged["suggestion"] = s["suggestion"]
            break

    return merged


# ============================================================
# 10. Main Pipeline
# ============================================================

def run_phase2(review_dir, output_dir=None):
    """
    Main Phase 2 entry point.
    Reads review-a/b/c.json from review_dir, writes outputs to output_dir.
    """
    if output_dir is None:
        output_dir = os.path.join(review_dir, "phase2")
    os.makedirs(output_dir, exist_ok=True)

    # --- Load reviews ---
    paths = {
        "A": os.path.join(review_dir, "review-a.json"),
        "B": os.path.join(review_dir, "review-b.json"),
        "C": os.path.join(review_dir, "review-c.json"),
    }

    reviews = {}
    for agent_id, path in paths.items():
        review = load_review(path)
        if review:
            reviews[agent_id] = review
            print(f"[Phase2] Loaded review-{agent_id}.json: {len(review['findings'])} findings")
        else:
            print(f"[Phase2] review-{agent_id}.json: empty or missing, skipping")

    if not reviews:
        print("[Phase2] ERROR: No valid reviews found. Aborting.")
        return None

    # --- Collect all findings ---
    all_findings = []
    for agent_id, review in reviews.items():
        for f in review.get("findings", []):
            all_findings.append(normalize_finding(f, agent_id))

    total_before = len(all_findings)
    print(f"[Phase2] Total findings before dedup: {total_before}")

    # --- Deduplication ---
    merged_groups, dedup_log_entries = deduplicate(all_findings)

    # --- Build merged findings ---
    merged_findings = []
    conflicts_list = []
    merged_id_counter = 1

    for group_indices in merged_groups:
        group_sources = [all_findings[i] for i in group_indices]
        mf_id = f"M-{merged_id_counter:03d}"
        merged_id_counter += 1

        mf = build_merged_finding(mf_id, group_sources)
        merged_findings.append(mf)

        # Generate conflict entries for severity disagreements
        if mf["conflicts"]["severity_conflict"]:
            sev_gap = mf["conflicts"]["severity_gap"]
            needs_human = sev_gap >= 2
            conflict = {
                "conflict_id": f"CFL-{len(conflicts_list) + 1:03d}",
                "type": "severity",
                "merged_finding": mf_id,
                "file": mf["file"],
                "severity_gap": sev_gap,
                "needs_human": needs_human,
                "disagreement": {},
            }
            for src in mf["sources"]:
                conflict["disagreement"][src["agent"]] = {
                    "severity": src["severity"],
                    "unified_severity": src["unified_severity"],
                }
            conflicts_list.append(conflict)

        if mf["conflicts"]["category_conflict"]:
            conflicts_list.append({
                "conflict_id": f"CFL-{len(conflicts_list) + 1:03d}",
                "type": "category",
                "merged_finding": mf_id,
                "file": mf["file"],
                "categories": mf["conflicts"]["categories"],
                "needs_human": False,
            })

    # --- Existence conflicts ---
    existence_conflicts = detect_existence_conflict(
        all_findings, merged_groups, reviews
    )
    for ec in existence_conflicts:
        conflicts_list.append({
            "conflict_id": f"CFL-{len(conflicts_list) + 1:03d}",
            "type": "existence",
            "merged_finding": None,
            "file": ec["file"],
            "missing_agent": ec["missing_agent"],
            "reported_by": ec["reported_by"],
            "finding_ids": ec["finding_ids"],
            "max_severity": ec["max_severity"],
            "needs_human": severity_rank(ec["max_severity"]) <= 1,
        })

    # --- Dedup log ---
    total_after = len(merged_findings)
    merged_count = total_before - total_after
    borderline_count = sum(1 for e in dedup_log_entries if e["match_type"] == "borderline")

    dedup_log = {
        "decisions": dedup_log_entries,
        "statistics": {
            "total_findings_before_dedup": total_before,
            "total_merged_groups": len(merged_groups),
            "total_findings_after_dedup": total_after,
            "findings_merged_away": merged_count,
            "merge_rate": round(merged_count / max(total_before, 1), 4),
            "borderline_cases": borderline_count,
        },
    }

    # --- Phase 2 Summary ---
    # Severity distribution after merge
    sev_dist = defaultdict(int)
    cat_dist = defaultdict(int)
    agent_contrib = defaultdict(int)
    consensus_count = 0
    single_source_count = 0

    for mf in merged_findings:
        sev_dist[mf["canonical_severity"]] += 1
        cats = mf["category"]
        if isinstance(cats, list):
            for c in cats:
                cat_dist[c] += 1
        else:
            cat_dist[cats] += 1
        for src in mf["sources"]:
            agent_contrib[src["agent"]] += 1
        if mf["status"] == "consensus":
            consensus_count += 1
        elif mf["status"] == "single_source":
            single_source_count += 1

    severity_conflict_count = sum(1 for c in conflicts_list if c["type"] == "severity")
    existence_conflict_count = sum(1 for c in conflicts_list if c["type"] == "existence")
    category_conflict_count = sum(1 for c in conflicts_list if c["type"] == "category")
    needs_human_count = sum(1 for c in conflicts_list if c.get("needs_human"))

    summary = {
        "phase": 2,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_reviews": {aid: len(r["findings"]) for aid, r in reviews.items()},
        "agents_loaded": list(reviews.keys()),
        "total_findings_before_dedup": total_before,
        "total_findings_after_dedup": total_after,
        "merged_away": merged_count,
        "merge_rate": round(merged_count / max(total_before, 1), 4),
        "consensus_findings": consensus_count,
        "single_source_findings": single_source_count,
        "total_conflicts": len(conflicts_list),
        "conflicts_by_type": {
            "severity": severity_conflict_count,
            "existence": existence_conflict_count,
            "category": category_conflict_count,
        },
        "needs_human_resolution": needs_human_count,
        "severity_distribution": dict(sev_dist),
        "category_distribution": dict(cat_dist),
        "agent_contributions": dict(agent_contrib),
        "quality_metrics": {
            "consensus_rate": round(
                consensus_count / max(total_after, 1), 4
            ),
            "conflict_rate": round(
                len(conflicts_list) / max(total_after, 1), 4
            ),
            "dedup_merge_rate": round(
                merged_count / max(total_before, 1), 4
            ),
        },
    }

    # --- Sort merged findings by severity then confidence ---
    merged_findings.sort(
        key=lambda m: (
            severity_rank(m.get("canonical_severity", "")),
            -m.get("consensus", {}).get("final_confidence", 0),
        )
    )

    # --- Write outputs ---
    outputs = {
        "merged-findings.json": merged_findings,
        "conflicts.json": conflicts_list,
        "dedup-log.json": dedup_log,
        "phase2-summary.json": summary,
    }

    for filename, data in outputs.items():
        out_path = os.path.join(output_dir, filename)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[Phase2] Written: {out_path}")

    # --- Console summary ---
    print("\n" + "=" * 60)
    print("PHASE 2 CROSS-VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Agents loaded:       {', '.join(reviews.keys())}")
    print(f"Findings before:     {total_before}")
    print(f"Findings after:      {total_after}")
    print(f"Merged away:         {merged_count} ({summary['merge_rate']:.1%})")
    print(f"Consensus findings:  {consensus_count}")
    print(f"Single-source:       {single_source_count}")
    print(f"Conflicts total:     {len(conflicts_list)}")
    print(f"  - Severity:        {severity_conflict_count}")
    print(f"  - Existence:       {existence_conflict_count}")
    print(f"  - Category:        {category_conflict_count}")
    print(f"Needs human:         {needs_human_count}")
    print()
    print("Severity distribution (unified):")
    for label in UNIFIED_LABELS:
        count = sev_dist.get(label, 0)
        if count:
            print(f"  {label}: {count}")
    print()
    print("Agent contributions:")
    for agent_id in sorted(agent_contrib):
        print(f"  Agent {agent_id}: {agent_contrib[agent_id]} findings in merged results")
    print("=" * 60)

    return summary


# ============================================================
# CLI Entry Point
# ============================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        review_dir = "C:/Users/Administrator/Claude-Code/cc-tools/MACRS/reports/review-20260601-172405"
    else:
        review_dir = sys.argv[1]

    output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(review_dir, "phase2")

    result = run_phase2(review_dir, output_dir)
    if result:
        print(f"\nDone. Outputs in: {output_dir}")
    else:
        print("\nFailed: no valid reviews found.")
        sys.exit(1)
