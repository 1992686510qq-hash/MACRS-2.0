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

### M-001 - buildRelationsResponse 是 266 行的巨型函数——职责过多难以维护和测试
- Severity: P0 BLOCKING
- File: server/routes/session.js lines [101, 367]
- Description: N/A
- Suggestion: 将 pLines 声明提升到 try 块之前（var pLines = []），或在 try 块外添加防御性检查（if (!pLines || pLines.length === 0)）提前返回响应。

Source code context:
```
(file not found)
```
### M-014 - XSS: import-data.json 内容直接注入 HTML 无任何编码
- Severity: P0 BLOCKING
- File: index.js lines [18, 26]
- Description: N/A
- Suggestion: 对 importData 进行 JSON 编码后再嵌入 HTML，或使用 CSP header 限制内联脚本执行。

Source code context:
```
// 阿勋的CC面板 5.22 — 缓存+增量版（端口5022），模块化架构
var http = require("http");
var fs = require("fs");
var path = require("path");
var shared = require("./shared");
var pricing = require("./pricing");
var scanner = require("./scanner");
var snapshot = require("./snapshot");
var sse = require("./sse");
var watcher = require("./watcher");
var agents = require("./agents");

// Route handlers
var sessionsRouter = require("./routes/sessions")();
var sessionRouter = require("./routes/session")();
var snapshotsRouter = require("./routes/snapshots")();
var openRouter = require("./routes/open")();

// ============ HTTP Server ============

var server = http.createServer(function(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");

  try {
    // SSE
    if (sse.handleSSE(req, res)) return;

    // 一次性 localStorage 导入路由
    if (req.url === "/import-localstorage") {
      var importFile = path.join(__dirname, "import-data.json");
      if (!fs.existsSync(importFile)) {
        res.writeHead(404); res.end("import-data.json not found");
        return;
      }
      var importData = fs.readFileSync(importFile, "utf8");
      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>导入配置</title><style>body{font-family:system-ui;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}.ok{color:#4caf50}.err{color:#f44336}.key{font-family:monospace;font-size:13px;margin:4px 0}.box{background:#16213e;border-radius:8px;padding:16px;margin:12px 0}h2{margin:0 0 8px}</style></head><body><h2>CC面板配置导入</h2><div id="status">正在导入...</div><div id="results" class="box"></div><script>!function(){var d=' + importData + ';var ok=0,fail=0,results=[];Object.entries(d).forEach(function(e){try{localStorage.setItem(e[0],e[1]);var v=e[1];results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"ok\\">OK</span> ("+(v.length>80?v.substring(0,80)+"...":v)+")</div>");ok++}catch(err){results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"err\\">FAIL: "+err.message+"</span></div>");fail++}});var status=document.getElementById("status");status.innerHTML=ok+" 个成功, "+fail+" 个失败 (共 "+Object.keys(d).length+" 项)";status.className=ok>0?"ok":"err";document.getElementById("results").innerHTML=results.join("");if(ok>0){var p=document.createElement("p");p.textContent="配置已写入 Edge localStorage for "+window.location.origin;p.className="ok";document.body.appendChild(p)}else{var p2=document.createElement("p");p2.textContent="未写入任何数据,请检查浏览器控制台";p2.className="err";document.body.appendChild(p2)}}();</script></body></html>';
      res.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      res.end(html);
      return;
    }

    // HTML
    if (req.url === "/" || req.url === "/index.html") {
      if (fs.existsSync(shared.HTML_FILE)) {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(fs.readFileSync(shared.HTML_FILE, "utf-8"));
      } else {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end("<h1>Dashboard HTML not found</h1>");
      }
      return;
    }

    // localStorage 迁移工具：从 3100 迁移到 5022
    if (req.url === "/migrate") {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end('<!DOCTYPE html><html><head><meta charset="utf-8"><title>迁移 localStorage 3100→5022</title><style>body{font-family:system-ui;max-width:500px;margin:80px auto;padding:20px;background:#0b0f14;color:#e0e0e0;text-align:center}h2{color:#ff6b35}.btn{display:inline-block;padding:14px 36px;background:#ff6b35;color:#fff;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:700;margin:16px 8px}.btn:hover{opacity:0.85}.ok{color:#4caf50}.err{color:#f44336}.info{font-size:13px;color:#888;margin-top:24px}#log{margin-top:16px;font-size:13px;color:#aaa}</style></head><body><h2>localStorage 迁移</h2><p>从 <code>localhost:3100</code> 迁移到 <code>localhost:5022</code></p><p><button class="btn" onclick="doMigrate()">开始迁移</button></p><div id="log"></div><p class="info">迁移完成后<a href="/">返回面板</a></p><script>function log(m,c){var d=document.getElementById("log");d.innerHTML+=m+"<br>";if(c)d.style.color=c}function doMigrate(){log("正在从 3100 读取…");var ifr=document.createElement("iframe");ifr.style.display="none";ifr.src="http://localhost:3100/";ifr.onload=function(){setTimeout(function(){try{var raw=ifr.contentDocument.body.textContent;var data=JSON.parse(raw);var keys=Object.keys(data);log("读取到 "+keys.length+" 个键");var ok=0,fail=0;for(var i=0;i<keys.length;i++){try{localStorage.setItem(keys[i],data[keys[i]]);ok++}catch(e){fail++;log(keys[i]+" 写入失败: "+e.message,"#f44336")}}log("迁移完成: "+ok+" 成功, "+fail+" 失败","#4caf50");log("3秒后跳转面板…");setTimeout(function(){location.href="/"},3000)}catch(e){log("读取失败，请确认 3100 端口的旧面板正在运行。错误: "+e.message,"#f44336")}},500)};document.body.appendChild(ifr)}</script></body></html>');
      return;
    }

    // Static files
    if (req.url === "/sortable.min.js") {
      var sortableFile = path.join(path.dirname
```
### M-026 - shared.js 作为全局可变状态中心，缺乏封装，是架构腐化的核心风险点
- Severity: P1 CRITICAL
- File: shared.js lines [1, 53]
- Description: N/A
- Suggestion: 将 shared.js 重构为状态管理模块，对关键状态提供受控的读写方法而非裸导出。例如：
1. sessionCache → 提供 getSession(id) / setSession(id, data) / getAllSessions()，内部可加入校验逻辑
2. sseClients → 提供 addClient(res) / removeClient(res) / broadcast(data)，由 sse.js 独占管理
3. 将不相关的状态分组到不同模块（SSE 相关 → sse.js, 快照相关 → snapshot.js），避免一个文件承载所有全局状态

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

module.exports = {
  PROJECTS_DIR: PROJECTS_DIR,
  SNAPSHOTS_DIR: SNAPSHOTS_DIR,
  PORT: PORT,
  HTML_FILE: HTML_FILE,
  AGENT_NAMES_FILE: AGENT_NAMES_FILE,
  saveSessionConfigMap: saveSessionConfigMap,

  // Session cache
  sessionCache: new Map(),
  subAgentCache: new Map(),
  fileOffsets: new Map(),
  sessionConfigMap: loadSessionConfigMap(),
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
### M-017 - CORS 通配符: Access-Control-Allow-Origin: * 允许任意网站访问 API
- Severity: P1 CRITICAL
- File: index.js lines [7, 7]
- Description: N/A
- Suggestion: 将 CORS 限制为 localhost 来源，或完全移除该 header（同源策略会自动保护）。

Source code context:
```
// 阿勋的CC面板 5.22 — 缓存+增量版（端口5022），模块化架构
var http = require("http");
var fs = require("fs");
var path = require("path");
var shared = require("./shared");
var pricing = require("./pricing");
var scanner = require("./scanner");
var snapshot = require("./snapshot");
var sse = require("./sse");
var watcher = require("./watcher");
var agents = require("./agents");

// Route handlers
var sessionsRouter = require("./routes/sessions")();
var sessionRouter = require("./routes/session")();
var snapshotsRouter = require("./routes/snapshots")();
var openRouter = require("./routes/open")();

// ============ HTTP Server ============

var server = http.createServer(function(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");

  try {
    // SSE
    if (sse.handleSSE(req, res)) return;

    // 一次性 localStorage 导入路由
    if (req.url === "/import-localstorage") {
      var importFile = path.join(__dirname, "import-data.json");
      if (!fs.existsSync(importFile)) {
        res.writeHead(404); res.end("import-data.json not found");
        return;
      }
      var importData = fs.readFileSync(importFile, "utf8");
      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>导入配置</title><style>body{font-family:system-ui;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}.ok{color:#4caf50}.err{color:#f44336}.key{font-family:monospace;font-size:13px;margin:4px 0}.box{background:#16213e;border-radius:8px;padding:16px;margin:12px 0}h2{margin:0 0 8px}</style></head><body><h2>CC面板配置导入</h2><div id="status">正在导入...</div><div id="results" class="box"></div><script>!function(){var d=' + importData + ';var ok=0,fail=0,results=[];Object.entries(d).forEach(function(e){try{localStorage.setItem(e[0],e[1]);var v=e[1];results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"ok\\">OK</span> ("+(v.length>80?v.substring(0,80)+"...":v)+")</div>");ok++}catch(err){results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"err\\">FAIL: "+err.message+"</span></div>");fail++}});var status=document.getElementById("status");status.innerHTML=ok+" 个成功, "+fail+" 个失败 (共 "+Object.keys(d).length+" 项)";status.className=ok>0?"ok":"err";document.getElementById("results").innerHTML=results.join("");if(ok>0){var p=document.createElement("p");p.textContent="配置已写入 Edge localStorage for "+window.location.origin;p.className="ok";document.body.appendChild(p)}else{var p2=document.createElement("p");p2.textContent="未写入任何数据,请检查浏览器控制台";p2.className="err";document.body.appendChild(p2)}}();</script></body></html>';
      res.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      res.end(html);
      return;
    }

    // HTML
    if (req.url === "/" || req.url === "/index.html") {
      if (fs.existsSync(shared.HTML_FILE)) {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(fs.readFileSync(shared.HTML_FILE, "utf-8"));
      } else {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end("<h1>Dashboard HTML not found</h1>");
      }
      return;
    }

    // localStorage 迁移工具：从 3100 迁移到 5022
    if (req.url === "/migrate") {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end('<!DOCTYPE html><html><head><meta charset="utf-8"><title>迁移 localStorage 3100→5022</title><style>body{font-family:system-ui;max-width:500px;margin:80px auto;padding:20px;background:#0b0f14;color:#e0e0e0;text-align:center}h2{color:#ff6b35}.btn{display:inline-block;padding:14px 36px;background:#ff6b35;color:#fff;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:700;margin:16px 8px}.btn:hover{opacity:0.85}.ok{color:#4caf50}.err{color:#f44336}.info{font-size:13px;color:#888;margin-top:24px}#log{margin-top:16px;font-size:13px;color:#aaa}</style></head><body><h2>localStorage 迁移</h2><p>从 <code>localhost:3100</code> 迁移到 <code>localhost:5022</code></p><p><button class="btn" onclick="doMigrate()">开始迁移</button></p><div id="log"></div><p class="info">迁移完成后<a href="/">返回面板</a></p><script>function log(m,c){var d=document.getElementById("log");d.innerHTML+=m+"<br>";if(c)d.style.color=c}function doMigrate(){log("正在从 3100 读取…");var ifr=document.createElement("iframe");ifr.style.display="none";ifr.src="http://localhost:3100/";ifr.onload=function(){setTimeout(function(){try{var raw=ifr.contentDocument.body.textContent;var data=JSON.parse(raw);var keys=Object.keys(data);log("读取到 "+keys.length+" 个键");var ok=0,fail=0;for(var i=0;i<keys.length;i++){try{localStorage.setItem(keys[i],data[keys[i]]);ok++}catch(e){fail++;log(keys[i]+" 写入失败: "+e.message,"#f44336")}}log("迁移完成: "+ok+" 成功, "+fail+" 失败","#4caf50");log("3秒后跳转面板…");setTimeout(function(){location.href="/"},3000)}catch(e){log("读取失败，请确认 3100 端口的旧面板正在运行。错误: "+e.message,"#f44336")}},500)};document.body.appendChild(ifr)}</script></body></html>');
      return;
    }

    // Static files
    if (req.url === "/sortable.min.js") {
      var sortableFile = path.join(path.dirname
```
### M-028 - buildRelationsResponse 是 God Function（170 行），耦合了 5 个不相关的关注点
- Severity: P1 CRITICAL
- File: routes/session.js lines [115, 280]
- Description: N/A
- Suggestion: 拆分为 5 个独立函数：
- parseDispatchEvents(jsonlContent) → dispatchCalls[]
- parseSubAgentNodes(subDirs) → nodes[]
- matchDispatchToAgents(dispatchCalls, agents, sessionName) → edges[]
- detectPhases(matchedEdges, userMessages) → phases[]
- buildWaterfallTrace(jsonlLines) → waterfallSpans[]

buildRelationsR

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
    cost: pricing.calcCost(cached),
    filePath: fpath
  };

  res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(resp));
}

function buildRelationsResponse(relTarget, relId, res) {
  if (!relTarget || !relTarget._file) { res.writeHead(404); res.end(JSON.stringify({ error: "not found" })); return; }

  var nodes = [];
  var edges = [];
  var dispatchCalls = [];

  // Main node
  nodes.push({
    id: relTarget.id, type: "main", title: relTarget.title || relTarget.id,
    status: scanner.getStatus(re
```
### M-002 - XSS 注入：import-data.json 内容直接拼接进 HTML script 标签
- Severity: P0 BLOCKING
- File: server/index.js lines [35, 38]
- Description: N/A
- Suggestion: 对 importData 进行 JSON 安全编码，或使用 CSP nonce。最简单的修复：将数据作为 HTML 实体编码的 JSON 放入一个隐藏的 data 属性中，再由 JS 读取并 JSON.parse。至少应对 <、>、&、'、" 进行 HTML 实体转义。

Source code context:
```
(file not found)
```
### M-009 - loadAgentNames() 在循环内每次迭代都读取磁盘文件
- Severity: P1 CRITICAL
- File: server/routes/session.js lines [199, 220]
- Description: N/A
- Suggestion: 将 loadAgentNames() 调用移到循环外部，只读取一次。或者在 agents 模块中添加缓存层（TTL 缓存或 fileMtime 检查）。

Source code context:
```
(file not found)
```
### M-015 - 命令注入: bat 文件生成时 env 变量值未转义
- Severity: P0 BLOCKING
- File: routes/open.js lines [44, 68]
- Description: N/A
- Suggestion: 对所有写入 bat 文件的值进行严格的输入验证和转义，过滤换行符和 bat 特殊字符，或使用 PowerShell 的 -Command 参数代替 bat 文件。

Source code context:
```
var path = require("path");
var fs = require("fs");
var shared = require("../shared");
var scanner = require("../scanner");

// 服务器启动时拍 settings.json 快照，所有 swap 最终都恢复到这个原始值
var ORIGINAL_SETTINGS = null;
(function() {
  try {
    var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
    var defaultPath = require("path").join(homeDir, ".claude", "settings.json");
    if (require("fs").existsSync(defaultPath)) {
      ORIGINAL_SETTINGS = require("fs").readFileSync(defaultPath, "utf-8");
      console.log("[open] settings.json 原始快照已保存");
    }
  } catch(e) {
    console.error("[open] 无法保存 settings.json 快照:", e.message);
  }
})();

function makeOpenRouter() {
  var handle = function(req, res) {
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
      var openId = decodeURI(req.url.split("/api/open-session/")[1]);
      var target = shared.sessionCache.get(openId);
      if (!target || !target._file) {
        scanner.scanSessions(shared.PROJECTS_DIR, []).then(function(all2) {
          for (var m = 0; m < all2.length; m++) { if (all2[m].id === openId) { target = all2[m]; break; } }
          launchSession(target, openId, res);
        });
      } else {
        launchSession(target, openId, res);
      }
      return true;
    }

    return false;
  };
  handle.launchSessionDirect = makeOpenRouter.launchSessionDirect;
  handle.swapSettingsJson = makeOpenRouter.swapSettingsJson;
  return handle;
}

// 写入临时 bat 文件并启动——env vars 通过 bat 的 set 命令直接设置，不依赖进程继承
function spawnWithBat(claudeExe, claudeArgs, configFile, cwd, callback) {
  var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
  var tempDir = path.join(homeDir, ".claude", "temp");
  try { fs.mkdirSync(tempDir, { recursive: true }); } catch (e) {}

  var batPath = path.join(tempDir, "launch-" + Date.now() + ".bat");
  var batLines = ["@echo off"];

  // 从配置文件中读取 env vars，写入 bat 的 set 命令
  if (configFile) {
    var configPath = path.join(homeDir, ".claude", configFile);
    if (fs.existsSync(configPath)) {
      try {
        var cfg = JSON.parse(fs.readFileSync(configPath, "utf-8"));
        // 顶层 model
        if (cfg.model) {
          batLines.push("set ANTHROPIC_MODEL=" + cfg.model);
        }
        // env 块中的所有 ANTHROPIC_ 和 CLAUDE_ 变量
        if (cfg.env) {
          var envKeys = Object.keys(cfg.env);
          for (var i = 0; i < envKeys.length; i++) {
            var k = envKeys[i];
            if (k.startsWith("ANTHROPIC_") || k.startsWith("CLAUDE_")) {
              batLines.push("set " + k + "=" + cfg.env[k]);
            }
          }
        }
      } catch (e) {}
    }
  }

  // 拼接 claude 命令
  var allArgs = [claudeExe].concat(claudeArgs);
  batLines.push("call " + allArgs.map(function(a) { return "\"" + a + "\""; }).join(" "));
  batLines.push("exit");

  fs.writeFileSync(batPath, batLines.join("\r\n"), "utf-8");
  console.log("[open] bat → " + batPath);

  try {
    var child = require("child_process").spawn("cmd", ["/c", "start", "\"Claude\"", "/min", batPath], {
      cwd: cwd || undefined,
      detached: true,
      stdio: "ignore"
    });
    child.unref();
    // 5 分钟后清理 bat 文件
    setTimeout(function() { try { fs.unlinkSync(batPath); } catch (e) {} }, 300000);
    if (callback) callback(true);
  } catch (e) {
    if (callback) callback(false);
  }
}

function launchTerminalBat(batCached, batId, res) {
  var batCwd = batCached && batCached.cwd ? batCached.cwd : "";
  var npmBin = process.env.APPDATA ? path.join(process.env.APPDATA, "npm") : null;
  var claudeExe = npmBin ? path.join(npmBin, "claude.cmd") : "claude";
  var configFile = shared.sessionConfigMap.get(batId);

  // 写 settings.json（保持一致性）
  swapSettingsJson(configFile);

  spawnWithBat(claudeExe, ["--resume", batId], configFile, batCwd || undefined);

  res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify({ ok: true }));
}

function launchSession(target, openId, res) {
  var cwd = target && target.cwd ? target.cwd : (target && target._file ? path.dirname(target._file) : "");
  var result = { ok: false, actions: [] };
  var npmBin = process.env.APPDATA ? path.join(process.env.APPDATA, "npm") : null;
  var claudeExe = npmBin ? path.join(npmBin, "node_modules", "@anthropic-ai", "claude-code", "bin", "c
```
### M-027 - /api/create-and-open 路由内联 100 行业务逻辑，违反单一职责和路由模块化原则
- Severity: P1 CRITICAL
- File: index.js lines [47, 145]
- Description: N/A
- Suggestion: 将 /api/create-and-open 提取到 routes/create-and-open.js 或合并到 routes/open.js 中，index.js 只保留路由分发。具体步骤：
1. 创建 makeCreateOpenRouter() 工厂函数
2. 将 UUID 生成、JSONL 克隆、时间戳替换封装为独立函数
3. index.js 中只保留 `if (req.url.startsWith('/api/create-and-open')) { createOpenRouter(req, res); return; }`

Source code context:
```
// 阿勋的CC面板 5.22 — 缓存+增量版（端口5022），模块化架构
var http = require("http");
var fs = require("fs");
var path = require("path");
var shared = require("./shared");
var pricing = require("./pricing");
var scanner = require("./scanner");
var snapshot = require("./snapshot");
var sse = require("./sse");
var watcher = require("./watcher");
var agents = require("./agents");

// Route handlers
var sessionsRouter = require("./routes/sessions")();
var sessionRouter = require("./routes/session")();
var snapshotsRouter = require("./routes/snapshots")();
var openRouter = require("./routes/open")();

// ============ HTTP Server ============

var server = http.createServer(function(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");

  try {
    // SSE
    if (sse.handleSSE(req, res)) return;

    // 一次性 localStorage 导入路由
    if (req.url === "/import-localstorage") {
      var importFile = path.join(__dirname, "import-data.json");
      if (!fs.existsSync(importFile)) {
        res.writeHead(404); res.end("import-data.json not found");
        return;
      }
      var importData = fs.readFileSync(importFile, "utf8");
      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>导入配置</title><style>body{font-family:system-ui;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}.ok{color:#4caf50}.err{color:#f44336}.key{font-family:monospace;font-size:13px;margin:4px 0}.box{background:#16213e;border-radius:8px;padding:16px;margin:12px 0}h2{margin:0 0 8px}</style></head><body><h2>CC面板配置导入</h2><div id="status">正在导入...</div><div id="results" class="box"></div><script>!function(){var d=' + importData + ';var ok=0,fail=0,results=[];Object.entries(d).forEach(function(e){try{localStorage.setItem(e[0],e[1]);var v=e[1];results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"ok\\">OK</span> ("+(v.length>80?v.substring(0,80)+"...":v)+")</div>");ok++}catch(err){results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"err\\">FAIL: "+err.message+"</span></div>");fail++}});var status=document.getElementById("status");status.innerHTML=ok+" 个成功, "+fail+" 个失败 (共 "+Object.keys(d).length+" 项)";status.className=ok>0?"ok":"err";document.getElementById("results").innerHTML=results.join("");if(ok>0){var p=document.createElement("p");p.textContent="配置已写入 Edge localStorage for "+window.location.origin;p.className="ok";document.body.appendChild(p)}else{var p2=document.createElement("p");p2.textContent="未写入任何数据,请检查浏览器控制台";p2.className="err";document.body.appendChild(p2)}}();</script></body></html>';
      res.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      res.end(html);
      return;
    }

    // HTML
    if (req.url === "/" || req.url === "/index.html") {
      if (fs.existsSync(shared.HTML_FILE)) {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(fs.readFileSync(shared.HTML_FILE, "utf-8"));
      } else {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end("<h1>Dashboard HTML not found</h1>");
      }
      return;
    }

    // localStorage 迁移工具：从 3100 迁移到 5022
    if (req.url === "/migrate") {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end('<!DOCTYPE html><html><head><meta charset="utf-8"><title>迁移 localStorage 3100→5022</title><style>body{font-family:system-ui;max-width:500px;margin:80px auto;padding:20px;background:#0b0f14;color:#e0e0e0;text-align:center}h2{color:#ff6b35}.btn{display:inline-block;padding:14px 36px;background:#ff6b35;color:#fff;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:700;margin:16px 8px}.btn:hover{opacity:0.85}.ok{color:#4caf50}.err{color:#f44336}.info{font-size:13px;color:#888;margin-top:24px}#log{margin-top:16px;font-size:13px;color:#aaa}</style></head><body><h2>localStorage 迁移</h2><p>从 <code>localhost:3100</code> 迁移到 <code>localhost:5022</code></p><p><button class="btn" onclick="doMigrate()">开始迁移</button></p><div id="log"></div><p class="info">迁移完成后<a href="/">返回面板</a></p><script>function log(m,c){var d=document.getElementById("log");d.innerHTML+=m+"<br>";if(c)d.style.color=c}function doMigrate(){log("正在从 3100 读取…");var ifr=document.createElement("iframe");ifr.style.display="none";ifr.src="http://localhost:3100/";ifr.onload=function(){setTimeout(function(){try{var raw=ifr.contentDocument.body.textContent;var data=JSON.parse(raw);var keys=Object.keys(data);log("读取到 "+keys.length+" 个键");var ok=0,fail=0;for(var i=0;i<keys.length;i++){try{localStorage.setItem(keys[i],data[keys[i]]);ok++}catch(e){fail++;log(keys[i]+" 写入失败: "+e.message,"#f44336")}}log("迁移完成: "+ok+" 成功, "+fail+" 失败","#4caf50");log("3秒后跳转面板…");setTimeout(function(){location.href="/"},3000)}catch(e){log("读取失败，请确认 3100 端口的旧面板正在运行。错误: "+e.message,"#f44336")}},500)};document.body.appendChild(ifr)}</script></body></html>');
      return;
    }

    // Static files
    if (req.url === "/sortable.min.js") {
      var sortableFile = path.join(path.dirname
```
### M-004 - Math.random() 生成会话 ID——可预测且有碰撞风险
- Severity: P1 CRITICAL
- File: server/index.js lines [107, 111]
- Description: N/A
- Suggestion: 使用 crypto.randomUUID()（Node.js 14.17+）或 crypto.randomBytes(16) 生成 session ID。fakePid 应使用递增计数器或 PID 文件管理，避免碰撞。

Source code context:
```
(file not found)
```
### M-008 - delete 操作修改共享缓存对象——后续请求可能读到残缺数据
- Severity: P1 CRITICAL
- File: server/routes/sessions.js lines [43, 48]
- Description: N/A
- Suggestion: 在发送响应前创建对象的浅拷贝，而非直接修改缓存对象。使用 Object.assign({}, s) 或在构造响应对象时选择性地只包含需要的字段。

Source code context:
```
(file not found)
```
### M-029 - parseSubAgent 与 buildRelationsResponse 中的子 Agent 解析逻辑大量重复
- Severity: P1 CRITICAL
- File: agents.js lines [37, 105]
- Description: N/A
- Suggestion: 统一为 agents.js 中的 parseSubAgent，并在 session.js 中复用。如果 relations 接口需要额外字段（如 startTime），扩展 parseSubAgent 的返回值即可。status 判定逻辑应统一到一个 getStatusForAgent(agentInfo) 函数中。

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
### M-003 - configName 查询参数未校验——路径遍历 + bat 文件命令注入
- Severity: P0 BLOCKING
- File: server/index.js lines [94, 198]
- Description: N/A
- Suggestion: 对 configName 做白名单校验：只允许匹配 /^[a-zA-Z0-9_-]+\.json$/ 的格式。在 spawnWithBat 中对 env 值做 cmd 转义（至少过滤 \n、\r、&、|、> 等字符）。

Source code context:
```
(file not found)
```
### M-005 - settings.json 竞态条件——并发请求可导致配置文件内容错乱
- Severity: P1 CRITICAL
- File: server/routes/open.js lines [82, 114]
- Description: N/A
- Suggestion: 引入文件锁（proper-lockfile 包）或使用写入临时文件 + rename 的原子操作。restore 时机应改为：监听 VSCode 进程启动完成事件，或使用文件内容 hash 比较而非固定延时。短期修复：将 restore 延迟增大到 15-30 秒。

Source code context:
```
(file not found)
```
### M-007 - 错误响应泄露服务器内部路径
- Severity: P1 CRITICAL
- File: server/index.js lines [117, 119]
- Description: N/A
- Suggestion: 返回通用错误消息，将详细错误信息记录到服务器日志。

Source code context:
```
(file not found)
```
### M-016 - TOCTOU 竞态: settings.json 被临时替换为任意配置
- Severity: P0 BLOCKING
- File: routes/open.js lines [130, 160]
- Description: N/A
- Suggestion: 使用文件锁或原子写入操作；在写入前创建备份，使用 try/finally 确保恢复；考虑使用 --settings 参数传递配置而不是修改全局文件。

Source code context:
```
var path = require("path");
var fs = require("fs");
var shared = require("../shared");
var scanner = require("../scanner");

// 服务器启动时拍 settings.json 快照，所有 swap 最终都恢复到这个原始值
var ORIGINAL_SETTINGS = null;
(function() {
  try {
    var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
    var defaultPath = require("path").join(homeDir, ".claude", "settings.json");
    if (require("fs").existsSync(defaultPath)) {
      ORIGINAL_SETTINGS = require("fs").readFileSync(defaultPath, "utf-8");
      console.log("[open] settings.json 原始快照已保存");
    }
  } catch(e) {
    console.error("[open] 无法保存 settings.json 快照:", e.message);
  }
})();

function makeOpenRouter() {
  var handle = function(req, res) {
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
      var openId = decodeURI(req.url.split("/api/open-session/")[1]);
      var target = shared.sessionCache.get(openId);
      if (!target || !target._file) {
        scanner.scanSessions(shared.PROJECTS_DIR, []).then(function(all2) {
          for (var m = 0; m < all2.length; m++) { if (all2[m].id === openId) { target = all2[m]; break; } }
          launchSession(target, openId, res);
        });
      } else {
        launchSession(target, openId, res);
      }
      return true;
    }

    return false;
  };
  handle.launchSessionDirect = makeOpenRouter.launchSessionDirect;
  handle.swapSettingsJson = makeOpenRouter.swapSettingsJson;
  return handle;
}

// 写入临时 bat 文件并启动——env vars 通过 bat 的 set 命令直接设置，不依赖进程继承
function spawnWithBat(claudeExe, claudeArgs, configFile, cwd, callback) {
  var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
  var tempDir = path.join(homeDir, ".claude", "temp");
  try { fs.mkdirSync(tempDir, { recursive: true }); } catch (e) {}

  var batPath = path.join(tempDir, "launch-" + Date.now() + ".bat");
  var batLines = ["@echo off"];

  // 从配置文件中读取 env vars，写入 bat 的 set 命令
  if (configFile) {
    var configPath = path.join(homeDir, ".claude", configFile);
    if (fs.existsSync(configPath)) {
      try {
        var cfg = JSON.parse(fs.readFileSync(configPath, "utf-8"));
        // 顶层 model
        if (cfg.model) {
          batLines.push("set ANTHROPIC_MODEL=" + cfg.model);
        }
        // env 块中的所有 ANTHROPIC_ 和 CLAUDE_ 变量
        if (cfg.env) {
          var envKeys = Object.keys(cfg.env);
          for (var i = 0; i < envKeys.length; i++) {
            var k = envKeys[i];
            if (k.startsWith("ANTHROPIC_") || k.startsWith("CLAUDE_")) {
              batLines.push("set " + k + "=" + cfg.env[k]);
            }
          }
        }
      } catch (e) {}
    }
  }

  // 拼接 claude 命令
  var allArgs = [claudeExe].concat(claudeArgs);
  batLines.push("call " + allArgs.map(function(a) { return "\"" + a + "\""; }).join(" "));
  batLines.push("exit");

  fs.writeFileSync(batPath, batLines.join("\r\n"), "utf-8");
  console.log("[open] bat → " + batPath);

  try {
    var child = require("child_process").spawn("cmd", ["/c", "start", "\"Claude\"", "/min", batPath], {
      cwd: cwd || undefined,
      detached: true,
      stdio: "ignore"
    });
    child.unref();
    // 5 分钟后清理 bat 文件
    setTimeout(function() { try { fs.unlinkSync(batPath); } catch (e) {} }, 300000);
    if (callback) callback(true);
  } catch (e) {
    if (callback) callback(false);
  }
}

function launchTerminalBat(batCached, batId, res) {
  var batCwd = batCached && batCached.cwd ? batCached.cwd : "";
  var npmBin = process.env.APPDATA ? path.join(process.env.APPDATA, "npm") : null;
  var claudeExe = npmBin ? path.join(npmBin, "claude.cmd") : "claude";
  var configFile = shared.sessionConfigMap.get(batId);

  // 写 settings.json（保持一致性）
  swapSettingsJson(configFile);

  spawnWithBat(claudeExe, ["--resume", batId], configFile, batCwd || undefined);

  res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify({ ok: true }));
}

function launchSession(target, openId, res) {
  var cwd = target && target.cwd ? target.cwd : (target && target._file ? path.dirname(target._file) : "");
  var result = { ok: false, actions: [] };
  var npmBin = process.env.APPDATA ? path.join(process.env.APPDATA, "npm") : null;
  var claudeExe = npmBin ? path.join(npmBin, "node_modules", "@anthropic-ai", "claude-code", "bin", "c
```
### M-030 - settings.json 全局文件替换存在并发竞态条件，多会话同时启动会互相覆盖
- Severity: P1 CRITICAL
- File: routes/open.js lines [78, 110]
- Description: N/A
- Suggestion: 根本解决方案：不修改全局 settings.json，而是通过 --settings 参数传递配置文件路径（launchSession 中已有此逻辑）。如果 VSCode 扩展不支持 --settings，则应使用文件锁（proper-lockfile）或队列机制确保串行化。至少应添加一个互斥锁：

var settingsLock = false;
function swapSettingsJson(configFile, callback) {
  if (settingsLock) { /* 等待或拒绝 */ return; }
  settingsLock = true;
  // .

Source code context:
```
var path = require("path");
var fs = require("fs");
var shared = require("../shared");
var scanner = require("../scanner");

// 服务器启动时拍 settings.json 快照，所有 swap 最终都恢复到这个原始值
var ORIGINAL_SETTINGS = null;
(function() {
  try {
    var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
    var defaultPath = require("path").join(homeDir, ".claude", "settings.json");
    if (require("fs").existsSync(defaultPath)) {
      ORIGINAL_SETTINGS = require("fs").readFileSync(defaultPath, "utf-8");
      console.log("[open] settings.json 原始快照已保存");
    }
  } catch(e) {
    console.error("[open] 无法保存 settings.json 快照:", e.message);
  }
})();

function makeOpenRouter() {
  var handle = function(req, res) {
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
      var openId = decodeURI(req.url.split("/api/open-session/")[1]);
      var target = shared.sessionCache.get(openId);
      if (!target || !target._file) {
        scanner.scanSessions(shared.PROJECTS_DIR, []).then(function(all2) {
          for (var m = 0; m < all2.length; m++) { if (all2[m].id === openId) { target = all2[m]; break; } }
          launchSession(target, openId, res);
        });
      } else {
        launchSession(target, openId, res);
      }
      return true;
    }

    return false;
  };
  handle.launchSessionDirect = makeOpenRouter.launchSessionDirect;
  handle.swapSettingsJson = makeOpenRouter.swapSettingsJson;
  return handle;
}

// 写入临时 bat 文件并启动——env vars 通过 bat 的 set 命令直接设置，不依赖进程继承
function spawnWithBat(claudeExe, claudeArgs, configFile, cwd, callback) {
  var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
  var tempDir = path.join(homeDir, ".claude", "temp");
  try { fs.mkdirSync(tempDir, { recursive: true }); } catch (e) {}

  var batPath = path.join(tempDir, "launch-" + Date.now() + ".bat");
  var batLines = ["@echo off"];

  // 从配置文件中读取 env vars，写入 bat 的 set 命令
  if (configFile) {
    var configPath = path.join(homeDir, ".claude", configFile);
    if (fs.existsSync(configPath)) {
      try {
        var cfg = JSON.parse(fs.readFileSync(configPath, "utf-8"));
        // 顶层 model
        if (cfg.model) {
          batLines.push("set ANTHROPIC_MODEL=" + cfg.model);
        }
        // env 块中的所有 ANTHROPIC_ 和 CLAUDE_ 变量
        if (cfg.env) {
          var envKeys = Object.keys(cfg.env);
          for (var i = 0; i < envKeys.length; i++) {
            var k = envKeys[i];
            if (k.startsWith("ANTHROPIC_") || k.startsWith("CLAUDE_")) {
              batLines.push("set " + k + "=" + cfg.env[k]);
            }
          }
        }
      } catch (e) {}
    }
  }

  // 拼接 claude 命令
  var allArgs = [claudeExe].concat(claudeArgs);
  batLines.push("call " + allArgs.map(function(a) { return "\"" + a + "\""; }).join(" "));
  batLines.push("exit");

  fs.writeFileSync(batPath, batLines.join("\r\n"), "utf-8");
  console.log("[open] bat → " + batPath);

  try {
    var child = require("child_process").spawn("cmd", ["/c", "start", "\"Claude\"", "/min", batPath], {
      cwd: cwd || undefined,
      detached: true,
      stdio: "ignore"
    });
    child.unref();
    // 5 分钟后清理 bat 文件
    setTimeout(function() { try { fs.unlinkSync(batPath); } catch (e) {} }, 300000);
    if (callback) callback(true);
  } catch (e) {
    if (callback) callback(false);
  }
}

function launchTerminalBat(batCached, batId, res) {
  var batCwd = batCached && batCached.cwd ? batCached.cwd : "";
  var npmBin = process.env.APPDATA ? path.join(process.env.APPDATA, "npm") : null;
  var claudeExe = npmBin ? path.join(npmBin, "claude.cmd") : "claude";
  var configFile = shared.sessionConfigMap.get(batId);

  // 写 settings.json（保持一致性）
  swapSettingsJson(configFile);

  spawnWithBat(claudeExe, ["--resume", batId], configFile, batCwd || undefined);

  res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify({ ok: true }));
}

function launchSession(target, openId, res) {
  var cwd = target && target.cwd ? target.cwd : (target && target._file ? path.dirname(target._file) : "");
  var result = { ok: false, actions: [] };
  var npmBin = process.env.APPDATA ? path.join(process.env.APPDATA, "npm") : null;
  var claudeExe = npmBin ? path.join(npmBin, "node_modules", "@anthropic-ai", "claude-code", "bin", "c
```
### M-021 - 信息泄露: 错误消息暴露内部文件路径
- Severity: P1 CRITICAL
- File: index.js lines [125, 140]
- Description: N/A
- Suggestion: 对客户端响应使用通用错误消息，将详细错误信息仅记录到服务器日志。

Source code context:
```
// 阿勋的CC面板 5.22 — 缓存+增量版（端口5022），模块化架构
var http = require("http");
var fs = require("fs");
var path = require("path");
var shared = require("./shared");
var pricing = require("./pricing");
var scanner = require("./scanner");
var snapshot = require("./snapshot");
var sse = require("./sse");
var watcher = require("./watcher");
var agents = require("./agents");

// Route handlers
var sessionsRouter = require("./routes/sessions")();
var sessionRouter = require("./routes/session")();
var snapshotsRouter = require("./routes/snapshots")();
var openRouter = require("./routes/open")();

// ============ HTTP Server ============

var server = http.createServer(function(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");

  try {
    // SSE
    if (sse.handleSSE(req, res)) return;

    // 一次性 localStorage 导入路由
    if (req.url === "/import-localstorage") {
      var importFile = path.join(__dirname, "import-data.json");
      if (!fs.existsSync(importFile)) {
        res.writeHead(404); res.end("import-data.json not found");
        return;
      }
      var importData = fs.readFileSync(importFile, "utf8");
      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>导入配置</title><style>body{font-family:system-ui;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}.ok{color:#4caf50}.err{color:#f44336}.key{font-family:monospace;font-size:13px;margin:4px 0}.box{background:#16213e;border-radius:8px;padding:16px;margin:12px 0}h2{margin:0 0 8px}</style></head><body><h2>CC面板配置导入</h2><div id="status">正在导入...</div><div id="results" class="box"></div><script>!function(){var d=' + importData + ';var ok=0,fail=0,results=[];Object.entries(d).forEach(function(e){try{localStorage.setItem(e[0],e[1]);var v=e[1];results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"ok\\">OK</span> ("+(v.length>80?v.substring(0,80)+"...":v)+")</div>");ok++}catch(err){results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"err\\">FAIL: "+err.message+"</span></div>");fail++}});var status=document.getElementById("status");status.innerHTML=ok+" 个成功, "+fail+" 个失败 (共 "+Object.keys(d).length+" 项)";status.className=ok>0?"ok":"err";document.getElementById("results").innerHTML=results.join("");if(ok>0){var p=document.createElement("p");p.textContent="配置已写入 Edge localStorage for "+window.location.origin;p.className="ok";document.body.appendChild(p)}else{var p2=document.createElement("p");p2.textContent="未写入任何数据,请检查浏览器控制台";p2.className="err";document.body.appendChild(p2)}}();</script></body></html>';
      res.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      res.end(html);
      return;
    }

    // HTML
    if (req.url === "/" || req.url === "/index.html") {
      if (fs.existsSync(shared.HTML_FILE)) {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(fs.readFileSync(shared.HTML_FILE, "utf-8"));
      } else {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end("<h1>Dashboard HTML not found</h1>");
      }
      return;
    }

    // localStorage 迁移工具：从 3100 迁移到 5022
    if (req.url === "/migrate") {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end('<!DOCTYPE html><html><head><meta charset="utf-8"><title>迁移 localStorage 3100→5022</title><style>body{font-family:system-ui;max-width:500px;margin:80px auto;padding:20px;background:#0b0f14;color:#e0e0e0;text-align:center}h2{color:#ff6b35}.btn{display:inline-block;padding:14px 36px;background:#ff6b35;color:#fff;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:700;margin:16px 8px}.btn:hover{opacity:0.85}.ok{color:#4caf50}.err{color:#f44336}.info{font-size:13px;color:#888;margin-top:24px}#log{margin-top:16px;font-size:13px;color:#aaa}</style></head><body><h2>localStorage 迁移</h2><p>从 <code>localhost:3100</code> 迁移到 <code>localhost:5022</code></p><p><button class="btn" onclick="doMigrate()">开始迁移</button></p><div id="log"></div><p class="info">迁移完成后<a href="/">返回面板</a></p><script>function log(m,c){var d=document.getElementById("log");d.innerHTML+=m+"<br>";if(c)d.style.color=c}function doMigrate(){log("正在从 3100 读取…");var ifr=document.createElement("iframe");ifr.style.display="none";ifr.src="http://localhost:3100/";ifr.onload=function(){setTimeout(function(){try{var raw=ifr.contentDocument.body.textContent;var data=JSON.parse(raw);var keys=Object.keys(data);log("读取到 "+keys.length+" 个键");var ok=0,fail=0;for(var i=0;i<keys.length;i++){try{localStorage.setItem(keys[i],data[keys[i]]);ok++}catch(e){fail++;log(keys[i]+" 写入失败: "+e.message,"#f44336")}}log("迁移完成: "+ok+" 成功, "+fail+" 失败","#4caf50");log("3秒后跳转面板…");setTimeout(function(){location.href="/"},3000)}catch(e){log("读取失败，请确认 3100 端口的旧面板正在运行。错误: "+e.message,"#f44336")}},500)};document.body.appendChild(ifr)}</script></body></html>');
      return;
    }

    // Static files
    if (req.url === "/sortable.min.js") {
      var sortableFile = path.join(path.dirname
```
### M-006 - 时间戳替换过于激进——匹配数据内容中的 ISO 时间戳导致语义破坏
- Severity: P1 CRITICAL
- File: server/index.js lines [153, 159]
- Description: N/A
- Suggestion: 只替换顶层 JSON 对象的 timestamp 字段，而非全文盲替。可以逐行 JSON.parse 后只修改 obj.timestamp 字段再序列化回去，避免误伤消息内容中的时间字符串。

Source code context:
```
(file not found)
```
### M-018 - 路径遍历风险: /api/create-and-open 中 config 参数未验证
- Severity: P1 CRITICAL
- File: index.js lines [83, 120]
- Description: N/A
- Suggestion: 验证 configName 只包含安全字符（字母数字、连字符、下划线、点号），且不包含路径分隔符或 .. 序列。

Source code context:
```
// 阿勋的CC面板 5.22 — 缓存+增量版（端口5022），模块化架构
var http = require("http");
var fs = require("fs");
var path = require("path");
var shared = require("./shared");
var pricing = require("./pricing");
var scanner = require("./scanner");
var snapshot = require("./snapshot");
var sse = require("./sse");
var watcher = require("./watcher");
var agents = require("./agents");

// Route handlers
var sessionsRouter = require("./routes/sessions")();
var sessionRouter = require("./routes/session")();
var snapshotsRouter = require("./routes/snapshots")();
var openRouter = require("./routes/open")();

// ============ HTTP Server ============

var server = http.createServer(function(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");

  try {
    // SSE
    if (sse.handleSSE(req, res)) return;

    // 一次性 localStorage 导入路由
    if (req.url === "/import-localstorage") {
      var importFile = path.join(__dirname, "import-data.json");
      if (!fs.existsSync(importFile)) {
        res.writeHead(404); res.end("import-data.json not found");
        return;
      }
      var importData = fs.readFileSync(importFile, "utf8");
      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>导入配置</title><style>body{font-family:system-ui;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}.ok{color:#4caf50}.err{color:#f44336}.key{font-family:monospace;font-size:13px;margin:4px 0}.box{background:#16213e;border-radius:8px;padding:16px;margin:12px 0}h2{margin:0 0 8px}</style></head><body><h2>CC面板配置导入</h2><div id="status">正在导入...</div><div id="results" class="box"></div><script>!function(){var d=' + importData + ';var ok=0,fail=0,results=[];Object.entries(d).forEach(function(e){try{localStorage.setItem(e[0],e[1]);var v=e[1];results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"ok\\">OK</span> ("+(v.length>80?v.substring(0,80)+"...":v)+")</div>");ok++}catch(err){results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"err\\">FAIL: "+err.message+"</span></div>");fail++}});var status=document.getElementById("status");status.innerHTML=ok+" 个成功, "+fail+" 个失败 (共 "+Object.keys(d).length+" 项)";status.className=ok>0?"ok":"err";document.getElementById("results").innerHTML=results.join("");if(ok>0){var p=document.createElement("p");p.textContent="配置已写入 Edge localStorage for "+window.location.origin;p.className="ok";document.body.appendChild(p)}else{var p2=document.createElement("p");p2.textContent="未写入任何数据,请检查浏览器控制台";p2.className="err";document.body.appendChild(p2)}}();</script></body></html>';
      res.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      res.end(html);
      return;
    }

    // HTML
    if (req.url === "/" || req.url === "/index.html") {
      if (fs.existsSync(shared.HTML_FILE)) {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(fs.readFileSync(shared.HTML_FILE, "utf-8"));
      } else {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end("<h1>Dashboard HTML not found</h1>");
      }
      return;
    }

    // localStorage 迁移工具：从 3100 迁移到 5022
    if (req.url === "/migrate") {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end('<!DOCTYPE html><html><head><meta charset="utf-8"><title>迁移 localStorage 3100→5022</title><style>body{font-family:system-ui;max-width:500px;margin:80px auto;padding:20px;background:#0b0f14;color:#e0e0e0;text-align:center}h2{color:#ff6b35}.btn{display:inline-block;padding:14px 36px;background:#ff6b35;color:#fff;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:700;margin:16px 8px}.btn:hover{opacity:0.85}.ok{color:#4caf50}.err{color:#f44336}.info{font-size:13px;color:#888;margin-top:24px}#log{margin-top:16px;font-size:13px;color:#aaa}</style></head><body><h2>localStorage 迁移</h2><p>从 <code>localhost:3100</code> 迁移到 <code>localhost:5022</code></p><p><button class="btn" onclick="doMigrate()">开始迁移</button></p><div id="log"></div><p class="info">迁移完成后<a href="/">返回面板</a></p><script>function log(m,c){var d=document.getElementById("log");d.innerHTML+=m+"<br>";if(c)d.style.color=c}function doMigrate(){log("正在从 3100 读取…");var ifr=document.createElement("iframe");ifr.style.display="none";ifr.src="http://localhost:3100/";ifr.onload=function(){setTimeout(function(){try{var raw=ifr.contentDocument.body.textContent;var data=JSON.parse(raw);var keys=Object.keys(data);log("读取到 "+keys.length+" 个键");var ok=0,fail=0;for(var i=0;i<keys.length;i++){try{localStorage.setItem(keys[i],data[keys[i]]);ok++}catch(e){fail++;log(keys[i]+" 写入失败: "+e.message,"#f44336")}}log("迁移完成: "+ok+" 成功, "+fail+" 失败","#4caf50");log("3秒后跳转面板…");setTimeout(function(){location.href="/"},3000)}catch(e){log("读取失败，请确认 3100 端口的旧面板正在运行。错误: "+e.message,"#f44336")}},500)};document.body.appendChild(ifr)}</script></body></html>');
      return;
    }

    // Static files
    if (req.url === "/sortable.min.js") {
      var sortableFile = path.join(path.dirname
```
### M-031 - parseSessionChunk 函数 110 行，混合了文件 I/O、JSON 解析、业务逻辑和数据聚合
- Severity: P1 CRITICAL
- File: scanner.js lines [68, 175]
- Description: N/A
- Suggestion: 分为 3 层：
1. readJsonlTail(filePath, offset) → string（纯 I/O）
2. parseJsonlLines(content) → object[]（纯解析）
3. aggregateSessionInfo(lines, existingPromptIds) → SessionInfo（纯业务）

这使得每层都可以独立测试和复用。

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
### M-022 - 路径遍历: 快照 ID 未验证可读取任意文件
- Severity: P1 CRITICAL
- File: routes/snapshots.js lines [20, 30]
- Description: N/A
- Suggestion: 验证 snapId 只包含安全字符，不包含路径分隔符。

Source code context:
```
var fs = require("fs");
var path = require("path");
var shared = require("../shared");
var scanner = require("../scanner");
var snapshot = require("../snapshot");

function makeSnapshotsRouter() {
  return function handle(req, res) {
    // API: list snapshots
    if (req.url === "/api/snapshots") {
      snapshot.loadSnapshotsFromDisk();
      var list = shared.snapshotList.map(function(s) { return { id: s.id, timestamp: s.timestamp, sessionCount: s.data ? s.data.sessionCount : 0 }; });
      list.sort(function(a, b) { return b.timestamp.localeCompare(a.timestamp); });
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify(list));
      return true;
    }

    // API: snapshot detail
    if (req.url.startsWith("/api/snapshot/") && req.url.indexOf("/api/snapshot/create") === -1 && req.url.indexOf("/api/snapshot/delete") === -1 && req.url.indexOf("/api/snapshot/rollback") === -1) {
      var snapId = decodeURI(req.url.split("/api/snapshot/")[1]);
      var snapFile = path.join(shared.SNAPSHOTS_DIR, snapId + ".json");
      if (!fs.existsSync(snapFile)) { res.writeHead(404); res.end(JSON.stringify({ error: "not found" })); return true; }
      try {
        var snapData = JSON.parse(fs.readFileSync(snapFile, "utf-8"));
        res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify(snapData));
      } catch (e) { res.writeHead(500); res.end(JSON.stringify({ error: "read error" })); }
      return true;
    }

    // API: create snapshot
    if (req.url === "/api/snapshot/create") {
      scanner.scanSessions(shared.PROJECTS_DIR, []).then(function(sess) {
        for (var n = 0; n < sess.length; n++) {
          sess[n].status = scanner.getStatus(sess[n].fileMtimeMs, sess[n].lastMeaningfulTimestamp, sess[n].lastMeaningfulStopReason);
        }
        var snap = snapshot.saveSnapshot("manual-" + Date.now(), sess);
        res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify(snap ? { ok: true, id: snap.id, timestamp: snap.timestamp } : { ok: false, error: "save failed" }));
      });
      return true;
    }

    // API: delete snapshot
    if (req.url.startsWith("/api/snapshot/delete/")) {
      var delId = decodeURI(req.url.split("/api/snapshot/delete/")[1]);
      snapshot.deleteSnapshot(delId);
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify({ ok: true }));
      return true;
    }

    return false;
  };
}

module.exports = makeSnapshotsRouter;

```
### M-019 - 路径遍历: 会话文件操作使用未经验证的 sessionId
- Severity: P1 CRITICAL
- File: index.js lines [105, 125]
- Description: N/A
- Suggestion: 使用 crypto.randomUUID() 或 crypto.randomBytes() 生成不可预测的会话 ID。

Source code context:
```
// 阿勋的CC面板 5.22 — 缓存+增量版（端口5022），模块化架构
var http = require("http");
var fs = require("fs");
var path = require("path");
var shared = require("./shared");
var pricing = require("./pricing");
var scanner = require("./scanner");
var snapshot = require("./snapshot");
var sse = require("./sse");
var watcher = require("./watcher");
var agents = require("./agents");

// Route handlers
var sessionsRouter = require("./routes/sessions")();
var sessionRouter = require("./routes/session")();
var snapshotsRouter = require("./routes/snapshots")();
var openRouter = require("./routes/open")();

// ============ HTTP Server ============

var server = http.createServer(function(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");

  try {
    // SSE
    if (sse.handleSSE(req, res)) return;

    // 一次性 localStorage 导入路由
    if (req.url === "/import-localstorage") {
      var importFile = path.join(__dirname, "import-data.json");
      if (!fs.existsSync(importFile)) {
        res.writeHead(404); res.end("import-data.json not found");
        return;
      }
      var importData = fs.readFileSync(importFile, "utf8");
      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>导入配置</title><style>body{font-family:system-ui;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}.ok{color:#4caf50}.err{color:#f44336}.key{font-family:monospace;font-size:13px;margin:4px 0}.box{background:#16213e;border-radius:8px;padding:16px;margin:12px 0}h2{margin:0 0 8px}</style></head><body><h2>CC面板配置导入</h2><div id="status">正在导入...</div><div id="results" class="box"></div><script>!function(){var d=' + importData + ';var ok=0,fail=0,results=[];Object.entries(d).forEach(function(e){try{localStorage.setItem(e[0],e[1]);var v=e[1];results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"ok\\">OK</span> ("+(v.length>80?v.substring(0,80)+"...":v)+")</div>");ok++}catch(err){results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"err\\">FAIL: "+err.message+"</span></div>");fail++}});var status=document.getElementById("status");status.innerHTML=ok+" 个成功, "+fail+" 个失败 (共 "+Object.keys(d).length+" 项)";status.className=ok>0?"ok":"err";document.getElementById("results").innerHTML=results.join("");if(ok>0){var p=document.createElement("p");p.textContent="配置已写入 Edge localStorage for "+window.location.origin;p.className="ok";document.body.appendChild(p)}else{var p2=document.createElement("p");p2.textContent="未写入任何数据,请检查浏览器控制台";p2.className="err";document.body.appendChild(p2)}}();</script></body></html>';
      res.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      res.end(html);
      return;
    }

    // HTML
    if (req.url === "/" || req.url === "/index.html") {
      if (fs.existsSync(shared.HTML_FILE)) {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(fs.readFileSync(shared.HTML_FILE, "utf-8"));
      } else {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end("<h1>Dashboard HTML not found</h1>");
      }
      return;
    }

    // localStorage 迁移工具：从 3100 迁移到 5022
    if (req.url === "/migrate") {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end('<!DOCTYPE html><html><head><meta charset="utf-8"><title>迁移 localStorage 3100→5022</title><style>body{font-family:system-ui;max-width:500px;margin:80px auto;padding:20px;background:#0b0f14;color:#e0e0e0;text-align:center}h2{color:#ff6b35}.btn{display:inline-block;padding:14px 36px;background:#ff6b35;color:#fff;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:700;margin:16px 8px}.btn:hover{opacity:0.85}.ok{color:#4caf50}.err{color:#f44336}.info{font-size:13px;color:#888;margin-top:24px}#log{margin-top:16px;font-size:13px;color:#aaa}</style></head><body><h2>localStorage 迁移</h2><p>从 <code>localhost:3100</code> 迁移到 <code>localhost:5022</code></p><p><button class="btn" onclick="doMigrate()">开始迁移</button></p><div id="log"></div><p class="info">迁移完成后<a href="/">返回面板</a></p><script>function log(m,c){var d=document.getElementById("log");d.innerHTML+=m+"<br>";if(c)d.style.color=c}function doMigrate(){log("正在从 3100 读取…");var ifr=document.createElement("iframe");ifr.style.display="none";ifr.src="http://localhost:3100/";ifr.onload=function(){setTimeout(function(){try{var raw=ifr.contentDocument.body.textContent;var data=JSON.parse(raw);var keys=Object.keys(data);log("读取到 "+keys.length+" 个键");var ok=0,fail=0;for(var i=0;i<keys.length;i++){try{localStorage.setItem(keys[i],data[keys[i]]);ok++}catch(e){fail++;log(keys[i]+" 写入失败: "+e.message,"#f44336")}}log("迁移完成: "+ok+" 成功, "+fail+" 失败","#4caf50");log("3秒后跳转面板…");setTimeout(function(){location.href="/"},3000)}catch(e){log("读取失败，请确认 3100 端口的旧面板正在运行。错误: "+e.message,"#f44336")}},500)};document.body.appendChild(ifr)}</script></body></html>');
      return;
    }

    // Static files
    if (req.url === "/sortable.min.js") {
      var sortableFile = path.join(path.dirname
```
### M-032 - /import-localstorage 路由存在 XSS 风险，importData 直接嵌入 HTML 未转义
- Severity: P1 CRITICAL
- File: index.js lines [30, 44]
- Description: N/A
- Suggestion: 对 importData 进行 JSON 转义后再嵌入 HTML，或改用 API 返回 JSON + 前端 fetch 的方式：
1. `/import-localstorage` 只返回 import-data.json 的原始内容（Content-Type: application/json）
2. 前端页面通过 fetch 获取数据并写入 localStorage
3. 如果必须内联，使用 `JSON.stringify(importData)` 而非直接拼接

Source code context:
```
// 阿勋的CC面板 5.22 — 缓存+增量版（端口5022），模块化架构
var http = require("http");
var fs = require("fs");
var path = require("path");
var shared = require("./shared");
var pricing = require("./pricing");
var scanner = require("./scanner");
var snapshot = require("./snapshot");
var sse = require("./sse");
var watcher = require("./watcher");
var agents = require("./agents");

// Route handlers
var sessionsRouter = require("./routes/sessions")();
var sessionRouter = require("./routes/session")();
var snapshotsRouter = require("./routes/snapshots")();
var openRouter = require("./routes/open")();

// ============ HTTP Server ============

var server = http.createServer(function(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");

  try {
    // SSE
    if (sse.handleSSE(req, res)) return;

    // 一次性 localStorage 导入路由
    if (req.url === "/import-localstorage") {
      var importFile = path.join(__dirname, "import-data.json");
      if (!fs.existsSync(importFile)) {
        res.writeHead(404); res.end("import-data.json not found");
        return;
      }
      var importData = fs.readFileSync(importFile, "utf8");
      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>导入配置</title><style>body{font-family:system-ui;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}.ok{color:#4caf50}.err{color:#f44336}.key{font-family:monospace;font-size:13px;margin:4px 0}.box{background:#16213e;border-radius:8px;padding:16px;margin:12px 0}h2{margin:0 0 8px}</style></head><body><h2>CC面板配置导入</h2><div id="status">正在导入...</div><div id="results" class="box"></div><script>!function(){var d=' + importData + ';var ok=0,fail=0,results=[];Object.entries(d).forEach(function(e){try{localStorage.setItem(e[0],e[1]);var v=e[1];results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"ok\\">OK</span> ("+(v.length>80?v.substring(0,80)+"...":v)+")</div>");ok++}catch(err){results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"err\\">FAIL: "+err.message+"</span></div>");fail++}});var status=document.getElementById("status");status.innerHTML=ok+" 个成功, "+fail+" 个失败 (共 "+Object.keys(d).length+" 项)";status.className=ok>0?"ok":"err";document.getElementById("results").innerHTML=results.join("");if(ok>0){var p=document.createElement("p");p.textContent="配置已写入 Edge localStorage for "+window.location.origin;p.className="ok";document.body.appendChild(p)}else{var p2=document.createElement("p");p2.textContent="未写入任何数据,请检查浏览器控制台";p2.className="err";document.body.appendChild(p2)}}();</script></body></html>';
      res.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      res.end(html);
      return;
    }

    // HTML
    if (req.url === "/" || req.url === "/index.html") {
      if (fs.existsSync(shared.HTML_FILE)) {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(fs.readFileSync(shared.HTML_FILE, "utf-8"));
      } else {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end("<h1>Dashboard HTML not found</h1>");
      }
      return;
    }

    // localStorage 迁移工具：从 3100 迁移到 5022
    if (req.url === "/migrate") {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end('<!DOCTYPE html><html><head><meta charset="utf-8"><title>迁移 localStorage 3100→5022</title><style>body{font-family:system-ui;max-width:500px;margin:80px auto;padding:20px;background:#0b0f14;color:#e0e0e0;text-align:center}h2{color:#ff6b35}.btn{display:inline-block;padding:14px 36px;background:#ff6b35;color:#fff;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:700;margin:16px 8px}.btn:hover{opacity:0.85}.ok{color:#4caf50}.err{color:#f44336}.info{font-size:13px;color:#888;margin-top:24px}#log{margin-top:16px;font-size:13px;color:#aaa}</style></head><body><h2>localStorage 迁移</h2><p>从 <code>localhost:3100</code> 迁移到 <code>localhost:5022</code></p><p><button class="btn" onclick="doMigrate()">开始迁移</button></p><div id="log"></div><p class="info">迁移完成后<a href="/">返回面板</a></p><script>function log(m,c){var d=document.getElementById("log");d.innerHTML+=m+"<br>";if(c)d.style.color=c}function doMigrate(){log("正在从 3100 读取…");var ifr=document.createElement("iframe");ifr.style.display="none";ifr.src="http://localhost:3100/";ifr.onload=function(){setTimeout(function(){try{var raw=ifr.contentDocument.body.textContent;var data=JSON.parse(raw);var keys=Object.keys(data);log("读取到 "+keys.length+" 个键");var ok=0,fail=0;for(var i=0;i<keys.length;i++){try{localStorage.setItem(keys[i],data[keys[i]]);ok++}catch(e){fail++;log(keys[i]+" 写入失败: "+e.message,"#f44336")}}log("迁移完成: "+ok+" 成功, "+fail+" 失败","#4caf50");log("3秒后跳转面板…");setTimeout(function(){location.href="/"},3000)}catch(e){log("读取失败，请确认 3100 端口的旧面板正在运行。错误: "+e.message,"#f44336")}},500)};document.body.appendChild(ifr)}</script></body></html>');
      return;
    }

    // Static files
    if (req.url === "/sortable.min.js") {
      var sortableFile = path.join(path.dirname
```
### M-023 - 路径遍历: 会话详情 API 使用未经验证的 session ID
- Severity: P1 CRITICAL
- File: routes/session.js lines [25, 40]
- Description: N/A
- Suggestion: 验证 session ID 符合 UUID 格式（8-4-4-4-12 十六进制字符）。

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
    cost: pricing.calcCost(cached),
    filePath: fpath
  };

  res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(resp));
}

function buildRelationsResponse(relTarget, relId, res) {
  if (!relTarget || !relTarget._file) { res.writeHead(404); res.end(JSON.stringify({ error: "not found" })); return; }

  var nodes = [];
  var edges = [];
  var dispatchCalls = [];

  // Main node
  nodes.push({
    id: relTarget.id, type: "main", title: relTarget.title || relTarget.id,
    status: scanner.getStatus(re
```
### M-020 - HTML 注入: /migrate 路由的 iframe src 包含硬编码端口
- Severity: P1 CRITICAL
- File: index.js lines [49, 52]
- Description: N/A
- Suggestion: 验证从 iframe 读取的数据结构，限制可写入的 localStorage 键名白名单。

Source code context:
```
// 阿勋的CC面板 5.22 — 缓存+增量版（端口5022），模块化架构
var http = require("http");
var fs = require("fs");
var path = require("path");
var shared = require("./shared");
var pricing = require("./pricing");
var scanner = require("./scanner");
var snapshot = require("./snapshot");
var sse = require("./sse");
var watcher = require("./watcher");
var agents = require("./agents");

// Route handlers
var sessionsRouter = require("./routes/sessions")();
var sessionRouter = require("./routes/session")();
var snapshotsRouter = require("./routes/snapshots")();
var openRouter = require("./routes/open")();

// ============ HTTP Server ============

var server = http.createServer(function(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");

  try {
    // SSE
    if (sse.handleSSE(req, res)) return;

    // 一次性 localStorage 导入路由
    if (req.url === "/import-localstorage") {
      var importFile = path.join(__dirname, "import-data.json");
      if (!fs.existsSync(importFile)) {
        res.writeHead(404); res.end("import-data.json not found");
        return;
      }
      var importData = fs.readFileSync(importFile, "utf8");
      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>导入配置</title><style>body{font-family:system-ui;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}.ok{color:#4caf50}.err{color:#f44336}.key{font-family:monospace;font-size:13px;margin:4px 0}.box{background:#16213e;border-radius:8px;padding:16px;margin:12px 0}h2{margin:0 0 8px}</style></head><body><h2>CC面板配置导入</h2><div id="status">正在导入...</div><div id="results" class="box"></div><script>!function(){var d=' + importData + ';var ok=0,fail=0,results=[];Object.entries(d).forEach(function(e){try{localStorage.setItem(e[0],e[1]);var v=e[1];results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"ok\\">OK</span> ("+(v.length>80?v.substring(0,80)+"...":v)+")</div>");ok++}catch(err){results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"err\\">FAIL: "+err.message+"</span></div>");fail++}});var status=document.getElementById("status");status.innerHTML=ok+" 个成功, "+fail+" 个失败 (共 "+Object.keys(d).length+" 项)";status.className=ok>0?"ok":"err";document.getElementById("results").innerHTML=results.join("");if(ok>0){var p=document.createElement("p");p.textContent="配置已写入 Edge localStorage for "+window.location.origin;p.className="ok";document.body.appendChild(p)}else{var p2=document.createElement("p");p2.textContent="未写入任何数据,请检查浏览器控制台";p2.className="err";document.body.appendChild(p2)}}();</script></body></html>';
      res.writeHead(200, {"Content-Type": "text/html; charset=utf-8"});
      res.end(html);
      return;
    }

    // HTML
    if (req.url === "/" || req.url === "/index.html") {
      if (fs.existsSync(shared.HTML_FILE)) {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end(fs.readFileSync(shared.HTML_FILE, "utf-8"));
      } else {
        res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
        res.end("<h1>Dashboard HTML not found</h1>");
      }
      return;
    }

    // localStorage 迁移工具：从 3100 迁移到 5022
    if (req.url === "/migrate") {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end('<!DOCTYPE html><html><head><meta charset="utf-8"><title>迁移 localStorage 3100→5022</title><style>body{font-family:system-ui;max-width:500px;margin:80px auto;padding:20px;background:#0b0f14;color:#e0e0e0;text-align:center}h2{color:#ff6b35}.btn{display:inline-block;padding:14px 36px;background:#ff6b35;color:#fff;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:700;margin:16px 8px}.btn:hover{opacity:0.85}.ok{color:#4caf50}.err{color:#f44336}.info{font-size:13px;color:#888;margin-top:24px}#log{margin-top:16px;font-size:13px;color:#aaa}</style></head><body><h2>localStorage 迁移</h2><p>从 <code>localhost:3100</code> 迁移到 <code>localhost:5022</code></p><p><button class="btn" onclick="doMigrate()">开始迁移</button></p><div id="log"></div><p class="info">迁移完成后<a href="/">返回面板</a></p><script>function log(m,c){var d=document.getElementById("log");d.innerHTML+=m+"<br>";if(c)d.style.color=c}function doMigrate(){log("正在从 3100 读取…");var ifr=document.createElement("iframe");ifr.style.display="none";ifr.src="http://localhost:3100/";ifr.onload=function(){setTimeout(function(){try{var raw=ifr.contentDocument.body.textContent;var data=JSON.parse(raw);var keys=Object.keys(data);log("读取到 "+keys.length+" 个键");var ok=0,fail=0;for(var i=0;i<keys.length;i++){try{localStorage.setItem(keys[i],data[keys[i]]);ok++}catch(e){fail++;log(keys[i]+" 写入失败: "+e.message,"#f44336")}}log("迁移完成: "+ok+" 成功, "+fail+" 失败","#4caf50");log("3秒后跳转面板…");setTimeout(function(){location.href="/"},3000)}catch(e){log("读取失败，请确认 3100 端口的旧面板正在运行。错误: "+e.message,"#f44336")}},500)};document.body.appendChild(ifr)}</script></body></html>');
      return;
    }

    // Static files
    if (req.url === "/sortable.min.js") {
      var sortableFile = path.join(path.dirname
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