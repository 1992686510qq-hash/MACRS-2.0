"""MACRS Coordinator - Prompt Builder.

Reads target code files and constructs complete prompts for Agent A/B/C.
"""

import json
from pathlib import Path
from config import AGENTS, SKILL_PATHS


def read_target_files(target_path: str) -> dict[str, str]:
    """Read all target files and return {relative_path: content}."""
    target = Path(target_path)
    files = {}

    if target.is_file():
        files[str(target)] = target.read_text(encoding="utf-8", errors="replace")
    elif target.is_dir():
        # Code file extensions to include
        code_exts = {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
            ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
            ".kt", ".scala", ".sh", ".bash", ".sql", ".html", ".css",
            ".scss", ".less", ".vue", ".svelte",
        }
        for f in sorted(target.rglob("*")):
            if f.is_file() and f.suffix.lower() in code_exts:
                # Skip vendor/node_modules/generated
                parts = f.parts
                if any(p in parts for p in ("node_modules", "vendor", ".git", "__pycache__", "dist", "build")):
                    continue
                rel = f.relative_to(target)
                try:
                    files[str(rel)] = f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass  # skip unreadable files
    return files


def load_skill_rules(agent_id: str) -> str:
    """Load skill-specific rules for the given agent."""
    skill_path = SKILL_PATHS[agent_id]

    if agent_id == "A":
        # code-review-skill: read SKILL.md
        skill_file = skill_path / "SKILL.md"
        if skill_file.exists():
            return skill_file.read_text(encoding="utf-8", errors="replace")[:3000]
        return "(code-review-skill SKILL.md not found)"

    elif agent_id == "B":
        # Claude-BugHunter: read top-level USAGE.md + a few key skill files
        parts = []
        usage = skill_path / "USAGE.md"
        if usage.exists():
            parts.append(usage.read_text(encoding="utf-8", errors="replace")[:4000])
        # Read a sample of skill files for vulnerability patterns
        skills_dir = skill_path / "skills"
        if skills_dir.exists():
            for skill_file in sorted(skills_dir.iterdir())[:5]:
                sm = skill_file / "SKILL.md"
                if sm.exists():
                    content = sm.read_text(encoding="utf-8", errors="replace")[:1500]
                    parts.append(f"### {skill_file.name}\n{content}")
        return "\n\n".join(parts)[:3000] if parts else "(BugHunter skills not found)"

    elif agent_id == "C":
        # pragmatic-clean-code-reviewer: read SKILL.md
        skill_file = skill_path / "SKILL.md"
        if skill_file.exists():
            return skill_file.read_text(encoding="utf-8", errors="replace")[:3000]
        return "(pragmatic-clean-code-reviewer SKILL.md not found)"

    return ""


def build_review_scope(files: dict[str, str]) -> str:
    """Build the review scope section from target files."""
    total_lines = 0
    file_list = []
    code_blocks = []

    for filepath, content in files.items():
        lines = content.split("\n")
        total_lines += len(lines)
        file_list.append(filepath)
        code_blocks.append(f"### File: {filepath}\n```\n{content}\n```")

    scope_header = f"审查文件列表 ({len(file_list)} 个文件, {total_lines} 行):\n"
    scope_header += "\n".join(f"  - {f}" for f in file_list)
    scope_header += "\n\n---\n\n"
    scope_header += "\n\n".join(code_blocks)

    return scope_header


def build_agent_prompt(agent_id: str, target_path: str, files: dict[str, str]) -> str:
    """Build the complete prompt for a specific agent."""
    agent = AGENTS[agent_id]
    skill_rules = load_skill_rules(agent_id)
    review_scope = build_review_scope(files)

    prompt = f"""# 角色
你是一名资深代码审查专家，正在对一份代码进行系统性的代码审查。
你的审查哲学：{agent['philosophy']}

# 你的身份
你是 MACRS（多智能体对抗式代码审查系统）中的 **{agent['name']}**。
你的技能来源：{agent['skill']}

# 审查范围
目标路径：{target_path}

{review_scope}

# 审查规则
{skill_rules}

# 输出格式要求
你必须严格按照以下 JSON Schema 输出审查结果。**只输出 JSON，不要输出任何 JSON 以外的文本。**

```json
{{
  "agent_id": "{agent_id}",
  "skill": "{agent['skill']}",
  "philosophy": "{agent['philosophy'][:60]}...",
  "review_scope": {{
    "files": ["文件路径列表"],
    "lines_total": 0
  }},
  "findings": [
    {{
      "id": "{agent_id}-001",
      "file": "文件路径",
      "line": 42,
      "line_range": [42, 58],
      "severity": "blocking | important | nit | suggestion | learning | praise",
      "category": "security | bug | performance | correctness | maintainability",
      "title": "简短标题（<80字符）",
      "description": "详细描述问题",
      "suggestion": "具体的修复建议",
      "code_snippet_bad": "有问题的代码（可选）",
      "code_snippet_good": "建议的代码（可选）",
      "rule_reference": "引用的规则ID或名称",
      "confidence": 0.9
    }}
  ],
  "metrics": {{
    "total_findings": 0,
    "by_severity": {{}},
    "by_category": {{}},
    "review_duration_seconds": 0
  }},
  "praise": [
    {{
      "file": "文件路径",
      "line": 0,
      "comment": "值得称赞的代码实践"
    }}
  ]
}}
```

# 审查要求
1. 只报告你**高度确信**的问题。置信度 < 0.7 的发现不要输出。
2. 每个发现必须包含**具体的修复建议**，不能只说"这里有问题"。
3. 优先报告安全漏洞和功能正确性问题，其次才是风格问题。
4. 如果代码中有值得称赞的实践，请在 `praise` 数组中提及。
5. **严格遵守 JSON 格式**，不要输出任何 JSON 以外的文本。
6. Finding ID 格式为 `{agent_id}-{{3位序号}}`，从 001 开始连续编号。
7. severity 使用各技能原生等级体系。
8. category 必须是以下之一：security | bug | performance | correctness | maintainability。
"""

    return prompt


def build_all_prompts(target_path: str) -> dict[str, str]:
    """Build prompts for all 3 agents. Returns {agent_id: prompt}."""
    files = read_target_files(target_path)
    if not files:
        raise ValueError(f"No code files found at: {target_path}")

    print(f"[PromptBuilder] Read {len(files)} files from {target_path}")

    prompts = {}
    for agent_id in ("A", "B", "C"):
        prompts[agent_id] = build_agent_prompt(agent_id, target_path, files)

    return prompts
