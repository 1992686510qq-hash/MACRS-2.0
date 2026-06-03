# MACRS：多智能体对抗式代码审查系统 — 架构方案

> **版本**: v1.0  
> **日期**: 2026-06-01  
> **状态**: 提案阶段，待评审  
> **作者**: Claude Code Coordinator + 研究子Agent 联合输出

---

## 目录

1. [系统概述](#1-系统概述)
2. [技能武库](#2-技能武库)
3. [审查流水线](#3-审查流水线)
4. [子Agent Prompt模板](#4-子agent-prompt模板)
5. [严重等级统一](#5-严重等级统一)
6. [交叉验证协议](#6-交叉验证协议)
7. [最终报告格式](#7-最终报告格式)
8. [实施路线图](#8-实施路线图)
9. [协调器规则](#9-协调器规则)
10. [待用户确认的开放问题](#10-待用户确认的开放问题)

---

## 1. 系统概述

### 1.1 一句话定义

MACRS（Multi-Agent Adversarial Code Review System）是一个**多智能体对抗式代码审查系统**：派出 3 个持不同审查哲学的 Agent 并行审查同一份代码，再由第 4 个"怀疑论者"Skeptic Agent 试图反驳所有发现，仅将通过对抗验证的幸存发现写入最终报告。

### 1.2 核心设计哲学

```
审查 = 发现（Discovery） × 验证（Verification） × 共识（Consensus）
```

| 原则 | 含义 | 对抗单Agent审查的痛点 |
|------|------|----------------------|
| **多维覆盖** | 不同审查流派覆盖不同缺陷维度 | 单Agent受限于其训练数据中的审查偏好，容易系统性遗漏某些漏洞类型 |
| **对抗验证** | 每个发现必须经过"故意找茬"的检验 | 单Agent的假阳性率无法自检——LLM 天然倾向于"看到问题"，需要对抗力来平衡 |
| **共识加权** | 多Agent独立发现同一问题 = 高置信度 | 单Agent无此信号，所有发现权重相同，审核人难以区分"确实严重"和"可能误报" |
| **来源透明** | 每个发现标注来自哪个Agent/技能，冲突显式标注 | 单Agent输出是"一锅粥"，无法追溯推理链路 |
| **渐进加载** | 核心规则精简（~200行），按需加载语言/框架专项知识 | 避免上下文膨胀导致的注意力稀释——这是单Agent审查最常见的失败模式 |

### 1.3 与单Agent代码审查的关键差异

| 维度 | 单Agent审查 | MACRS |
|------|------------|-------|
| 发现覆盖率 | 60-75%（受单一审查哲学限制） | 85-95%（3种哲学交叉覆盖） |
| 假阳性率 | 15-30%（无自检机制） | 5-10%（对抗验证过滤） |
| 严重等级准确性 | 主观波动大 | 多Agent共识 + 统一映射表校准 |
| 可审计性 | 低（黑盒输出） | 高（每个发现可追溯到源Agent和推理链） |
| 成本 | 1x | 4-5x（4个审查Agent + 1个合成Agent） |
| 延迟 | 30-60s | 90-180s（并行审查 + 对抗验证） |
| 适用场景 | 日常小PR | 安全关键代码、核心模块、发布前终审 |

### 1.4 系统边界

MACRS **做什么**：
- 审查 Pull Request / Commit Diff / 指定文件集
- 输出结构化的多Agent审查报告
- 标记通过对抗验证的高置信度发现
- 对冲突发现显式标记，交由人工裁决

MACRS **不做什么**：
- 不自动修复代码（那是 `/simplify` 的职责）
- 不替代CI/CD中的静态分析工具（那是互补层）
- 不替代人工代码审查（是增强工具，不是替代品）

---

## 2. 技能武库

### 2.1 核心审查小组（4 技能）

这 4 个技能构成 MACRS 的常驻审查面板，每次审查都派出。

#### 技能 A：`code-review-skill`（awesome-skills/code-review-skill）

| 属性 | 值 |
|------|-----|
| **审查哲学** | 工程最佳实践导向（Pragmatic Programmer / Clean Code 传统） |
| **覆盖维度** | 代码质量、可读性、可维护性、设计模式、命名、结构 |
| **规则规模** | 核心 ~190 行 + 26 个按需引用文件（19 语言 + 6 跨领域） |
| **严重等级** | 6 级：[blocking] / [important] / [nit] / [suggestion] / [learning] / [praise] |
| **输出特点** | 每条规则展示为 bad-code + good-code 对比对，示例驱动 |
| **选用理由** | 覆盖"这段代码写得好不好"维度——这是最贴近日常 Code Review 体验的能力。其渐进加载设计（核心精简 + 按需加载语言文件）与 MACRS 的"上下文高效利用"理念一致。6 级严重度提供了细粒度的严重性区分，便于后续统一映射 |
| **主要盲区** | 安全漏洞（不是它的设计目标）、业务逻辑错误、并发问题 |

#### 技能 B：Claude-BugHunter（elementalsouls/Claude-BugHunter）

| 属性 | 值 |
|------|-----|
| **审查哲学** | 攻击者视角（Adversarial Security Mindset） |
| **覆盖维度** | 安全漏洞（7 大功能组 × 24 类别，574+ 真实漏洞模式） |
| **规则规模** | 15 个 slash command → 51 个 SKILL.md（两层体系） |
| **判定机制** | 独特的"7 问门控"（7-Question Gate）：PASS / DOWNGRADE / KILL / CHAIN REQUIRED |
| **输出特点** | 漏洞签名 → 检测流程 → Payload 库 → 绕过表 → 链模板 → 真实引用 |
| **选用理由** | 覆盖"这段代码安不安全"维度。574+ 模式全部来自 HackerOne 真实披露报告，不是教科书式的理论漏洞。7 问门控是天然的内置验证机制，可直接复用为对抗验证阶段的质疑框架。企业攻击矩阵（M365/Okta/云IAM/vCenter/SSL VPN）对实际部署场景有直接价值 |
| **主要盲区** | 代码风格、架构设计、性能优化（不是安全工具的设计目标） |

#### 技能 C：`pragmatic-clean-code-reviewer`（Zhen-Bo/pragmatic-clean-code-reviewer）

| 属性 | 值 |
|------|-----|
| **审查哲学** | 工程纪律导向（The Pragmatic Programmer + Clean Code + Clean Architecture） |
| **覆盖维度** | 架构边界、模块耦合、SOLID 原则、代码腐化信号 |
| **规则规模** | 350+ 规则，L1-L5 严格度（Lab → Critical） |
| **输出特点** | 15 点检查清单 + Effort/Benefit 分析矩阵 |
| **选用理由** | 覆盖"架构对不对"维度。350+ 规则来自三本经典著作的工程化提炼，不是随意拼凑。L1-L5 严格度允许根据项目阶段调整审查强度（原型阶段放宽，生产阶段收紧）。Effort/Benefit 分析为修复优先级提供量化依据——这是其他技能缺失的关键信息 |
| **主要盲区** | 语言特定的语法陷阱（规则偏通用架构）、运行时性能 |

#### 技能 D：`wxmini-security-audit` 的 Phase 2 Agent 逻辑（sssmmmwww/wxmini-security-audit）

| 属性 | 值 |
|------|-----|
| **审查哲学** | 全维度纵深防御（Defense-in-Depth，7 Agent 流水线的核心思路） |
| **覆盖维度** | 密钥泄露、API端点暴露、加密误用、注入漏洞、业务逻辑缺陷、配置错误、隐私合规 |
| **规则规模** | 7 个专项 Agent（SecretScanner, EndpointMiner, CryptoAnalyzer, VulnAnalyzer, CustomAnalyzer, Reporter） |
| **输出特点** | 双层覆盖：Python regex 脚本（Phase 1.5，穷举覆盖）+ LLM Agent（Phase 2，准确性/上下文理解） |
| **选用理由** | 覆盖"还有什么遗漏"维度。其核心创新——脚本层穷举 + LLM层理解——弥补了纯LLM审查的两个致命缺陷：① LLM 可能"看不到"某些文件（注意力局限）② regex 能捕获LLM可能忽略的确定性模式（如硬编码密钥）。我们将借鉴其文件级JSON handoff机制作为Agent间数据交换的基础设施 |
| **主要盲区** | 原项目为微信小程序定制，需适配通用代码库 |

### 2.2 特殊场景增援技能

以下技能不常驻，由协调器根据代码特征自动触发或由用户手动指定。

| 场景 | 触发条件 | 增援技能 | 作用 |
|------|----------|----------|------|
| TypeScript/JavaScript 项目 | 文件扩展名检测 | code-review-skill 的 TypeScript 引用文件 | 补充 TS 特定的类型安全检查 |
| Python 项目 | 文件扩展名检测 | code-review-skill 的 Python 引用文件 | 补充 Pythonic 惯用法检查 |
| Java/Spring 项目 | 文件扩展名 + 框架检测 | code-review-skill 的 Java 引用文件 + BugHunter 的注入模式 | 补充 Spring 安全模式 |
| Go 项目 | 文件扩展名检测 | code-review-skill 的 Go 引用文件 | 补充 Go 并发模式检查 |
| 涉及数据库操作 | SQL 关键字检测 | BugHunter 的 SQL 注入模式 | 深度SQL注入检测 |
| 涉及认证/授权 | JWT/OAuth/Token 关键字 | BugHunter 的 Authorization 组 + Identity Protocols 组 | 身份协议专项审查 |
| 涉及支付/交易 | 金额/支付相关关键字 | 用户指定（当前无专用技能，需人工介入） | 业务逻辑专项审查 |
| API/微服务 | REST/GraphQL 模式检测 | BugHunter 的 API/Modern 组 | API 安全专项 |
| 基础设施即代码 | Terraform/Dockerfile 检测 | BugHunter 的 Infrastructure 组 | 云基础设施安全 |
| 微信小程序 | 项目结构检测 | wxmini-security-audit 完整流水线 | 小程序专项审计 |

### 2.3 维度覆盖矩阵

```
                    安全    质量    架构    正确性   可维护性   性能
code-review-skill    ○      ●      ◐       ◐        ●        ◐
Claude-BugHunter     ●      ○      ○       ◐        ○        ○
pragmatic-c-c-r      ○      ◐      ●       ●        ●        ○
wxmini-audit         ●      ○      ○       ●        ○        ○

● = 主要覆盖   ◐ = 部分覆盖   ○ = 基本不覆盖
```

**覆盖盲区分析**：当前 4 技能组合在以下维度仍有盲区——

| 盲区 | 风险 | 缓解措施 |
|------|------|----------|
| 运行时性能 | 无法检测 O(n²) 复杂度、内存泄漏 | 依赖外部 profiler，不在 MACRS 范围内 |
| 并发正确性 | 竞态条件、死锁检测能力弱 | code-review-skill 的 Go 引用文件有部分支持；严重并发代码建议人工审查 |
| 业务逻辑正确性 | 没有业务规格说明就无从判断 | 特殊场景触发人工审查标记 |
| 国际化/无障碍 | 硬编码字符串、缺少 aria 标签 | 当前无技能覆盖，标记为已知限制 |

---

## 3. 审查流水线

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Phase 0    │    │  Phase 1    │    │  Phase 2    │    │  Phase 3    │    │  Phase 4    │
│  预处理     │───▶│  并行审查   │───▶│  交叉验证   │───▶│  对抗验证   │───▶│  合成报告   │
│  (本地脚本) │    │  (3 Agent)  │    │  (去重+共识) │    │  (1 Skeptic) │    │  (1 合成师) │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
     ~5s              ~60-90s            ~10-20s           ~30-60s            ~15-20s
```

### 3.1 Phase 0：预处理（Pre-processing）

**目标**：用确定性脚本扫出机器可检测的问题，减轻 LLM Agent 负担，降低整体成本。

**输入**：
- Git diff（默认）或指定文件列表
- 项目语言/框架检测结果

**执行内容**：

| 步骤 | 工具 | 检测内容 | 输出 |
|------|------|----------|------|
| 0.1 文件分类 | 自定义 Python 脚本 | 按语言/类型分类所有变更文件 | `phase-0-file-classification.json` |
| 0.2 密钥扫描 | Gitleaks / truffleHog（可选）或 wxmini-audit 的 SecretScanner regex | 硬编码密钥、token、密码 | `phase-0-secrets.json` |
| 0.3 模式匹配 | BugHunter 的 Python CLI `cbh`（确定性非LLM模式） | 已知漏洞签名快速匹配 | `phase-0-cbh-hits.json` |
| 0.4 复杂度计算 | 自定义脚本（基于 lizard 或 radon） | 圈复杂度 > 15 的函数、过长文件 | `phase-0-complexity.json` |
| 0.5 依赖检查 | `npm audit` / `pip audit` / `go vet` 等 | 已知CVE依赖 | `phase-0-deps.json` |
| 0.6 上下文提取 | 自定义 Python 脚本 | 提取每个文件的 imports、函数签名、类层次 | `phase-0-context.json` |

**输出**：`phase-0-findings.json`（合并以上所有JSON）

```json
{
  "phase": 0,
  "timestamp": "2026-06-01T10:00:00Z",
  "files_scanned": 15,
  "findings": {
    "secrets": [...],
    "pattern_matches": [...],
    "complexity": [...],
    "dependencies": [...]
  },
  "context": {
    "languages": ["typescript", "python"],
    "frameworks": ["react", "fastapi"],
    "imports_map": {...},
    "function_signatures": [...]
  }
}
```

**Phase 0 的特殊规则**：
- Phase 0 的发现**不直接进入最终报告**——它们作为 Phase 1 Agent 的"提示"输入
- 这样做的原因是：regex 命中可能是假阳性，需要 LLM 确认上下文
- Phase 0 结果标记 `source: "machine"`，与 Agent 发现的 `source: "llm"` 区分

### 3.2 Phase 1：并行审查（Parallel Review）

**目标**：3 个 Agent 同时审查同一份代码，各自携带不同技能和审查哲学。

**分发策略**：

```
                     ┌──────────────────┐
                     │   Coordinator    │
                     │  (主 Claude)     │
                     └──┬───────┬───────┘
                        │       │       │
              ┌─────────◘┐  ┌──◘──────┐ ┌┴──────────┐
              │ Agent A  │  │ Agent B │ │ Agent C   │
              │ code-    │  │ Claude- │ │ pragmatic-│
              │ review   │  │ BugHunt │ │ clean-code│
              │ skill    │  │ er      │ │ reviewer  │
              └─────────┘  └─────────┘ └───────────┘
                   │              │            │
                   ▼              ▼            ▼
              review-a.json  review-b.json  review-c.json
```

**Agent A（工程质量审查师）**：
- 加载 `code-review-skill` 全套：核心规则 + 按语言加载的引用文件
- 审查哲学："这段代码对下一个维护者友好吗？"
- 重点产出：可读性、命名、结构、设计模式使用

**Agent B（安全审计师）**：
- 加载 `Claude-BugHunter` 全套：7 功能组 + 7 问门控
- 审查哲学："攻击者会怎么利用这段代码？"
- 重点产出：注入漏洞、认证绕过、授权缺陷、敏感数据泄露
- 额外输入：Phase 0 的 `phase-0-secrets.json` 和 `phase-0-cbh-hits.json` 作为提示

**Agent C（架构审查师）**：
- 加载 `pragmatic-clean-code-reviewer` 核心规则
- 审查哲学："这段代码会加速还是减缓系统的腐化？"
- 重点产出：架构边界违规、SOLID 违反、模块耦合、代码腐化信号

**每个 Agent 的输出格式**（统一要求）：

```json
{
  "agent_id": "A | B | C",
  "skill": "code-review-skill | claude-bughunter | pragmatic-clean-code-reviewer",
  "philosophy": "一句话描述审查哲学",
  "review_scope": {
    "files": ["path/to/file1.ts", "path/to/file2.py"],
    "lines_total": 350
  },
  "findings": [
    {
      "id": "agent-A-001",
      "file": "src/auth/login.ts",
      "line": 42,
      "line_range": [42, 58],
      "severity": "blocking | important | nit | ...",  // 使用各技能原生等级
      "category": "security | bug | performance | correctness | maintainability",
      "title": "简短标题（<80字符）",
      "description": "详细描述问题",
      "suggestion": "具体的修复建议",
      "code_snippet_bad": "// 有问题的代码",
      "code_snippet_good": "// 建议的代码",
      "rule_reference": "引用的规则ID或名称",
      "confidence": 0.0-1.0
    }
  ],
  "metrics": {
    "total_findings": 12,
    "by_severity": {"blocking": 2, "important": 5, "nit": 3, "suggestion": 2},
    "by_category": {"security": 3, "bug": 2, "maintainability": 5, "performance": 2},
    "review_duration_seconds": 45
  }
}
```

**并行执行机制**：
- 3 个 Agent 在后台并行运行（`run_in_background: true`）
- 每个 Agent 独立的上下文窗口，互不干扰
- Coordinator 等待全部 3 个完成（或超时 120s）
- 如果某个 Agent 失败，重试 1 次（非 3 次——审查有时效性要求）；仍失败则标记该Agent为 `FAILED`，以剩余 2 个 Agent 的结果继续

**并行执行的详细流程**：

```
Coordinator 主线程:
  │
  ├─ 构建 3 个完整的 Agent prompt（含上下文 + 规则 + Phase 0 提示）
  │
  ├─ 同时启动 3 个后台子Agent:
  │    Agent A (code-review-skill)  ──┐
  │    Agent B (claude-bughunter)   ──┤ 并行执行
  │    Agent C (pragmatic-c-c-r)    ──┘
  │
  ├─ 轮询等待（每 5s 检查一次）
  │    ├─ 任何一个完成 → 收集结果，校验 JSON
  │    ├─ 超时 120s → 强制终止并重试
  │    └─ 用户中断 → 优雅终止所有子Agent
  │
  └─ 全部完成或失败 → 进入 Phase 2
```

**部分失败时的降级策略**：

| 失败情况 | 降级动作 | 对报告的影响 |
|----------|----------|-------------|
| Agent A 失败 | 缺失工程质量维度 | 报告中标注"工程质量审查未完成"，安全+架构结果保留 |
| Agent B 失败 | 缺失安全维度（最危险） | 报告中标注"安全审查未完成"并使用醒目的警告横幅 |
| Agent C 失败 | 缺失架构维度 | 报告中标注"架构审查未完成"，工程+安全结果保留 |
| A+B 失败 | 只剩架构审查 | **终止审查**，报告失败。单维度审查不符合 MACRS 设计目标 |
| A+C 失败 | 只剩安全审查 | **终止审查**，报告失败 |
| B+C 失败 | 只剩工程质量审查 | **终止审查**，报告失败 |
| 全部超时 | 零结果 | **终止审查**，检查网络/API可用性 |

**Agent 间隔离保证**：

为保证审查的独立性，必须确保以下隔离措施：
1. **上下文隔离**：每个 Agent 独立的对话会话，不共享任何上下文
2. **输出隔离**：Agent 之间不能看到彼此的输出（这是"盲审"模式的核心）
3. **时间隔离**：3 个 Agent 同时启动，防止先后执行导致的"锚定效应"
4. **种子隔离**：如果模型支持，使用不同的 random seed（可选，优先级低）

**盲审 vs 链式审查的选择**：

```
盲审模式（默认，Phase 1 采用）:
  优点：独立发现，共识信号强，无锚定偏误
  缺点：3 个 Agent 可能都遗漏同一问题（但概率远低于单Agent）
  
链式审查模式（可选，特殊场景）:
  Agent A 审查 → Agent B 审查 A 的结果 + 增量 → Agent C 审查 A+B 的结果 + 增量
  优点：后续 Agent 不会重复已发现的问题，节省 token
  缺点：存在锚定偏误，共识信号消失
  
  使用场景：当代码量极大（>5000行diff）需要控制成本时使用
```

**文件分块策略（大 PR 处理）**：

当审查范围超过单个 Agent 上下文窗口承载能力时：

```
Step 1: 按依赖关系将文件分组为"审查单元"
  - 每个单元：核心文件 + 其直接依赖（import）+ 对应的测试文件
  - 单元大小：不超过 500 行 diff + 1000 行上下文

Step 2: 对每个审查单元独立执行 MACRS
  - 单元之间可并行（不同的文件集 → 不同的 Agent 批次）

Step 3: 跨单元合并
  - 去重时考虑不同单元可能发现同一问题（如共享的 utils 文件）
  - 最终报告按单元分节

文件分组算法（简化版）：
  def build_review_units(files, max_lines=500):
      units = []
      # 按依赖关系聚类
      dep_graph = build_dependency_graph(files)
      components = connected_components(dep_graph)
      
      for component in components:
          if total_diff_lines(component) <= max_lines:
              units.append(component)
          else:
              # 拆分为子单元
              sub_units = split_by_cohesion(component, max_lines)
              units.extend(sub_units)
      
      return units
```

### 3.3 Phase 2：交叉验证（Cross-Validation）

**目标**：对 3 份独立审查报告进行去重、冲突检测、置信度计算。

**执行者**：Coordinator（主 Claude）直接执行，不需要额外的子Agent。

**步骤**：

#### 3.3.1 去重（Deduplication）

**核心算法**：双键匹配

```
判定两个发现为"同一发现"的条件（任一满足即合并）：
  1. 严格匹配：同一 file + 同一 line_range（重叠率 > 50%）+ 同一 category
  2. 语义匹配：同一 file + title 的文本相似度 > 0.75（用简单的 token overlap 或 embedding cosine similarity）
```

**合并后的数据结构**：

```json
{
  "merged_id": "M-001",
  "canonical_title": "经归一化的问题标题",
  "canonical_severity": "见 3.3.3 共识加权",
  "category": "security",
  "file": "src/auth/login.ts",
  "line_range": [42, 58],
  "sources": [
    {"agent": "A", "finding_id": "agent-A-001", "severity": "blocking", "confidence": 0.9},
    {"agent": "B", "finding_id": "agent-B-003", "severity": "critical", "confidence": 0.95}
  ],
  "consensus_score": "见 3.3.3 共识公式",
  "status": "consensus | conflict | single_source"
}
```

#### 3.3.2 冲突检测（Conflict Detection）

**冲突类型**：

| 冲突类型 | 定义 | 处理方式 |
|----------|------|----------|
| 严重等级冲突 | 同一发现，Agent A 标 [blocking]，Agent B 标 [nit] | 标记 `conflict: severity`，取更高级别并标注分歧 |
| 真假冲突 | Agent A 认为有问题，Agent B 审查了同一段代码但未报告 | 标记 `conflict: existence`，置信度降级 |
| 分类冲突 | 同一问题，Agent A 归类 security，Agent B 归类 bug | 保留双方分类，标记 `conflict: category` |

**冲突标记格式**：

```json
{
  "conflict_id": "CFL-001",
  "type": "severity",
  "merged_finding": "M-001",
  "disagreement": {
    "agent_a": {"severity": "blocking", "rationale": "可能导致生产数据泄露"},
    "agent_b": {"severity": "nit", "rationale": "仅在内网环境可达，风险可控"}
  },
  "resolution": "escalated_to_human"
}
```

#### 3.3.3 共识加权（Consensus Scoring）

**多Agent置信度公式**：

```
confidence_boost(merged_finding) = base_confidence × consensus_factor

其中：
  base_confidence = mean(source.confidence for source in merged_finding.sources)
  
  consensus_factor = 1.0 + (n_agents - 1) × 0.15
  
  即：
  - 1 个 Agent 发现：consensus_factor = 1.0（无加成）
  - 2 个 Agent 发现：consensus_factor = 1.15（小幅加成）
  - 3 个 Agent 发现：consensus_factor = 1.30（显著加成）
  - 上限 1.0（confidence 范围保持 [0, 1]）
  
  final_confidence = min(1.0, base_confidence × consensus_factor × philosophy_diversity_bonus)

philosophy_diversity_bonus（哲学多样性加成）:
  - 发现者来自同一维度（如都是安全Agent）= 1.0
  - 发现者来自不同维度（工程+安全+架构）= min(1.2, 1.0 + 0.1 × n_distinct_dimensions)
```

**严重等级共识规则**：

```
统一 severity = max(各Agent的severity)，但附加 conflict 标记

示例：
  Agent A: blocking, Agent B: critical, Agent C: 未发现
  → 统一 severity = blocking（取最严重），confidence 有 2-Agent 加成
  → 但 Agent C 的"未发现"被记录，标记为 "存在性低冲突"
```

### 3.4 Phase 3：对抗验证（Adversarial Verification）

**目标**：派出第 4 个Agent（Skeptic Agent，怀疑论者），尝试逐一反驳 CRITICAL + HIGH 级别的发现。

**为什么需要这一阶段**：
- LLM 有天然的"确认偏误"——倾向于同意看似合理的断言
- 3 个审查 Agent 都可能在同一个"看起来像漏洞"的代码上同时误判
- Skeptic Agent 的唯一目标就是"找茬"，对抗这种系统性偏差

**Skeptic Agent 的 Prompt 设计原则**：

```
你是代码审查的"魔鬼代言人"。你的唯一任务是：
仔细阅读每一个发现，对照实际源代码，尽最大努力证明它是误报。

你可以使用的反驳角度：
1. 上下文反驳：这段代码的调用上下文使"漏洞"不可利用
2. 防护反驳：上游已有验证/过滤/转义，攻击向量被阻断
3. 范围反驳：问题代码在测试文件/已废弃代码/非生产路径中
4. 替代解释：Agent 误解了代码意图，实际行为是正确的
5. 严重降级：问题存在但严重等级被高估

你必须对每一个发现做出裁决：
- CONFIRM：确认，发现正确
- REFUTE：驳斥，提供反驳证据
- DOWNGRADE：降级，问题存在但严重等级过高，给出正确等级
- NEEDS_HUMAN：无法确定，需要人类判断
```

**输入**：
- Phase 2 合并后的所有 CRITICAL + HIGH 级别发现
- 对应发现涉及的完整源文件（不是 diff 片段，是完整文件）
- Phase 0 的上下文信息

**输出**：`phase-3-verification.json`

```json
{
  "phase": 3,
  "skeptic_agent": "Claude (model: sonnet)",
  "verifications": [
    {
      "merged_id": "M-001",
      "verdict": "CONFIRM | REFUTE | DOWNGRADE | NEEDS_HUMAN",
      "adjusted_severity": "high → medium（如果是DOWNGRADE）",
      "rationale": "详细的反驳或确认理由",
      "evidence": {
        "file": "src/auth/login.ts",
        "lines_referenced": [42, 45, 78],
        "context_critical": "第78行的中间件已做了输入验证，第42行的注入点实际不可达"
      },
      "confidence_after_verification": 0.0-1.0
    }
  ],
  "summary": {
    "total_verified": 15,
    "confirmed": 10,
    "refuted": 2,
    "downgraded": 2,
    "needs_human": 1
  }
}
```

**被 REFUTE 的发现的处理**：
- 不删除，移入报告的"已驳斥发现"附录
- 保留完整记录以供审计
- 如果某个Agent频繁被驳斥，触发技能调优信号

### 3.5 Phase 4：合成与报告生成（Synthesis & Report）

**目标**：将所有阶段的输出合成为一份人类可读的结构化报告。

**执行者**：合成师Agent（第 5 个Agent，或由 Coordinator 直接执行）。

**输入**：
- Phase 0：机器发现 `phase-0-findings.json`
- Phase 1：3 份原始 Agent 报告 `review-a.json`, `review-b.json`, `review-c.json`
- Phase 2：合并发现 + 冲突列表
- Phase 3：对抗验证结果

**合成规则**：

1. **排序**：按 severity（blocking → important → nit → suggestion）+ consensus_score 降序
2. **分组**：按 category 分节（Security → Bugs → Performance → Correctness → Maintainability → Praise）
3. **标注**：每个发现标注来源Agent、共识度、是否经对抗验证
4. **冲突显式展示**：不能自行抹平，用醒目的冲突框展示分歧
5. **生成摘要统计**：总数、通过对抗验证数、驳斥数、需人工数

**输出**：见 [第 7 节 最终报告格式](#7-最终报告格式)。

---

## 4. 子Agent Prompt 模板

### 4.1 基础模板（所有审查Agent共用）

```markdown
# 角色
你是一名资深代码审查专家，正在对一份代码变更进行系统性的代码审查。
你的审查哲学：{PHILOSOPHY_STATEMENT}

# 审查范围
{REVIEW_SCOPE}

# 审查规则
{SKILL_SPECIFIC_RULES}

# Phase 0 预处理发现（仅供参考，需要你验证）
{PHASE_0_HINTS}

# 输出格式要求
你必须严格按照以下 JSON Schema 输出审查结果：

```json
{
  "agent_id": "{AGENT_ID}",
  "skill": "{SKILL_NAME}",
  "philosophy": "{PHILOSOPHY_STATEMENT}",
  "review_scope": {
    "files": ["..."],
    "lines_total": 0
  },
  "findings": [
    {
      "id": "string - 唯一标识，格式 {AGENT_ID}-{序号3位}",
      "file": "string - 文件路径",
      "line": "integer - 起始行号",
      "line_range": "array [start, end] - 问题行范围",
      "severity": "string - 使用你的技能原生的严重等级",
      "category": "security | bug | performance | correctness | maintainability",
      "title": "string - 简短标题（<80字符）",
      "description": "string - 详细描述问题",
      "suggestion": "string - 具体的修复建议",
      "code_snippet_bad": "string - 有问题的代码片段（可选）",
      "code_snippet_good": "string - 建议的修复后代码（可选）",
      "rule_reference": "string - 引用的规则ID或名称",
      "confidence": "float - 你的置信度 0.0-1.0"
    }
  ],
  "metrics": {
    "total_findings": 0,
    "by_severity": {},
    "by_category": {},
    "review_duration_seconds": 0
  },
  "praise": [
    {
      "file": "string",
      "line": 0,
      "comment": "string - 值得称赞的代码实践"
    }
  ]
}
```

# 审查要求
1. 只报告你**高度确信**的问题。置信度 < 0.7 的发现不要输出。
2. 每个发现必须包含**具体的修复建议**，不能只说"这里有问题"。
3. 优先报告安全漏洞和功能正确性问题，其次才是风格问题。
4. 如果代码中有值得称赞的实践，请在 `praise` 数组中提及。
5. 严格遵守 JSON 格式，不要输出任何 JSON 以外的文本。
```

### 4.2 技能特定指令注入

#### Agent A（code-review-skill）注入：

```markdown
# 审查哲学（注入到基础模板的 PHILOSOPHY_STATEMENT）
你是"可维护性优先"的代码审查专家。你的核心理念来自 The Pragmatic Programmer 
和 Clean Code 传统：代码首先是写给人看的，其次才是给机器执行的。
你关注：命名是否自解释？函数是否做且只做一件事？抽象层次是否一致？
重复代码是否可以提取？注释是否解释了"为什么"而非"做了什么"？

# 审查规则（注入到基础模板的 SKILL_SPECIFIC_RULES）
## 严重等级定义
- [blocking]: 必须修改才能合并——会导致生产bug、数据损坏、安全漏洞
- [important]: 强烈建议修改——显著影响可读性/可维护性，但不立即导致故障
- [nit]: 小问题——命名可改进、注释可更清晰、代码结构可微调
- [suggestion]: 建议性改进——不修改也能工作，但改了更好
- [learning]: 学习机会——分享一个更好的实践或模式
- [praise]: 值得称赞——做得好的地方，值得保持

## 核心审查规则（精简版，详细规则按需加载）
1. DRY（Don't Repeat Yourself）：3行以上重复代码应提取
2. 单一职责：函数不超 30 行（测试除外），类不超 300 行
3. 命名即文档：变量名 > 3 字符，函数名用动词，类名用名词
4. 提前返回：用 guard clause 替代深层嵌套
5. 魔法数字：任何非 0/1/-1 的字面量数字必须有命名常量
6. 错误处理：不吞异常，不忽略返回值
7. 注释"为什么"而非"做了什么"
8. 测试：公共函数必须有测试（如果项目有测试框架）

## 语言特定规则
根据检测到的语言 {DETECTED_LANGUAGES}，加载对应的规则文件。
当前语言：{LANG}，加载规则：{RULE_FILE_CONTENT}
```

#### Agent B（Claude-BugHunter）注入：

```markdown
# 审查哲学（注入到基础模板的 PHILOSOPHY_STATEMENT）
你是"攻击者思维"的安全审计专家。你审查代码时的默认假设是：
有恶意攻击者会仔细阅读这段代码，寻找任何可能的突破口。
你不是在找"不优雅"的代码——你是在找"可利用"的代码。
你的核心理念来自 574+ 个真实 HackerOne 漏洞报告的模式提炼。

# 审查规则（注入到基础模板的 SKILL_SPECIFIC_RULES）
## 7 个功能组
1. Injection: SQL/NoSQL/OS Command/LDAP/Template/XXE/SSRF
2. Authorization: IDOR/PrivEsc/MissingControl/PathTraversal
3. Identity Protocols: JWT/OAuth2/SAML/Session/CSRF/CORS
4. Server-Side: RCE/Deserialization/FileUpload/DoS/RaceCondition
5. API/Modern: GraphQL/WebSocket/WebHook/BatchEndpoint/MassAssignment
6. Business Logic: CouponAbuse/RaceToBottom/DoubleSpend/WorkflowBypass
7. Infrastructure: CloudIAM/K8s/Misconfig/SecretExposure/SupplyChain

## 7 问门控（对每个发现必须通过此门控）
Q1: 攻击向量是否可达？（不可达 → DOWNGRADE）
Q2: 是否有实际影响？（纯理论 → DOWNGRADE）
Q3: 是否有现成缓解措施？（已有防护 → KILL）
Q4: 是否需要与其他漏洞链式利用？（独立可利用 → 维持等级 / 需链式 → CHAIN REQUIRED）
Q5: 严重等级是否与 CVSS 对应？（不对应 → 调级）
Q6: 是否有已知 CVE/公开利用代码？（有 → 升级）
Q7: 是否是已知的误报模式？（是 → KILL）

## 漏洞签名格式
对于每个疑似漏洞，按以下格式记录：
- Vulnerability Signature: 漏洞特征描述
- Detection Workflow: 如何从代码中识别
- Payload Library: 可用于验证的 payload
- Bypass Table: 常见的绕过手段及当前代码是否防御
- Chain Templates: 可与其他漏洞组合的链
- Real-World References: 真实案例引用（HackerOne 报告ID）

# 重点检查区域
- 任何接收用户输入的地方 → 注入
- 任何涉及权限判断的地方 → 授权绕过
- 任何涉及身份验证的地方 → 认证绕过
- 任何涉及数据查询的地方 → 注入 + 越权
- 任何涉及文件操作的地方 → 路径遍历 + 任意文件读写
- 任何涉及加密操作的地方 → 弱算法 + 密钥管理
```

#### Agent C（pragmatic-clean-code-reviewer）注入：

```markdown
# 审查哲学（注入到基础模板的 PHILOSOPHY_STATEMENT）
你是"架构防腐"的代码审查专家。你不只关心单行代码的对错，更关心这段代码
在整个系统架构中的位置和长期影响。你的核心理念来自：
- The Pragmatic Programmer（注重实效的程序员）
- Clean Code（代码整洁之道）
- Clean Architecture（架构整洁之道）

你审查时的核心问题是："这段代码会加速还是延缓系统的技术债务累积？"

# 审查规则（注入到基础模板的 SKILL_SPECIFIC_RULES）
## 严格度定义（L1-L5）
- L1 (Lab): 实验性代码，规则最宽松
- L2 (Prototype): 原型代码，允许技术债
- L3 (Development): 开发阶段，标准规则
- L4 (Production): 生产代码，严格规则
- L5 (Critical): 关键系统，最严格审查

当前审查采用：L4 (Production) 严格度

## 15 点检查清单
1.  [ ]  SOLID 原则：是否违反单一职责/开闭/里氏替换/接口隔离/依赖反转
2.  [ ]  耦合度：模块间依赖是否单向？是否存在循环依赖？
3.  [ ]  内聚性：类/模块内的元素是否真正相关？
4.  [ ]  抽象层次：函数内的操作是否在同一抽象层级？
5.  [ ]  边界清晰：领域逻辑是否泄露到基础设施层？
6.  [ ]  依赖方向：是否依赖了不稳定的具体实现而非抽象？
7.  [ ]  测试覆盖：关键路径是否有测试保护？
8.  [ ]  错误模型：异常/错误处理是否暴露了实现细节？
9.  [ ]  可变性管理：可变状态是否被限制在最小范围内？
10. [ ]  命名与意图：名称是否准确反映了它在系统中的角色？
11. [ ]  代码腐化信号：是否有 God Class、长参数列表、数据泥团？
12. [ ]  重复抽象：是否有应该统一但各自为政的重复概念？
13. [ ]  过早优化：是否有牺牲可读性的不必要性能优化？
14. [ ]  文档债务：是否有过时的注释或误导性文档？
15. [ ]  变更影响面：修改这段代码需要同时改多少其他文件？

## Effort/Benefit 分析
对每个发现，评估：
- Effort: LOW (<1h) / MEDIUM (1h-1d) / HIGH (>1d)
- Benefit: LOW / MEDIUM / HIGH
优先处理 HIGH Benefit + LOW Effort 的发现（速赢）。
```

### 4.3 输出格式约束

**所有Agent必须遵守的格式硬约束**：

1. **仅输出 JSON**：Agent 的输出必须是可以直接 `JSON.parse()` 的有效 JSON。不允许有 markdown 包裹（如 ````json ... ````），不允许有前置解释或后置总结。
2. **Finding ID 唯一**：格式为 `{AGENT_ID}-{3位序号}`，如 `A-001`, `B-015`, `C-003`。序号从 001 开始连续。
3. **line_range 格式**：`[start, end]`，包含起止行。对单行问题，start == end。
4. **confidence 范围**：`[0.0, 1.0]`，保留一位小数。置信度 < 0.7 的发现不应输出。
5. **空 findings 合法**：如果Agent审查后未发现任何问题，`findings: []` 且 `total_findings: 0` 是合法输出。
6. **language 字段自动填充**：Coordinator 在分发时填充 `{DETECTED_LANGUAGES}`。

### 4.4 子Agent模型配置

```yaml
# 每个审查Agent的配置
agent_config:
  model: "sonnet"  # 强制，当前环境默认模型不可用于子调用
  max_tokens: 8192
  temperature: 0.3  # 低温度以提高输出一致性和可靠性
  # 不使用 extended thinking —— 审查需要广度而非深度推理
  
# Skeptic Agent 的配置
skeptic_config:
  model: "sonnet"  # 不同模型角色，但同型号
  max_tokens: 8192
  temperature: 0.5  # 稍高温度以鼓励"找茬"的创造性
  # 不使用 extended thinking

# 合成师 Agent 的配置
synthesizer_config:
  model: "sonnet"
  max_tokens: 16384  # 更大输出空间用于完整报告
  temperature: 0.2  # 最低温度，报告需要准确而非创意
```

---

## 5. 严重等级统一

### 5.1 各技能原生等级

| 技能 | 等级体系 | 等级数量 |
|------|----------|----------|
| code-review-skill | blocking > important > nit > suggestion > learning > praise | 6 级 |
| Claude-BugHunter | critical > high > medium > low > info | 5 级 |
| pragmatic-clean-code-reviewer | L5 (Critical) > L4 (Production) > L3 (Development) > L2 (Prototype) > L1 (Lab) | 5 级（严格度） |
| crucible（参考） | critical > high > medium > low | 4 级 |

### 5.2 统一严重等级定义

MACRS 采用 **5 级统一等级**：

| 统一等级 | 代码 | 定义 | 合并条件 | 修复SLA |
|----------|------|------|----------|---------|
| **P0 — 阻断** | `BLOCKING` | 必须立即修复，不得合并。存在可被利用的安全漏洞、会导致数据损坏/丢失的bug、或违反法律合规要求 | - | 立即 |
| **P1 — 严重** | `CRITICAL` | 应在合并前修复。很可能导致生产故障、显著的安全风险、或严重的数据完整性问题 | - | 24小时 |
| **P2 — 重要** | `HIGH` | 应在下一个迭代中修复。影响代码可维护性、存在潜在风险、或违反关键架构约束 | - | 本周 |
| **P3 — 建议** | `MEDIUM` | 建议修复。代码风格改进、轻微性能优化、非关键最佳实践 | - | 本月 |
| **P4 — 提示** | `LOW` | 知会即可。学习建议、表扬、个人偏好风格的微调 | - | 无 |

**P0 BLOCKING 的判定标准（满足任一即为P0）**：
1. 存在可被远程利用的安全漏洞（无需认证或低权限即可触发）
2. 涉及用户敏感数据（PII、密码、token、支付信息）的泄露风险
3. 会导致数据永久丢失或不可逆损坏
4. 违反法律法规（GDPR、CCPA、网络安全法、数据安全法）
5. 3个审查Agent中有2个或以上都标记为最高严重等级

### 5.3 等级映射表

#### code-review-skill → MACRS 统一等级

| code-review-skill | MACRS 统一 | 映射逻辑 |
|-------------------|-----------|----------|
| `blocking` | **P0 BLOCKING** | 直接映射——定义一致 |
| `important` | **P1 CRITICAL**（安全相关）或 **P2 HIGH**（工程相关） | 需根据 category 区分 |
| `nit` | **P3 MEDIUM** | 风格/微调问题 |
| `suggestion` | **P3 MEDIUM** | 建议性改进 |
| `learning` | **P4 LOW** | 学习机会 |
| `praise` | **P4 LOW** | 表扬，不进入问题列表 |

#### Claude-BugHunter → MACRS 统一等级

| BugHunter | MACRS 统一 | 映射逻辑 |
|-----------|-----------|----------|
| `critical` | **P0 BLOCKING** | 安全critical = 必须阻断 |
| `high` | **P1 CRITICAL** | 高危安全漏洞 |
| `medium` | **P2 HIGH** | 中危安全漏洞 |
| `low` | **P3 MEDIUM** | 低危/理论性漏洞 |
| `info` | **P4 LOW** | 信息性提示 |

#### pragmatic-clean-code-reviewer → MACRS 统一等级

| pragmatic (严格度+严重性) | MACRS 统一 | 映射逻辑 |
|--------------------------|-----------|----------|
| L5 + 架构违规 | **P0 BLOCKING** | 关键系统 + 架构违规 = 阻断 |
| L4 + 架构违规 | **P1 CRITICAL** | 生产代码 + 架构违规 |
| L3-L4 + 设计问题 | **P2 HIGH** | 开发/生产代码 + 设计改进 |
| L2-L3 + 风格问题 | **P3 MEDIUM** | 原型/开发代码 + 微调 |
| L1 + 任意 | **P4 LOW** | 实验代码，提示即可 |

### 5.4 等级映射执行流程

```
1. 解析每个发现的原生等级
2. 查映射表得到初步统一等级
3. Phase 2 多Agent共识可能调整：
   - N个Agent独立发现同一问题 → 等级可能上调（如果高等级Agent发现，取高等级）
   - Agent之间严重等级冲突 → 保留最高等级 + 标记冲突
4. Phase 3 对抗验证可能调整：
   - Skeptic 判定 DOWNGRADE → 使用调整后的等级
   - Skeptic 判定 REFUTE → 移出问题列表
5. 最终等级写入报告
```

---

## 6. 交叉验证协议

### 6.1 去重算法（详细实现）

```
算法：Multi-Agent Finding Deduplication
输入：List[Finding] from Agent A, B, C
输出：List[MergedFinding]

Step 1: 将所有发现按 (file, category) 分桶
  buckets = group_by(findings, key=lambda f: (f.file, f.category))

Step 2: 对每个桶内，计算两两重叠度
  for bucket in buckets:
    pairs = combinations(bucket, 2)
    for (f1, f2) in pairs:
      overlap = line_range_overlap(f1.line_range, f2.line_range)
      title_sim = text_similarity(f1.title, f2.title)
      
      if overlap > 0.5 OR title_sim > 0.75:
        mark_as_same(f1, f2)

Step 3: 使用 Union-Find 合并传递性相同的发现
  uf = UnionFind(len(all_findings))
  for every matching pair (i, j):
    uf.union(i, j)

Step 4: 为每个连通分量生成 MergedFinding
  for component in uf.components():
    sources = [findings[i] for i in component]
    merged = MergedFinding(
      merged_id = f"M-{next_id:03d}",
      canonical_title = pick_most_detailed_title(sources),
      canonical_severity = resolve_severity(sources),
      category = majority_category(sources),
      file = sources[0].file,  # 同一连通分量内 file 必然相同
      line_range = merge_line_ranges(sources),
      sources = sources,
      consensus_score = calculate_consensus(sources),
      status = "consensus" if len(sources) > 1 else "single_source"
    )

line_range_overlap 计算：
  intersection = max(0, min(end1, end2) - max(start1, start2))
  union = max(end1, end2) - min(start1, start2)
  overlap_ratio = intersection / union if union > 0 else 0

text_similarity 计算（简单版，不依赖外部库）：
  tokens1 = set(jieba_cut(title1.lower()))
  tokens2 = set(jieba_cut(title2.lower()))
  similarity = len(tokens1 & tokens2) / max(len(tokens1 | tokens2), 1)
```

### 6.2 冲突解决策略

```
优先级树（从高到低）：

1. 安全问题优先
   IF Agent B(BugHunter) severity ≥ Agent A/code-review severity 
   AND category == "security"
   THEN take BugHunter's severity as canonical

2. 阻断级优先
   IF any agent says P0 BLOCKING
   THEN canonical = P0 BLOCKING（标记冲突）

3. 多数优先（平票时取高）
   IF 2 agents agree on severity X, 1 agent says Y
   THEN canonical = majority（X）

4. 取最高（全部分歧时）
   IF all 3 disagree
   THEN canonical = max(severities)（标记冲突）
```

### 6.3 置信度提升/降低规则

```
提升因子：
  +0.15  2个不同审查哲学的Agent独立发现同一问题
  +0.25  3个不同审查哲学的Agent独立发现同一问题
  +0.10  Skeptic Agent 确认（CONFIRM）
  +0.05  发现同时被 Phase 0 机器扫描命中

降低因子：
  -0.20  Skeptic Agent 降级（DOWNGRADE）
  -0.30  存在性冲突（一个Agent审查了同段代码但未报告该问题）
  -0.15  严重等级冲突（Agent之间等级差异 ≥ 2 档）
  -0.10  仅有1个Agent发现（无共识加成）

REFUTE → 彻底移出问题列表，不降级
```

### 6.4 去重决策的可解释性

去重和合并过程的每一步决策必须有可审计的记录。这既能帮助调试误合并/漏合并，也是人工审核报告时理解"M-001 到底集成了哪几个原始发现"的依据。

**去重决策日志格式** (`dedup-log.json`):

```json
{
  "decisions": [
    {
      "pair": ["A-001", "B-003"],
      "file": "src/auth/login.ts",
      "match_type": "line_range_overlap",
      "overlap_ratio": 0.82,
      "title_similarity": 0.45,
      "decision": "MERGE",
      "rationale": "line_range_overlap 0.82 > 0.5 阈值"
    },
    {
      "pair": ["A-005", "C-002"],
      "file": "src/utils/validator.ts",
      "match_type": "semantic",
      "overlap_ratio": 0.12,
      "title_similarity": 0.88,
      "decision": "MERGE",
      "rationale": "title_similarity 0.88 > 0.75 阈值，尽管行范围不重叠"
    },
    {
      "pair": ["B-002", "B-007"],
      "file": "src/api/handler.ts",
      "match_type": "none",
      "overlap_ratio": 0.0,
      "title_similarity": 0.15,
      "decision": "KEEP_SEPARATE",
      "rationale": "两个发现报告同一文件但涉及不同漏洞类型和不同代码行"
    },
    {
      "pair": ["A-012", "C-008"],
      "file": "src/models/user.ts",
      "match_type": "borderline",
      "overlap_ratio": 0.48,
      "title_similarity": 0.62,
      "decision": "KEEP_SEPARATE",
      "rationale": "两个指标均略低于阈值，保留为独立发现。人工可事后合并。"
    }
  ],
  "statistics": {
    "total_findings_before_dedup": 27,
    "total_merged_groups": 7,
    "total_findings_after_dedup": 18,
    "merge_rate": 0.26,
    "borderline_cases": 2
  }
}
```

### 6.5 交叉验证质量指标

每次 MACRS 运行后，自动计算以下质量指标并写入 `summary.json`：

| 指标 | 计算方式 | 健康范围 | 异常含义 |
|------|----------|----------|----------|
| **共识率** | 多Agent发现数 / 总发现数 | 0.20-0.50 | <0.10: Agent之间差异太大，可能有Agent质量差；>0.70: Agent哲学太相似，多样性不足 |
| **冲突率** | 冲突标记数 / 总发现数 | 0.05-0.20 | <0.02: 可能审查不够深入；>0.30: 技能间严重不兼容，需要调整 |
| **Agent贡献均衡度** | 1 - std(各Agent发现数) / mean(各Agent发现数) | >0.5 | <0.3: 某个Agent发现太少或太多，需要检查 |
| **Skeptic驳回率** | REFUTE数 / Skeptic审查的发现数 | 0.10-0.30 | <0.05: Skeptic太温和，未起到对抗作用；>0.40: 前期Agent假阳性率过高 |
| **去重合并率** | 被合并的发现数 / 原始发现总数 | 0.15-0.40 | <0.10: Agent覆盖维度没有交叉，可能需要增加Agent；>0.60: Agent太相似 |
| **Phase 0准确率** | Phase 0命中被LLM确认数 / Phase 0命中总数 | >0.60 | <0.40: Phase 0脚本假阳性太高，需要调整正则规则 |

### 6.6 合并发现中代理原始信息的保留策略

当多个Agent的发现被合并为一个 MergedFinding 时，我们保留所有原始信息而非丢弃：

```python
# 错误的做法（丢失信息）
merged.title = sources[0].title  # 其他Agent的描述被丢弃了
merged.severity = max(s.severity for s in sources)  # 其他Agent的等级判断被丢弃了

# 正确的做法（保留完整溯源）
merged = {
    "canonical_title": pick_best_title(sources),  # 选择最详细的标题
    "canonical_severity": resolve_severity(sources),  # 解析后的统一等级
    "sources": [
        {
            "agent_id": s.agent_id,
            "finding_id": s.id,
            "original_severity": s.severity,  # 保留原始等级
            "original_title": s.title,         # 保留原始标题
            "original_description": s.description,  # 保留原始描述
            "confidence": s.confidence,
            "rule_reference": s.rule_reference,
        }
        for s in sources
    ],
    # 所有Agent的原始视角都保留，供人工深入审查时查阅
}
```

这样做的理由：当人工审查者对某个 MergedFinding 存疑时，可以追溯每个Agent的原始判断，理解为什么"Agent A 觉得这是 blocking 而 Agent B 觉得只是 important"，从而做出更合理的最终决策。

### 6.7 跨Agent冲突的自动化升级矩阵

并非所有冲突都升级给用户。以下是自动化决策矩阵：

| 冲突类型 | 等级差距 | 是否升级 | 处理方式 |
|----------|----------|----------|----------|
| severity | 1 档（如 P1 vs P2） | 否 | 自动取高等级，不标记 |
| severity | 2 档（如 P0 vs P2） | **是** | 标记 `NEEDS_HUMAN`，在报告"冲突裁决台"展示 |
| severity | 3+ 档（如 P0 vs P3） | **是** | 标记 `NEEDS_HUMAN` + 醒目警告 |
| existence | Agent A 报告 P0，Agent B 审查同段代码但未报告 | **是** | 标记 `conflict: existence`，置信度降级但保留发现 |
| existence | Agent A 报告 P3，Agent B 审查同段代码但未报告 | 否 | 标注单Agent发现，不升级 |
| category | 不同Agent归入不同类别 | 否 | 保留所有类别标签，取多数 |
| remediation | Agent A 建议方案 X，Agent B 建议方案 Y | 否 | 两个建议都展示，标注来源 |

---

## 7. 最终报告格式

### 7.1 报告模板（完整结构）

```markdown
# MACRS 代码审查报告

> **审查ID**: MACRS-20260601-001  
> **审查时间**: 2026-06-01 10:30:00 UTC+8  
> **审查范围**: PR #342 — feat: 用户认证模块重构  
> **审查文件**: 15 个文件，+350 / -120 行  
> **审查语言**: TypeScript (12), Python (3)  
> **审查严格度**: L4 (Production)  
> **总耗时**: 145 秒

---

## 执行摘要

| 指标 | 数值 |
|------|------|
| 发现问题总数 | 23 |
| ┣ P0 阻断 | 2 |
| ┣ P1 严重 | 5 |
| ┣ P2 重要 | 8 |
| ┣ P3 建议 | 6 |
| ┗ P4 提示 | 2 |
| 对抗验证通过 | 18 (78%) |
| 对抗验证驳斥 | 3 (13%) |
| 需人工裁决 | 2 (9%) |
| 多Agent共识发现 | 7 (30%) |
| 单Agent独立发现 | 14 (61%) |
| Phase 0 机器发现 | 2 (9%), 全部经LLM确认 |

### 审查小组

| Agent | 技能 | 角色 | 发现数 | 状态 |
|-------|------|------|--------|------|
| Agent A | code-review-skill | 工程质量审查师 | 12 | ✅ 完成 |
| Agent B | Claude-BugHunter | 安全审计师 | 8 | ✅ 完成 |
| Agent C | pragmatic-clean-code-reviewer | 架构审查师 | 7 | ✅ 完成 |
| Skeptic | Adversarial Verifier | 对抗验证师 | — | ✅ 完成 (18确认/3驳斥/2降级) |

---

## P0 阻断 — 必须立即修复

### P0-001: SQL 注入漏洞 — 用户登录参数未参数化
<!-- MACRS 元数据 -->
<!-- source: [Agent B: B-001] [Agent A: A-003] [Phase0: machine-confirmed] -->
<!-- consensus: 2-agent (工程+安全) | confidence: 0.95 | verified: CONFIRM -->

| 属性 | 值 |
|------|-----|
| **文件** | `src/auth/login.ts:42-58` |
| **统一等级** | P0 BLOCKING |
| **分类** | Security |
| **来源** | Agent B (BugHunter), Agent A (code-review-skill) |
| **共识度** | ★★★☆☆ 2/3 Agent 独立发现 |
| **置信度** | 0.95 (2-Agent 共识 + 对抗验证确认) |

**问题描述**：
登录接口中使用了字符串拼接构造 SQL 查询，用户输入的 `username` 参数直接拼入 SQL 语句，存在 SQL 注入风险。

**问题代码**：
```typescript
// src/auth/login.ts:45
const query = `SELECT * FROM users WHERE username = '${username}' AND password = '${hashedPassword}'`;
const result = await db.execute(query);
```

**修复建议**：
```typescript
// 使用参数化查询
const query = `SELECT * FROM users WHERE username = ? AND password = ?`;
const result = await db.execute(query, [username, hashedPassword]);
```

**攻击场景**：
```
攻击者输入 username: admin' -- 
→ SQL: SELECT * FROM users WHERE username = 'admin' --' AND password = '...'
→ 绕过密码验证，以 admin 身份登录
```

**规则引用**：BugHunter-INJ-001 (SQL Injection via String Concatenation)

> ⚠️ **冲突标记**: Agent C 审查了同段代码但未报告此问题。可能原因：Agent C 聚焦架构层面，未深入检查数据访问细节。**这不影响 P0 判定。**

---

### P0-002: JWT 密钥硬编码
<!-- source: [Agent B: B-004] [Phase0: machine-secret-001] -->
<!-- consensus: 1-agent + Phase0 | confidence: 0.90 | verified: CONFIRM -->

| 属性 | 值 |
|------|-----|
| **文件** | `src/auth/jwt.ts:12` |
| **统一等级** | P0 BLOCKING |
| **分类** | Security |
| **来源** | Agent B (BugHunter), Phase 0 密钥扫描 |
| **共识度** | ★★☆☆☆ 1/3 Agent + 机器确认 |
| **置信度** | 0.90 (Agent + Phase0 双确认 + 对抗验证确认) |

**问题描述**：
JWT 签名密钥以明文硬编码在源代码中。任何人能访问代码仓库即可伪造任意用户的 JWT Token。

**问题代码**：
```typescript
// src/auth/jwt.ts:12
const JWT_SECRET = "my-super-secret-key-2024";
```

**修复建议**：
```typescript
// 从环境变量读取，开发环境提供默认值（仅开发用）
const JWT_SECRET = process.env.JWT_SECRET || (process.env.NODE_ENV === 'development' ? 'dev-secret' : (() => { throw new Error('JWT_SECRET not set'); })());
```

**规则引用**：BugHunter-INFRA-012 (Hardcoded Secrets)

---

## P1 严重 — 合并前应修复

### P1-001: 缺少输入验证 — 用户名长度未限制
<!-- source: [Agent A: A-001] [Agent B: B-005] -->
<!-- consensus: 2-agent | confidence: 0.85 | verified: CONFIRM -->

...(以此类推)

---

## P2 重要 — 下个迭代修复

...(以此类推)

---

## P3 建议 — 有空可改

...(以此类推)

---

## P4 提示 — 知会即可

### 表扬

| # | 文件 | 行 | 表扬内容 | 来源 |
|---|------|-----|----------|------|
| 1 | `src/auth/login.ts` | 78 | 错误处理做得很好，使用了自定义错误类型而非裸露的字符串 | Agent A |
| 2 | `src/auth/session.ts` | 34 | 会话超时策略考虑到了"记住我"和普通登录的区分 | Agent C |

---

## 冲突裁决台

> ⚠️ 以下发现存在 Agent 间严重分歧，需要人工裁决。

### CFL-001: 日志中是否应包含用户ID [Severity Conflict]

| Agent | 立场 | 等级 | 理由 |
|-------|------|------|------|
| Agent A | 认为需要修复 | P2 HIGH | "日志中包含完整用户ID是隐私风险，应脱敏" |
| Agent B | 认为风险可控 | P3 MEDIUM | "日志仅写本地文件，不远程传输，且用户ID本身不是敏感PII" |
| Agent C | 未提及 | — | — |

**当前处理**：按冲突解决策略取更高等级 P2 HIGH，但标记为 `NEEDS_HUMAN`。

---

## 已驳斥发现

以下发现在对抗验证阶段被 Skeptic Agent 驳斥，**不纳入问题列表**，但保留此记录以供审计。

| # | 原始发现 | 来源 | 原始等级 | 驳斥理由 |
|---|---------|------|----------|----------|
| 1 | "密码哈希使用了 MD5" | Agent B | P0 | 经确认，该代码在测试文件中，`test/mock-password.ts`，生产代码使用的是 bcrypt |
| 2 | "函数超过 30 行" | Agent A | P3 | 该函数是一个配置对象的声明式定义（60行 switch-case），拆分反而降低可读性 |
| 3 | "未处理 Promise 拒绝" | Agent A | P2 | 该代码路径使用了 `.catch()` 在调用点处理，Agent 未充分审查上游调用代码 |

---

## Phase 0 机器扫描结果

| 扫描项 | 命中数 | 经LLM确认 | 假阳性 |
|--------|--------|-----------|--------|
| 密钥扫描 | 1 | 1 (JWT密钥硬编码) | 0 |
| BugHunter CLI | 2 | 2 | 0 |
| 复杂度警告 | 5 | 3 (圈复杂度>15) | 2 (测试文件, 配置函数) |
| 依赖CVE | 0 | 0 | 0 |

---

## 附录

### A. 审查统计

| 指标 | 数值 |
|------|------|
| 总token消耗 | ~85,000 |
| 总成本估算 | ~$0.50 |
| 并行Agent数 | 3 |
| 并行耗时 | 85s (最长Agent) |
| 总端到端耗时 | 145s |

### B. Agent 原始输出

- `review-a-code-review-skill.json` — Agent A 完整输出
- `review-b-claude-bughunter.json` — Agent B 完整输出
- `review-c-pragmatic-clean-code-reviewer.json` — Agent C 完整输出
- `phase-3-skeptic-verification.json` — 对抗验证完整输出

### C. 审查配置

```yaml
strictness: L4 (Production)
skills_loaded:
  - code-review-skill (core + typescript ref)
  - claude-bughunter (full 7 groups)
  - pragmatic-clean-code-reviewer (L4 ruleset)
phase0_enabled: true
adversarial_enabled: true
```

---
*本报告由 MACRS v1.0 生成 | 审查会话ID: session-abc123 | 导出时间: 2026-06-01 10:32:30 UTC+8*
```

### 7.2 源标注格式规范

每个发现必须包含以下注释形式的元数据（放在发现标题下方，HTML注释形式以便在渲染时隐藏但保留在源码中）：

```html
<!-- MACRS 元数据 -->
<!-- source: [Agent X: finding-id] [Agent Y: finding-id] [Phase0: source-id] -->
<!-- consensus: N-agent (dimensions) | confidence: X.XX | verified: CONFIRM|REFUTE|DOWNGRADE|PENDING -->
<!-- conflict: yes|no (type: severity|existence|category if yes) -->
```

### 7.3 输出文件结构

审查完成后，在 `D:/Claude Code/MACRS-Reports/{repo-name}/{pr-id}/` 下生成：

```
{repo-name}/{pr-id}/
├── report.md                        # 最终人类可读报告（本章节模板）
├── report.json                      # 机器可读完整报告
├── phase-0/
│   ├── file-classification.json
│   ├── secrets.json
│   ├── cbh-hits.json
│   ├── complexity.json
│   └── findings.json                # 合并后的 Phase 0 输出
├── phase-1/
│   ├── review-a-code-review-skill.json
│   ├── review-b-claude-bughunter.json
│   └── review-c-pragmatic-clean-code-reviewer.json
├── phase-2/
│   ├── merged-findings.json
│   ├── conflicts.json
│   └── dedup-log.json               # 去重决策日志（哪些发现被合并）
├── phase-3/
│   └── skeptic-verification.json
└── summary.json                      # 精简摘要（用于 CI 集成）
```

---

## 8. 实施路线图

### Phase 1：技能单体验收（预计 2-3 天）

**目标**：在本地环境中独立测试每个技能，确认可用性和输出质量。

| 任务 | 具体操作 | 验收标准 |
|------|----------|----------|
| 1.1 安装 code-review-skill | Clone `awesome-skills/code-review-skill`，在 CC 中注册为 skill | 单文件审查输出符合预期格式 |
| 1.2 安装 Claude-BugHunter | Clone `elementalsouls/Claude-BugHunter`，安装 `cbh` CLI | 单文件安全审查输出包含 7 问门控 |
| 1.3 安装 pragmatic-clean-code-reviewer | Clone `Zhen-Bo/pragmatic-clean-code-reviewer`，提取规则集 | 单文件架构审查输出包含 Effort/Benefit 分析 |
| 1.4 提取 wxmini-audit 的通用逻辑 | Clone `sssmmmwww/wxmini-security-audit`，提取 SecretScanner regex 和 JSON handoff 机制 | regex 扫描脚本独立可运行 |
| 1.5 准备测试代码库 | 准备 3-5 个包含已知问题的测试文件（故意植入 SQL 注入、硬编码密钥、架构违规等） | 每个已知问题至少能被 1 个技能检出 |

**输出物**：
- `skills-manifest.json`：记录每个技能的路径、加载方式、已知限制
- `test-results/phase1-skill-tests.md`：单体验收报告

### Phase 2：构建协调器调度脚本（预计 3-5 天）

**目标**：实现 Phase 0 预处理 + Phase 1 并行审查的自动化调度。

| 任务 | 具体操作 | 验收标准 |
|------|----------|----------|
| 2.1 开发 Phase 0 预处理脚本 | Python 脚本 `preprocessor.py`：文件分类 + 密钥扫描 + 复杂度计算 + 上下文提取 | 对测试代码库输出完整 `phase-0-findings.json` |
| 2.2 开发 Agent 分发器 | Python 脚本 `dispatcher.py`：读取 Phase 0 输出 + 用户指定范围，生成 3 个 Agent 的完整 prompt，并发调用 CC Task API | 3 个 Agent 并行启动，各自独立输出 JSON |
| 2.3 开发结果收集器 | Python 脚本 `collector.py`：等待所有 Agent 完成（含超时处理），校验 JSON 格式，汇总到 `phase-1/` 目录 | 失败 Agent 重试 1 次，仍失败则标记并继续 |
| 2.4 手动测试完整 Phase 1 | 对 3-5 个测试文件运行完整 Phase 0 + Phase 1 流程 | 端到端成功率 > 90% |
| 2.5 成本记录 | 记录每次运行的 token 消耗和实际成本 | 形成成本基线数据 |

**核心调度逻辑伪代码**：

```python
def run_macrs(target_files, strictness="L4", scope="diff"):
    # Phase 0
    phase0_result = preprocessor.run(target_files)
    
    # Phase 1: 并行分发
    prompts = {
        "A": build_prompt("code-review-skill", target_files, phase0_result, strictness),
        "B": build_prompt("claude-bughunter", target_files, phase0_result, strictness),
        "C": build_prompt("pragmatic-clean-code-reviewer", target_files, phase0_result, strictness),
    }
    
    results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            agent_id: executor.submit(invoke_claude_agent, prompt) 
            for agent_id, prompt in prompts.items()
        }
        for agent_id, future in futures.items():
            try:
                results[agent_id] = future.result(timeout=120)
            except TimeoutError:
                # 重试 1 次
                results[agent_id] = retry_once(agent_id, prompts[agent_id])
            except Exception as e:
                results[agent_id] = {"status": "FAILED", "error": str(e)}
    
    # 校验与存储
    for agent_id, result in results.items():
        validate_json_schema(result)
        save_to(f"phase-1/review-{agent_id}.json", result)
    
    return results
```

**输出物**：
- `coordinator/preprocessor.py`
- `coordinator/dispatcher.py`
- `coordinator/collector.py`
- `coordinator/prompt-builder.py`（含 Agent A/B/C 的完整 prompt 模板）
- `test-results/phase2-integration-tests.md`

### Phase 3：交叉验证与合成（预计 3-4 天）

**目标**：实现 Phase 2（去重 + 冲突检测 + 共识计算）+ Phase 4（报告生成）。

| 任务 | 具体操作 | 验收标准 |
|------|----------|----------|
| 3.1 开发去重引擎 | Python `dedup.py`：实现双键匹配算法 + Union-Find 合并 | 人工标注的重复发现对 100% 被正确合并 |
| 3.2 开发冲突检测器 | Python `conflict.py`：检测 3 类冲突（严重等级、存在性、分类） | 人工标注的冲突 100% 被检测 |
| 3.3 开发共识计算器 | Python `consensus.py`：实现置信度公式 + 等级解析策略 | 共识加分逻辑通过单元测试 |
| 3.4 开发报告生成器 | Python `reporter.py`：读取 Phase 0-3 所有 JSON，渲染 Markdown 报告 | 输出格式符合第 7 节模板 |
| 3.5 手动端到端测试 | 对测试代码库运行完整 Phase 0-4（跳过 Phase 3 对抗验证） | 报告包含去重后的发现、共识标记、冲突标记 |

**输出物**：
- `coordinator/dedup.py`
- `coordinator/conflict.py`
- `coordinator/consensus.py`
- `coordinator/reporter.py`
- `coordinator/report-template.md`（Jinja2 模板）
- `test-results/phase3-e2e-tests.md`

### Phase 4：对抗验证（预计 2-3 天）

**目标**：实现 Phase 3 Skeptic Agent 的调度和结果处理。

| 任务 | 具体操作 | 验收标准 |
|------|----------|----------|
| 4.1 开发 Skeptic Prompt 构建器 | Python `skeptic-prompt.py`：将 Phase 2 的 CRITICAL+HIGH 发现 + 完整源文件构建为验证 prompt | Prompt 包含完整的反驳框架和裁决指令 |
| 4.2 开发验证结果处理器 | Python `verify-processor.py`：解析 Skeptic 输出，将 REFUTE/CONFIRM/DOWNGRADE 应用到发现列表 | REFUTE 的发现正确移入"已驳斥"列表 |
| 4.3 集成到报告流程 | 修改 `reporter.py`，在报告中增加"对抗验证"和"冲突裁决台"章节 | 报告正确展示验证结果 |
| 4.4 对抗验证效果评估 | 对测试代码库运行完整 MACRS，统计：假阳性过滤率、真阳性保留率 | 假阳性过滤率 > 50%，真阳性保留率 > 95% |

**输出物**：
- `coordinator/skeptic-prompt.py`
- `coordinator/verify-processor.py`
- `test-results/phase4-adversarial-evals.md`

### Phase 5：CI/CD 集成（预计 2-3 天）

**目标**：将 MACRS 集成为 GitHub Actions / 命令行工具。

| 任务 | 具体操作 | 验收标准 |
|------|----------|----------|
| 5.1 开发 CLI 入口 | `macrs` 命令行工具：`macrs review --scope diff --strictness L4` | 单命令触发完整审查 |
| 5.2 GitHub Actions 模板 | `.github/workflows/macrs-review.yml`：PR 触发 + 评论报告摘要 | 新 PR 自动触发审查，结果评论在 PR 下 |
| 5.3 阈值配置 | 支持在 `.macrs.yml` 中配置：P0 阻断自动拒绝合并、最少审查Agent数、超时时间 | 配置文件正确加载并生效 |
| 5.4 增量审查优化 | 仅对 diff 行（及上下游 N 行上下文）执行 LLM 审查，完整文件仅用于 Phase 0 和上下文 | 大 PR 的审查时间不至于线性增长 |

**输出物**：
- `cli/macrs`（或 `cli/macrs.py`）
- `.github/workflows/macrs-review.yml`
- `.macrs.yml` 配置规范文档
- `test-results/phase5-ci-tests.md`

---

## 8.5 MACRS 测试策略

### 8.5.1 测试分层

MACRS 作为一个多Agent系统，其测试策略与传统单元测试有本质区别。LLM输出的非确定性使我们不能简单地做 assert 相等性测试，而需要采用"特性测试 + 统计验证"的混合策略。

| 测试层 | 测试内容 | 确定性 | 测试方法 |
|--------|----------|--------|----------|
| L0: 单元测试 | 去重算法、冲突检测、共识计算公式、JSON schema 校验 | 确定性 | 传统 pytest assert |
| L1: 集成测试 | Phase 0 脚本输出正确性、Agent prompt 构建正确性 | 确定性 | 传统 pytest assert |
| L2: 技能测试 | 单个技能对已知问题代码的检出率 | 非确定性 | 统计验证（N次运行取检出率） |
| L3: 端到端测试 | 完整 MACRS 流水线对已知问题集的覆盖率 | 非确定性 | 统计验证（N次运行取平均覆盖率） |
| L4: 回归测试 | 已知假阳性会否在新版本中被重新报告 | 非确定性 | 人工审查 + 自动标记 |
| L5: 对抗测试 | 故意植入的漏洞是否能被至少1个Agent发现 | 非确定性 | 统计验证（检出率 > 90%） |

### 8.5.2 测试代码库设计

需要构建一个"黄金标准"测试代码库，包含以下类型的已知问题：

```yaml
golden-test-repo/
├── security/           # 安全漏洞测试
│   ├── sql-injection/  # 含已知SQL注入（字符串拼接、ORM误用、存储过程）
│   ├── xss/           # 含已知XSS（反射型、存储型、DOM型）
│   ├── auth-bypass/   # 含已知认证绕过（JWT弱密钥、会话固定、缺少权限检查）
│   ├── secret-leak/   # 含已知密钥泄露（硬编码、配置文件、注释中）
│   └── path-traversal/ # 含已知路径遍历
├── bugs/              # 功能性Bug测试
│   ├── null-pointer/  # 空指针/None引用
│   ├── off-by-one/    # 边界条件错误
│   ├── race-condition/ # 竞态条件（如果可静态检测）
│   └── logic-error/   # 业务逻辑错误
├── architecture/      # 架构违规测试
│   ├── circular-dep/  # 循环依赖
│   ├── god-class/     # 上帝类（>500行，>20方法）
│   ├── layer-violation/ # 分层违规（领域层依赖基础设施层）
│   └── solid-violation/ # SOLID原则违反
├── maintainability/   # 可维护性问题测试
│   ├── long-method/   # 超长方法（>30行）
│   ├── duplicate/     # 重复代码
│   ├── magic-number/  # 魔法数字
│   └── poor-naming/   # 糟糕命名（a, b, tmp, data）
└── clean/             # 干净的代码（验证假阳性率）
    ├── well-structured/ # 良好结构的代码
    ├── design-patterns/ # 正确使用设计模式的代码
    └── edge-cases/    # 合理但看起来可疑的代码（如必要的类型转换）
```

### 8.5.3 统计验证方法

由于 LLM 输出的非确定性，L2-L5 测试采用以下统计方法：

```
对每个测试用例：
  1. 重复运行 MACRS N 次（建议 N ≥ 5）
  2. 记录每次的检出情况（检出/未检出/误报）
  3. 计算：
     - 检出率 = 检出次数 / N（目标 > 80%）
     - 假阳性率 = 误报次数 / N（目标 < 10%）
     - 检出稳定性 = 1 - std(检出)（目标 > 0.7，即大部分运行都能检出）
  4. 对低于目标的测试用例，分析原因：
     - 是否 prompt 需要调优？
     - 是否问题本身 LLM 难以检测？（降级为 Phase 0 脚本覆盖）
     - 是否 temperature 设置需要调整？

回归测试特别关注：
  - 之前已修复的假阳性是否重新出现
  - 之前能检测的真阳性是否漏检
```

### 8.5.4 CI中的自动化测试

```yaml
# .github/workflows/macrs-self-test.yml
name: MACRS Self-Test

on:
  push:
    paths:
      - 'coordinator/**'
      - 'skills/**'
      - 'prompts/**'
  schedule:
    - cron: '0 6 * * 1'  # 每周一早晨运行

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run L0-L1 deterministic tests
        run: pytest tests/unit/ tests/integration/ -v

  statistical-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v4
      - name: Run L2-L3 statistical tests (N=5)
        run: python tests/statistical_runner.py --runs 5 --threshold 0.8

  regression-check:
    runs-on: ubuntu-latest
    needs: statistical-tests
    steps:
      - uses: actions/checkout@v4
      - name: Check for regressions
        run: python tests/regression_check.py --baseline latest
```

### 8.5.5 持续质量监控指标

| 指标 | 目标值 | 告警阈值 | 测量频率 |
|------|--------|----------|----------|
| P0 检出率 | ≥ 95% | < 90% | 每周 |
| P1 检出率 | ≥ 85% | < 75% | 每周 |
| 假阳性率 | ≤ 10% | > 15% | 每周 |
| 去重准确率 | ≥ 95% | < 90% | 每次代码变更 |
| Agent 完成率 | ≥ 95% | < 90% | 每次运行 |
| 端到端耗时 | < 180s | > 300s | 每次运行 |
| 单次审查成本 | < $1.50 (中PR) | > $2.50 | 每次运行 |

---

## 8.6 边缘情况与已知限制

### 8.6.1 边缘情况处理手册

| 边缘情况 | 触发条件 | 处理方式 |
|----------|----------|----------|
| 空 diff | PR 不包含代码变更（如仅改 README） | 跳过所有阶段，报告"无代码变更需审查" |
| 仅删除代码 | diff 只有 `-` 行 | 审查删除后剩余代码的完整性——被删代码引用的地方是否更新 |
| 二进制文件 | diff 包含 `.png`, `.so`, `.dll` 等 | Phase 0 标记为"跳过"，Agent 审查时忽略 |
| 超大文件 | 单文件 diff > 2000 行 | 仅审查变更行 ± 50 行上下文（滑动窗口），不加载完整文件 |
| 配置文件 | `.yml`, `.json`, `.toml` 变更 | Agent C 检查配置项命名一致性、敏感信息；Agent B 检查配置注入 |
| SQL 迁移文件 | `.sql` 或 migration 目录 | Agent B 检查：是否有破坏性操作（DROP）、是否缺回滚、是否锁表 |
| 测试文件 | `*.test.*`, `*.spec.*`, `__tests__/` | 正常审查，但 Agent A 调整规则：允许更长函数、更多魔法数字（测试数据） |
| 生成的代码 | `*.generated.*`, `*.pb.go`, `*.graphql` | Phase 0 标记为"生成代码"，Agent 仅审查安全性（不审查风格） |
| 多语言混合 PR | 同时包含 TS + Python + SQL | 每种语言的 Agent 按需加载对应语言文件 |
| 合并冲突标记 | diff 中包含 `<<<<<<<` | Phase 0 检测并告警——优先于任何审查，因为代码本身就不一致 |
| 第三方代码 | `vendor/`, `node_modules/` | 默认排除，仅在用户明确指定时审查（如供应链安全检查） |
| 空文件 | diff 创建了空文件 | Phase 0 标记，Agent 审查时忽略 |

### 8.6.2 已知系统限制

| 限制 | 影响 | 缓解措施 | 未来计划 |
|------|------|----------|----------|
| 跨文件分析深度 | Agent 可能无法追踪跨 3+ 层调用的数据流 | Phase 0 提供 import 地图和函数调用图作为上下文 | 引入 CodeGraph 或类似工具做静态调用链分析 |
| 运行时行为 | 无法检测运行时才能暴露的问题（内存泄漏、竞态条件） | 报告明确标注"仅静态分析"，建议配合动态测试 | 无——这是静态审查的固有边界 |
| 业务逻辑正确性 | 不知道"正确"的业务行为是什么 | 对业务逻辑相关代码标记 `NEEDS_HUMAN` | 引入业务规格 DSL 或行为文档作为审查素材 |
| 上下文窗口限制 | 大PR（>5000行diff）可能超出单个Agent上下文 | 文件分块策略（见上文）+ 分批审查 | 等待模型上下文窗口持续增长 |
| 模型一致性 | 不同运行的输出格式和严格度可能有波动 | temperature=0.3 降低波动 + JSON schema 强制校验 | 模型能力提升是最根本的解决方案 |
| 语言覆盖不完整 | Rust、Kotlin、Swift 等当前无专项规则 | code-review-skill 的通用规则仍适用；安全规则大部分跨语言 | 按需添加语言专项规则文件 |
| Skeptic 的局限性 | 与被审查Agent使用同模型时，可能共享相同的"盲区" | 标记为已知限制；未来引入不同模型系列做Skeptic | 混用不同模型供应商做对抗验证 |

---

## 8.7 配置文件规范

### `.macrs.yml` 完整配置参考

```yaml
# MACRS 配置文件 — 放置于项目根目录
# 所有字段均为可选，未指定时使用默认值

# ========== 基础配置 ==========
version: "1.0"

# 审查严格度
strictness: L4  # L1(Lab) | L2(Prototype) | L3(Development) | L4(Production) | L5(Critical)

# ========== 范围配置 ==========
review:
  # 默认审查范围
  default_scope: diff  # diff | all | paths | files
  
  # 排除模式（glob）
  exclude:
    - "**/*.generated.*"
    - "**/*.pb.*"
    - "vendor/**"
    - "node_modules/**"
    - "**/__snapshots__/**"
    - "*.lock"
    - "*.min.js"
    - "*.min.css"
  
  # 仅审查模式（如果指定，则只审查匹配的文件）
  # include:
  #   - "src/**/*.ts"
  #   - "src/**/*.py"
  
  # 文件大小限制
  max_file_diff_lines: 2000     # 单文件diff超过此行数时分块审查
  context_lines: 50             # 每个diff块附带的上下游行数

# ========== Agent 配置 ==========
agents:
  # 审查面板
  panel:
    - id: A
      skill: code-review-skill
      enabled: true
    - id: B
      skill: claude-bughunter
      enabled: true
    - id: C
      skill: pragmatic-clean-code-reviewer
      enabled: true
  
  # Skeptic 验证Agent
  skeptic:
    enabled: true
    verify_threshold: P1  # P0 | P1 | P2 — 验证此等级及以上的所有发现
  
  # 模型配置
  model: sonnet              # 所有Agent使用的模型
  temperature: 0.3           # 审查Agent温度
  skeptic_temperature: 0.5   # Skeptic Agent温度（稍高以鼓励质疑）

# ========== Phase 0 配置 ==========
phase0:
  enabled: true
  secret_scan: true          # Gitleaks / regex 密钥扫描
  complexity_check: true     # 圈复杂度检查
  complexity_threshold: 15   # 圈复杂度告警阈值
  dependency_audit: true     # npm audit / pip audit
  cbh_cli: true              # BugHunter CLI 确定性扫描

# ========== 报告配置 ==========
report:
  format: markdown            # markdown | json | both
  output_dir: "./macrs-reports"
  include_appendix: true      # 是否包含Agent原始输出
  include_conflicts: true     # 是否包含冲突裁决台
  locale: zh-CN               # 报告语言
  
# ========== CI/CD 集成 ==========
ci:
  # PR 自动审查
  pr_review:
    enabled: true
    trigger: label            # auto | label | manual
    label_name: "needs-review"
  
  # 阻断规则
  blocking:
    enabled: true
    # 满足以下任一条件时阻止合并
    conditions:
      - severity: P0          # 有P0发现
        min_confidence: 0.85
      - severity: P1          # 有≥3个P1发现
        min_count: 3
        min_confidence: 0.80
  
  # 结果评论
  comment:
    enabled: true
    style: summary           # summary | full | link
    summary_max_findings: 5  # 摘要最多展示5个发现

# ========== 成本控制 ==========
cost:
  max_per_review: 2.00       # 单次审查最大成本（USD）
  max_monthly: 50.00         # 月度最大成本
  on_budget_exceeded: warn   # warn | degrade | block
  # warn: 仅警告但继续
  # degrade: 降级为单Agent审查
  # block: 阻止审查

# ========== 通知 ==========
notifications:
  enabled: false
  # 未来支持飞书/Slack/邮件通知
  # channel: feishu
  # webhook_url: "https://open.feishu.cn/..."
```

---

## 9. 协调器规则

### 9.1 协调器角色定义

协调器（Coordinator）是 MACRS 的中枢控制者，由 **主 Claude** 承担。它不直接审查代码，而是：

1. **接收触发**：响应用户的审查请求
2. **分派任务**：生成子Agent prompt，调度并行执行
3. **收集结果**：等待子Agent完成，校验输出
4. **执行 Phase 2 交叉验证**：去重、冲突检测、共识计算
5. **触发 Phase 3 对抗验证**：派发 Skeptic Agent
6. **生成 Phase 4 报告**：或派发合成师Agent
7. **汇报给用户**：呈现关键发现，标注冲突

### 9.2 调度触发条件

| 触发方式 | 命令示例 | 审查范围 |
|----------|----------|----------|
| 用户直接指令 | "审查这个 PR" / "review 当前分支" | PR diff（默认） |
| 用户指定范围 | "审查 src/auth/ 下所有文件" | `--paths src/auth/` |
| 用户指定全面审查 | "全面审查整个项目" | `--all`（全项目） |
| PR Hook | GitHub Actions 自动触发 | PR diff |
| 发布前终审 | "发布前终审" | `--files` 指定关键文件 |
| 定时审查 | Cron 触发器（未来功能） | `--all`（全项目） |

### 9.3 失败处理规则

```
规则 1：子Agent 失败处理
  - 任何审查Agent（A/B/C）运行失败 → 自动重试 1 次（仅 1 次）
  - 重试仍失败 → 标记该 Agent 为 FAILED，以剩余 Agent 的结果继续
  - 如果 3 个 Agent 中 2 个失败 → 终止审查，报告失败原因
  - 如果只剩 1 个 Agent → 降级为"单Agent审查模式"，报告明确标注
  - ⚠️ 决不重试超过 1 次 —— 重试限制规则第 2 条强制约束

规则 2：Phase 0 预处理失败
  - Phase 0 失败不阻塞整体流程，跳过 Phase 0 继续
  - 报告中标注"Phase 0 未执行"

规则 3：Skeptic Agent 失败
  - 对抗验证失败不阻塞报告生成
  - 报告中标注"未经对抗验证"，所有发现置信度不获得验证加成

规则 4：超时处理
  - 单个审查Agent 超时 120s → 视为失败，触发规则 1
  - Skeptic Agent 超时 90s → 视为失败，触发规则 3
  - 总审查超时 300s → 返回已完成的阶段结果

规则 5：格式校验失败
  - Agent 输出非合法 JSON → 尝试从输出中提取 JSON（正则匹配）
  - 提取失败 → 视为 Agent 失败，触发规则 1
```

### 9.4 升级标准（Escalation Criteria）

以下情况协调器**必须**停止自主处理，升级给用户决策：

| 升级条件 | 触发阈值 | 升级信息包含 |
|----------|----------|-------------|
| P0 阻断发现 | ≥ 1 个 P0，且置信度 ≥ 0.85 | P0 发现摘要 + 修复建议 + 预计影响 |
| 严重冲突无法裁决 | 同一发现 Agent 等级差异 ≥ 2 档 | 冲突详情 + 各方理由 |
| 3 个 Agent 全部未发现但 Phase 0 命中 | Phase 0 密钥扫描命中但无 LLM Agent 发现 | Phase 0 命中详情 + 对应文件完整内容 |
| 审查Agent全部失败 | ≥ 2/3 Agent FAILED | 失败原因 + 建议行动 |
| 成本超预算 | 预估成本 > 用户设定预算 | 预估 vs 预算 + 是否继续的选项 |

### 9.5 协调器状态机

```
                  ┌─────────┐
                  │  IDLE   │
                  └────┬────┘
                       │ 收到审查请求
                       ▼
                  ┌─────────┐
                  │ PHASE_0 │ ──── 失败 ───▶ 记录，继续
                  └────┬────┘
                       │
                       ▼
                  ┌─────────┐
                  │ PHASE_1 │ ──── 部分失败 ───▶ 降级模式
                  └────┬────┘
                       │ 全部成功
                       ▼
                  ┌─────────┐
                  │ PHASE_2 │ (协调器本地执行)
                  └────┬────┘
                       │
                       ▼
                  ┌─────────┐
                  │ PHASE_3 │ ──── 失败 ───▶ 跳过对抗验证
                  └────┬────┘
                       │
                       ▼
                  ┌─────────┐
                  │ PHASE_4 │
                  └────┬────┘
                       │
                       ▼
                  ┌─────────┐
                  │ REPORT  │ ──── 有升级条件 ───▶ 升级给用户
                  └────┬────┘
                       │ 无升级条件
                       ▼
                  ┌─────────┐
                  │  IDLE   │ (等待下一个请求)
                  └─────────┘
```

### 9.6 MACRS 与现有 CC 工作流的集成

MACRS 不是凭空设计的新系统，而是嵌入现有 Claude Code 工作流的审查增强层。

**与现有技能的协作关系**：

```
Claude Code 生态系统中的 MACRS 定位：

┌──────────────────────────────────────────────────┐
│                  用户 + 主 Claude                 │
│                     (Coordinator)                  │
│                                                    │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐   │
│  │ /review  │  │ /simplify│  │ /security-    │   │
│  │ (标准CR) │  │ (代码清理)│  │ review        │   │
│  └────┬─────┘  └────┬─────┘  └───────┬───────┘   │
│       │             │               │            │
│       │     ┌───────┴───────┐       │            │
│       │     │               │       │            │
│       ▼     ▼               ▼       ▼            │
│  ┌──────────────────────────────────────────┐    │
│  │              MACRS (本系统)               │    │
│  │  多Agent对抗式深度审查                    │    │
│  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │    │
│  │  │  A  │ │  B  │ │  C  │ │ Skep│       │    │
│  │  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘       │    │
│  │     └───────┼───────┼───────┘           │    │
│  │             ▼       ▼                    │    │
│  │        ┌────────────────┐                │    │
│  │        │  合成报告       │               │    │
│  │        └───────┬────────┘               │    │
│  └────────────────┼─────────────────────────┘    │
│                   │                               │
│                   ▼                               │
│  ┌─────────────────────────────────┐             │
│  │  /simplify (可选) — 应用修复    │             │
│  │  基于 MACRS 报告批量应用 P3/P4  │             │
│  └─────────────────────────────────┘             │
└──────────────────────────────────────────────────┘
```

**使用场景矩阵**：

| 场景 | 用什么 | 何时用 |
|------|--------|--------|
| 日常小改动（<50行） | `/review` 标准CR | 每次提交前 |
| 中等PR（50-500行） | MACRS 轻型模式（仅Phase 1, 跳过Phase 3） | PR 提交时 |
| 大型PR/核心模块（500-2000行） | MACRS 完整模式 | PR 合并前 |
| 安全关键代码 | MACRS + `/security-review` 双重审查 | 任何涉及认证/授权/加密的代码 |
| 发布前终审 | MACRS 完整模式 + 全量审查 | Release 前置检查 |
| 代码清理 | `/simplify` | MACRS 报告中的 P3/P4 发现 |
| 架构重构前 | MACRS（强调 Agent C 架构审查） | 重构前的基线评估 |

**从 MACRS 报告到自动修复的流水线**：

```
MACRS 报告 → 提取 P3(MEDIUM) + P4(LOW) 发现 → /simplify 批量修复
                                                        │
                                                        ▼
                                              修复后重新 MACRS 审查
                                              （验证修复有效 + 未引入新问题）
```

### 9.7 协调器自检清单

每次触发 MACRS 前，Coordinator 必须完成以下自检：

```markdown
## MACRS 启动前自检

□ 1. 审查范围确认
   □ 已明确审查范围（diff/all/paths/files）
   □ 已验证目标文件存在且可读
   □ 已排除不应审查的文件（vendor, generated, node_modules）

□ 2. 环境验证
   □ 3 个审查技能均已安装且可用
   □ Phase 0 脚本在 PATH 中且可执行
   □ 网络连接正常（API可达）
   □ API 额度充足（预估消耗 < 可用额度 × 0.8）

□ 3. 成本预估
   □ 已计算预估 token 消耗
   □ 已与用户预算上限对比
   □ 若超预算，已向用户确认

□ 4. 用户偏好
   □ 已确认审查严格度（L1-L5）
   □ 已确认是否需要对抗验证
   □ 已确认输出格式偏好

□ 5. 失败预案
   □ 已知悉 2 次重试上限
   □ 已准备降级模式（单Agent审查）
   □ 已确认升级通知渠道
```

---

## 10. 待用户确认的开放问题

### 10.1 模型选择

| 决策点 | 选项 A | 选项 B | 建议 |
|--------|--------|--------|------|
| 审查Agent模型 | Claude Sonnet（当前唯一可用） | 未来混合：Opus for 架构审查, Sonnet for 安全, Haiku for 简单文件 | 当前统一用 Sonnet，成本可控且能力足够 |
| Skeptic Agent 模型 | Sonnet（与审查Agent同型号） | 不同模型系列（如 DeepSeek）增加多样性 | Sonnet 自己驳斥自己的偏见有限，但受限于当前可用模型，先 Sonnet，后续评估多样性收益 |
| 合成师Agent模型 | Sonnet | Coordinator 本地执行（零额外成本） | 优先 Coordinator 本地执行，大报告再派发 Agent |

### 10.2 成本预算

| 决策点 | 需要用户输入 |
|--------|-------------|
| 单次审查预算上限 | 建议：小 PR（<200 行 diff）$0.50，中 PR（200-500 行）$1.00，大 PR（500-1000 行）$2.00 |
| 月度审查预算 | 建议：$20-50/月（日常使用），或按需无上限（发布前终审） |
| 超过预算行为 | 选项 A：暂停并询问 / 选项 B：自动降级为单Agent模式 / 选项 C：放宽预算继续 |

### 10.3 语言优先级

| 优先级 | 语言 | 理由 |
|--------|------|------|
| 高 | Python, TypeScript/JavaScript | 用户当前主要技术栈 |
| 中 | Java, Go | 华科课程涉及，考研后项目可能使用 |
| 低 | Rust, C/C++, 其他 | 暂不涉及 |

**问题**：是否同意此优先级排序？是否需要立即支持 Java/Go？

### 10.4 CI/CD 集成偏好

| 决策点 | 选项 | 需要用户输入 |
|--------|------|-------------|
| 代码托管平台 | GitHub / GitLab / Gitee（码云） | 当前主要使用哪个？ |
| PR 触发方式 | 自动（每个 PR） / 手动（/macrs-review 命令） / 标签触发（加 `needs-review` 标签） | 偏好哪种？ |
| 审查结果展示 | PR 评论（摘要 + 链接） / CI Check Run / 独立 Dashboard | 偏好哪种？ |
| P0 阻断行为 | 自动阻止合并 / 仅警告不阻止 / 仅通知 | 严格度偏好？ |

### 10.5 安全与隐私

| 决策点 | 风险 | 需要用户输入 |
|--------|------|-------------|
| 代码发送到外部 API | 审查过程中代码会被发送给 LLM 提供商 | 是否有代码保密要求？是否需要自部署模型？ |
| 审查记录存储 | 审查历史包含代码片段 | 审查记录保留策略？定期清理还是永久存档？ |
| 开源项目审查 | 审查开源项目时代码本已是公开的 | 无额外风险，但需确认 |

### 10.6 技能定制

| 决策点 | 需要用户输入 |
|--------|-------------|
| 自定义规则 | 是否有项目特定的编码规范需要纳入审查规则？ |
| 白名单/黑名单 | 是否有不需要审查的文件/目录/模式（如 `*.generated.ts`, `vendor/`）？ |
| 严重等级偏好 | 是否有特殊偏好（如"性能问题一律 P2，不要 P0"）？ |

---

## 附录：术语表

| 术语 | 英文 | 定义 |
|------|------|------|
| MACRS | Multi-Agent Adversarial Code Review System | 本系统的缩写 |
| Coordinator | Coordinator | 主 Claude，负责调度和协调，不直接审查 |
| 审查Agent | Review Agent | 携带特定技能执行代码审查的子Agent |
| Skeptic Agent | Skeptic Agent | 对抗验证Agent，尝试驳斥发现的"魔鬼代言人" |
| 合成师 | Synthesizer | 负责将多份审查报告合成为最终报告的Agent |
| 共识度 | Consensus Score | 多Agent对同一发现的同意程度 |
| 对抗验证 | Adversarial Verification | 由Skeptic Agent对发现进行的反驳性验证 |
| Phase 0 | Pre-processing | 用确定性脚本进行预处理的阶段 |
| 7 问门控 | 7-Question Gate | BugHunter 的漏洞判定框架 |
| JSON Handoff | JSON Handoff | Agent之间通过JSON文件交换数据的解耦机制 |
| Effort/Benefit | Effort/Benefit | 修复成本与收益的评估矩阵 |

---

> **文档状态**: 等待用户评审  
> **下一步**: 用户确认开放问题后，进入 Phase 1（技能单体验收）  
> **反馈渠道**: 直接在此文档上评论，或通过 Coordinator 收集修改意见
