# MACRS 会话工作汇总 & 交接文档

> **会话日期**: 2026-06-01
> **状态**: 架构设计完成，系统已就绪，待首次实测
> **下次接手**: 新 Agent 读此文档即可继续

---

## 一、做了什么

### 1.1 调研阶段（由外部报告输入）

用户提供了 `11-github-code-review-tools.md` 调研报告，覆盖 GitHub 上 100+ 个代码审查相关工具/Skills。

**核心结论**：Claude Code Skills 生态 2025-2026 爆发，代码审查是最热门方向。最有价值的 3 个项目：
- awesome-skills/code-review-skill (825 stars) — 最完整的审查 Skill
- Claude-BugHunter (1420 stars) — 最丰富的漏洞模式库
- crucible (51 stars) — 最创新的多模型对抗审查设计

### 1.2 深度分析阶段（4个子Agent并行）

派出 4 个子 Agent 深入研究每个项目的核心架构，产出 4 份分析报告：

| 研究对象 | 分析重点 | 产出文件 |
|---------|---------|---------|
| code-review-skill | 四阶段流程、渐进加载机制、6级Severity、19+语言指南 | analysis-code-review-skill.md（未写盘，内容在上下文中） |
| Claude-BugHunter | 24漏洞分类、574+模式格式、7问门禁、企业攻击矩阵 | analysis-claude-bughunter.md |
| crucible | 四模型对抗面板、Claude裁判验证、5种审查范围、3种策略 | analysis-crucible.md |
| wxmini-security-audit | 7Agent流水线、脚本+LLM双层架构、文件握手通信 | analysis-wxmini-security-audit.md |

### 1.3 架构设计阶段（合成Agent）

基于 4 份分析，产出完整的架构提案：`architecture-proposal.md`（92KB，2070行，10大章节）

### 1.4 系统搭建阶段

- 在 D:/MACRS/ 创建完整目录结构
- Git clone 4个核心 skill 仓库
- 将文档归档到 D:/MACRS/docs/

---

## 二、当前系统状态

```
D:/MACRS/                              ← MACRS 系统根目录
├── skills/                            ← 4个核心审查技能（封装，仅代码审查专家调用）
│   ├── code-review-skill/       (64 files, 1.1MB)
│   │   ├── SKILL.md                   ← 主入口，四阶段流程定义
│   │   ├── reference/                 ← 19个语言指南 + 6个跨切面指南
│   │   ├── assets/                    ← PR模板、审查清单
│   │   └── scripts/pr-analyzer.py     ← PR复杂度分析脚本
│   │
│   ├── Claude-BugHunter/       (174 files, 5.1MB)
│   │   ├── skills/                    ← 51个漏洞检测技能（SKILL.md格式）
│   │   ├── commands/                  ← 15个slash命令
│   │   ├── docs/disclosed-reports/    ← 15类漏洞披露报告
│   │   └── scripts/cbh.py             ← Python CLI（可用于CI/CD）
│   │
│   ├── pragmatic-clean-code-reviewer/ (46 files, 348KB)
│   │   ├── SKILL.md                   ← 主入口，350+规则
│   │   └── references/                ← Clean Code/Architecture/Pragmatic Programmer 规则库
│   │
│   └── crucible/                (40 files, 4.8MB)
│       ├── skill.md                   ← 主入口，多模型对抗审查流程
│       ├── review-prompts.md          ← 审查提示词模板
│       └── scripts/                   ← orchestrate.py、build_report.py 等
│
├── docs/                              ← 架构文档
│   ├── architecture-proposal.md       (92KB) ← 完整架构提案（必读）
│   ├── analysis-claude-bughunter.md   (40KB)
│   ├── analysis-crucible.md           (40KB)
│   ├── analysis-wxmini-security-audit.md (32KB)
│   └── session-handoff.md             ← 本文件（交接文档）
│
├── reports/                           ← 审查报告输出目录（空，待使用）
└── coordinator/                       ← 调度脚本目录（空，待开发）
```

**残留文件**：`D:/Claude Code/Xun-CC-Panel/11-github-code-review-tools.md` — 原始调研报告（未移动，可保留作参考）

---

## 三、架构设计核心要点

### 3.1 四维审查 + 对抗验证

```
Phase 0: 预处理（脚本层，保证覆盖率）
  ├── semgrep / ESLint 等静态分析工具
  └── 产出：机器可检问题列表（无需AI判断的）

Phase 1: 并行审查（LLM层，保证准确率）
  ├── Agent A [code-review-skill]  → 质量审查报告
  ├── Agent B [Claude-BugHunter]   → 安全审计报告
  └── Agent C [pragmatic-clean-code-reviewer] → 工程原则报告

Phase 2: 交叉验证
  ├── 去重：多Agent发现同一问题 → 置信度提升
  ├── 冲突检测：Agent A说blocking、Agent B说nit → 标记冲突
  └── 置信度评分

Phase 3: 对抗验证（Skeptic Agent）
  ├── 逐条证伪每个发现
  └── 分类：确认/修正/驳回/需人工

Phase 4: 合成报告
  └── 统一Severity × 置信度排序，来源标注，可执行修复方案
```

### 3.2 四个核心武器的分工

| Agent | Skill | 审查维度 | 独特价值 |
|-------|-------|---------|---------|
| **A 质量审查官** | code-review-skill | 代码质量、可维护性 | 19+语言规则、四阶段流程、渐进加载 |
| **B 安全猎人** | Claude-BugHunter | 安全漏洞、攻击面 | 574+真实漏洞模式、7问门禁、企业攻击矩阵 |
| **C 原则法官** | pragmatic-clean-code-reviewer | 工程原则、架构设计 | 350+经典规则、L1-L5严格度、Effort/Benefit分析 |
| **验证官** | 借鉴crucible模式 | 对抗证伪、交叉验证 | Claude读源码逐条确认/驳回，降低误报 |

### 3.3 Severity 统一映射

| code-review-skill | BugHunter | pragmatic | crucible | **统一等级** |
|-------------------|-----------|-----------|----------|------------|
| [blocking] | Critical | L5 Critical | critical | **P0 阻塞** |
| [important] | High | L4 Serious | high | **P1 重要** |
| [nit] | Medium | L3 Moderate | medium | **P2 一般** |
| [suggestion] | Low | L2 Minor | low | **P3 建议** |
| [learning]/[praise] | Info | L1 Lab | — | **P4 信息** |

### 3.4 关键设计原则

1. **双层保障**（wxmini启发）：脚本跑覆盖率，LLM保证准确率
2. **独立审查 + 对抗验证**（crucible启发）：Agent各自独立出报告，验证官去证伪
3. **渐进加载**（code-review-skill启发）：子Agent只加载当前代码需要的语言规则
4. **来源标注**（Coordinator规则）：每条结论标注来自哪个Agent，冲突不抹平

---

## 四、使用方式

### 4.1 手动触发（当前阶段）

对 Claude 说：

> "用MACRS审查一下 D:/path/to/project/ 的代码"

或

> "用MACRS审查一下这个文件：D:/path/to/file.py"

### 4.2 预期行为

1. Coordinator（主Agent）识别审查请求
2. 派出 3 个子Agent并行审查，各自加载不同 skill
3. 收集 3 份报告，执行交叉验证
4. 派出验证Agent对抗证伪
5. 合成最终报告，输出到 `D:/MACRS/reports/`
6. 向用户汇报结果

---

## 五、已知问题 & 待改进

| 问题 | 严重度 | 说明 |
|------|--------|------|
| analysis-code-review-skill.md 未写盘 | 低 | 内容在对话上下文中，skill本身已clone |
| Phase 0 脚本层未配置 | 中 | semgrep/ESLint 需要单独安装和配置 |
| 验证Agent的prompt未定义 | 中 | crucible的验证逻辑需要转化为我们的prompt模板 |
| Coordinator调度脚本未开发 | 中 | 目前靠主Agent手动调度 |
| 统一Severity映射规则未落地 | 低 | 已设计，需在prompt中实现 |
| CI/CD集成未开始 | 低 | Phase 5，当前阶段不需要 |

---

## 六、决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 模型 | Claude Code 自带（当前模型） | 包含在订阅内，无额外成本 |
| 语言优先级 | 自动检测 | code-review-skill 支持自动检测 |
| 触发方式 | 手动触发 | 先跑通再考虑自动化 |
| 安全隐私 | 外地方案（默认） | 用户说无所谓 |
| Skill定制 | 先fork直接用 | 后续再精简 |
| 系统存放位置 | D:/MACRS/ | 独立于其他项目，结构清晰 |
| 子Agent模型 | model: "sonnet" | CLAUDE.local.md 规定 |

---

## 七、下一步行动

### 立即可做
1. **首次实测**：选一个代码文件，手动触发 MACRS 审查流程
2. **验证流水线**：确认 3 个子Agent能否并行运行、报告能否正确收集

### 短期（1-2次会话）
3. 编写 Coordinator 调度脚本（放到 coordinator/ 目录）
4. 定义标准化的子Agent prompt 模板
5. 实现交叉验证和报告合成逻辑

### 中期（3-5次会话）
6. 安装 semgrep/ESLint，配置 Phase 0 脚本层
7. 实现 Skeptic Agent 的对抗验证逻辑
8. 输出标准化报告模板

### 长期
9. CI/CD 集成（GitHub Actions / GitLab CI）
10. 增量审查模式（只审查变更部分）

---

## 八、关键文件快速索引

| 想了解... | 读这个文件 |
|----------|-----------|
| 完整架构设计 | `D:/MACRS/docs/architecture-proposal.md` |
| code-review-skill 怎么用 | `D:/MACRS/skills/code-review-skill/SKILL.md` |
| BugHunter 有哪些漏洞模式 | `D:/MACRS/skills/Claude-BugHunter/skills/` 下的 51 个 SKILL.md |
| 工程原则审查规则 | `D:/MACRS/skills/pragmatic-clean-code-reviewer/SKILL.md` |
| crucible 多模型对抗怎么实现 | `D:/MACRS/skills/crucible/skill.md` + `scripts/orchestrate.py` |
| wxmini 双层架构分析 | `D:/MACRS/docs/analysis-wxmini-security-audit.md` |
| 原始调研报告（100+工具） | `D:/Claude Code/Xun-CC-Panel/11-github-code-review-tools.md` |

---

*文档生成时间: 2026-06-01 | 会话内所有工作已归档到 D:/MACRS/*
