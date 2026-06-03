# MACRS 代码审查报告

> **审查时间**: 2026-06-01
> **审查范围**: Xun-CC-Panel/server/ (0个文件, 0行)
> **总耗时**: 1291.9 秒

---

## 执行摘要

| 指标 | 数值 |
|------|------|
| 发现问题总数 | 6 |
| ┣ P0 阻断 | 1 |
| ┣ P1 严重 | 2 |
| ┣ P2 重要 | 2 |
| ┣ P3 建议 | 1 |
| 对抗验证通过 | 6 (60%) |
| 对抗验证驳斥 | 2 |
| 需人工裁决 | 1 |

---

## P0 阻断 -- 必须立即修复

### P0-001: 命令注入：edit_config 通过未转义路径拼接执行系统命令

| 属性 | 值 |
|------|-----|
| **文件** | `D:\CC项目\00\ccl-launcher.js:775-790` |
| **来源** | Agent B |
| **分类** | security |
| **置信度** | 0.85 |
| **对抗验证** | CONFIRM |

**问题描述**：session_action_screen 的 edit_config 分支（e===2）直接将 session.settingsFile 拼接到 shell 命令字符串中，未做任何转义。攻击者可通过创建包含 shell 元字符（如 `;calc` 或 `$(whoami)`）的 settingsFile 名称注入任意命令。Windows 端使用 `me.exec('start "" "' + cfgPath + '"')` 拼接，Unix 端使用模板字符串拼接，两者均存在注入风险。

**问题代码**：
```javascript
if (process.platform === 'win32') {
  me.exec('start "" "' + cfgPath + '"', () => {})
} else {
  me.exec('${EDITOR:-vi} "' + cfgPath + '"', () => {})
}
```

**修复建议**：使用 execFile/execFileSync 传参数组而非字符串拼接；对路径做 shell 元字符过滤或白名单校验（仅允许字母数字和连字符）。Windows 端使用 `execFile('cmd', ['/c', 'start', '', cfgPath])`，Unix 端使用 `execFile(process.env.EDITOR || 'vi', [cfgPath])`。

**修复后代码**：
```javascript
if (process.platform === 'win32') {
  me.execFile('cmd', ['/c', 'start', '', cfgPath], () => {})
} else {
  let editor = process.env.EDITOR || 'vi';
  me.execFile(editor, [cfgPath], () => {})
}
```

**对抗验证备注**：确认存在命令注入漏洞。实际漏洞代码在 lines 938-945（报告标注的 775/790 行是权限选择界面，非漏洞位置）。edit_config 使用 `exec('start "" "' + cfgPath + '"')` (Windows) 和 `exec('${EDITOR:-vi} "' + cfgPath + '"')` (Unix) 拼接命令。如果 session.settingsFile 包含双引号 `"`，可突破引号注入任意命令。例如 Windows: `foo" & calc.exe "` 会执行 calc。settingsFile 来自 .ccl-sessions.json 会话记录，如果远端 tips API 的 force_update 修改了模型配置中的 configFile 字段，可链式利用。虽然需要一定前置条件（修改本地会话文件或链式攻击），但 exec 字符串拼接确实是不安全的编码模式，应当使用 execFile + 参数数组。

---

## P1 严重 -- 合并前应修复

### P1-002: 供应链风险：首次运行时 npm install blessed 无完整性校验

| 属性 | 值 |
|------|-----|
| **文件** | `D:\CC项目\00\ccl-launcher.js:10-25` |
| **来源** | Agent B |
| **分类** | security |
| **置信度** | 0.92 |
| **对抗验证** | CONFIRM |

**问题描述**：IIFE 块在 `~/.claude/node_modules/blessed` 不存在时执行 `npm install blessed --no-package-lock`，未指定版本锁定、未使用 `--ignore-scripts`、未校验安装包完整性。攻击者可通过 DNS 劫持、registry 污染或中间人攻击注入恶意包，或利用 blessed 的 postinstall 脚本执行任意代码。

**问题代码**：
```javascript
c.execSync('npm install blessed --no-package-lock', {
  cwd: h,
  stdio: 'pipe',
  timeout: 6e4
})
```

**修复建议**：1) 锁定 blessed 版本（如 `blessed@0.1.81`）；2) 添加 `--ignore-scripts` 防止 postinstall 执行；3) 安装后校验包的 SHA256 哈希；4) 考虑将 blessed 预打包内嵌而非运行时安装。

**修复后代码**：
```javascript
c.execSync('npm install blessed@0.1.81 --no-package-lock --ignore-scripts', {
  cwd: h,
  stdio: 'pipe',
  timeout: 6e4
})
// Then verify integrity:
// const pkg = JSON.parse(fs.readFileSync(b, 'utf-8'));
// if (pkg.version !== '0.1.81') throw new Error('Version mismatch');
```

**对抗验证备注**：确认存在供应链风险。Line 17: `npm install blessed --no-package-lock` 存在以下问题：1) 无版本锁定——不指定版本号，安装最新版，可能安装到被投毒的版本。2) `--no-package-lock` 显式禁用 lock 文件，无法保证可重现构建。3) 未使用 `--ignore-scripts`，blessed 的 postinstall 脚本会自动执行。4) 无安装后哈希校验。5) blessed 是知名包，实际被投毒概率低，但 2018 年 event-stream 事件证明即使是流行包也可能被劫持。严重等级 P1 合理——这是真实的供应链攻击面，虽然概率不高但影响面大（首次运行时所有用户都会触发）。

---

### P1-003: 远端配置注入：tips API 可通过 force_update 覆写任意本地配置

| 属性 | 值 |
|------|-----|
| **文件** | `D:\CC项目\00\ccl-launcher.js:385-395` |
| **来源** | Agent B |
| **分类** | security |
| **置信度** | 0.90 |
| **对抗验证** | DOWNGRADE |
| **原始等级** | P0 BLOCKING (已降级) |

**问题描述**：ot() 函数从 `ie()>/api/ccl/tips` 拉取配置，当响应中 `force_update === true` 时，直接将远端 JSON 写入本地 `.ccl.config` 文件，不校验字段内容。攻击者若控制了 API 服务器（或通过 DNS 劫持/MITM），可通过 force_update 向本地注入恶意 tips 数据（如钓鱼提示、恶意 URL）。该接口使用 HTTP（非 HTTPS 也有可能，由 ie() 返回值决定），增大中间人攻击面。

**问题代码**：
```javascript
if (i) {
  let p = de();
  p?.tips?.current_index !== void 0 && (s.tips.current_index = p.tips.current_index),
  Oe(s);
  return
}
```

**修复建议**：1) 对远端响应做 schema 校验，仅允许已知字段写入；2) 移除或限制 force_update 逻辑，改为本地签名验证；3) 强制 HTTPS 并校验证书；4) 对 tips 内容做 XSS/注入过滤。

**修复后代码**：
```javascript
// Validate response schema before writing
const allowedKeys = ['tips', 'force_update', 'enabled'];
const isValid = Object.keys(s).every(k => allowedKeys.includes(k));
if (!isValid) return;
// Only allow known tip fields
const allowedTipKeys = ['items', 'current_index', 'protect_days', 'version', 'fetched_at'];
if (s.tips && !Object.keys(s.tips).every(k => allowedTipKeys.includes(k))) return;
```

**对抗验证备注**：降级理由：1) 漏洞确实存在——当远端响应 `force_update === true` 时，`Oe(s)` 将整个服务器响应写入本地配置（lines 486-489），可覆盖 agentBase、models、defaultPermission 等全部字段。2) 但利用需要服务器被攻陷或 MITM 攻击。代码 line 476 检查 URL 是否以 https 开头并使用对应模块（`Qe.get` 即 https.get），提供了传输层保护。3) 没有证书固定（certificate pinning）和响应 schema 校验是真实的缺陷，但 HTTPS 已提供基线防护。4) 从 P0 降级到 P1——不是阻断性问题，而是纵深防御不足。建议添加 schema 校验和移除 force_update 逻辑。

---

## P2 重要 -- 下个迭代修复

### P2-004: 权限提升：默认 bypassPermissions 绕过所有安全确认

| 属性 | 值 |
|------|-----|
| **文件** | `D:\CC项目\00\ccl-launcher.js:640-660` |
| **来源** | Agent B |
| **分类** | security |
| **置信度** | 0.91 |
| **对抗验证** | DOWNGRADE |
| **原始等级** | P1 CRITICAL (已降级) |

**问题描述**：代码默认权限模式为 `bypassPermissions`，对应 Claude CLI 的 `--permission-mode bypassPermissions`，这会跳过所有操作确认。用户在 TUI 中选择「跳过所有权限确认」时，生成的 claude 命令将拥有无限制的文件读写和命令执行权限。这个默认值应该更保守。

**问题代码**：
```javascript
defaultPermission: 'bypassPermissions'
```

**修复建议**：将默认权限模式改为 `acceptEdits`（仅自动接受编辑，危险操作仍需确认）。在 TUI 中增加安全警告提示，告知用户 bypassPermissions 模式的风险。

**修复后代码**：
```javascript
defaultPermission: 'acceptEdits'
```

**对抗验证备注**：降级理由：1) 默认权限 `bypassPermissions` 是设计选择而非漏洞。该工具是 Claude Code 启动器，其 TUI 在 line 762-771 明确提供了三个权限选项供用户选择（bypassPermissions/auto/acceptEdits）。2) 用户在启动前必须经过权限选择界面（dt screen），默认选中 bypassPermissions 但可更改。3) 在 Unix root 用户下，代码 line 609-610 会强制降级为 acceptEdits：`process.getuid() === 0 ? c.push('--permission-mode', 'acceptEdits')`，说明开发者有安全意识。4) bypassPermissions 是 Claude CLI 本身支持的合法模式，许多用户确实需要此模式以提高效率。建议在 TUI 中添加安全警告提示，但不应将此标为 P1 CRITICAL。

---

### P2-005: 命令注入：ct() 中 project_path 通过 shell 模式注入命令

| 属性 | 值 |
|------|-----|
| **文件** | `D:\CC项目\00\ccl-launcher.js:840-870` |
| **来源** | Agent B |
| **分类** | security |
| **置信度** | 0.88 |
| **对抗验证** | DOWNGRADE |
| **原始等级** | P0 BLOCKING (已降级) |

**问题描述**：ct() 函数在 Windows 端使用 `spawnSync(t, e, {shell: true})` 启动 claude CLI，当 shell:true 时，参数会经过 cmd.exe 解释。攻击者若能控制 project_path（通过项目列表），可注入 shell 特殊字符。Unix 端虽然对路径做了单引号转义，但 `'\''` 拼接方式在某些边缘场景下仍可能被绕过。

**问题代码**：
```javascript
let o = {
  stdio: 'inherit',
  shell: true
};
n && (o.cwd = n);
let r = me.spawnSync(t, e, o);
```

**修复建议**：Windows 端移除 `shell: true`，直接传参数数组给 spawnSync。对 project_path 做路径合法性校验（拒绝包含 `|`, `&`, `;`, `$`, `(`, `)`, backtick 等字符的路径）。Unix 端验证路径不含空字节。

**修复后代码**：
```javascript
let o = {
  stdio: 'inherit'
};
n && (o.cwd = n);
let r = me.spawnSync(t, e, o);
```

**对抗验证备注**：降级理由：1) Windows 端 project_path 仅用作 `cwd` 参数（line 624: `n && (o.cwd = n)`），cwd 不经过 shell 解释，不是注入向量。2) 但 project_path 同时也会作为 claude 的参数传入（来自 Ht() 函数的 c.push(o)），在 shell: true 模式下参数经过 cmd.exe 处理，如果路径含 `&`、`|` 等元字符理论上可被解释。3) Unix 端对路径做了单引号转义 `n.replace(/'/g, "'\\''")`，是标准安全做法。4) 攻击需要用户自己配置恶意路径或攻击者已能修改本地配置文件——此时已有同等权限。shell: true 是代码异味，但实际利用难度高。

---

## P3 建议 -- 有空可改

### P3-006: TOCTOU 竞态条件：原子写入使用可预测的 PID 拼接临时文件名

| 属性 | 值 |
|------|-----|
| **文件** | `D:\CC项目\00\ccl-launcher.js:310-330` |
| **来源** | Agent B |
| **分类** | security |
| **置信度** | 0.93 |
| **对抗验证** | DOWNGRADE |
| **原始等级** | P1 CRITICAL (已降级) |

**问题描述**：全文使用 `filePath + '.tmp.' + process.pid` 模式进行原子写入（write + rename）。在共享目录（如 `~/.claude/`）中，同一进程的多个实例可能产生相同 PID（极罕见但理论上可能），且攻击者可预先创建符号链接指向同名 tmp 文件，在 rename 阶段实现任意文件覆写。

**问题代码**：
```javascript
let e = te + '.tmp.' + process.pid;
T.writeFileSync(e, JSON.stringify(u, null, 2)),
T.renameSync(e, te)
```

**修复建议**：使用 `fs.writeFileSync` 的 `tmpfile` 模式或 `crypto.randomBytes` 生成随机后缀：`filePath + '.tmp.' + crypto.randomBytes(8).toString('hex')`。或使用 Node.js 的 `fs.mkdtemp` 创建临时目录。

**修复后代码**：
```javascript
const crypto = require('crypto');
let e = te + '.tmp.' + crypto.randomBytes(8).toString('hex');
T.writeFileSync(e, JSON.stringify(u, null, 2));
T.renameSync(e, te);
```

**对抗验证备注**：降级理由：1) PID 作为临时文件后缀确实可预测（`file.tmp.${process.pid}`），但这是 Node.js 生态中常见的原子写入模式。2) 实际利用需要：攻击者在 writeFileSync 和 renameSync 之间的时间窗口（微秒级）内，预测 PID 并在同目录创建符号链接——这在 Windows 上需要管理员权限（创建符号链接需 SeCreateSymbolicLinkPrivilege）。3) Windows 上 renameSync 在目标文件已存在时会覆盖（与 Unix 不同），但这也意味着攻击者需要在极短时间内完成符号链接创建。4) 使用 crypto.randomBytes 生成随机后缀确实是更好的实践，但当前实现的实际可利用性极低。

---

## 已驳斥发现

| # | 原始发现 | 来源 | 原始等级 | 驳斥理由 |
|---|---------|------|----------|----------|
| 1 | M-008: 任意文件读取：项目路径未验证，可遍历至系统任意目录 | Agent B | P1 CRITICAL | 驳斥理由：1) 报告称「项目路径未验证，可遍历至系统任意目录」——但 project_path 仅用作 Claude CLI 的工作目录（cwd）和参数，不是文件读取接口。2) 用户通过 TUI 选择项目目录（lines 730-754），... |
| 2 | M-009: 路径注入：Zt() 中 project 路径用于正则构造，可 ReDoS 或绕过过滤 | Agent B | P1 CRITICAL | 驳斥理由：1) 报告称「project 路径用于正则构造，可 ReDoS 或绕过过滤」——这是对代码的误读。Zt() 函数（lines 644-661）使用 `t.replace(/[^a-zA-Z0-9]/g, "-")` 将路径中的非字... |

---

## 需人工裁决

| # | 发现 | 来源 | 原始等级 | 理由 |
|---|------|------|----------|------|
| 1 | M-005: 敏感凭证明文写入配置文件且可被同机用户读取 | Agent B | P1 CRITICAL | 无法确定。报告标注 lines 570-590，但该区域是权限模式映射代码（bypassPermissions/acceptEdits 等），不涉及凭证写入。配置文件 claude-launcher-config.json 存储的是 mod... |

---

## 审查统计

| Agent | 技能 | 发现数 | 状态 |
|-------|------|--------|------|
| Agent A | unknown | 0 | FAILED () (311.2s) |
| Agent B | Claude-BugHunter | 10 | OK (133.1s) |
| Agent C | unknown | 0 | FAILED () (517.6s) |

---

*报告生成时间: 2026-06-02 19:27:21*
*Phase 2 去重后发现数: 10*
*Phase 3 对抗验证: 2 CONFIRM, 4 DOWNGRADE, 2 REFUTE, 1 NEEDS_HUMAN*
