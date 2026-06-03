你是代码审查的"魔鬼代言人"。你的唯一任务是：
仔细阅读每一个发现，对照实际源代码，尽最大努力证明它是误报。

## 你可以使用的反驳角度：
1. 上下文反驳：这段代码的调用上下文使"漏洞"不可利用
2. 防护反驳：上游已有验证/过滤/转义，攻击向量被阻断
3. 范围反驳：问题代码在测试文件/已废弃代码/非生产路径中
4. 替代解释：Agent 误解了代码意图，实际行为是正确的
5. 严重降级：问题存在但严重等级被高估

## 你必须对每一个发现做出裁决：
- CONFIRM：确认，发现正确
- REFUTE：驳斥，提供反驳证据
- DOWNGRADE：降级，问题存在但严重等级过高，给出正确等级
- NEEDS_HUMAN：无法确定，需要人类判断

## 待验证的发现：

### M-012 - parseSessionChunk 中嵌套循环变量名 k 在多个作用域中重复使用
- Severity: P0 BLOCKING
- File: scanner.js lines [66, 155]
- Description: N/A
- Suggestion: 为每层循环使用语义化变量名：lineIdx、contentBlockIdx、toolUseIdx。或将解析逻辑拆分为更小的函数（parseUserMessage、parseAssistantMessage）。

Source code context:
```
var fs = require("fs");
var fsp = fs.promises;
var path = require("path");
var shared = require("./shared");

// ============ Status / Activity / TokenHeat ============

function getStatus(fileMtimeMs, lastMeaningfulTs, lastMeaningfulStopReason) {
  var now = Date.now();
  var fileAge = (fileMtimeMs > 0) ? (now - fileMtimeMs) : Infinity;
  var tsMs = typeof lastMeaningfulTs === "string" ? new Date(lastMeaningfulTs).getTime() : (lastMeaningfulTs || 0);
  var msgAge = (tsMs > 0) ? (now - tsMs) : Infinity;

  // end_turn → AI自然结束 → 时间递进链
  if (lastMeaningfulStopReason === "end_turn") {
    if (msgAge < 1 * 60 * 60 * 1000) return "completed";
    if (msgAge < 6 * 60 * 60 * 1000) return "idle";
    if (msgAge < 7 * 24 * 60 * 60 * 1000) return "休眠";
    return "归档";
  }

  // stop_sequence(用户按停止) / pause_turn / max_tokens → 中断，不随时间降级
  if (lastMeaningfulStopReason === "stop_sequence" || lastMeaningfulStopReason === "pause_turn" || lastMeaningfulStopReason === "max_tokens") {
    return "interrupted";
  }

  // tool_use → AI正在干活，文件应该频繁写入
  if (lastMeaningfulStopReason === "tool_use") {
    if (fileAge < 10 * 60 * 1000) return "running";
    return "异常"; // 文件10分钟没动，进程可能崩了
  }

  // null (最后有意义消息是user) → 等待AI回复
  if (fileAge < 10 * 60 * 1000) return "running";
  return "异常"; // 用户发了消息但10分钟内无响应
}

// 活跃度 Lv = floor(sqrt(近3h提问数 × 20))，上限99
function getActivity(recentUserMsgs) {
  if (!recentUserMsgs || recentUserMsgs <= 0) return "L0";
  var lv = Math.floor(Math.sqrt(recentUserMsgs * 20));
  if (lv > 99) lv = 99;
  return "L" + lv;
}

// 热度 Lv = floor(cbrt(累计token / 10))，上限99
function getTokenHeat(totalTokens) {
  if (!totalTokens || totalTokens <= 0) return "L0";
  var lv = Math.floor(Math.cbrt(totalTokens / 10));
  if (lv < 0) lv = 0;
  if (lv > 99) lv = 99;
  return "L" + lv;
}

// ============ JSONL Parsing ============

function parseLine(line) {
  try { return JSON.parse(line); } catch (e) { return null; }
}

function parseSessionFull(filePath) {
  return parseSessionChunk(filePath, 0);
}

function parseSessionChunk(filePath, startOffset, existingPromptIds) {
  var info = {
    id: null, title: null, customTitle: null, aiTitle: null,
    firstUserMsg: null, lastTimestamp: null, cwd: null,
    version: null, slug: null, entrypoint: null, model: null,
    totalLines: 0,
    _itok: 0, _otok: 0, _ctok: 0,
    recentUserMsgs: 0, recentMsgTotal: 0,
    userMsgCount: 0, assistantMsgCount: 0,
    fileSize: 0, fileMtime: null, fileMtimeMs: 0,
    lastStopReason: null, lastEntryType: null, lastEntrySubtype: null,
    lastMeaningfulTimestamp: null, lastMeaningfulStopReason: undefined,
    keyDecisions: [], toolCallCount: 0, fileWriteCount: 0,
    _seenPromptIds: {}
  };
  if (existingPromptIds) { info._seenPromptIds = Object.assign({}, existingPromptIds); }

  var content;
  try {
    var stat = fs.statSync(filePath);
    info.fileSize = stat.size;
    info.fileMtime = stat.mtime.toISOString();
    info.fileMtimeMs = stat.mtimeMs;
    if (startOffset > 0 && stat.size <= startOffset) {
      if (stat.size < startOffset) return { _truncated: true, filePath: filePath, fileSize: stat.size, fileMtime: info.fileMtime, fileMtimeMs: info.fileMtimeMs };
      return null;
    }
    var fd = fs.openSync(filePath, "r");
    try {
      var buf = Buffer.alloc(Math.max(1, stat.size - startOffset));
      var bytesRead = fs.readSync(fd, buf, 0, buf.length, startOffset);
      content = buf.toString("utf-8", 0, bytesRead);
    } finally { fs.closeSync(fd); }
  } catch (e) {
    if (startOffset > 0) return null;
    return info;
  }

  if (!content || content.trim() === "") {
    return (startOffset === 0) ? info : null;
  }

  var lines = content.split("\n");
  var lineCount = 0;
  var recentCutoff = Date.now() - 3 * 60 * 60 * 1000;

  for (var i = 0; i < lines.length; i++) {
    if (lines[i].trim() === "") continue;
    var obj = parseLine(lines[i]);
    if (!obj) continue;
    lineCount++;

    if (!info.id && obj.sessionId) info.id = obj.sessionId;
    if (!info.cwd && obj.cwd) info.cwd = obj.cwd;
    if (!info.version && obj.version) info.version = obj.version;
    if (!info.slug && obj.slug) info.slug = obj.slug;
    if (!info.entrypoint && obj.entrypoint) info.entrypoint = obj.entrypoint;

    if (obj.type === "ai-title" && obj.aiTitle) info.aiTitle = obj.aiTitle;
    if (obj.type === "custom-title" && obj.customTitle) info.customTitle = obj.customTitle;

    if (obj.type === "user") {
      var pid = obj.promptId;
      var isNewUserMsg = false;
      if (pid) {
        if (!info._seenPromptIds[pid]) {
          info._seenPromptIds[pid] = true;
          info.userMsgCount++;
          if (obj.timestamp && new Date(obj.timestamp).getTime() > recentCutoff) info.recentUserMsgs++;
          isNewUserMsg = true;
        }
      } else {
        info.userMsgCount++;
        if (obj.timestamp && new Date(obj.timestamp).getTime() > recentCutoff) info.recentUserMsgs++;
        isNewUserMsg = true;
      }
      if (!info.firstUserMsg && o
```
### M-001 - create-and-open handler 中 urlObj 重复声明，遮蔽外部变量
- Severity: P1 CRITICAL
- File: index.js lines [136, 138]
- Description: N/A
- Suggestion: 删除 create-and-open 分支内的重复 var urlObj 声明，直接复用外部已有的 urlObj（它在解析 req.url 时已包含 query 参数）。

Source code context:
```
// 阿勋的CC面板 5.22 — 缓存+增量版（端口5022），模块化架构
var http = require("http");
var fs = require("fs");
var path = require("path");
var crypto = require("crypto");
var shared = require("./shared");
var pricing = require("./pricing");
var scanner = require("./scanner");
var snapshot = require("./snapshot");
var sse = require("./sse");
var watcher = require("./watcher");
var agents = require("./agents");

// ============ Token 认证 ============
var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
var TOKEN_PATH = path.join(homeDir, ".claude", "panel-token");
var PANEL_TOKEN;

try {
  if (fs.existsSync(TOKEN_PATH)) {
    PANEL_TOKEN = fs.readFileSync(TOKEN_PATH, "utf-8").trim();
    console.log("[认证] 已加载 panel-token");
  } else {
    PANEL_TOKEN = crypto.randomBytes(32).toString("hex");
    fs.mkdirSync(path.dirname(TOKEN_PATH), { recursive: true });
    fs.writeFileSync(TOKEN_PATH, PANEL_TOKEN);
    console.log("[认证] 已生成新的 panel-token: " + TOKEN_PATH);
  }
} catch (e) {
  console.error("[认证] token 处理失败，使用临时 token:", e.message);
  PANEL_TOKEN = crypto.randomBytes(32).toString("hex");
}

console.log("[认证] Token: " + PANEL_TOKEN.substring(0, 8) + "...");

// 不需要认证的路径（静态资源、迁移工具）
var PUBLIC_PATHS = [
  "/",
  "/index.html",
  "/sortable.min.js",
  "/qr-wechat.png",
  "/qr-alipay.jpg",
  "/migrate",
  "/import-localstorage"
];

function isPublicPath(urlPath) {
  for (var i = 0; i < PUBLIC_PATHS.length; i++) {
    if (urlPath === PUBLIC_PATHS[i]) return true;
  }
  return false;
}

function authenticateRequest(req, urlObj) {
  // 优先从 Authorization header 获取
  var authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith("Bearer ")) {
    return authHeader.substring(7) === PANEL_TOKEN;
  }
  // 其次从 query param 获取（用于 SSE）
  var tokenParam = urlObj.searchParams.get("token");
  if (tokenParam) {
    return tokenParam === PANEL_TOKEN;
  }
  return false;
}

// Route handlers
var sessionsRouter = require("./routes/sessions")();
var sessionRouter = require("./routes/session")();
var snapshotsRouter = require("./routes/snapshots")();
var openRouter = require("./routes/open")();

// ============ HTTP Server ============

var server = http.createServer(function(req, res) {
  var origin = req.headers.origin;
  if (origin && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
  }

  try {
    var urlObj = new URL(req.url, "http://localhost");
    var urlPath = urlObj.pathname;

    // 公开路径不需要认证
    if (!isPublicPath(urlPath)) {
      // API 路径需要认证
      if (!authenticateRequest(req, urlObj)) {
        res.writeHead(401, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ error: "unauthorized", message: "请提供有效的 token" }));
        return;
      }
    }

    // SSE（需要认证，通过 query param 传递 token）
    if (sse.handleSSE(req, res)) return;

    // 一次性 localStorage 导入路由
    if (req.url === "/import-localstorage") {
      var importFile = path.join(__dirname, "import-data.json");
      if (!fs.existsSync(importFile)) {
        res.writeHead(404); res.end("import-data.json not found");
        return;
      }
      var importData = fs.readFileSync(importFile, "utf8");
      var safeData = JSON.stringify(JSON.parse(importData)).replace(/<\/script/gi, '<\\/script');
      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>导入配置</title><style>body{font-family:system-ui;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}.ok{color:#4caf50}.err{color:#f44336}.key{font-family:monospace;font-size:13px;margin:4px 0}.box{background:#16213e;border-radius:8px;padding:16px;margin:12px 0}h2{margin:0 0 8px}</style></head><body><h2>CC面板配置导入</h2><div id="status">正在导入...</div><div id="results" class="box"></div><script>!function(){var d=' + safeData + ';var ok=0,fail=0,results=[];Object.entries(d).forEach(function(e){try{localStorage.setItem(e[0],e[1]);var v=e[1];results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"ok\\">OK</span> ("+(v.length>80?v.substring(0,80)+"...":v)+")</div>");ok++}catch(err){results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"err\\">FAIL: "+err.message+"</span></div>");fail++}});var status=document.getElementById("status");status.innerHTML=ok+" 个成功, "+fail+" 个失败 (共 "+Object.keys(d).length+" 项)";status.className=ok>0?"ok":"err";document.getElementById("results").innerHTML=results.join("");if(ok>0){var p=document.createElement("p");p.textContent="配置已写入 Edge localStorage for "+window.location.origin;p.className="ok";document.body.appendChild(p)}else{var p2=document.createElement("p");p2.textContent="未写入任何数据,请检查浏览器控制台";p2.className="err";document.body.appendChild(p2)}}();</script></body></html>';
      res.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      res.end(html);
      return;
    }

    // HTML
    if (req.url === "/" || req.url === "/index.html") {
      if (fs.existsSync(shared.HTML_FILE)) {
        res
```
### M-003 - _processing 模块局部变量遮蔽 shared._processing，后者成为死代码
- Severity: P1 CRITICAL
- File: watcher.js lines [46, 48]
- Description: N/A
- Suggestion: 统一使用 shared._processing 作为唯一的并发守卫，删除 watcher.js 的模块级 _processing 变量。或从 shared.js 中移除 _processing 导出。

Source code context:
```
var fs = require("fs");
var path = require("path");
var shared = require("./shared");
var scanner = require("./scanner");
var agents = require("./agents");
var sse = require("./sse");
var snapshot = require("./snapshot");

function setupFileWatcher() {
  if (!fs.existsSync(shared.PROJECTS_DIR)) return;

  // Watch top-level project dirs recursively
  try {
    var topEntries = fs.readdirSync(shared.PROJECTS_DIR, { withFileTypes: true });
    for (var i = 0; i < topEntries.length; i++) {
      if (topEntries[i].isDirectory()) {
        var dirPath = path.join(shared.PROJECTS_DIR, topEntries[i].name);
        watchDir(dirPath);
      }
    }
  } catch (e) {
    console.error("[CC面板] watcher setup error:", e.message);
  }
}

function watchDir(dirPath) {
  try {
    var watcher = fs.watch(dirPath, { recursive: true }, function(eventType, filename) {
      if (!filename) return;
      // Debounce
      var key = dirPath;
      if (shared.pendingChanges.has(key)) clearTimeout(shared.pendingChanges.get(key));
      shared.pendingChanges.set(key, setTimeout(function() {
        shared.pendingChanges.delete(key);
        processChanges();
      }, shared.WATCH_DEBOUNCE_MS));
    });
    watcher.on("error", function() { /* swallow */ });
    shared.watchers.push(watcher);
  } catch (e) {
    // fs.watch may fail on some systems, polling fallback covers it
  }
}

var _processing = false;
function processChanges() {
  if (_processing) return;
  _processing = true;
  try {
    scanner.scanSessions(shared.PROJECTS_DIR, []).then(function(sessions) {
      agents.scanSubAgents(sessions);

      for (var i = 0; i < sessions.length; i++) {
        sessions[i].status = scanner.getStatus(sessions[i].fileMtimeMs, sessions[i].lastMeaningfulTimestamp, sessions[i].lastMeaningfulStopReason);
      }

      // Auto-snapshot
      var now = Date.now();
      if (now - shared.lastAutoSnapshot > shared.AUTO_SNAPSHOT_INTERVAL) {
        shared.lastAutoSnapshot = now;
        snapshot.saveSnapshot("auto-" + new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19), sessions);
      }

      sse.broadcastSSE({ type: "sessions-update", timestamp: new Date().toISOString() });
    }).finally(function() {
      _processing = false;
    });
  } catch (e) {
    _processing = false;
  }
}

function cleanupWatchers() {
  for (var i = 0; i < shared.watchers.length; i++) {
    try { shared.watchers[i].close(); } catch (e) {}
  }
  shared.watchers.length = 0;
}

module.exports = {
  setupFileWatcher: setupFileWatcher,
  watchDir: watchDir,
  processChanges: processChanges,
  cleanupWatchers: cleanupWatchers
};

```
### M-024 - Session ID 使用 Math.random() 生成，可预测
- Severity: P0 BLOCKING
- File: index.js lines [95, 100]
- Description: N/A
- Suggestion: 使用 crypto.randomUUID()（Node.js 14.17+）或 crypto.randomBytes(16) 生成 session ID。代码中已经引入了 crypto 模块，可直接使用。

Source code context:
```
// 阿勋的CC面板 5.22 — 缓存+增量版（端口5022），模块化架构
var http = require("http");
var fs = require("fs");
var path = require("path");
var crypto = require("crypto");
var shared = require("./shared");
var pricing = require("./pricing");
var scanner = require("./scanner");
var snapshot = require("./snapshot");
var sse = require("./sse");
var watcher = require("./watcher");
var agents = require("./agents");

// ============ Token 认证 ============
var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
var TOKEN_PATH = path.join(homeDir, ".claude", "panel-token");
var PANEL_TOKEN;

try {
  if (fs.existsSync(TOKEN_PATH)) {
    PANEL_TOKEN = fs.readFileSync(TOKEN_PATH, "utf-8").trim();
    console.log("[认证] 已加载 panel-token");
  } else {
    PANEL_TOKEN = crypto.randomBytes(32).toString("hex");
    fs.mkdirSync(path.dirname(TOKEN_PATH), { recursive: true });
    fs.writeFileSync(TOKEN_PATH, PANEL_TOKEN);
    console.log("[认证] 已生成新的 panel-token: " + TOKEN_PATH);
  }
} catch (e) {
  console.error("[认证] token 处理失败，使用临时 token:", e.message);
  PANEL_TOKEN = crypto.randomBytes(32).toString("hex");
}

console.log("[认证] Token: " + PANEL_TOKEN.substring(0, 8) + "...");

// 不需要认证的路径（静态资源、迁移工具）
var PUBLIC_PATHS = [
  "/",
  "/index.html",
  "/sortable.min.js",
  "/qr-wechat.png",
  "/qr-alipay.jpg",
  "/migrate",
  "/import-localstorage"
];

function isPublicPath(urlPath) {
  for (var i = 0; i < PUBLIC_PATHS.length; i++) {
    if (urlPath === PUBLIC_PATHS[i]) return true;
  }
  return false;
}

function authenticateRequest(req, urlObj) {
  // 优先从 Authorization header 获取
  var authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith("Bearer ")) {
    return authHeader.substring(7) === PANEL_TOKEN;
  }
  // 其次从 query param 获取（用于 SSE）
  var tokenParam = urlObj.searchParams.get("token");
  if (tokenParam) {
    return tokenParam === PANEL_TOKEN;
  }
  return false;
}

// Route handlers
var sessionsRouter = require("./routes/sessions")();
var sessionRouter = require("./routes/session")();
var snapshotsRouter = require("./routes/snapshots")();
var openRouter = require("./routes/open")();

// ============ HTTP Server ============

var server = http.createServer(function(req, res) {
  var origin = req.headers.origin;
  if (origin && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
  }

  try {
    var urlObj = new URL(req.url, "http://localhost");
    var urlPath = urlObj.pathname;

    // 公开路径不需要认证
    if (!isPublicPath(urlPath)) {
      // API 路径需要认证
      if (!authenticateRequest(req, urlObj)) {
        res.writeHead(401, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ error: "unauthorized", message: "请提供有效的 token" }));
        return;
      }
    }

    // SSE（需要认证，通过 query param 传递 token）
    if (sse.handleSSE(req, res)) return;

    // 一次性 localStorage 导入路由
    if (req.url === "/import-localstorage") {
      var importFile = path.join(__dirname, "import-data.json");
      if (!fs.existsSync(importFile)) {
        res.writeHead(404); res.end("import-data.json not found");
        return;
      }
      var importData = fs.readFileSync(importFile, "utf8");
      var safeData = JSON.stringify(JSON.parse(importData)).replace(/<\/script/gi, '<\\/script');
      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>导入配置</title><style>body{font-family:system-ui;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}.ok{color:#4caf50}.err{color:#f44336}.key{font-family:monospace;font-size:13px;margin:4px 0}.box{background:#16213e;border-radius:8px;padding:16px;margin:12px 0}h2{margin:0 0 8px}</style></head><body><h2>CC面板配置导入</h2><div id="status">正在导入...</div><div id="results" class="box"></div><script>!function(){var d=' + safeData + ';var ok=0,fail=0,results=[];Object.entries(d).forEach(function(e){try{localStorage.setItem(e[0],e[1]);var v=e[1];results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"ok\\">OK</span> ("+(v.length>80?v.substring(0,80)+"...":v)+")</div>");ok++}catch(err){results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"err\\">FAIL: "+err.message+"</span></div>");fail++}});var status=document.getElementById("status");status.innerHTML=ok+" 个成功, "+fail+" 个失败 (共 "+Object.keys(d).length+" 项)";status.className=ok>0?"ok":"err";document.getElementById("results").innerHTML=results.join("");if(ok>0){var p=document.createElement("p");p.textContent="配置已写入 Edge localStorage for "+window.location.origin;p.className="ok";document.body.appendChild(p)}else{var p2=document.createElement("p");p2.textContent="未写入任何数据,请检查浏览器控制台";p2.className="err";document.body.appendChild(p2)}}();</script></body></html>';
      res.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      res.end(html);
      return;
    }

    // HTML
    if (req.url === "/" || req.url === "/index.html") {
      if (fs.existsSync(shared.HTML_FILE)) {
        res
```
### M-002 - create-and-open handler 中 homeDir 重复声明遮蔽模块级变量
- Severity: P1 CRITICAL
- File: index.js lines [147, 148]
- Description: N/A
- Suggestion: 删除 create-and-open 内的 var homeDir 重新声明，直接复用模块顶部的 homeDir。

Source code context:
```
// 阿勋的CC面板 5.22 — 缓存+增量版（端口5022），模块化架构
var http = require("http");
var fs = require("fs");
var path = require("path");
var crypto = require("crypto");
var shared = require("./shared");
var pricing = require("./pricing");
var scanner = require("./scanner");
var snapshot = require("./snapshot");
var sse = require("./sse");
var watcher = require("./watcher");
var agents = require("./agents");

// ============ Token 认证 ============
var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
var TOKEN_PATH = path.join(homeDir, ".claude", "panel-token");
var PANEL_TOKEN;

try {
  if (fs.existsSync(TOKEN_PATH)) {
    PANEL_TOKEN = fs.readFileSync(TOKEN_PATH, "utf-8").trim();
    console.log("[认证] 已加载 panel-token");
  } else {
    PANEL_TOKEN = crypto.randomBytes(32).toString("hex");
    fs.mkdirSync(path.dirname(TOKEN_PATH), { recursive: true });
    fs.writeFileSync(TOKEN_PATH, PANEL_TOKEN);
    console.log("[认证] 已生成新的 panel-token: " + TOKEN_PATH);
  }
} catch (e) {
  console.error("[认证] token 处理失败，使用临时 token:", e.message);
  PANEL_TOKEN = crypto.randomBytes(32).toString("hex");
}

console.log("[认证] Token: " + PANEL_TOKEN.substring(0, 8) + "...");

// 不需要认证的路径（静态资源、迁移工具）
var PUBLIC_PATHS = [
  "/",
  "/index.html",
  "/sortable.min.js",
  "/qr-wechat.png",
  "/qr-alipay.jpg",
  "/migrate",
  "/import-localstorage"
];

function isPublicPath(urlPath) {
  for (var i = 0; i < PUBLIC_PATHS.length; i++) {
    if (urlPath === PUBLIC_PATHS[i]) return true;
  }
  return false;
}

function authenticateRequest(req, urlObj) {
  // 优先从 Authorization header 获取
  var authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith("Bearer ")) {
    return authHeader.substring(7) === PANEL_TOKEN;
  }
  // 其次从 query param 获取（用于 SSE）
  var tokenParam = urlObj.searchParams.get("token");
  if (tokenParam) {
    return tokenParam === PANEL_TOKEN;
  }
  return false;
}

// Route handlers
var sessionsRouter = require("./routes/sessions")();
var sessionRouter = require("./routes/session")();
var snapshotsRouter = require("./routes/snapshots")();
var openRouter = require("./routes/open")();

// ============ HTTP Server ============

var server = http.createServer(function(req, res) {
  var origin = req.headers.origin;
  if (origin && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
  }

  try {
    var urlObj = new URL(req.url, "http://localhost");
    var urlPath = urlObj.pathname;

    // 公开路径不需要认证
    if (!isPublicPath(urlPath)) {
      // API 路径需要认证
      if (!authenticateRequest(req, urlObj)) {
        res.writeHead(401, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ error: "unauthorized", message: "请提供有效的 token" }));
        return;
      }
    }

    // SSE（需要认证，通过 query param 传递 token）
    if (sse.handleSSE(req, res)) return;

    // 一次性 localStorage 导入路由
    if (req.url === "/import-localstorage") {
      var importFile = path.join(__dirname, "import-data.json");
      if (!fs.existsSync(importFile)) {
        res.writeHead(404); res.end("import-data.json not found");
        return;
      }
      var importData = fs.readFileSync(importFile, "utf8");
      var safeData = JSON.stringify(JSON.parse(importData)).replace(/<\/script/gi, '<\\/script');
      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>导入配置</title><style>body{font-family:system-ui;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}.ok{color:#4caf50}.err{color:#f44336}.key{font-family:monospace;font-size:13px;margin:4px 0}.box{background:#16213e;border-radius:8px;padding:16px;margin:12px 0}h2{margin:0 0 8px}</style></head><body><h2>CC面板配置导入</h2><div id="status">正在导入...</div><div id="results" class="box"></div><script>!function(){var d=' + safeData + ';var ok=0,fail=0,results=[];Object.entries(d).forEach(function(e){try{localStorage.setItem(e[0],e[1]);var v=e[1];results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"ok\\">OK</span> ("+(v.length>80?v.substring(0,80)+"...":v)+")</div>");ok++}catch(err){results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"err\\">FAIL: "+err.message+"</span></div>");fail++}});var status=document.getElementById("status");status.innerHTML=ok+" 个成功, "+fail+" 个失败 (共 "+Object.keys(d).length+" 项)";status.className=ok>0?"ok":"err";document.getElementById("results").innerHTML=results.join("");if(ok>0){var p=document.createElement("p");p.textContent="配置已写入 Edge localStorage for "+window.location.origin;p.className="ok";document.body.appendChild(p)}else{var p2=document.createElement("p");p2.textContent="未写入任何数据,请检查浏览器控制台";p2.className="err";document.body.appendChild(p2)}}();</script></body></html>';
      res.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      res.end(html);
      return;
    }

    // HTML
    if (req.url === "/" || req.url === "/index.html") {
      if (fs.existsSync(shared.HTML_FILE)) {
        res
```
### M-023 - shared.js 是 God Module：全局可变状态集中营
- Severity: P0 BLOCKING
- File: shared.js lines [40, 75]
- Description: N/A
- Suggestion: 将状态按领域拆分：SessionStore（sessionCache + fileOffsets + sessionConfigMap）、AgentStore（subAgentCache）、SSEClients（sseClients + SSE_MAX_CLIENTS）、SnapshotStore（snapshotList + lastAutoSnapshot）。每个 Store 通过方法暴露操作（get/set/delete），不直接暴露 Map/Array。这使得状态变更可追踪、可测试、可加锁。

Source code context:
```
var path = require("path");
var fs = require("fs");

var PROJECTS_DIR = process.env.CLAUDE_PROJECTS_DIR || path.join(process.env.HOME || process.env.USERPROFILE || "~", ".claude", "projects");
var SNAPSHOTS_DIR = path.join(process.env.HOME || process.env.USERPROFILE || "~", ".claude", "armada", "snapshots");
var PORT = parseInt(process.env.CC_DASHBOARD_PORT || "5022", 10);
var HTML_FILE = path.join(__dirname, "..", "index.html");
var AGENT_NAMES_FILE = path.join(process.env.HOME || process.env.USERPROFILE || "~", ".claude", "agent-names.json");
var SESSION_CONFIG_FILE = path.join(process.env.HOME || process.env.USERPROFILE || "~", ".claude", "session-config-map.json");
var CCL_SESSIONS_FILE = path.join(process.env.HOME || process.env.USERPROFILE || "~", ".claude", ".ccl-sessions.json");

// 持久化 sessionConfigMap
function loadSessionConfigMap() {
  try {
    if (fs.existsSync(SESSION_CONFIG_FILE)) {
      var data = JSON.parse(fs.readFileSync(SESSION_CONFIG_FILE, "utf-8"));
      var m = new Map();
      var keys = Object.keys(data);
      for (var i = 0; i < keys.length; i++) { m.set(keys[i], data[keys[i]]); }
      console.log("[shared] 加载 sessionConfigMap: " + m.size + " 条");
      return m;
    }
  } catch (e) { console.error("[shared] 加载 sessionConfigMap 失败:", e.message); }
  return new Map();
}

function saveSessionConfigMap(m) {
  try {
    var obj = {};
    m.forEach(function(v, k) { obj[k] = v; });
    fs.writeFileSync(SESSION_CONFIG_FILE, JSON.stringify(obj, null, 2), "utf-8");
  } catch (e) { console.error("[shared] 保存 sessionConfigMap 失败:", e.message); }
}

// 加载 CCL 会话记录（project → settingsFile 映射）
function loadCclSessions() {
  try {
    if (fs.existsSync(CCL_SESSIONS_FILE)) {
      var data = JSON.parse(fs.readFileSync(CCL_SESSIONS_FILE, "utf-8"));
      var m = new Map();
      for (var i = 0; i < data.length; i++) {
        var rec = data[i];
        if (rec.project && rec.settingsFile) {
          // 同一项目可能有多个记录，取最新的（后面的覆盖前面的）
          m.set(rec.project, rec.settingsFile);
        }
      }
      console.log("[shared] 加载 CCL 会话记录: " + m.size + " 个项目");
      return m;
    }
  } catch (e) { console.error("[shared] 加载 CCL 会话记录失败:", e.message); }
  return new Map();
}

// 监控 CCL 会话文件变化，自动将新 CCL 会话映射到 JSONL 文件
function watchCclSessions(sessionConfigMap, projectsDir) {
  if (!fs.existsSync(CCL_SESSIONS_FILE)) return;
  var lastCount = 0;
  try { lastCount = JSON.parse(fs.readFileSync(CCL_SESSIONS_FILE, "utf-8")).length; } catch {}
  fs.watch(CCL_SESSIONS_FILE, function() {
    try {
      var data = JSON.parse(fs.readFileSync(CCL_SESSIONS_FILE, "utf-8"));
      if (data.length <= lastCount) return;
      lastCount = data.length;
      var latest = data[data.length - 1];
      if (!latest.project || !latest.settingsFile) return;
      // 扫描 projects 目录，找最近 15 秒内创建的 JSONL 文件
      var cutoff = Date.now() - 15000;
      var subdirs = fs.readdirSync(projectsDir);
      for (var i = 0; i < subdirs.length; i++) {
        var dir = path.join(projectsDir, subdirs[i]);
        try {
          if (!fs.statSync(dir).isDirectory()) continue;
          var files = fs.readdirSync(dir);
          for (var j = 0; j < files.length; j++) {
            if (!files[j].endsWith(".jsonl")) continue;
            var fp = path.join(dir, files[j]);
            var st = fs.statSync(fp);
            if (st.birthtimeMs > cutoff || st.mtimeMs > cutoff) {
              var uuid = files[j].replace(".jsonl", "");
              if (!sessionConfigMap.has(uuid)) {
                sessionConfigMap.set(uuid, latest.settingsFile);
                saveSessionConfigMap(sessionConfigMap);
                console.log("[shared] CCL 自动映射: " + uuid.substring(0, 8) + " → " + latest.settingsFile);
              }
            }
          }
        } catch {}
      }
    } catch {}
  });
  console.log("[shared] CCL 会话监控已启动");
}

module.exports = {
  PROJECTS_DIR: PROJECTS_DIR,
  SNAPSHOTS_DIR: SNAPSHOTS_DIR,
  PORT: PORT,
  HTML_FILE: HTML_FILE,
  AGENT_NAMES_FILE: AGENT_NAMES_FILE,
  saveSessionConfigMap: saveSessionConfigMap,
  watchCclSessions: watchCclSessions,

  // Session cache
  sessionCache: new Map(),
  subAgentCache: new Map(),
  fileOffsets: new Map(),
  sessionConfigMap: loadSessionConfigMap(),
  cclProjectMap: loadCclSessions(),
  currentSettingsConfig: null,

  // SSE
  sseClients: [],
  SSE_MAX_CLIENTS: 50,

  // Watchers
  watchers: [],
  WATCH_DEBOUNCE_MS: 800,
  pendingChanges: new Map(),
  _processing: false,

  // Snapshots
  snapshotList: [],
  lastAutoSnapshot: 0,
  AUTO_SNAPSHOT_INTERVAL: 5 * 60 * 1000,

  // Pricing (loaded dynamically)
  PRICING: null
};

```
### M-026 - buildRelationsResponse 是 200+ 行的 God Function
- Severity: P1 CRITICAL
- File: routes/session.js lines [95, 300]
- Description: N/A
- Suggestion: 拆分为 5 个独立函数：parseDispatchCalls(parentLines)、buildSubAgentNodes(subDirs)、matchDispatchToAgents(dispatches, agents)、detectPhases(matchedEdges, userMessages)、buildWaterfallTrace(parentLines)。子 Agent 解析复用 agents.parseSubAgent。

Source code context:
```
var fs = require("fs");
var path = require("path");
var shared = require("../shared");
var scanner = require("../scanner");
var pricing = require("../pricing");
var agentsMod = require("../agents");

function makeSessionRouter() {
  return function handle(req, res) {
    // API: session agent relations (tree/timeline data)
    if (req.url.indexOf("/api/session/") === 0 && req.url.indexOf("/relations") > 0) {
      var relId = decodeURI(req.url.split("/api/session/")[1].split("/relations")[0]);
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(relId)) {
        res.writeHead(400, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ error: "invalid session id format" }));
        return true;
      }
      var relTarget = shared.sessionCache.get(relId);
      if (!relTarget || !relTarget._file) {
        scanner.scanSessions(shared.PROJECTS_DIR, []).then(function(all3) {
          for (var ri = 0; ri < all3.length; ri++) { if (all3[ri].id === relId) { relTarget = all3[ri]; break; } }
          buildRelationsResponse(relTarget, relId, res);
        });
      } else {
        buildRelationsResponse(relTarget, relId, res);
      }
      return true;
    }

    // API: single session
    if (req.url.startsWith("/api/session/") && !req.url.startsWith("/api/session/snapshot")) {
      var sessUrl = req.url.split("/api/session/")[1];
      var qpos = sessUrl.indexOf("?");
      var sid = qpos >= 0 ? decodeURI(sessUrl.slice(0, qpos)) : decodeURI(sessUrl);
      if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(sid)) {
        res.writeHead(400, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ error: "invalid session id format" }));
        return true;
      }
      var query = {};
      if (qpos >= 0) { var qs = sessUrl.slice(qpos+1).split("&"); for (var qi=0; qi<qs.length; qi++) { var kv=qs[qi].split("="); query[kv[0]]=kv[1]||""; } }
      var isFull = query.full === "1";
      var limit = parseInt(query.limit) || (isFull ? 0 : 200);

      // Look up session from cache first (fast path), fall back to full scan
      var cached = shared.sessionCache.get(sid);
      if (!cached || !cached._file) {
        scanner.scanSessions(shared.PROJECTS_DIR, []).then(function(all) {
          for (var j = 0; j < all.length; j++) { if (all[j].id === sid) { cached = all[j]; break; } }
          buildSessionDetailResponse(cached, sid, limit, res);
        });
      } else {
        buildSessionDetailResponse(cached, sid, limit, res);
      }
      return true;
    }

    return false;
  };
}

function buildSessionDetailResponse(cached, sid, limit, res) {
  if (!cached || !cached._file) { res.writeHead(404); res.end(JSON.stringify({ error: "not found" })); return; }
  var fpath = cached._file;

  var rawLines = [];
  var totalLines = cached.totalLines || 0;
  try {
    if (limit > 0) {
      var fsize = fs.statSync(fpath).size;
      var tailBytes = Math.min(fsize, limit * 1200 + 32768);
      var buf = Buffer.alloc(tailBytes);
      var fd = fs.openSync(fpath, "r");
      fs.readSync(fd, buf, 0, tailBytes, fsize - tailBytes);
      fs.closeSync(fd);
      var tailText = buf.toString("utf-8");
      var lines = tailText.split("\n");
      if (tailBytes < fsize && lines.length > 1) lines.shift();
      var takeStart = Math.max(0, lines.length - limit);
      if (!totalLines && lines.length > 0) totalLines = Math.max(lines.length, Math.round(fsize / (tailBytes / lines.length)));
      for (var k = takeStart; k < lines.length; k++) { try { rawLines.push(JSON.parse(lines[k])); } catch (e) {} }
    } else {
      var raw = fs.readFileSync(fpath, "utf-8").trim().split("\n");
      totalLines = raw.length;
      for (var k = 0; k < raw.length; k++) { try { rawLines.push(JSON.parse(raw[k])); } catch (e) {} }
    }
  } catch (e) {}

  var resp = {
    id: cached.id, title: cached.title, cwd: cached.cwd, model: cached.model,
    firstUserMsg: cached.firstUserMsg, customTitle: cached.customTitle, aiTitle: cached.aiTitle,
    _itok: cached._itok, _otok: cached._otok, _ctok: cached._ctok,
    userMsgCount: cached.userMsgCount, assistantMsgCount: cached.assistantMsgCount,
    recentUserMsgs: cached.recentUserMsgs, recentMsgTotal: cached.recentMsgTotal,
    keyDecisions: cached.keyDecisions, toolCallCount: cached.toolCallCount,
    fileWriteCount: cached.fileWriteCount, subAgents: cached.subAgents,
    lastTimestamp: cached.lastTimestamp, lastMeaningfulTimestamp: cached.lastMeaningfulTimestamp,
    lastStopReason: cached.lastStopReason, lastMeaningfulStopReason: cached.lastMeaningfulStopReason,
    messages: rawLines, totalLines: totalLines, limitUsed: limit,
    status: scanner.getStatus(cached.fileMtimeMs, cached.lastMeaningfulTimestamp, cached.lastMeaningfulStopReason),
    activity: scanner.getActivity(cached.recentUserMsgs || 0),
    tokenHeat: scanner.getTokenHeat((cached._itok || 0) + (cached._otok || 0)),
 
```
### M-004 - parseSubAgent 使用 readFileSync 读取整个 JSONL 文件，大文件阻塞事件循环
- Severity: P1 CRITICAL
- File: agents.js lines [67, 76]
- Description: N/A
- Suggestion: 将 parseSubAgent 改为流式解析（逐行读取），或复用 scanner.parseSessionChunk 的增量读取模式。至少应改为异步读取（fsp.readFile）。

Source code context:
```
var fs = require("fs");
var path = require("path");
var shared = require("./shared");
var scanner = require("./scanner");

function loadAgentNames() {
  try { return JSON.parse(fs.readFileSync(shared.AGENT_NAMES_FILE, "utf-8")); } catch (e) { return {}; }
}

function buildAgentName(subagent_type, description, fallback) {
  var parts = [];
  if (subagent_type) parts.push(subagent_type);
  if (description) parts.push(description.slice(0, 50));
  if (parts.length > 0) return parts.join(": ");
  return fallback || "";
}

// ============ Sub-Agent Detection ============

function findSubAgentFiles(sessionDir) {
  var results = [];
  var subagentsDir = path.join(sessionDir, "subagents");
  if (!fs.existsSync(subagentsDir)) return results;
  var entries;
  try { entries = fs.readdirSync(subagentsDir, { withFileTypes: true }); } catch (e) { return results; }
  for (var i = 0; i < entries.length; i++) {
    if (entries[i].isFile() && entries[i].name.endsWith(".jsonl") && entries[i].name.startsWith("agent-")) {
      results.push({ filePath: path.join(subagentsDir, entries[i].name), agentId: entries[i].name.replace(".jsonl", ""), parentSessionDir: sessionDir });
    }
  }
  return results;
}

function parseSubAgent(filePath, agentId, parentSessionId) {
  var info = {
    id: agentId, parentSessionId: parentSessionId, title: agentId, type: "sub-agent",
    model: null, status: "idle",
    totalLines: 0, _itok: 0, _otok: 0,
    lastTimestamp: null, lastEntryType: null, lastStopReason: null,
    lastMeaningfulTimestamp: null, lastMeaningfulStopReason: undefined,
    fileSize: 0, fileMtime: null, fileMtimeMs: 0,
    keyDecisions: [], toolCallCount: 0
  };

  try {
    var stat = fs.statSync(filePath);
    info.fileSize = stat.size;
    info.fileMtime = stat.mtime.toISOString();
    info.fileMtimeMs = stat.mtimeMs;
  } catch (e) { return info; }

  var content;
  try { content = fs.readFileSync(filePath, "utf-8"); } catch (e) { return info; }

  var lines = content.trim().split("\n");
  info.totalLines = lines.length;

  var firstUserText = null;
  for (var i = 0; i < lines.length; i++) {
    if (lines[i].trim() === "") continue;
    var obj = scanner.parseLine(lines[i]);
    if (!obj) continue;

    // Extract title from first user message
    if (firstUserText === null && obj.type === "user" && obj.message && obj.message.content) {
      for (var k2 = 0; k2 < obj.message.content.length; k2++) {
        if (obj.message.content[k2].type === "text" && obj.message.content[k2].text) {
          var rawText = obj.message.content[k2].text;
          var textLines = rawText.split("\n");
          var cleaned = "";
          for (var li = 0; li < textLines.length; li++) {
            var tline = textLines[li].trim();
            if (/^(Base directory|You are|你是一个|System:|\[|#)/.test(tline)) continue;
            if (tline) { cleaned = tline; break; }
          }
          if (!cleaned) cleaned = rawText.replace(/\n/g, " ").trim();
          firstUserText = cleaned.slice(0, 60);
          break;
        }
      }
    }

    if (obj.type === "assistant") {
      if (obj.message && obj.message.stop_reason) info.lastStopReason = obj.message.stop_reason;
      if (obj.message && obj.message.usage) {
        info._itok += (obj.message.usage.input_tokens || 0);
        info._otok += (obj.message.usage.output_tokens || 0);
      }
      if (!info.model && obj.message && obj.message.model) info.model = obj.message.model;
      if (obj.message && obj.message.content && Array.isArray(obj.message.content)) {
        for (var k = 0; k < obj.message.content.length; k++) {
          if (obj.message.content[k].type === "tool_use") {
            info.toolCallCount++;
            info.keyDecisions.push({
              timestamp: obj.timestamp || null,
              tool: obj.message.content[k].name || "unknown",
              input: obj.message.content[k].input ? JSON.stringify(obj.message.content[k].input).slice(0, 200) : ""
            });
          }
        }
      }
    }
    if (obj.type === "user" || obj.type === "assistant") {
      info.lastMeaningfulTimestamp = obj.timestamp || info.lastMeaningfulTimestamp;
      if (obj.type === "assistant" && obj.message && obj.message.stop_reason) {
        info.lastMeaningfulStopReason = obj.message.stop_reason;
      } else if (obj.type === "user") {
        info.lastMeaningfulStopReason = null;
      }
    }
    info.lastEntryType = obj.type;
    if (obj.timestamp) info.lastTimestamp = obj.timestamp;
  }

  // Use extracted first user message as title if available and no better name yet
  if (firstUserText && info.title === agentId) {
    info.title = firstUserText;
  }

  // Try meta file for descriptive title (takes priority over auto-extraction)
  var metaPath = filePath.replace(".jsonl", ".meta.json");
  try {
    var meta = JSON.parse(fs.readFileSync(metaPath, "utf-8"));
    if (meta.description) info.title = meta.description.slice(0, 80);
  } catch (e) {}

  return info;
}

function scanSubA
```
### M-017 - SSE 认证 token 通过 URL query 参数传递，易泄露
- Severity: P1 CRITICAL
- File: server/index.js lines [54, 68]
- Description: N/A
- Suggestion: 1) SSE 连接建立后立即轮换 token（短生命周期 token）；2) 使用一次性 nonce 机制：先通过 POST /api/sse-token 获取一次性 token，用完即废；3) 至少在 Access-Control-Allow-Origin 中严格限制来源（当前已限制 localhost，这点做得好）；4) 在文档中明确说明 token 不应通过反向代理暴露。

Source code context:
```
(file not found)
```
### M-021 - 会话 ID 使用 Math.random() 生成，可预测
- Severity: P1 CRITICAL
- File: server/index.js lines [206, 215]
- Description: N/A
- Suggestion: 使用 crypto.randomUUID()（Node.js 14.17+）或 crypto.randomBytes(16) 生成会话 ID：var sessionId = crypto.randomUUID(); 或手动实现符合 RFC 4122 v4 的 UUID。

Source code context:
```
(file not found)
```
### M-025 - swapSettingsJson 的写入锁是假锁，无法防止并发竞态
- Severity: P1 CRITICAL
- File: routes/open.js lines [178, 210]
- Description: N/A
- Suggestion: 既然所有启动路径都已通过 --settings 参数注入配置，swapSettingsJson 应该被完全移除。如果确实需要保留，应使用真正的异步互斥锁（如 async-mutex 库），而不是布尔标志。

Source code context:
```
var path = require("path");
var fs = require("fs");
var shared = require("../shared");
var scanner = require("../scanner");

// NOTE: 不再需要 settings.json 快照——所有启动路径都通过 --settings CLI 参数注入配置，不修改默认 settings.json

function makeOpenRouter() {
  var handle = function(req, res) {
    // API: list available settings files
    if (req.url === "/api/settings-list" && req.method === "GET") {
      var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
      var list = [];
      try {
        var files = fs.readdirSync(homeDir).filter(function(f) { return f.match(/^setting-.*\.json$/); });
        for (var i = 0; i < files.length; i++) {
          try {
            var cfg = JSON.parse(fs.readFileSync(path.join(homeDir, files[i]), "utf-8"));
            var url = (cfg.env && cfg.env.ANTHROPIC_BASE_URL) || "";
            list.push({ file: files[i], url: url.replace("https://", "").replace("/anthropic", ""), model: cfg.model || "" });
          } catch (e) {}
        }
      } catch (e) {}
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify(list));
      return true;
    }

    // API: open terminal to resume session
    if (req.url.startsWith("/api/terminal-bat/") && req.method === "GET") {
      var batId = decodeURI(req.url.split("/api/terminal-bat/")[1]);
      var batCached = shared.sessionCache.get(batId);
      if (!batCached || !batCached._file) {
        scanner.scanSessions(shared.PROJECTS_DIR, []).then(function(all2) {
          for (var bi = 0; bi < all2.length; bi++) { if (all2[bi].id === batId) { batCached = all2[bi]; break; } }
          launchTerminalBat(batCached, batId, res);
        });
      } else {
        launchTerminalBat(batCached, batId, res);
      }
      return true;
    }

    // API: open session in VSCode
    if (req.url.startsWith("/api/open-session/")) {
      var urlParts = req.url.split("?");
      var openId = decodeURI(urlParts[0].split("/api/open-session/")[1]);
      var queryConfig = null;
      if (urlParts[1]) {
        var m = urlParts[1].match(/config=([^&]+)/);
        if (m) queryConfig = decodeURIComponent(m[1]);
      }
      var target = shared.sessionCache.get(openId);
      if (!target || !target._file) {
        scanner.scanSessions(shared.PROJECTS_DIR, []).then(function(all2) {
          for (var m = 0; m < all2.length; m++) { if (all2[m].id === openId) { target = all2[m]; break; } }
          launchSession(target, openId, res, queryConfig);
        });
      } else {
        launchSession(target, openId, res, queryConfig);
      }
      return true;
    }

    return false;
  };
  handle.launchSessionDirect = makeOpenRouter.launchSessionDirect;
  handle.swapSettingsJson = makeOpenRouter.swapSettingsJson;
  return handle;
}

// P0-003: 验证 configName 格式，防止路径遍历
function isValidConfigName(name) {
  return typeof name === "string" && /^setting-[a-zA-Z0-9_-]+\.json$/.test(name);
}

// 静默启动 Claude Code——不弹终端窗口，通过 --settings 注入 API 配置，不修改默认 settings.json
function spawnDirect(claudeExe, claudeArgs, configFile, cwd) {
  var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
  var env = Object.assign({}, process.env);

  // 从配置文件读取 env vars，注入到子进程环境中（不影响当前进程）
  if (configFile) {
    var configPath = path.join(homeDir, ".claude", configFile);
    if (fs.existsSync(configPath)) {
      try {
        var cfg = JSON.parse(fs.readFileSync(configPath, "utf-8"));
        if (cfg.model) env.ANTHROPIC_MODEL = cfg.model;
        if (cfg.env) {
          var envKeys = Object.keys(cfg.env);
          for (var i = 0; i < envKeys.length; i++) {
            var k = envKeys[i];
            if (k.startsWith("ANTHROPIC_") || k.startsWith("CLAUDE_")) {
              env[k] = cfg.env[k];
            }
          }
        }
      } catch (e) {}
    }
  }

  console.log("[open] spawn → " + claudeExe + " " + claudeArgs.join(" "));
  try {
    var child = require("child_process").spawn(claudeExe, claudeArgs, {
      cwd: cwd || undefined,
      env: env,
      detached: true,
      windowsHide: true,
      stdio: "ignore"
    });
    child.unref();
    // 检测进程是否在 3 秒内立即退出（启动失败）
    var exited = false;
    child.on("exit", function(code) {
      exited = true;
      if (code !== 0 && code !== null) {
        console.error("[open] 进程立即退出，code=" + code + "，可能是 --resume 失败或 settings.json 配置错误");
      }
    });
    setTimeout(function() {
      if (!exited) {
        console.log("[open] 进程运行中，PID=" + child.pid);
      }
    }, 3000);
    return true;
  } catch (e) {
    console.error("[open] spawn failed:", e.message);
    return false;
  }
}

function launchTerminalBat(batCached, batId, res) {
  var batCwd = batCached && batCached.cwd ? batCached.cwd : "";
  var npmBin = process.env.APPDATA ? path.join(process.env.APPDATA, "npm") : null;
  var claudeExe = npmBin ? path.join(npmBin, "claude.cmd") : "claude";
  var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users
```
### M-030 - watchCclSessions 在 fs.watch 回调中使用同步 I/O
- Severity: P1 CRITICAL
- File: shared.js lines [72, 85]
- Description: N/A
- Suggestion: 将 fs.watch 回调中的逻辑改为异步：使用 fs.promises.readFile、fs.promises.readdir、fs.promises.stat。或者使用 chokidar 等库提供更可靠的文件监控。

Source code context:
```
var path = require("path");
var fs = require("fs");

var PROJECTS_DIR = process.env.CLAUDE_PROJECTS_DIR || path.join(process.env.HOME || process.env.USERPROFILE || "~", ".claude", "projects");
var SNAPSHOTS_DIR = path.join(process.env.HOME || process.env.USERPROFILE || "~", ".claude", "armada", "snapshots");
var PORT = parseInt(process.env.CC_DASHBOARD_PORT || "5022", 10);
var HTML_FILE = path.join(__dirname, "..", "index.html");
var AGENT_NAMES_FILE = path.join(process.env.HOME || process.env.USERPROFILE || "~", ".claude", "agent-names.json");
var SESSION_CONFIG_FILE = path.join(process.env.HOME || process.env.USERPROFILE || "~", ".claude", "session-config-map.json");
var CCL_SESSIONS_FILE = path.join(process.env.HOME || process.env.USERPROFILE || "~", ".claude", ".ccl-sessions.json");

// 持久化 sessionConfigMap
function loadSessionConfigMap() {
  try {
    if (fs.existsSync(SESSION_CONFIG_FILE)) {
      var data = JSON.parse(fs.readFileSync(SESSION_CONFIG_FILE, "utf-8"));
      var m = new Map();
      var keys = Object.keys(data);
      for (var i = 0; i < keys.length; i++) { m.set(keys[i], data[keys[i]]); }
      console.log("[shared] 加载 sessionConfigMap: " + m.size + " 条");
      return m;
    }
  } catch (e) { console.error("[shared] 加载 sessionConfigMap 失败:", e.message); }
  return new Map();
}

function saveSessionConfigMap(m) {
  try {
    var obj = {};
    m.forEach(function(v, k) { obj[k] = v; });
    fs.writeFileSync(SESSION_CONFIG_FILE, JSON.stringify(obj, null, 2), "utf-8");
  } catch (e) { console.error("[shared] 保存 sessionConfigMap 失败:", e.message); }
}

// 加载 CCL 会话记录（project → settingsFile 映射）
function loadCclSessions() {
  try {
    if (fs.existsSync(CCL_SESSIONS_FILE)) {
      var data = JSON.parse(fs.readFileSync(CCL_SESSIONS_FILE, "utf-8"));
      var m = new Map();
      for (var i = 0; i < data.length; i++) {
        var rec = data[i];
        if (rec.project && rec.settingsFile) {
          // 同一项目可能有多个记录，取最新的（后面的覆盖前面的）
          m.set(rec.project, rec.settingsFile);
        }
      }
      console.log("[shared] 加载 CCL 会话记录: " + m.size + " 个项目");
      return m;
    }
  } catch (e) { console.error("[shared] 加载 CCL 会话记录失败:", e.message); }
  return new Map();
}

// 监控 CCL 会话文件变化，自动将新 CCL 会话映射到 JSONL 文件
function watchCclSessions(sessionConfigMap, projectsDir) {
  if (!fs.existsSync(CCL_SESSIONS_FILE)) return;
  var lastCount = 0;
  try { lastCount = JSON.parse(fs.readFileSync(CCL_SESSIONS_FILE, "utf-8")).length; } catch {}
  fs.watch(CCL_SESSIONS_FILE, function() {
    try {
      var data = JSON.parse(fs.readFileSync(CCL_SESSIONS_FILE, "utf-8"));
      if (data.length <= lastCount) return;
      lastCount = data.length;
      var latest = data[data.length - 1];
      if (!latest.project || !latest.settingsFile) return;
      // 扫描 projects 目录，找最近 15 秒内创建的 JSONL 文件
      var cutoff = Date.now() - 15000;
      var subdirs = fs.readdirSync(projectsDir);
      for (var i = 0; i < subdirs.length; i++) {
        var dir = path.join(projectsDir, subdirs[i]);
        try {
          if (!fs.statSync(dir).isDirectory()) continue;
          var files = fs.readdirSync(dir);
          for (var j = 0; j < files.length; j++) {
            if (!files[j].endsWith(".jsonl")) continue;
            var fp = path.join(dir, files[j]);
            var st = fs.statSync(fp);
            if (st.birthtimeMs > cutoff || st.mtimeMs > cutoff) {
              var uuid = files[j].replace(".jsonl", "");
              if (!sessionConfigMap.has(uuid)) {
                sessionConfigMap.set(uuid, latest.settingsFile);
                saveSessionConfigMap(sessionConfigMap);
                console.log("[shared] CCL 自动映射: " + uuid.substring(0, 8) + " → " + latest.settingsFile);
              }
            }
          }
        } catch {}
      }
    } catch {}
  });
  console.log("[shared] CCL 会话监控已启动");
}

module.exports = {
  PROJECTS_DIR: PROJECTS_DIR,
  SNAPSHOTS_DIR: SNAPSHOTS_DIR,
  PORT: PORT,
  HTML_FILE: HTML_FILE,
  AGENT_NAMES_FILE: AGENT_NAMES_FILE,
  saveSessionConfigMap: saveSessionConfigMap,
  watchCclSessions: watchCclSessions,

  // Session cache
  sessionCache: new Map(),
  subAgentCache: new Map(),
  fileOffsets: new Map(),
  sessionConfigMap: loadSessionConfigMap(),
  cclProjectMap: loadCclSessions(),
  currentSettingsConfig: null,

  // SSE
  sseClients: [],
  SSE_MAX_CLIENTS: 50,

  // Watchers
  watchers: [],
  WATCH_DEBOUNCE_MS: 800,
  pendingChanges: new Map(),
  _processing: false,

  // Snapshots
  snapshotList: [],
  lastAutoSnapshot: 0,
  AUTO_SNAPSHOT_INTERVAL: 5 * 60 * 1000,

  // Pricing (loaded dynamically)
  PRICING: null
};

```
### M-027 - parseSubAgent 对每个子 Agent 读取完整文件到内存
- Severity: P1 CRITICAL
- File: agents.js lines [43, 48]
- Description: N/A
- Suggestion: 与 scanner.js 统一处理：(1) 使用异步 I/O；(2) 对于只需要最后几行的场景（如 status 判断），从文件末尾反向读取；(3) 复用 scanner.parseSessionChunk 的增量解析逻辑，避免重复实现。

Source code context:
```
var fs = require("fs");
var path = require("path");
var shared = require("./shared");
var scanner = require("./scanner");

function loadAgentNames() {
  try { return JSON.parse(fs.readFileSync(shared.AGENT_NAMES_FILE, "utf-8")); } catch (e) { return {}; }
}

function buildAgentName(subagent_type, description, fallback) {
  var parts = [];
  if (subagent_type) parts.push(subagent_type);
  if (description) parts.push(description.slice(0, 50));
  if (parts.length > 0) return parts.join(": ");
  return fallback || "";
}

// ============ Sub-Agent Detection ============

function findSubAgentFiles(sessionDir) {
  var results = [];
  var subagentsDir = path.join(sessionDir, "subagents");
  if (!fs.existsSync(subagentsDir)) return results;
  var entries;
  try { entries = fs.readdirSync(subagentsDir, { withFileTypes: true }); } catch (e) { return results; }
  for (var i = 0; i < entries.length; i++) {
    if (entries[i].isFile() && entries[i].name.endsWith(".jsonl") && entries[i].name.startsWith("agent-")) {
      results.push({ filePath: path.join(subagentsDir, entries[i].name), agentId: entries[i].name.replace(".jsonl", ""), parentSessionDir: sessionDir });
    }
  }
  return results;
}

function parseSubAgent(filePath, agentId, parentSessionId) {
  var info = {
    id: agentId, parentSessionId: parentSessionId, title: agentId, type: "sub-agent",
    model: null, status: "idle",
    totalLines: 0, _itok: 0, _otok: 0,
    lastTimestamp: null, lastEntryType: null, lastStopReason: null,
    lastMeaningfulTimestamp: null, lastMeaningfulStopReason: undefined,
    fileSize: 0, fileMtime: null, fileMtimeMs: 0,
    keyDecisions: [], toolCallCount: 0
  };

  try {
    var stat = fs.statSync(filePath);
    info.fileSize = stat.size;
    info.fileMtime = stat.mtime.toISOString();
    info.fileMtimeMs = stat.mtimeMs;
  } catch (e) { return info; }

  var content;
  try { content = fs.readFileSync(filePath, "utf-8"); } catch (e) { return info; }

  var lines = content.trim().split("\n");
  info.totalLines = lines.length;

  var firstUserText = null;
  for (var i = 0; i < lines.length; i++) {
    if (lines[i].trim() === "") continue;
    var obj = scanner.parseLine(lines[i]);
    if (!obj) continue;

    // Extract title from first user message
    if (firstUserText === null && obj.type === "user" && obj.message && obj.message.content) {
      for (var k2 = 0; k2 < obj.message.content.length; k2++) {
        if (obj.message.content[k2].type === "text" && obj.message.content[k2].text) {
          var rawText = obj.message.content[k2].text;
          var textLines = rawText.split("\n");
          var cleaned = "";
          for (var li = 0; li < textLines.length; li++) {
            var tline = textLines[li].trim();
            if (/^(Base directory|You are|你是一个|System:|\[|#)/.test(tline)) continue;
            if (tline) { cleaned = tline; break; }
          }
          if (!cleaned) cleaned = rawText.replace(/\n/g, " ").trim();
          firstUserText = cleaned.slice(0, 60);
          break;
        }
      }
    }

    if (obj.type === "assistant") {
      if (obj.message && obj.message.stop_reason) info.lastStopReason = obj.message.stop_reason;
      if (obj.message && obj.message.usage) {
        info._itok += (obj.message.usage.input_tokens || 0);
        info._otok += (obj.message.usage.output_tokens || 0);
      }
      if (!info.model && obj.message && obj.message.model) info.model = obj.message.model;
      if (obj.message && obj.message.content && Array.isArray(obj.message.content)) {
        for (var k = 0; k < obj.message.content.length; k++) {
          if (obj.message.content[k].type === "tool_use") {
            info.toolCallCount++;
            info.keyDecisions.push({
              timestamp: obj.timestamp || null,
              tool: obj.message.content[k].name || "unknown",
              input: obj.message.content[k].input ? JSON.stringify(obj.message.content[k].input).slice(0, 200) : ""
            });
          }
        }
      }
    }
    if (obj.type === "user" || obj.type === "assistant") {
      info.lastMeaningfulTimestamp = obj.timestamp || info.lastMeaningfulTimestamp;
      if (obj.type === "assistant" && obj.message && obj.message.stop_reason) {
        info.lastMeaningfulStopReason = obj.message.stop_reason;
      } else if (obj.type === "user") {
        info.lastMeaningfulStopReason = null;
      }
    }
    info.lastEntryType = obj.type;
    if (obj.timestamp) info.lastTimestamp = obj.timestamp;
  }

  // Use extracted first user message as title if available and no better name yet
  if (firstUserText && info.title === agentId) {
    info.title = firstUserText;
  }

  // Try meta file for descriptive title (takes priority over auto-extraction)
  var metaPath = filePath.replace(".jsonl", ".meta.json");
  try {
    var meta = JSON.parse(fs.readFileSync(metaPath, "utf-8"));
    if (meta.description) info.title = meta.description.slice(0, 80);
  } catch (e) {}

  return info;
}

function scanSubA
```
### M-032 - UUID 全局替换策略过于激进，可能误伤数据内容
- Severity: P1 CRITICAL
- File: index.js lines [107, 135]
- Description: N/A
- Suggestion: 只替换已知的结构性字段中的 UUID（如 sessionId、parentSessionId），而不是全局正则替换。可以逐行 JSON.parse，只修改特定字段，然后 JSON.stringify 回去。这样更安全，也避免了二次替换问题。

Source code context:
```
// 阿勋的CC面板 5.22 — 缓存+增量版（端口5022），模块化架构
var http = require("http");
var fs = require("fs");
var path = require("path");
var crypto = require("crypto");
var shared = require("./shared");
var pricing = require("./pricing");
var scanner = require("./scanner");
var snapshot = require("./snapshot");
var sse = require("./sse");
var watcher = require("./watcher");
var agents = require("./agents");

// ============ Token 认证 ============
var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
var TOKEN_PATH = path.join(homeDir, ".claude", "panel-token");
var PANEL_TOKEN;

try {
  if (fs.existsSync(TOKEN_PATH)) {
    PANEL_TOKEN = fs.readFileSync(TOKEN_PATH, "utf-8").trim();
    console.log("[认证] 已加载 panel-token");
  } else {
    PANEL_TOKEN = crypto.randomBytes(32).toString("hex");
    fs.mkdirSync(path.dirname(TOKEN_PATH), { recursive: true });
    fs.writeFileSync(TOKEN_PATH, PANEL_TOKEN);
    console.log("[认证] 已生成新的 panel-token: " + TOKEN_PATH);
  }
} catch (e) {
  console.error("[认证] token 处理失败，使用临时 token:", e.message);
  PANEL_TOKEN = crypto.randomBytes(32).toString("hex");
}

console.log("[认证] Token: " + PANEL_TOKEN.substring(0, 8) + "...");

// 不需要认证的路径（静态资源、迁移工具）
var PUBLIC_PATHS = [
  "/",
  "/index.html",
  "/sortable.min.js",
  "/qr-wechat.png",
  "/qr-alipay.jpg",
  "/migrate",
  "/import-localstorage"
];

function isPublicPath(urlPath) {
  for (var i = 0; i < PUBLIC_PATHS.length; i++) {
    if (urlPath === PUBLIC_PATHS[i]) return true;
  }
  return false;
}

function authenticateRequest(req, urlObj) {
  // 优先从 Authorization header 获取
  var authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith("Bearer ")) {
    return authHeader.substring(7) === PANEL_TOKEN;
  }
  // 其次从 query param 获取（用于 SSE）
  var tokenParam = urlObj.searchParams.get("token");
  if (tokenParam) {
    return tokenParam === PANEL_TOKEN;
  }
  return false;
}

// Route handlers
var sessionsRouter = require("./routes/sessions")();
var sessionRouter = require("./routes/session")();
var snapshotsRouter = require("./routes/snapshots")();
var openRouter = require("./routes/open")();

// ============ HTTP Server ============

var server = http.createServer(function(req, res) {
  var origin = req.headers.origin;
  if (origin && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
  }

  try {
    var urlObj = new URL(req.url, "http://localhost");
    var urlPath = urlObj.pathname;

    // 公开路径不需要认证
    if (!isPublicPath(urlPath)) {
      // API 路径需要认证
      if (!authenticateRequest(req, urlObj)) {
        res.writeHead(401, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ error: "unauthorized", message: "请提供有效的 token" }));
        return;
      }
    }

    // SSE（需要认证，通过 query param 传递 token）
    if (sse.handleSSE(req, res)) return;

    // 一次性 localStorage 导入路由
    if (req.url === "/import-localstorage") {
      var importFile = path.join(__dirname, "import-data.json");
      if (!fs.existsSync(importFile)) {
        res.writeHead(404); res.end("import-data.json not found");
        return;
      }
      var importData = fs.readFileSync(importFile, "utf8");
      var safeData = JSON.stringify(JSON.parse(importData)).replace(/<\/script/gi, '<\\/script');
      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>导入配置</title><style>body{font-family:system-ui;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}.ok{color:#4caf50}.err{color:#f44336}.key{font-family:monospace;font-size:13px;margin:4px 0}.box{background:#16213e;border-radius:8px;padding:16px;margin:12px 0}h2{margin:0 0 8px}</style></head><body><h2>CC面板配置导入</h2><div id="status">正在导入...</div><div id="results" class="box"></div><script>!function(){var d=' + safeData + ';var ok=0,fail=0,results=[];Object.entries(d).forEach(function(e){try{localStorage.setItem(e[0],e[1]);var v=e[1];results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"ok\\">OK</span> ("+(v.length>80?v.substring(0,80)+"...":v)+")</div>");ok++}catch(err){results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"err\\">FAIL: "+err.message+"</span></div>");fail++}});var status=document.getElementById("status");status.innerHTML=ok+" 个成功, "+fail+" 个失败 (共 "+Object.keys(d).length+" 项)";status.className=ok>0?"ok":"err";document.getElementById("results").innerHTML=results.join("");if(ok>0){var p=document.createElement("p");p.textContent="配置已写入 Edge localStorage for "+window.location.origin;p.className="ok";document.body.appendChild(p)}else{var p2=document.createElement("p");p2.textContent="未写入任何数据,请检查浏览器控制台";p2.className="err";document.body.appendChild(p2)}}();</script></body></html>';
      res.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      res.end(html);
      return;
    }

    // HTML
    if (req.url === "/" || req.url === "/index.html") {
      if (fs.existsSync(shared.HTML_FILE)) {
        res
```
### M-016 - XSS: import-localstorage 端点将未净化数据嵌入 HTML script 上下文
- Severity: P0 BLOCKING
- File: server/index.js lines [106, 109]
- Description: N/A
- Suggestion: 方案一：将 JSON 数据 base64 编码后嵌入 HTML，JS 端解码：var safeData = Buffer.from(JSON.stringify(JSON.parse(importData))).toString('base64'); 然后 JS 端用 atob() 解码。方案二：将数据写入独立 JS 文件，通过 <script src> 引用（CSP 可控）。方案三：至少对 < 字符也做转义：replace(/</g, '\\u003c')。方案四：添加认证要求，移出 PUBLIC_PATHS。

Source code context:
```
(file not found)
```
### M-018 - parseSubAgent 无文件大小限制，可被巨型 JSONL 文件触发 OOM
- Severity: P1 CRITICAL
- File: server/agents.js lines [46, 56]
- Description: N/A
- Suggestion: 1) 在 readFileSync 前检查 stat.size，超过阈值（如 10MB）则跳过或截断读取；2) 使用流式逐行读取替代一次性读取；3) 添加异常处理确保 OOM 时进程能优雅恢复。

Source code context:
```
(file not found)
```
### M-019 - swapSettingsJson 使用非原子写入，进程崩溃可损坏 settings.json
- Severity: P1 CRITICAL
- File: server/routes/open.js lines [155, 180]
- Description: N/A
- Suggestion: 1) 使用原子写入模式：先写入 .tmp 文件，然后 fs.rename 覆盖（rename 在大多数文件系统上是原子操作）；2) 写入前备份当前 settings.json；3) 如果确认不再需要此功能，删除整个函数。

Source code context:
```
(file not found)
```
### M-029 - Panel token 以明文写入文件系统
- Severity: P1 CRITICAL
- File: index.js lines [55, 60]
- Description: N/A
- Suggestion: 方案1：设置严格的文件权限（chmod 600 / icacls 仅当前用户）。方案2：不在文件系统存储 token，改为环境变量传入。方案3：如果必须存储，使用加密存储（如 Windows DPAPI）。

Source code context:
```
// 阿勋的CC面板 5.22 — 缓存+增量版（端口5022），模块化架构
var http = require("http");
var fs = require("fs");
var path = require("path");
var crypto = require("crypto");
var shared = require("./shared");
var pricing = require("./pricing");
var scanner = require("./scanner");
var snapshot = require("./snapshot");
var sse = require("./sse");
var watcher = require("./watcher");
var agents = require("./agents");

// ============ Token 认证 ============
var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
var TOKEN_PATH = path.join(homeDir, ".claude", "panel-token");
var PANEL_TOKEN;

try {
  if (fs.existsSync(TOKEN_PATH)) {
    PANEL_TOKEN = fs.readFileSync(TOKEN_PATH, "utf-8").trim();
    console.log("[认证] 已加载 panel-token");
  } else {
    PANEL_TOKEN = crypto.randomBytes(32).toString("hex");
    fs.mkdirSync(path.dirname(TOKEN_PATH), { recursive: true });
    fs.writeFileSync(TOKEN_PATH, PANEL_TOKEN);
    console.log("[认证] 已生成新的 panel-token: " + TOKEN_PATH);
  }
} catch (e) {
  console.error("[认证] token 处理失败，使用临时 token:", e.message);
  PANEL_TOKEN = crypto.randomBytes(32).toString("hex");
}

console.log("[认证] Token: " + PANEL_TOKEN.substring(0, 8) + "...");

// 不需要认证的路径（静态资源、迁移工具）
var PUBLIC_PATHS = [
  "/",
  "/index.html",
  "/sortable.min.js",
  "/qr-wechat.png",
  "/qr-alipay.jpg",
  "/migrate",
  "/import-localstorage"
];

function isPublicPath(urlPath) {
  for (var i = 0; i < PUBLIC_PATHS.length; i++) {
    if (urlPath === PUBLIC_PATHS[i]) return true;
  }
  return false;
}

function authenticateRequest(req, urlObj) {
  // 优先从 Authorization header 获取
  var authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith("Bearer ")) {
    return authHeader.substring(7) === PANEL_TOKEN;
  }
  // 其次从 query param 获取（用于 SSE）
  var tokenParam = urlObj.searchParams.get("token");
  if (tokenParam) {
    return tokenParam === PANEL_TOKEN;
  }
  return false;
}

// Route handlers
var sessionsRouter = require("./routes/sessions")();
var sessionRouter = require("./routes/session")();
var snapshotsRouter = require("./routes/snapshots")();
var openRouter = require("./routes/open")();

// ============ HTTP Server ============

var server = http.createServer(function(req, res) {
  var origin = req.headers.origin;
  if (origin && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
  }

  try {
    var urlObj = new URL(req.url, "http://localhost");
    var urlPath = urlObj.pathname;

    // 公开路径不需要认证
    if (!isPublicPath(urlPath)) {
      // API 路径需要认证
      if (!authenticateRequest(req, urlObj)) {
        res.writeHead(401, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ error: "unauthorized", message: "请提供有效的 token" }));
        return;
      }
    }

    // SSE（需要认证，通过 query param 传递 token）
    if (sse.handleSSE(req, res)) return;

    // 一次性 localStorage 导入路由
    if (req.url === "/import-localstorage") {
      var importFile = path.join(__dirname, "import-data.json");
      if (!fs.existsSync(importFile)) {
        res.writeHead(404); res.end("import-data.json not found");
        return;
      }
      var importData = fs.readFileSync(importFile, "utf8");
      var safeData = JSON.stringify(JSON.parse(importData)).replace(/<\/script/gi, '<\\/script');
      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>导入配置</title><style>body{font-family:system-ui;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}.ok{color:#4caf50}.err{color:#f44336}.key{font-family:monospace;font-size:13px;margin:4px 0}.box{background:#16213e;border-radius:8px;padding:16px;margin:12px 0}h2{margin:0 0 8px}</style></head><body><h2>CC面板配置导入</h2><div id="status">正在导入...</div><div id="results" class="box"></div><script>!function(){var d=' + safeData + ';var ok=0,fail=0,results=[];Object.entries(d).forEach(function(e){try{localStorage.setItem(e[0],e[1]);var v=e[1];results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"ok\\">OK</span> ("+(v.length>80?v.substring(0,80)+"...":v)+")</div>");ok++}catch(err){results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"err\\">FAIL: "+err.message+"</span></div>");fail++}});var status=document.getElementById("status");status.innerHTML=ok+" 个成功, "+fail+" 个失败 (共 "+Object.keys(d).length+" 项)";status.className=ok>0?"ok":"err";document.getElementById("results").innerHTML=results.join("");if(ok>0){var p=document.createElement("p");p.textContent="配置已写入 Edge localStorage for "+window.location.origin;p.className="ok";document.body.appendChild(p)}else{var p2=document.createElement("p");p2.textContent="未写入任何数据,请检查浏览器控制台";p2.className="err";document.body.appendChild(p2)}}();</script></body></html>';
      res.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      res.end(html);
      return;
    }

    // HTML
    if (req.url === "/" || req.url === "/index.html") {
      if (fs.existsSync(shared.HTML_FILE)) {
        res
```
### M-020 - scanSessions 使用同步 fs 操作，大目录扫描可阻塞事件循环
- Severity: P1 CRITICAL
- File: server/scanner.js lines [140, 150]
- Description: N/A
- Suggestion: 1) 将 parseSessionChunk 中的同步文件操作替换为异步版本（fsp.readFile 等）；2) 使用 fs.promises API 替代 fs 同步方法；3) 考虑增量扫描策略：只扫描 mtime 变化的文件（已有 fileOffsets 机制，但 fallback 路径仍用同步全量读取）。

Source code context:
```
(file not found)
```
### M-028 - 认证逻辑中 token 比较未使用时间安全函数
- Severity: P1 CRITICAL
- File: index.js lines [72, 80]
- Description: N/A
- Suggestion: 使用 crypto.timingSafeEqual 进行 token 比较。需要先确保两个 buffer 长度相同。

Source code context:
```
// 阿勋的CC面板 5.22 — 缓存+增量版（端口5022），模块化架构
var http = require("http");
var fs = require("fs");
var path = require("path");
var crypto = require("crypto");
var shared = require("./shared");
var pricing = require("./pricing");
var scanner = require("./scanner");
var snapshot = require("./snapshot");
var sse = require("./sse");
var watcher = require("./watcher");
var agents = require("./agents");

// ============ Token 认证 ============
var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
var TOKEN_PATH = path.join(homeDir, ".claude", "panel-token");
var PANEL_TOKEN;

try {
  if (fs.existsSync(TOKEN_PATH)) {
    PANEL_TOKEN = fs.readFileSync(TOKEN_PATH, "utf-8").trim();
    console.log("[认证] 已加载 panel-token");
  } else {
    PANEL_TOKEN = crypto.randomBytes(32).toString("hex");
    fs.mkdirSync(path.dirname(TOKEN_PATH), { recursive: true });
    fs.writeFileSync(TOKEN_PATH, PANEL_TOKEN);
    console.log("[认证] 已生成新的 panel-token: " + TOKEN_PATH);
  }
} catch (e) {
  console.error("[认证] token 处理失败，使用临时 token:", e.message);
  PANEL_TOKEN = crypto.randomBytes(32).toString("hex");
}

console.log("[认证] Token: " + PANEL_TOKEN.substring(0, 8) + "...");

// 不需要认证的路径（静态资源、迁移工具）
var PUBLIC_PATHS = [
  "/",
  "/index.html",
  "/sortable.min.js",
  "/qr-wechat.png",
  "/qr-alipay.jpg",
  "/migrate",
  "/import-localstorage"
];

function isPublicPath(urlPath) {
  for (var i = 0; i < PUBLIC_PATHS.length; i++) {
    if (urlPath === PUBLIC_PATHS[i]) return true;
  }
  return false;
}

function authenticateRequest(req, urlObj) {
  // 优先从 Authorization header 获取
  var authHeader = req.headers.authorization;
  if (authHeader && authHeader.startsWith("Bearer ")) {
    return authHeader.substring(7) === PANEL_TOKEN;
  }
  // 其次从 query param 获取（用于 SSE）
  var tokenParam = urlObj.searchParams.get("token");
  if (tokenParam) {
    return tokenParam === PANEL_TOKEN;
  }
  return false;
}

// Route handlers
var sessionsRouter = require("./routes/sessions")();
var sessionRouter = require("./routes/session")();
var snapshotsRouter = require("./routes/snapshots")();
var openRouter = require("./routes/open")();

// ============ HTTP Server ============

var server = http.createServer(function(req, res) {
  var origin = req.headers.origin;
  if (origin && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
  }

  try {
    var urlObj = new URL(req.url, "http://localhost");
    var urlPath = urlObj.pathname;

    // 公开路径不需要认证
    if (!isPublicPath(urlPath)) {
      // API 路径需要认证
      if (!authenticateRequest(req, urlObj)) {
        res.writeHead(401, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ error: "unauthorized", message: "请提供有效的 token" }));
        return;
      }
    }

    // SSE（需要认证，通过 query param 传递 token）
    if (sse.handleSSE(req, res)) return;

    // 一次性 localStorage 导入路由
    if (req.url === "/import-localstorage") {
      var importFile = path.join(__dirname, "import-data.json");
      if (!fs.existsSync(importFile)) {
        res.writeHead(404); res.end("import-data.json not found");
        return;
      }
      var importData = fs.readFileSync(importFile, "utf8");
      var safeData = JSON.stringify(JSON.parse(importData)).replace(/<\/script/gi, '<\\/script');
      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>导入配置</title><style>body{font-family:system-ui;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}.ok{color:#4caf50}.err{color:#f44336}.key{font-family:monospace;font-size:13px;margin:4px 0}.box{background:#16213e;border-radius:8px;padding:16px;margin:12px 0}h2{margin:0 0 8px}</style></head><body><h2>CC面板配置导入</h2><div id="status">正在导入...</div><div id="results" class="box"></div><script>!function(){var d=' + safeData + ';var ok=0,fail=0,results=[];Object.entries(d).forEach(function(e){try{localStorage.setItem(e[0],e[1]);var v=e[1];results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"ok\\">OK</span> ("+(v.length>80?v.substring(0,80)+"...":v)+")</div>");ok++}catch(err){results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"err\\">FAIL: "+err.message+"</span></div>");fail++}});var status=document.getElementById("status");status.innerHTML=ok+" 个成功, "+fail+" 个失败 (共 "+Object.keys(d).length+" 项)";status.className=ok>0?"ok":"err";document.getElementById("results").innerHTML=results.join("");if(ok>0){var p=document.createElement("p");p.textContent="配置已写入 Edge localStorage for "+window.location.origin;p.className="ok";document.body.appendChild(p)}else{var p2=document.createElement("p");p2.textContent="未写入任何数据,请检查浏览器控制台";p2.className="err";document.body.appendChild(p2)}}();</script></body></html>';
      res.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      res.end(html);
      return;
    }

    // HTML
    if (req.url === "/" || req.url === "/index.html") {
      if (fs.existsSync(shared.HTML_FILE)) {
        res
```


## 输出格式要求
**只输出 JSON，不要输出任何 JSON 以外的文本。**

```json
{
  "verifications": [
    {
      "merged_id": "M-001",
      "verdict": "CONFIRM | REFUTE | DOWNGRADE | NEEDS_HUMAN",
      "adjusted_severity": "如果DOWNGRADE填新等级，否则null",
      "rationale": "详细理由",
      "confidence_after_verification": 0.9
    }
  ],
  "summary": {
    "total_verified": 0,
    "confirmed": 0,
    "refuted": 0,
    "downgraded": 0,
    "needs_human": 0
  }
}
```