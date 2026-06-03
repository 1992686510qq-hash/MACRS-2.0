# MACRS 代码审查报告

> **审查时间**: 2026-06-01
> **审查范围**: Xun-CC-Panel/server/ (12个文件, 1821行)
> **总耗时**: 206.0 秒

---

## 执行摘要

| 指标 | 数值 |
|------|------|
| 发现问题总数 | 11 |
| ┣ P0 阻断 | 1 |
| ┣ P1 严重 | 5 |
| ┣ P2 重要 | 2 |
| ┣ P3 建议 | 3 |
| 对抗验证通过 | 11 (31%) |
| 对抗验证驳斥 | 15 |
| 需人工裁决 | 0 |

---

## P0 阻断 -- 必须立即修复

### P0-001: XSS: import-data.json 内容直接注入 HTML 无任何编码

| 属性 | 值 |
|------|-----|
| **文件** | `index.js:18-26` |
| **来源** | Agent B |
| **分类** | security |
| **置信度** | 0.90 |
| **对抗验证** | CONFIRM |

**问题描述**：/import-localstorage 路由从磁盘读取 import-data.json 文件内容，然后直接拼接进 HTML 的 <script> 标签中：var html = '...var d=' + importData + ';...'. 如果攻击者能控制该文件内容（通过文件写入漏洞、共享目录、或供应链攻击），可以注入任意 JavaScript。例如文件内容为：});</script><script>alert(document.cookie)</script><script>!function(){// 时，会闭合原有 script 标签并注入新脚本。即使文件由管理员创建，这也违反了纵深防御原则——任何文件内容都不应被信任为安全的 HTML/JS。

**问题代码**：
```javascript
var importData = fs.readFileSync(importFile, "utf8");
var html = '...var d=' + importData + ';...';
```

**修复建议**：对 importData 进行 JSON 编码后再嵌入 HTML，或使用 CSP header 限制内联脚本执行。

**修复后代码**：
```javascript
var importData = fs.readFileSync(importFile, "utf8");
// 验证是合法 JSON 对象
var parsed = JSON.parse(importData);
var safeData = JSON.stringify(parsed).replace(/<\/script/gi, '<\\/script');
var html = '...var d=' + safeData + ';...';
```

**对抗验证备注**：index.js 第 35-36 行确实将 importData（文件原始内容）直接拼接进 HTML 的 script 标签中：`var d=' + importData + '`。import-data.json 虽然当前只包含 UUID 和 JSON 字符串等良性数据，但若该文件被篡改或包含 `';alert(1);//` 等 payload，即可触发 XSS。不过该路由仅用于一次性 localStorage 导入，攻击面有限。P0 BLOCKING 合理。

---

## P1 严重 -- 合并前应修复

### P1-002: CORS 通配符: Access-Control-Allow-Origin: * 允许任意网站访问 API

| 属性 | 值 |
|------|-----|
| **文件** | `index.js:7-7` |
| **来源** | Agent B |
| **分类** | security |
| **置信度** | 0.95 |
| **对抗验证** | CONFIRM |

**问题描述**：服务器对所有响应设置 Access-Control-Allow-Origin: *，这意味着互联网上任何网站都可以向 localhost:5022 发起跨域请求并读取响应。攻击者可以创建恶意页面，通过 JavaScript 调用 /api/sessions 获取所有会话信息、通过 /api/session/{id} 读取会话内容（可能包含敏感的代码和对话）、通过 /api/snapshot/create 创建快照。对于本地开发工具面板，应限制为 localhost 来源。

**问题代码**：
```javascript
var server = http.createServer(function(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
```

**修复建议**：将 CORS 限制为 localhost 来源，或完全移除该 header（同源策略会自动保护）。

**修复后代码**：
```javascript
var server = http.createServer(function(req, res) {
  // 仅允许本地访问
  var origin = req.headers.origin;
  if (origin && /^https?:\/\/localhost(:\d+)?$/.test(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
  }
```

**对抗验证备注**：index.js 第 22 行确实设置了 `res.setHeader('Access-Control-Allow-Origin', '*')`。server.listen 默认绑定 0.0.0.0（所有接口），意味着局域网内任何设备都可访问 API。CORS 通配符 + 监听所有接口 = 任何同网络的网页可通过 JavaScript 读取该面板的所有 API 数据。P1 CRITICAL 合理。

---

### P1-003: 信息泄露: 错误消息暴露内部文件路径

| 属性 | 值 |
|------|-----|
| **文件** | `index.js:125-140` |
| **来源** | Agent B |
| **分类** | security |
| **置信度** | 0.90 |
| **对抗验证** | CONFIRM |

**问题描述**：当源会话文件不存在时，错误响应包含完整的文件系统路径：error: 'Source session not found: ' + sourceFile. 这向攻击者泄露了内部目录结构（如 C:\Users\Administrator\.claude\projects\C--Users-Administrator\），可用于后续的路径遍历攻击。服务器的通用错误处理也泄露了堆栈信息：res.end('Server Error: ' + err.message).

**问题代码**：
```javascript
res.end(JSON.stringify({ ok: false, error: "Source session not found: " + sourceFile }));
```

**修复建议**：对客户端响应使用通用错误消息，将详细错误信息仅记录到服务器日志。

**修复后代码**：
```javascript
console.error('[create-and-open] Source session not found:', sourceFile);
res.end(JSON.stringify({ ok: false, error: "Source session not found" }));
```

**对抗验证备注**：index.js 第 101-103 行的 catch 块确实泄露了服务器内部错误信息：`res.writeHead(500); res.end('Server Error: ' + err.message)`。err.message 可能包含文件路径等内部信息。但降级为 P2——该面板是本地开发工具，错误信息泄露对本地用户影响有限，且攻击者需要触发服务器异常才能获取信息。

---

### P1-004: 路径遍历: 快照 ID 未验证可读取任意文件

| 属性 | 值 |
|------|-----|
| **文件** | `routes/snapshots.js:20-30` |
| **来源** | Agent B |
| **分类** | security |
| **置信度** | 0.90 |
| **对抗验证** | CONFIRM |

**问题描述**：/api/snapshot/ 端点从 URL 提取 snapId，直接拼接到文件路径：var snapFile = path.join(shared.SNAPSHOTS_DIR, snapId + '.json'). 虽然 SNAPSHOTS_DIR 是固定的，但 snapId 可能包含路径遍历序列。例如 snapId = '../../etc/passwd' 会导致读取 /etc/passwd.json（虽然 .json 后缀限制了利用，但在 Windows 上可以尝试 snapId = '..\\..\\Windows\\win.ini' 读取系统文件）。同样，/api/snapshot/delete/ 端点也存在相同问题，可以删除任意 .json 文件。

**问题代码**：
```javascript
var snapId = decodeURI(req.url.split("/api/snapshot/")[1]);
var snapFile = path.join(shared.SNAPSHOTS_DIR, snapId + ".json");
```

**修复建议**：验证 snapId 只包含安全字符，不包含路径分隔符。

**修复后代码**：
```javascript
var snapId = decodeURI(req.url.split("/api/snapshot/")[1]);
if (!/^auto-|manual-/.test(snapId) || /[\\/\.]/.test(snapId)) {
  res.writeHead(400); res.end(JSON.stringify({ error: "invalid snapshot id" }));
  return true;
}
var snapFile = path.join(shared.SNAPSHOTS_DIR, snapId + ".json");
```

**对抗验证备注**：snapshots.js 第 21-22 行：`var snapId = decodeURI(req.url.split('/api/snapshot/')[1]); var snapFile = path.join(shared.SNAPSHOTS_DIR, snapId + '.json')`。snapId 来自 URL 未经验证，path.join 不会阻止 ../ 序列。攻击者可通过 `/api/snapshot/../../etc/passwd` 读取任意文件。但降级为 P2——该面板监听 localhost，远程利用需要结合 CORS 通配符和网络访问，且 .json 后缀限制了读取范围。

---

### P1-005: parseSubAgent 与 buildRelationsResponse 中的子 Agent 解析逻辑大量重复

| 属性 | 值 |
|------|-----|
| **文件** | `agents.js:37-105` |
| **来源** | Agent C |
| **分类** | maintainability |
| **置信度** | 0.90 |
| **对抗验证** | CONFIRM |

**问题描述**：agents.js 的 parseSubAgent（70 行）和 session.js buildRelationsResponse 中的子 Agent 解析块（约 50 行）执行几乎相同的逻辑：读取 JSONL、提取 firstUserMsg、累加 token、计算 toolCallCount、确定 status。两者仅在输出字段和 status 判定细节上略有不同。这违反了 DRY 原则，且未来修改解析逻辑时需要同步两处，容易遗漏。

**问题代码**：
```javascript
// session.js 中重复的解析逻辑
var saContent = fs.readFileSync(saPath, "utf-8");
var saLines = saContent.trim().split("\n");
for (var sl = 0; sl < saLines.length; sl++) {
  var saObj = scanner.parseLine(saLines[sl]);
  // ... 与 parseSubAgent 几乎相同的逻辑
}
```

**修复建议**：统一为 agents.js 中的 parseSubAgent，并在 session.js 中复用。如果 relations 接口需要额外字段（如 startTime），扩展 parseSubAgent 的返回值即可。status 判定逻辑应统一到一个 getStatusForAgent(agentInfo) 函数中。

**修复后代码**：
```javascript
// session.js 中复用 agents 模块
var agentFiles = agents.findSubAgentFiles(subDir);
var agentNodes = agentFiles.map(function(f) {
  return agents.parseSubAgent(f.filePath, f.agentId, relId);
});
```

**对抗验证备注**：agents.js 的 parseSubAgent 函数（第 34-128 行，95 行）和 session.js 的 buildRelationsResponse 中子 Agent 解析逻辑（第 140-192 行，53 行）确实大量重复：两者都读取 JSONL 文件、解析 user 消息提取标题、累加 token、提取 toolCallCount。但降级为 P2——这是代码维护问题，不影响功能或安全。

---

### P1-006: 路径遍历: 会话详情 API 使用未经验证的 session ID

| 属性 | 值 |
|------|-----|
| **文件** | `routes/session.js:25-40` |
| **来源** | Agent B |
| **分类** | security |
| **置信度** | 0.85 |
| **对抗验证** | CONFIRM |

**问题描述**：/api/session/ 端点从 URL 提取 session ID，用于查找缓存和读取文件。当缓存未命中时，会触发全量扫描。session ID 直接来自 URL 路径，没有进行格式验证。虽然缓存查找使用 Map（不会遍历文件系统），但 buildRelationsResponse 中直接使用 relTarget._file 读取文件，如果缓存被污染或存在竞态条件，可能导致任意文件读取。

**问题代码**：
```javascript
var sid = qpos >= 0 ? decodeURI(sessUrl.slice(0, qpos)) : decodeURI(sessUrl);
```

**修复建议**：验证 session ID 符合 UUID 格式（8-4-4-4-12 十六进制字符）。

**修复后代码**：
```javascript
var sid = qpos >= 0 ? decodeURI(sessUrl.slice(0, qpos)) : decodeURI(sessUrl);
if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(sid)) {
  res.writeHead(400); res.end(JSON.stringify({ error: "invalid session id format" }));
  return true;
}
```

**对抗验证备注**：session.js 第 26-30 行从 URL 提取 session ID 未经 UUID 格式验证。但 session ID 用作 Map 查找键（sessionCache.get(sid)），不直接用于文件路径构造。文件路径来自 cached._file（scanner 设置的安全路径）。唯一的风险是 scanner.scanSessions 的 fallback 路径——但它遍历目录而非用 ID 构造路径。降级为 P2——实际攻击向量不明确。

---

## P2 重要 -- 下个迭代修复

### P2-007: buildRelationsResponse 是 266 行的巨型函数——职责过多难以维护和测试

| 属性 | 值 |
|------|-----|
| **文件** | `server/routes/session.js:101-367` |
| **来源** | Agent A |
| **分类** | bug, maintainability |
| **置信度** | 0.95 |
| **对抗验证** | DOWNGRADE |
| **原始等级** | P0 BLOCKING (已降级) |

**问题描述**：在 buildRelationsResponse 中，pLines 在第 120 行的 try 块内声明（var pLines = pContent.trim().split('\n')）。但同一函数在第 236 行（userMessages 循环）和第 289 行（waterfall 循环）中引用了 pLines，这两处都在 try 块之外。如果文件读取失败（权限问题、文件被删除等），pLines 未定义，两处 for 循环将抛出 ReferenceError，导致整个 /api/session/:id/relations 请求 500 崩溃。这个 bug 的触发条件是：会话文件在扫描缓存后、请求处理前被删除或移动——在文件系统活跃的环境中完全可能发生。

**问题代码**：
```javascript
  try {
    var pContent = fs.readFileSync(relTarget._file, "utf-8");
    var pLines = pContent.trim().split("\n");
    // ...
  } catch (e) {}
  // ... 100+ lines later ...
  for (var pi2 = 0; pi2 < pLines.length; pi2++) {  // ← pLines 可能未定义!
```

**修复建议**：将 pLines 声明提升到 try 块之前（var pLines = []），或在 try 块外添加防御性检查（if (!pLines || pLines.length === 0)）提前返回响应。

**修复后代码**：
```javascript
  var pLines = [];  // 提升声明
  try {
    var pContent = fs.readFileSync(relTarget._file, "utf-8");
    pLines = pContent.trim().split("\n");
    // ...
  } catch (e) { /* 文件不可读，pLines 保持空数组 */ }
```

**对抗验证备注**：buildRelationsResponse 在 session.js 第 101-367 行确实是一个 267 行的巨型函数，包含了 dispatch 解析、子 Agent 解析、时间匹配、阶段检测、瀑布流追踪五个不相关的关注点。P0 BLOCKING 过高——这是代码质量问题而非安全漏洞，且该函数内部有 try/catch 保护不会导致崩溃。应降为 P2。

---

### P2-008: shared.js 作为全局可变状态中心，缺乏封装，是架构腐化的核心风险点

| 属性 | 值 |
|------|-----|
| **文件** | `shared.js:1-53` |
| **来源** | Agent C |
| **分类** | maintainability |
| **置信度** | 0.85 |
| **对抗验证** | DOWNGRADE |
| **原始等级** | P1 CRITICAL (已降级) |

**问题描述**：shared.js 导出 13 个可变状态（sessionCache, subAgentCache, fileOffsets, sseClients, watchers, pendingChanges, snapshotList 等），所有模块直接 import 后读写，没有任何访问控制或不变量保护。这是典型的 'Global Mutable State' 反模式——任何模块都可以在任何时刻破坏状态一致性，且无法追踪是谁、在何时修改了什么。随着模块增多，这种架构会以超线性速度积累技术债务。

**问题代码**：
```javascript
module.exports = {
  sessionCache: new Map(),
  subAgentCache: new Map(),
  fileOffsets: new Map(),
  sseClients: [],
  watchers: [],
  pendingChanges: new Map(),
  snapshotList: [],
  // ... 13 个可变字段
};
```

**修复建议**：将 shared.js 重构为状态管理模块，对关键状态提供受控的读写方法而非裸导出。例如：
1. sessionCache → 提供 getSession(id) / setSession(id, data) / getAllSessions()，内部可加入校验逻辑
2. sseClients → 提供 addClient(res) / removeClient(res) / broadcast(data)，由 sse.js 独占管理
3. 将不相关的状态分组到不同模块（SSE 相关 → sse.js, 快照相关 → snapshot.js），避免一个文件承载所有全局状态

**修复后代码**：
```javascript
// session-store.js
var _cache = new Map();
module.exports = {
  get: function(id) { return _cache.get(id); },
  set: function(id, data) { /* 校验 */ _cache.set(id, data); },
  getAll: function() { return Array.from(_cache.values()); },
  has: function(id) { return _cache.has(id); }
};
```

**对抗验证备注**：shared.js 确实导出了可变的 Map 和数组（sessionCache、subAgentCache、sseClients 等），任何模块都可以直接修改。但该面板是单进程 Node.js 服务，不存在多进程并发写入问题。且 v5.22 版 shared.js 仅 38 行，比发现中声称的 53 行更小，状态规模有限。作为本地开发工具，全局可变状态是可接受的设计选择。严重等级从 P1 CRITICAL 降为 P2 IMPORTANT。

---

## P3 建议 -- 有空可改

### P3-009: loadAgentNames() 在循环内每次迭代都读取磁盘文件

| 属性 | 值 |
|------|-----|
| **文件** | `server/routes/session.js:199-220` |
| **来源** | Agent A |
| **分类** | performance |
| **置信度** | 0.95 |
| **对抗验证** | DOWNGRADE |
| **原始等级** | P1 CRITICAL (已降级) |

**问题描述**：在 buildRelationsResponse 的 dispatch 匹配循环中，agentsMod.loadAgentNames() 在第 209 行被调用，位于 for (var ci = 0; ci < sortedCalls.length; ci++) 循环体内。loadAgentNames 使用 fs.readFileSync 读取磁盘文件。如果一个会话有 50 次 dispatch 调用，就会产生 50 次同步文件读取，每次都在事件循环中阻塞。对于大型会话（频繁的 Agent/Task dispatch），这会显著增加 API 响应时间。

**问题代码**：
```javascript
for (var ci = 0; ci < sortedCalls.length; ci++) {
  // ...
  if (bestMatch) {
    var nameCfg = agentsMod.loadAgentNames(); // ← 每次迭代都读文件!
```

**修复建议**：将 loadAgentNames() 调用移到循环外部，只读取一次。或者在 agents 模块中添加缓存层（TTL 缓存或 fileMtime 检查）。

**修复后代码**：
```javascript
var nameCfg = agentsMod.loadAgentNames(); // 循环外读取一次
for (var ci = 0; ci < sortedCalls.length; ci++) {
  // ...
  if (bestMatch) {
    if (nameCfg.agents && nameCfg.agents[bestMatch.id]) {
```

**对抗验证备注**：session.js 第 209 行在 sortedCalls 的循环内调用 `agentsMod.loadAgentNames()`，该函数每次都同步读取磁盘文件 agent-names.json。当有 N 个 dispatch 调用时，会读取 N 次文件。在典型会话中 N 可能为 10-50，造成不必要的 I/O。P1 CRITICAL 过高——这是性能问题而非安全漏洞，降为 P3 SUGGESTION。

---

### P3-010: HTML 注入: /migrate 路由的 iframe src 包含硬编码端口

| 属性 | 值 |
|------|-----|
| **文件** | `index.js:49-52` |
| **来源** | Agent B |
| **分类** | security |
| **置信度** | 0.85 |
| **对抗验证** | DOWNGRADE |
| **原始等级** | P1 CRITICAL (已降级) |

**问题描述**：/migrate 路由返回的 HTML 中包含 iframe.src = 'http://localhost:3100/'，这本身不是漏洞，但该页面的 doMigrate() 函数会读取 iframe 内容并直接写入 localStorage：localStorage.setItem(keys[i], data[keys[i]]). 如果攻击者能控制 localhost:3100 的响应（通过端口劫持、DNS 重绑定、或在同一台机器上运行恶意服务），可以注入任意 localStorage 数据，这些数据随后可能被面板 JavaScript 使用，导致 XSS 或数据篡改。

**问题代码**：
```javascript
var raw=ifr.contentDocument.body.textContent;
var data=JSON.parse(raw);
for(var i=0;i<keys.length;i++){
  localStorage.setItem(keys[i],data[keys[i]]);
```

**修复建议**：验证从 iframe 读取的数据结构，限制可写入的 localStorage 键名白名单。

**修复后代码**：
```javascript
// 添加数据验证
var ALLOWED_KEYS = ['theme', 'config', 'preferences'];
for(var i=0;i<keys.length;i++){
  if(ALLOWED_KEYS.includes(keys[i])) {
    localStorage.setItem(keys[i],data[keys[i]]);
  }
}
```

**对抗验证备注**：index.js 第 55-58 行的 /migrate 路由确实硬编码了 `ifr.src='http://localhost:3100/'`。但这是一次性迁移工具，iframe 读取的是同源 localhost 数据，不存在用户可控输入。发现建议验证 iframe 数据结构是过度防御。降级为 P3 SUGGESTION。

---

### P3-011: parseSessionChunk 函数 110 行，混合了文件 I/O、JSON 解析、业务逻辑和数据聚合

| 属性 | 值 |
|------|-----|
| **文件** | `scanner.js:68-175` |
| **来源** | Agent C |
| **分类** | maintainability |
| **置信度** | 0.85 |
| **对抗验证** | DOWNGRADE |
| **原始等级** | P1 CRITICAL (已降级) |

**问题描述**：parseSessionChunk 同时负责：1) 文件 stat 和 seek 读取（I/O 层）、2) 逐行 JSON 解析（解析层）、3) 用户消息/助手消息的分类计数（业务层）、4) token 累加和 keyDecisions 收集（聚合层）。这些关注点应该分离，否则任何一层的变化都会影响整个函数。此外，该函数在循环内对每个 JSONL 行执行 JSON.stringify(block.input).slice(0, 200)，对于大文件会产生大量临时字符串。

**修复建议**：分为 3 层：
1. readJsonlTail(filePath, offset) → string（纯 I/O）
2. parseJsonlLines(content) → object[]（纯解析）
3. aggregateSessionInfo(lines, existingPromptIds) → SessionInfo（纯业务）

这使得每层都可以独立测试和复用。

**对抗验证备注**：scanner.js 的 parseSessionChunk 确实是 135 行（第 65-199 行），混合了文件 I/O、JSON 解析和业务逻辑。但该函数是增量解析的核心，已有清晰的结构（stat → read → parse → aggregate）。拆分虽好但收益有限。降级为 P3 SUGGESTION。

---

## 已驳斥发现

| # | 原始发现 | 来源 | 原始等级 | 驳斥理由 |
|---|---------|------|----------|----------|
| 1 | M-028: buildRelationsResponse 是 God Function（170 行），耦合了 5 个不相关的关注点 | Agent C | P1 CRITICAL | 与 M-001 完全重复。M-028 描述 buildRelationsResponse 为 170 行的 God Function（第 115-280 行），但实际函数是第 101-367 行共 267 行。两个发现指向同一函数，M-00... |
| 2 | M-002: XSS 注入：import-data.json 内容直接拼接进 HTML script 标签 | Agent A | P0 BLOCKING | 与 M-014 完全重复。M-002 引用 'server/index.js lines [35, 38]'，M-014 引用 'index.js lines [18, 26]'，但两者描述的是同一个 XSS 漏洞（import-data.... |
| 3 | M-015: 命令注入: bat 文件生成时 env 变量值未转义 | Agent B | P0 BLOCKING | 发现描述的是 routes/open.js 中 bat 文件生成时 env 变量值未转义的命令注入漏洞，并引用了 spawnWithBat 函数。但在 v5.22 版本中，open.js 已完全重写——不再有 spawnWithBat 函数... |
| 4 | M-027: /api/create-and-open 路由内联 100 行业务逻辑，违反单一职责和路由模块化原则 | Agent C | P1 CRITICAL | 发现描述 index.js 第 47-145 行 /api/create-and-open 路由内联 100 行业务逻辑。v5.22 的 index.js 不存在此路由，整个文件仅 149 行且路由已模块化到 routes/ 目录。此发现针... |
| 5 | M-004: Math.random() 生成会话 ID——可预测且有碰撞风险 | Agent A | P1 CRITICAL | 发现描述 Math.random() 生成会话 ID，引用 server/index.js 第 107-111 行。grep 确认 v5.22 整个 server 目录不存在 Math.random() 调用。会话 ID 来自 Claude... |
| 6 | M-008: delete 操作修改共享缓存对象——后续请求可能读到残缺数据 | Agent A | P1 CRITICAL | 发现描述 sessions.js 第 43-48 行 delete 操作修改共享缓存对象。v5.22 的 routes/sessions.js 仅 86 行，第 43-48 行是空行和注释。虽然 sessions.js 确实在第 23-25... |
| 7 | M-003: configName 查询参数未校验——路径遍历 + bat 文件命令注入 | Agent A | P0 BLOCKING | 发现描述 configName 查询参数未校验导致路径遍历和 bat 文件命令注入，引用 server/index.js 第 94-198 行。在 v5.22 中，index.js 仅 149 行，不存在 configName 参数、不存在... |
| 8 | M-005: settings.json 竞态条件——并发请求可导致配置文件内容错乱 | Agent A | P1 CRITICAL | 发现描述 server/routes/open.js 第 82-114 行 settings.json 竞态条件。v5.22 的 open.js 仅 98 行，无 settings.json 读写操作。此发现针对的是旧版代码中已移除的功能。 |
| 9 | M-007: 错误响应泄露服务器内部路径 | Agent A | P1 CRITICAL | 与 M-021 重复。M-007 引用 server/index.js 第 117-119 行，M-021 引用 index.js 第 125-140 行，两者描述同一问题。M-021 已确认并降级，M-007 作为重复项驳斥。 |
| 10 | M-016: TOCTOU 竞态: settings.json 被临时替换为任意配置 | Agent B | P0 BLOCKING | 发现描述 routes/open.js 第 130-160 行 settings.json TOCTOU 竞态。v5.22 的 open.js 仅 98 行，不存在 settings.json 替换逻辑。v5.22 已重构为使用 spawn... |
| 11 | M-030: settings.json 全局文件替换存在并发竞态条件，多会话同时启动会互相覆盖 | Agent C | P1 CRITICAL | 与 M-016 重复，且针对旧版代码。v5.22 的 open.js 不再修改 settings.json。此发现驳斥。 |
| 12 | M-006: 时间戳替换过于激进——匹配数据内容中的 ISO 时间戳导致语义破坏 | Agent A | P1 CRITICAL | 发现描述 server/index.js 第 153-159 行时间戳替换过于激进。v5.22 的 index.js 仅 149 行，不存在时间戳替换逻辑。此发现针对的是旧版代码中已移除的 /api/create-and-open 路由功能... |
| 13 | M-018: 路径遍历风险: /api/create-and-open 中 config 参数未验证 | Agent B | P1 CRITICAL | 发现描述 index.js 第 83-120 行 /api/create-and-open 中 config 参数路径遍历。v5.22 的 index.js 不存在 /api/create-and-open 路由。grep 确认整个 ser... |
| 14 | M-019: 路径遍历: 会话文件操作使用未经验证的 sessionId | Agent B | P1 CRITICAL | 发现描述 index.js 第 105-125 行会话文件操作使用未经验证的 sessionId。v5.22 的 index.js 第 105-125 行是启动日志输出代码，不涉及会话文件操作。会话文件访问在 routes/session.... |
| 15 | M-032: /import-localstorage 路由存在 XSS 风险，importData 直接嵌入 HTML 未转义 | Agent C | P1 CRITICAL | 与 M-014/M-002 完全重复。M-014 已确认，M-032 作为第三份重复项驳斥。 |

---

## 审查统计

| Agent | 技能 | 发现数 | 状态 |
|-------|------|--------|------|
| Agent A | code-review-skill | 14 | OK (206.0s) |
| Agent B | Claude-BugHunter | 12 | OK (115.7s) |
| Agent C | pragmatic-clean-code-reviewer | 10 | OK (121.2s) |

---

*报告生成时间: 2026-06-01 23:17:30*
*Phase 2 去重后发现数: 35*
*Phase 3 对抗验证: 6 CONFIRM, 5 DOWNGRADE, 15 REFUTE, 0 NEEDS_HUMAN*
