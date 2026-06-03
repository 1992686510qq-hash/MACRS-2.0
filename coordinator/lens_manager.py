"""MACRS Coordinator - Lens Manager.

Manages 7 specialized review lenses inspired by adamsreview's multi-lens
architecture. Each lens focuses on a specific aspect of code review,
with targeted prompts and conditional execution logic.

Lens Overview:
  L1: Diff-local (sonnet)     - Off-by-one, inverted conditions, typos
  L2: Structure/Blast (opus)   - Cross-file tracing, invariant checks
  L3: CLAUDE.md Compliance     - Rule violation checks against project rules
  L4: Comment Compliance        - Comment vs code contradiction detection
  L5: UX                        - User experience and error message review
  L6: Security                  - Lightweight security scan
  L7: Holistic Review (opus)    - Catches what other lenses missed
"""

from dataclasses import dataclass, field
from typing import Optional

from prompts.lens_templates import (
    LENS_L1_PROMPT,
    LENS_L2_PROMPT,
    LENS_L3_PROMPT,
    LENS_L4_PROMPT,
    LENS_L5_PROMPT,
    LENS_L6_PROMPT,
    LENS_L7_PROMPT,
)


# ============================================================
# Data Structures
# ============================================================

@dataclass
class LensDefinition:
    """Definition of a single review lens."""

    id: str                              # L1-L7
    name: str                            # Human-readable name
    model: str                           # sonnet or opus
    description: str                     # What this lens checks
    prompt_template: str                 # Full prompt template (with {placeholders})
    run_condition: str                   # always | non_trivial | user_facing | ensemble
    focus_areas: list[str] = field(default_factory=list)   # Keywords for routing
    severity_bias: str = "normal"        # normal | strict | lenient
    max_findings: int = 20               # Cap on findings per lens
    timeout_seconds: int = 300           # Per-lens timeout


@dataclass
class LensResult:
    """Result from running a single lens."""

    lens_id: str
    status: str                          # OK | FAILED | TIMEOUT | SKIPPED
    findings: list[dict] = field(default_factory=list)
    raw_output: str = ""
    elapsed_seconds: float = 0.0
    error: Optional[str] = None


# ============================================================
# Change Type Classification
# ============================================================

# Maps change_type keywords to lens applicability
_CHANGE_TYPE_LENS_MAP: dict[str, list[str]] = {
    # Structural / architectural changes
    "refactor":       ["L1", "L2", "L3", "L7"],
    "architecture":   ["L2", "L3", "L7"],
    "interface":      ["L2", "L3", "L5", "L7"],

    # Bug fixes and patches
    "bugfix":         ["L1", "L2", "L6", "L7"],
    "hotfix":         ["L1", "L6", "L7"],
    "patch":          ["L1", "L7"],

    # Feature work
    "feature":        ["L1", "L2", "L3", "L4", "L5", "L6", "L7"],
    "enhancement":    ["L1", "L4", "L5", "L7"],

    # Security-sensitive
    "security":       ["L1", "L2", "L6", "L7"],
    "auth":           ["L1", "L2", "L5", "L6", "L7"],
    "crypto":         ["L1", "L6", "L7"],

    # User-facing
    "ui":             ["L1", "L4", "L5", "L7"],
    "ux":             ["L1", "L4", "L5", "L7"],
    "api":            ["L1", "L2", "L4", "L5", "L6", "L7"],
    "cli":            ["L1", "L4", "L5", "L7"],

    # Documentation / config
    "docs":           ["L3", "L4", "L7"],
    "config":         ["L1", "L3", "L6", "L7"],
    "migration":      ["L1", "L2", "L6", "L7"],

    # Default / unknown
    "unknown":        ["L1", "L6", "L7"],
}


# Prompt templates are now imported from prompts.lens_templates


# ============================================================
# Lens Manager
# ============================================================

class LensManager:
    """Manages the 7 specialized review lenses."""

    def __init__(self, project_rules: str = ""):
        """Initialize the lens manager.

        Args:
            project_rules: Content of CLAUDE.md or project-specific rules.
                          Used by L3 (CLAUDE.md Compliance) lens.
        """
        self.project_rules = project_rules
        self.lenses = self._init_lenses()

    def _init_lenses(self) -> list[LensDefinition]:
        """Initialize the 7 lens definitions."""
        return [
            LensDefinition(
                id="L1",
                name="Diff-local",
                model="sonnet",
                description="Off-by-one errors, inverted conditions, typos, and local logic bugs",
                prompt_template=LENS_L1_PROMPT,
                run_condition="always",
                focus_areas=["boundary", "condition", "typo", "logic", "off-by-one"],
                severity_bias="normal",
                max_findings=20,
                timeout_seconds=300,
            ),
            LensDefinition(
                id="L2",
                name="Structure & Blast Radius",
                model="opus",
                description="Cross-file tracing, invariant checks, dependency analysis, API contracts",
                prompt_template=LENS_L2_PROMPT,
                run_condition="non_trivial",
                focus_areas=["cross-file", "invariant", "dependency", "api", "architecture"],
                severity_bias="strict",
                max_findings=15,
                timeout_seconds=600,
            ),
            LensDefinition(
                id="L3",
                name="CLAUDE.md Compliance",
                model="sonnet",
                description="Checks code against project CLAUDE.md rules and conventions",
                prompt_template=LENS_L3_PROMPT,
                run_condition="always",
                focus_areas=["rules", "convention", "compliance", "naming", "structure"],
                severity_bias="normal",
                max_findings=15,
                timeout_seconds=300,
            ),
            LensDefinition(
                id="L4",
                name="Comment Compliance",
                model="sonnet",
                description="Detects contradictions between comments and actual code behavior",
                prompt_template=LENS_L4_PROMPT,
                run_condition="always",
                focus_areas=["comment", "docstring", "documentation", "todo", "fixme"],
                severity_bias="lenient",
                max_findings=15,
                timeout_seconds=300,
            ),
            LensDefinition(
                id="L5",
                name="User Experience",
                model="sonnet",
                description="Reviews error messages, input validation, API design, and CLI usability",
                prompt_template=LENS_L5_PROMPT,
                run_condition="user_facing",
                focus_areas=["error-message", "validation", "api", "cli", "ux"],
                severity_bias="normal",
                max_findings=15,
                timeout_seconds=300,
            ),
            LensDefinition(
                id="L6",
                name="Security",
                model="sonnet",
                description="Lightweight security scan for common vulnerabilities",
                prompt_template=LENS_L6_PROMPT,
                run_condition="always",
                focus_areas=["injection", "auth", "crypto", "xss", "vulnerability"],
                severity_bias="strict",
                max_findings=20,
                timeout_seconds=300,
            ),
            LensDefinition(
                id="L7",
                name="Holistic Review",
                model="opus",
                description="Catches what other lenses missed; cross-cutting and systemic issues",
                prompt_template=LENS_L7_PROMPT,
                run_condition="ensemble",
                focus_areas=["cross-cutting", "systemic", "architecture", "smell"],
                severity_bias="normal",
                max_findings=10,
                timeout_seconds=600,
            ),
        ]

    def get_lens_by_id(self, lens_id: str) -> LensDefinition | None:
        """Get a lens definition by its ID (e.g., 'L1')."""
        for lens in self.lenses:
            if lens.id == lens_id:
                return lens
        return None

    def get_applicable_lenses(
        self,
        change_type: str = "unknown",
        is_trivial: bool = False,
        is_user_facing: bool = True,
        custom_lens_ids: list[str] | None = None,
    ) -> list[LensDefinition]:
        """Determine which lenses should run based on the change context.

        Args:
            change_type: Type of change (e.g., 'bugfix', 'feature', 'security').
            is_trivial: If True, skip non_trivial-only lenses (L2).
            is_user_facing: If False, skip user_facing-only lenses (L5).
            custom_lens_ids: Explicit list of lens IDs to use (overrides auto-detection).

        Returns:
            List of applicable LensDefinition objects.
        """
        # If explicit lens IDs provided, use them
        if custom_lens_ids:
            result = []
            for lid in custom_lens_ids:
                lens = self.get_lens_by_id(lid.upper())
                if lens:
                    result.append(lens)
            return result

        # Auto-detect based on change type
        change_key = change_type.lower().strip()
        lens_ids = _CHANGE_TYPE_LENS_MAP.get(change_key, _CHANGE_TYPE_LENS_MAP["unknown"])

        # Filter by run_condition
        applicable = []
        for lens in self.lenses:
            if lens.id not in lens_ids:
                continue

            # Check run conditions
            if lens.run_condition == "non_trivial" and is_trivial:
                continue
            if lens.run_condition == "user_facing" and not is_user_facing:
                continue
            # "always" and "ensemble" always pass

            applicable.append(lens)

        # L7 (ensemble) always runs if any other lens ran, unless trivial
        l7 = self.get_lens_by_id("L7")
        if l7 and l7 not in applicable and applicable and not is_trivial:
            applicable.append(l7)

        return applicable

    def build_lens_prompt(
        self,
        lens: LensDefinition,
        code_files: dict[str, str],
        project_context: str = "",
        other_lens_findings: list[dict] | None = None,
    ) -> str:
        """Build the complete prompt for a specific lens.

        Args:
            lens: The lens definition to build a prompt for.
            code_files: Dict of {relative_path: content} for the target files.
            project_context: Additional project context (README, architecture docs, etc.).
            other_lens_findings: Findings from other lenses (used by L7 ensemble lens).

        Returns:
            Complete prompt string ready for agent execution.
        """
        # Build the review scope section
        review_scope = self._build_review_scope(code_files)

        # Format other lens findings for L7
        other_findings_text = ""
        if lens.id == "L7" and other_lens_findings:
            other_findings_text = self._format_other_findings(other_lens_findings)

        # Build project context section
        context_section = project_context if project_context else "(No additional project context provided)"

        # Fill in the prompt template
        prompt = lens.prompt_template.format(
            review_scope=review_scope,
            project_context=context_section,
            project_rules=self.project_rules if self.project_rules else "(No CLAUDE.md rules loaded)",
            other_lens_findings=other_findings_text if other_findings_text else "(No other lens findings yet)",
            max_findings=lens.max_findings,
        )

        return prompt

    def _build_review_scope(self, code_files: dict[str, str]) -> str:
        """Build the review scope section from target files.

        Args:
            code_files: Dict of {relative_path: content}.

        Returns:
            Formatted review scope string with file listing and code blocks.
        """
        if not code_files:
            return "(No code files provided for review)"

        total_lines = 0
        file_list = []
        code_blocks = []

        for filepath, content in code_files.items():
            lines = content.split("\n")
            total_lines += len(lines)
            file_list.append(filepath)
            code_blocks.append(f"### File: {filepath}\n```\n{content}\n```")

        header = f"审查文件列表 ({len(file_list)} 个文件, {total_lines} 行):\n"
        header += "\n".join(f"  - {f}" for f in file_list)
        header += "\n\n---\n\n"
        header += "\n\n".join(code_blocks)

        return header

    def _format_other_findings(self, findings: list[dict]) -> str:
        """Format findings from other lenses for L7's reference.

        Args:
            findings: List of finding dicts from other lenses.

        Returns:
            Formatted string summarizing other lens findings.
        """
        if not findings:
            return "(No findings from other lenses)"

        lines = ["以下是从其他 lens 已经发现的问题，请避免重复报告：\n"]

        for f in findings[:30]:  # Cap at 30 to avoid overwhelming L7
            fid = f.get("id", "N/A")
            title = f.get("title", "N/A")
            severity = f.get("severity", "N/A")
            file_path = f.get("file", "N/A")
            line = f.get("line", "N/A")
            lines.append(f"- [{fid}] ({severity}) {title} @ {file_path}:{line}")

        if len(findings) > 30:
            lines.append(f"\n... 以及其他 {len(findings) - 30} 个发现")

        return "\n".join(lines)

    def get_lenses_by_model(self, model: str) -> list[LensDefinition]:
        """Get all lenses that use a specific model.

        Args:
            model: 'sonnet' or 'opus'.

        Returns:
            List of lenses using the specified model.
        """
        return [l for l in self.lenses if l.model == model]

    def get_lens_summary(self) -> list[dict]:
        """Get a summary of all lens definitions.

        Returns:
            List of dicts with lens metadata (without prompt templates).
        """
        return [
            {
                "id": lens.id,
                "name": lens.name,
                "model": lens.model,
                "description": lens.description,
                "run_condition": lens.run_condition,
                "focus_areas": lens.focus_areas,
                "severity_bias": lens.severity_bias,
                "max_findings": lens.max_findings,
                "timeout_seconds": lens.timeout_seconds,
            }
            for lens in self.lenses
        ]

    def estimate_total_timeout(self, applicable_lenses: list[LensDefinition]) -> int:
        """Estimate total timeout for running a set of lenses.

        Args:
            applicable_lenses: List of lenses to run.

        Returns:
            Estimated total timeout in seconds (sum of individual timeouts).
        """
        return sum(lens.timeout_seconds for lens in applicable_lenses)

    def estimate_cost_hint(self, applicable_lenses: list[LensDefinition]) -> dict:
        """Estimate relative cost of running a set of lenses.

        Opus models are ~5x more expensive than Sonnet.

        Args:
            applicable_lenses: List of lenses to run.

        Returns:
            Dict with cost estimation metadata.
        """
        sonnet_count = sum(1 for l in applicable_lenses if l.model == "sonnet")
        opus_count = sum(1 for l in applicable_lenses if l.model == "opus")

        # Relative cost units (sonnet=1, opus=5)
        total_cost_units = sonnet_count * 1 + opus_count * 5

        return {
            "sonnet_lenses": sonnet_count,
            "opus_lenses": opus_count,
            "total_lenses": len(applicable_lenses),
            "relative_cost_units": total_cost_units,
            "estimated_tokens_hint": total_cost_units * 2000,  # rough estimate
        }
