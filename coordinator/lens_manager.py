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


# ============================================================
# Prompt Templates
# ============================================================

_LENS_L1_PROMPT = """# L1: Diff-local Review - Off-by-One, Inverted Conditions, Typos

你是 MACRS 的 L1 Diff-local 审查 lens。你的唯一职责是审查代码变更中的**局部级错误**：
错位的边界、反转的条件、拼写错误、遗漏的分支。

## 审查重点

1. **Off-by-one 错误**
   - 循环边界：`<` vs `<=`，`>` vs `>=`
   - 数组/切片索引：是否越界或遗漏首尾元素
   - 区间表示：闭区间 vs 半开区间混用

2. **反转条件**
   - `if` / `elif` / `else` 逻辑是否正确
   - `not` / `!` 是否多余或遗漏
   - 短路求值顺序是否影响结果
   - De Morgan 定律应用是否正确

3. **拼写与命名**
   - 变量名、函数名拼写错误（尤其是相似命名的误用）
   - 字符串字面量中的拼写错误
   - 拷贝粘贴后未修改的名称

4. **遗漏的边界情况**
   - 空集合/None/零值处理
   - 异常路径是否被覆盖
   - `switch`/`match` 是否遗漏分支
   - 默认值是否合理

5. **简单的逻辑错误**
   - 赋值 vs 比较（`=` vs `==`）
   - 返回值是否正确
   - 死代码（unreachable code）
   - 变量遮蔽（shadowing）

## 审查范围

{review_scope}

## 项目上下文

{project_context}

## 输出格式要求

**只输出 JSON，不要输出任何 JSON 以外的文本。**

```json
{{
  "lens_id": "L1",
  "lens_name": "Diff-local",
  "findings": [
    {{
      "id": "L1-001",
      "file": "文件路径",
      "line": 42,
      "line_range": [42, 45],
      "severity": "blocking | important | nit | suggestion",
      "category": "bug",
      "title": "简短标题（<80字符）",
      "description": "详细描述问题",
      "suggestion": "具体的修复建议",
      "code_snippet_bad": "有问题的代码",
      "code_snippet_good": "建议的代码",
      "confidence": 0.9
    }}
  ],
  "metrics": {{
    "total_findings": 0,
    "by_severity": {{}},
    "scan_duration_estimate_seconds": 0
  }}
}}
```

## 约束
- 只报告置信度 >= 0.7 的发现
- 最多报告 {max_findings} 个发现
- 优先报告 blocking 和 important 级别
- 每个发现必须包含具体的修复建议
"""

_LENS_L2_PROMPT = """# L2: Structure & Blast Radius Review

你是 MACRS 的 L2 Structure/Blast Radius 审查 lens。你的职责是**跨文件追踪**和**不变量检查**，
评估代码变更的影响范围和结构性风险。

## 审查重点

1. **跨文件影响追踪**
   - 被修改的函数/类被哪些文件调用？调用方是否需要同步修改？
   - 接口变更是否所有消费者都已适配？
   - 数据流变更是否影响下游处理逻辑？

2. **不变量检查**
   - 类的不变量（class invariant）是否在所有方法中被维护？
   - 循环不变量是否正确？
   - 状态机转换是否完整？有无非法状态转换？
   - 并发场景下不变量是否仍然成立？

3. **依赖关系分析**
   - 新增的依赖是否引入循环依赖？
   - 依赖方向是否符合架构分层（依赖倒置原则）？
   - 模块间的耦合度是否在可接受范围内？

4. **API 契约**
   - 函数签名变更是否向后兼容？
   - 返回值结构是否变更？消费者是否适配？
   - 错误处理契约是否一致（异常 vs 错误码）？

5. **架构一致性**
   - 新代码是否遵循项目现有的架构模式？
   - 抽象层次是否一致？
   - 是否存在"霰弹式修改"（shotgun surgery）的信号？

## 审查范围

{review_scope}

## 项目上下文

{project_context}

## 输出格式要求

**只输出 JSON，不要输出任何 JSON 以外的文本。**

```json
{{
  "lens_id": "L2",
  "lens_name": "Structure & Blast Radius",
  "findings": [
    {{
      "id": "L2-001",
      "file": "主要文件路径",
      "line": 42,
      "line_range": [42, 58],
      "severity": "blocking | important | nit | suggestion",
      "category": "correctness | maintainability",
      "title": "简短标题（<80字符）",
      "description": "详细描述问题及影响范围",
      "suggestion": "具体的修复建议",
      "blast_radius": {{
        "affected_files": ["文件1", "文件2"],
        "affected_functions": ["func1", "func2"],
        "risk_level": "high | medium | low"
      }},
      "confidence": 0.9
    }}
  ],
  "metrics": {{
    "total_findings": 0,
    "by_severity": {{}},
    "blast_radius_summary": {{
      "max_affected_files": 0,
      "high_risk_areas": []
    }}
  }}
}}
```

## 约束
- 只报告置信度 >= 0.7 的发现
- 最多报告 {max_findings} 个发现
- 跨文件影响必须列出具体的受影响文件
- blast_radius 字段必须填写
"""

_LENS_L3_PROMPT = """# L3: CLAUDE.md Compliance Review

你是 MACRS 的 L3 CLAUDE.md Compliance 审查 lens。你的职责是检查代码是否违反了
项目 CLAUDE.md 中定义的规则和约定。

## 审查重点

1. **命名约定**
   - 变量、函数、类的命名是否符合项目约定？
   - 文件命名是否遵循项目模式？
   - 常量命名是否正确（UPPER_SNAKE_CASE 等）？

2. **代码组织规则**
   - 文件结构是否符合项目要求？
   - 模块划分是否遵循项目架构？
   - 导入顺序是否符合约定？

3. **技术栈约束**
   - 是否使用了项目禁止的库或模式？
   - 是否遵循项目指定的框架用法？
   - 依赖版本是否符合约束？

4. **流程规范**
   - 提交信息格式是否正确？
   - 测试覆盖率是否达标？
   - 文档更新是否同步？

5. **自定义规则**
   - 项目特有的业务规则是否被遵守？
   - 安全策略是否被正确实施？
   - 性能约束是否被满足？

## 项目规则（来自 CLAUDE.md）

{project_rules}

## 审查范围

{review_scope}

## 输出格式要求

**只输出 JSON，不要输出任何 JSON 以外的文本。**

```json
{{
  "lens_id": "L3",
  "lens_name": "CLAUDE.md Compliance",
  "findings": [
    {{
      "id": "L3-001",
      "file": "文件路径",
      "line": 42,
      "line_range": [42, 45],
      "severity": "blocking | important | nit | suggestion",
      "category": "maintainability",
      "title": "简短标题（<80字符）",
      "description": "详细描述违规内容",
      "suggestion": "具体的修复建议",
      "rule_reference": "引用的规则ID或名称",
      "confidence": 0.9
    }}
  ],
  "metrics": {{
    "total_findings": 0,
    "by_severity": {{}},
    "rules_checked": 0,
    "compliance_rate": 0.0
  }}
}}
```

## 约束
- 只报告置信度 >= 0.7 的发现
- 最多报告 {max_findings} 个发现
- 每个发现必须引用具体的规则条款
- 如果没有 CLAUDE.md 内容可用，跳过此 lens 并在输出中说明
"""

_LENS_L4_PROMPT = """# L4: Comment Compliance Review

你是 MACRS 的 L4 Comment Compliance 审查 lens。你的职责是检测**注释与代码之间的矛盾**。

## 审查重点

1. **过时注释**
   - 注释描述的行为与实际代码不一致
   - 注释引用的变量名/函数名已不存在
   - TODO/FIXME/HACK 注释是否仍然相关

2. **误导性注释**
   - 注释声称代码做了某事，但实际做了另一件事
   - 注释描述的参数/返回值与实际不符
   - 注释中的示例代码已过时

3. **缺失的关键注释**
   - 复杂算法缺少解释
   - 非直觉的业务逻辑缺少说明
   - 安全相关的决策缺少文档

4. **注释质量**
   - 注释是否解释了"为什么"而非仅仅"做了什么"
   - 是否存在无意义的噪音注释（如 `// increment i`）
   - 注释的语言是否与项目约定一致

5. **文档一致性**
   - 函数 docstring 与实际行为是否一致
   - 类型注解与实际类型是否匹配
   - API 文档与实现是否同步

## 审查范围

{review_scope}

## 项目上下文

{project_context}

## 输出格式要求

**只输出 JSON，不要输出任何 JSON 以外的文本。**

```json
{{
  "lens_id": "L4",
  "lens_name": "Comment Compliance",
  "findings": [
    {{
      "id": "L4-001",
      "file": "文件路径",
      "line": 42,
      "line_range": [42, 45],
      "severity": "important | nit | suggestion",
      "category": "maintainability",
      "title": "简短标题（<80字符）",
      "description": "详细描述注释与代码的矛盾",
      "suggestion": "具体的修复建议（更新注释或代码）",
      "comment_text": "有问题的注释原文",
      "actual_behavior": "代码的实际行为",
      "confidence": 0.9
    }}
  ],
  "metrics": {{
    "total_findings": 0,
    "by_severity": {{}},
    "comments_scanned": 0,
    "contradiction_rate": 0.0
  }}
}}
```

## 约束
- 只报告置信度 >= 0.7 的发现
- 最多报告 {max_findings} 个发现
- 必须同时提供注释原文和实际行为描述
- 对于缺失注释的情况，说明为什么需要注释
"""

_LENS_L5_PROMPT = """# L5: User Experience Review

你是 MACRS 的 L5 UX 审查 lens。你的职责是从**用户视角**审查代码的可用性、
错误消息质量和整体用户体验。

## 审查重点

1. **错误消息质量**
   - 错误消息是否对用户友好且可操作？
   - 是否暴露了内部实现细节（如堆栈跟踪、SQL 语句）？
   - 错误消息是否提供了修复建议？

2. **输入验证与反馈**
   - 用户输入验证是否充分？
   - 验证失败时的反馈是否清晰？
   - 必填字段缺失时是否有明确提示？
   - 边界值处理是否合理？

3. **API 设计**
   - API 端点命名是否直观？
   - 请求/响应格式是否一致？
   - 分页、过滤、排序参数是否合理？
   - 版本控制策略是否明确？

4. **CLI 体验**
   - 命令行帮助信息是否完整？
   - 进度指示是否清晰？
   - 输出格式是否易于解析？
   - 退出码是否有意义？

5. **国际化与可访问性**
   - 硬编码的字符串是否应该外部化？
   - 错误消息是否支持多语言？
   - 是否考虑了无障碍访问需求？

## 审查范围

{review_scope}

## 项目上下文

{project_context}

## 输出格式要求

**只输出 JSON，不要输出任何 JSON 以外的文本。**

```json
{{
  "lens_id": "L5",
  "lens_name": "User Experience",
  "findings": [
    {{
      "id": "L5-001",
      "file": "文件路径",
      "line": 42,
      "line_range": [42, 50],
      "severity": "blocking | important | nit | suggestion",
      "category": "maintainability",
      "title": "简短标题（<80字符）",
      "description": "详细描述用户体验问题",
      "suggestion": "具体的改进建议",
      "user_impact": "对用户的影响描述",
      "current_behavior": "当前行为",
      "expected_behavior": "期望行为",
      "confidence": 0.9
    }}
  ],
  "metrics": {{
    "total_findings": 0,
    "by_severity": {{}},
    "ux_score": 0.0
  }}
}}
```

## 约束
- 只报告置信度 >= 0.7 的发现
- 最多报告 {max_findings} 个发现
- 必须从用户视角描述问题
- 必须区分当前行为和期望行为
"""

_LENS_L6_PROMPT = """# L6: Security Review

你是 MACRS 的 L6 Security 审查 lens。你的职责是执行**轻量级安全扫描**，
识别常见的安全漏洞和不安全的编码实践。

## 审查重点

1. **注入漏洞**
   - SQL 注入：是否使用参数化查询？
   - 命令注入：是否安全地调用外部命令？
   - XSS：用户输入是否经过适当的转义/清理？
   - 路径遍历：文件路径是否经过验证？

2. **认证与授权**
   - 密码/密钥是否硬编码？
   - 认证逻辑是否有绕过风险？
   - 权限检查是否在正确的位置？
   - Session/Token 管理是否安全？

3. **数据保护**
   - 敏感数据（密码、密钥、token）是否在日志中泄露？
   - 数据传输是否使用加密？
   - 数据存储是否加密（静态数据）？
   - PII 数据处理是否合规？

4. **依赖安全**
   - 是否使用了已知有漏洞的依赖版本？
   - 依赖来源是否可信？
   - 是否有不必要的权限请求？

5. **常见漏洞模式**
   - 不安全的反序列化
   - 不安全的随机数生成
   - 竞态条件（TOCTOU）
   - 资源泄露（文件句柄、连接）
   - 拒绝服务风险（ReDoS、无限循环）

## 审查范围

{review_scope}

## 项目上下文

{project_context}

## 输出格式要求

**只输出 JSON，不要输出任何 JSON 以外的文本。**

```json
{{
  "lens_id": "L6",
  "lens_name": "Security",
  "findings": [
    {{
      "id": "L6-001",
      "file": "文件路径",
      "line": 42,
      "line_range": [42, 45],
      "severity": "blocking | important | nit | suggestion",
      "category": "security",
      "title": "简短标题（<80字符）",
      "description": "详细描述安全漏洞",
      "suggestion": "具体的修复建议",
      "vulnerability_type": "漏洞类型（如 SQL_INJECTION, XSS 等）",
      "attack_vector": "攻击向量描述",
      "cwe_id": "CWE 编号（如 CWE-89）",
      "confidence": 0.9
    }}
  ],
  "metrics": {{
    "total_findings": 0,
    "by_severity": {{}},
    "by_vulnerability_type": {{}},
    "security_score": 0.0
  }}
}}
```

## 约束
- 只报告置信度 >= 0.7 的发现
- 最多报告 {max_findings} 个发现
- 安全发现优先级最高，blocking 级别必须报告
- 尽可能提供 CWE 编号
- 不要报告纯风格问题，只关注安全
"""

_LENS_L7_PROMPT = """# L7: Holistic Review (Ensemble)

你是 MACRS 的 L7 Holistic Review lens。你是**最后一道防线**，专门捕获其他 lens 遗漏的问题。

你的审查哲学：其他 lens 各有专精，但可能因为过于聚焦而忽略全局视角。
你的任务是以**整体视角**审视代码，发现那些不属于任何单一类别但仍然重要的问题。

## 审查重点

1. **跨类别问题**
   - 一个问题同时涉及安全、性能、可维护性等多个方面
   - 局部优化导致全局退化
   - 看似无关的修改之间的隐含关联

2. **系统性风险**
   - 技术债务的累积信号
   - 重复出现的模式（可能是系统性问题的症状）
   - 缺失的抽象或过度抽象

3. **变更的隐含影响**
   - 对性能的隐含影响（如 N+1 查询、不必要的拷贝）
   - 对可测试性的影响
   - 对部署和运维的影响

4. **代码气味**
   - 过长的函数/类（上帝对象）
   - 过深的嵌套
   - 过多的参数
   - 过度工程化

5. **整体架构健康度**
   - 模块边界是否清晰？
   - 职责划分是否合理？
   - 是否存在循环依赖？
   - 是否有明显的架构反模式？

## 审查范围

{review_scope}

## 项目上下文

{project_context}

## 其他 Lens 的发现（供参考，避免重复）

{other_lens_findings}

## 输出格式要求

**只输出 JSON，不要输出任何 JSON 以外的文本。**

```json
{{
  "lens_id": "L7",
  "lens_name": "Holistic Review",
  "findings": [
    {{
      "id": "L7-001",
      "file": "文件路径",
      "line": 42,
      "line_range": [42, 80],
      "severity": "blocking | important | nit | suggestion",
      "category": "bug | performance | correctness | maintainability | security",
      "title": "简短标题（<80字符）",
      "description": "详细描述问题及全局影响",
      "suggestion": "具体的修复建议",
      "cross_cutting": true,
      "related_areas": ["security", "performance"],
      "confidence": 0.9
    }}
  ],
  "metrics": {{
    "total_findings": 0,
    "by_severity": {{}},
    "cross_cutting_count": 0,
    "holistic_health_score": 0.0
  }}
}}
```

## 约束
- 只报告置信度 >= 0.7 的发现
- 最多报告 {max_findings} 个发现
- 不要重复其他 lens 已经报告的问题
- 如果其他 lens 的发现已经覆盖了所有问题，在 metrics 中说明
- 重点关注跨类别和系统性问题
"""


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
                prompt_template=_LENS_L1_PROMPT,
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
                prompt_template=_LENS_L2_PROMPT,
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
                prompt_template=_LENS_L3_PROMPT,
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
                prompt_template=_LENS_L4_PROMPT,
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
                prompt_template=_LENS_L5_PROMPT,
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
                prompt_template=_LENS_L6_PROMPT,
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
                prompt_template=_LENS_L7_PROMPT,
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
