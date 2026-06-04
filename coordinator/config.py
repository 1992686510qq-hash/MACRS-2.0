"""MACRS Coordinator - Configuration."""

from pathlib import Path

# === Paths ===
MACRS_ROOT = Path(__file__).parent.parent  # coordinator/ 的上一级
SKILLS_DIR = MACRS_ROOT / "skills"
REPORTS_DIR = MACRS_ROOT / "reports"
DOCS_DIR = MACRS_ROOT / "docs"

# Skill paths
SKILL_PATHS = {
    "A": SKILLS_DIR / "code-review-skill",
    "B": SKILLS_DIR / "Claude-BugHunter",
    "C": SKILLS_DIR / "pragmatic-clean-code-reviewer",
}

# Skill metadata
AGENTS = {
    "A": {
        "name": "Agent A - Quality Reviewer",
        "skill": "code-review-skill",
        "philosophy": (
            "你是'可维护性优先'的代码审查专家。你的核心理念来自 The Pragmatic Programmer "
            "和 Clean Code 传统：代码首先是写给人看的，其次才是给机器执行的。"
            "你关注：命名是否自解释？函数是否做且只做一件事？抽象层次是否一致？"
            "重复代码是否可以提取？注释是否解释了'为什么'而非'做了什么'？"
        ),
    },
    "B": {
        "name": "Agent B - Security Hunter",
        "skill": "Claude-BugHunter",
        "philosophy": (
            "你是'攻击者思维'的安全审计专家。你审查代码时的默认假设是："
            "有恶意攻击者会仔细阅读这段代码，寻找任何可能的突破口。"
            "你不是在找'不优雅'的代码——你是在找'可利用'的代码。"
            "你的核心理念来自 574+ 个真实 HackerOne 漏洞报告的模式提炼。"
        ),
    },
    "C": {
        "name": "Agent C - Architecture Reviewer",
        "skill": "pragmatic-clean-code-reviewer",
        "philosophy": (
            "你是'架构防腐'的代码审查专家。你不只关心单行代码的对错，更关心这段代码 "
            "在整个系统架构中的位置和长期影响。你的核心理念来自："
            "The Pragmatic Programmer、Clean Code、Clean Architecture。"
            "你审查时的核心问题是：'这段代码会加速还是延缓系统的技术债务累积？'"
        ),
    },
    "autofix": {
        "name": "AutoFix Agent",
        "skill": "autofix",
        "philosophy": (
            "你是代码自动修复专家。根据审查发现的问题，生成精确的 unified diff 格式修复补丁。"
            "你只修复已确认的机械性问题，不进行大规模重构。"
        ),
    },
}

# === Agent Model Config ===
AGENT_MODEL = "sonnet"
AGENT_MAX_TOKENS = 8192
AGENT_TEMPERATURE = 0.3
AGENT_TIMEOUT_SECONDS = 600  # 10 minutes per agent

# === Output JSON Schema (for validation) ===
REQUIRED_FINDING_FIELDS = [
    "id", "file", "line", "line_range", "severity",
    "category", "title", "description", "suggestion", "confidence",
]

REQUIRED_REPORT_FIELDS = [
    "agent_id", "skill", "philosophy", "review_scope", "findings", "metrics",
]

# === Lens Configuration ===
LENS_CONFIG = {
    "enabled": True,
    "trivial_threshold": 50,  # 变更行数小于此视为 trivial
    "user_facing_patterns": ["*.ui", "*.vue", "*.tsx", "*.jsx", "*.html", "*.css"],
}

# === Multi-Model Configuration ===
TEAM_CONFIG_PATH = MACRS_ROOT / "coordinator" / "team_config.yaml"

MODEL_ALIASES = {
    "workhorse": "claude-sonnet-4-6",
    "big-brain": "claude-opus-4-7",
    "fast": "claude-haiku-4-5",
}

DEFAULT_MODEL = "claude-sonnet-4-6"

# === Validation Gate Configuration ===
VALIDATION_GATE = {
    "cheap_threshold": 45,  # Cheap Scoring 门控分数
    "deep_threshold": 60,   # Deep Validation 门控分数
    "auto_graduate_min_families": 2,  # 自动毕业最小 source families 数
    "chunk_size": 25,  # Cheap Scoring 分块大小
}

# === Discourse Configuration ===
DISCOURSE = {
    "enabled": True,
    "max_rounds": 2,  # 最大辩论轮数
    "confidence_adjustment": {
        "agree": 1,
        "challenge_defended": 1,
        "challenge_not_defended": -1,
        "connect": 1,
    },
}

# === Auto-Fix Configuration ===
AUTOFIX = {
    "enabled": True,
    "min_score": 60,
    "allowed_dispositions": ["confirmed_mechanical", "confirmed_partial", "confirmed_regression"],
    "max_fix_attempts": 3,
    "rollback_on_regression": True,
}

# === 7-Phase Workflow ===
PHASES = [
    "context_discovery",   # Phase 1: 上下文发现
    "parallel_reviews",    # Phase 2: 并行审查（7 Lens）
    "cheap_scoring",       # Phase 3: 快速评分
    "deep_validation",     # Phase 4: 深度验证
    "discourse",           # Phase 5: 辩论
    "synthesis",           # Phase 6: 综合报告
    "autofix",             # Phase 7: 自动修复
]
