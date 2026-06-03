# 角色
你是一名资深代码审查专家，正在对一份代码进行系统性的代码审查。
你的审查哲学：你是'攻击者思维'的安全审计专家。你审查代码时的默认假设是：有恶意攻击者会仔细阅读这段代码，寻找任何可能的突破口。你不是在找'不优雅'的代码——你是在找'可利用'的代码。你的核心理念来自 574+ 个真实 HackerOne 漏洞报告的模式提炼。

# 你的身份
你是 MACRS（多智能体对抗式代码审查系统）中的 **Agent B - Security Hunter**。
你的技能来源：Claude-BugHunter

# 审查范围
目标路径：C:\Users\Administrator\Claude-Code\cc-tools\Xun-CC-Panel\server

审查文件列表 (12 个文件, 1955 行):
  - agents.js
  - index.js
  - pricing.js
  - routes\open.js
  - routes\session.js
  - routes\sessions.js
  - routes\snapshots.js
  - scanner.js
  - shared.js
  - snapshot.js
  - sse.js
  - watcher.js

---

### File: agents.js
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

function scanSubAgents(sessions) {
  shared.subAgentCache.clear();
  for (var i = 0; i < sessions.length; i++) {
    var s = sessions[i];
    if (!s._file) continue;
    var sessionDir = path.dirname(s._file);
    var subDir = path.join(sessionDir, s.id);
    // Check both possible locations for subagents/
    var dirs = [subDir, sessionDir];
    for (var d = 0; d < dirs.length; d++) {
      var agentFiles = findSubAgentFiles(dirs[d]);
      for (var a = 0; a < agentFiles.length; a++) {
        var agentKey = s.id + "::" + agentFiles[a].agentId;
        if (!shared.subAgentCache.has(agentKey)) {
          var agentInfo = parseSubAgent(agentFiles[a].filePath, agentFiles[a].agentId, s.id);
          shared.subAgentCache.set(agentKey, agentInfo);
        }
      }
    }
  }
}

module.exports = {
  loadAgentNames: loadAgentNames,
  buildAgentName: buildAgentName,
  findSubAgentFiles: findSubAgentFiles,
  parseSubAgent: parseSubAgent,
  scanSubAgents: scanSubAgents
};

```

### File: index.js
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
  var origin = req.headers.origin;
  if (origin && /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin)) {
    res.setHeader("Access-Control-Allow-Origin", origin);
  }

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
      var safeData = JSON.stringify(JSON.parse(importData));
      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>导入配置</title><style>body{font-family:system-ui;max-width:600px;margin:50px auto;padding:20px;background:#1a1a2e;color:#e0e0e0}.ok{color:#4caf50}.err{color:#f44336}.key{font-family:monospace;font-size:13px;margin:4px 0}.box{background:#16213e;border-radius:8px;padding:16px;margin:12px 0}h2{margin:0 0 8px}</style></head><body><h2>CC面板配置导入</h2><div id="status">正在导入...</div><div id="results" class="box"></div><script>!function(){var d=' + safeData + ';var ok=0,fail=0,results=[];Object.entries(d).forEach(function(e){try{localStorage.setItem(e[0],e[1]);var v=e[1];results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"ok\\">OK</span> ("+(v.length>80?v.substring(0,80)+"...":v)+")</div>");ok++}catch(err){results.push("<div class=\\"key\\">"+e[0]+" <span class=\\"err\\">FAIL: "+err.message+"</span></div>");fail++}});var status=document.getElementById("status");status.innerHTML=ok+" 个成功, "+fail+" 个失败 (共 "+Object.keys(d).length+" 项)";status.className=ok>0?"ok":"err";document.getElementById("results").innerHTML=results.join("");if(ok>0){var p=document.createElement("p");p.textContent="配置已写入 Edge localStorage for "+window.location.origin;p.className="ok";document.body.appendChild(p)}else{var p2=document.createElement("p");p2.textContent="未写入任何数据,请检查浏览器控制台";p2.className="err";document.body.appendChild(p2)}}();</script></body></html>';
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
      var sortableFile = path.join(path.dirname(shared.HTML_FILE), "sortable.min.js");
      if (fs.existsSync(sortableFile)) {
        res.writeHead(200, {"Content-Type": "application/javascript"});
        res.end(fs.readFileSync(sortableFile));
      } else {
        res.writeHead(404); res.end("404");
      }
      return;
    }

    // QR code images (优先 assets/ 目录，兼容根目录)
    if (req.url === "/qr-wechat.png") {
      var qrWx = path.join(path.dirname(shared.HTML_FILE), "assets", "qr-wechat.png");
      if (!fs.existsSync(qrWx)) qrWx = path.join(path.dirname(shared.HTML_FILE), "qr-wechat.png");
      if (fs.existsSync(qrWx)) {
        res.writeHead(200, {"Content-Type": "image/png"});
        res.end(fs.readFileSync(qrWx));
      } else { res.writeHead(404); res.end("404"); }
      return;
    }
    if (req.url === "/qr-alipay.jpg") {
      var qrAli = path.join(path.dirname(shared.HTML_FILE), "assets", "qr-alipay.jpg");
      if (!fs.existsSync(qrAli)) qrAli = path.join(path.dirname(shared.HTML_FILE), "qr-alipay.jpg");
      if (fs.existsSync(qrAli)) {
        res.writeHead(200, {"Content-Type": "image/jpeg"});
        res.end(fs.readFileSync(qrAli));
      } else { res.writeHead(404); res.end("404"); }
      return;
    }

    // API: create session & open in VSCode with specific settings
    if (req.url.startsWith("/api/create-and-open")) {
      var urlObj = new URL(req.url, "http://localhost");
      var configName = urlObj.searchParams.get("config");
      if (!configName) {
        res.writeHead(400, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ ok: false, error: "config required" }));
        return;
      }
      // P0-002: 验证 configName 格式，防止路径遍历攻击
      if (!/^setting-[a-zA-Z0-9_-]+\.json$/.test(configName)) {
        res.writeHead(400, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ ok: false, error: "invalid config name format" }));
        return;
      }
      var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
      var settingsPath = path.join(homeDir, ".claude", configName);
      var projectsDir = path.join(shared.PROJECTS_DIR, "C--Users-Administrator");
      var sessionsDir = path.join(homeDir, ".claude", "sessions");

      // Generate new session ID
      var sessionId = "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c === "x" ? r : (r & 0x3 | 0x8);
        return v.toString(16);
      });

      // Fork 源会话（保留完整结构，Claude Code 需要 hook 行才能识别）
      var sourceSessionId = "a67f1853-fcfb-4226-9647-49da7ed13cdd";
      var sourceFile = path.join(projectsDir, sourceSessionId + ".jsonl");
      if (!fs.existsSync(sourceFile)) {
        res.writeHead(500, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify({ ok: false, error: "Source session not found: " + sourceFile }));
        return;
      }

      var sourceContent = fs.readFileSync(sourceFile, "utf-8");

      // 收集所有 UUID（用于生成映射表，保证一致性）
      var uuidMap = {};
      function genUuid() {
        return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function(c) {
          var r = Math.random() * 16 | 0, v = c === "x" ? r : (r & 0x3 | 0x8);
          return v.toString(16);
        });
      }
      var uuidRegex = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
      var foundUuids = sourceContent.match(uuidRegex);
      if (foundUuids) {
        for (var ui = 0; ui < foundUuids.length; ui++) {
          var uid = foundUuids[ui].toLowerCase();
          if (uid !== sourceSessionId && !uuidMap.hasOwnProperty(uid)) {
            uuidMap[uid] = genUuid();
          }
        }
      }

      // 替换：先替换 sessionId，再替换所有其他 UUID
      var newContent = sourceContent.split(sourceSessionId).join(sessionId);
      var oldUuids = Object.keys(uuidMap);
      for (var oi = 0; oi < oldUuids.length; oi++) {
        // 全局替换每个 old UUID（不区分大小写）
        newContent = newContent.split(oldUuids[oi]).join(uuidMap[oldUuids[oi]]);
        // 也替换大写版本
        newContent = newContent.split(oldUuids[oi].toUpperCase()).join(uuidMap[oldUuids[oi]]);
      }

      // 替换所有时间戳为当前时间（面板按 lastTimestamp 排序，新会话需要置顶）
      var tsRegex = /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z/g;
      var tsBase = Date.now();
      var tsCounter = 0;
      newContent = newContent.replace(tsRegex, function() {
        return new Date(tsBase + tsCounter++).toISOString();
      });

      // 写入新的 JSONL 文件
      var newJsonl = path.join(projectsDir, sessionId + ".jsonl");
      fs.writeFileSync(newJsonl, newContent);

      // 追加 custom title
      var label = configName.replace("setting-", "").replace(".json", "");
      var titleLine = JSON.stringify({ type: "custom-title", sessionId: sessionId, customTitle: "[" + label + "] 新会话" });
      fs.appendFileSync(newJsonl, titleLine + "\n");

      // 创建 session metadata
      try {
        var fakePid = Math.floor(Math.random() * 900000) + 100000;
        var sessionMeta = {
          pid: fakePid,
          sessionId: sessionId,
          cwd: "C:\\Users\\Administrator",
          startedAt: Date.now(),
          version: "2.1.158",
          kind: "interactive",
          entrypoint: "claude-vscode"
        };
        fs.writeFileSync(path.join(sessionsDir, fakePid + ".json"), JSON.stringify(sessionMeta, null, 2));
      } catch (e) {}

      // Store config mapping
      shared.sessionConfigMap.set(sessionId, configName);
      shared.saveSessionConfigMap(shared.sessionConfigMap);

      // 直接 spawn VSCode 打开会话（绕过 open-session 的扫描流程）
      try {
        var spawnResult = openRouter.launchSessionDirect(configName, sessionId, "C:\\Users\\Administrator");
        console.log("[create-and-open] spawn result:", JSON.stringify(spawnResult));
      } catch (spawnErr) {
        console.error("[create-and-open] spawn failed:", spawnErr.message);
      }

      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
      res.end(JSON.stringify({ ok: true, sessionId: sessionId, configFile: configName }));
      return;
    }

    // Route modules
    if (openRouter(req, res)) return;
    if (sessionsRouter(req, res)) return;
    if (sessionRouter(req, res)) return;
    if (snapshotsRouter(req, res)) return;

    // 404
    res.writeHead(404); res.end("404");
  } catch (err) {
    console.error("[CC-Panel] Internal error:", err);
    res.writeHead(500); res.end("Internal Server Error");
  }
});

// ============ Graceful Shutdown ============

function shutdown() {
  console.log("[CC面板] 正在关闭...");
  watcher.cleanupWatchers();
  sse.cleanupSSE();
  server.close(function() {
    console.log("[CC面板] 已关闭");
    process.exit(0);
  });
  // Force exit after 5s if cleanup hangs
  setTimeout(function() { process.exit(0); }, 5000);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

// ============ Start ============

try { fs.mkdirSync(shared.SNAPSHOTS_DIR, { recursive: true }); } catch (e) {}
snapshot.loadSnapshotsFromDisk();

scanner.scanSessions(shared.PROJECTS_DIR, []).then(function(initialSessions) {
  agents.scanSubAgents(initialSessions);
  var runningCount = 0;
  for (var i = 0; i < initialSessions.length; i++) {
    initialSessions[i].status = scanner.getStatus(initialSessions[i].fileMtimeMs, initialSessions[i].lastMeaningfulTimestamp, initialSessions[i].lastMeaningfulStopReason);
    if (initialSessions[i].status === "running") runningCount++;
  }

  watcher.setupFileWatcher();

  // Fallback poll: 30s full scan
  setInterval(function() { watcher.processChanges(); }, 30000);

  server.on("error", function(err) {
    if (err.code === "EADDRINUSE") {
      console.error("[CC-Panel] 端口 " + shared.PORT + " 已被占用，可能是旧进程未退出");
      console.error("[CC-Panel] 尝试: netstat -ano | findstr :" + shared.PORT + " 然后 taskkill /F /PID <pid>");
      process.exit(1);
    } else {
      console.error("[CC-Panel] 服务器错误:", err);
      process.exit(1);
    }
  });

  server.listen(shared.PORT, function() {
    console.log("[阿勋的CC面板 5.22] CC多任务管理面板 → http://localhost:" + shared.PORT);
    console.log("[阿勋的CC面板 5.22] " + initialSessions.length + " 主会话 + " + shared.subAgentCache.size + " 子Agent (" + runningCount + " 活跃中)");
    console.log("[阿勋的CC面板 5.22] 实时推送: fs.watch + SSE /api/events");
    console.log("[阿勋的CC面板 5.22] 快照: " + shared.SNAPSHOTS_DIR);
    // 启动 CCL 会话自动映射监控
    shared.watchCclSessions(shared.sessionConfigMap, shared.PROJECTS_DIR);
    console.log("[阿勋的CC面板 5.22] Ctrl+C to stop");
  });
});

```

### File: pricing.js
```
var fs = require("fs");
var path = require("path");

var DEFAULT_PRICING = {
  "deepseek-v4-pro":   { input: 1.0, cacheRead: 0.2, output: 2.0 },
  "deepseek-v4-flash": { input: 0.5, cacheRead: 0.1, output: 1.0 },
  "deepseek-v4":       { input: 0.5, cacheRead: 0.1, output: 1.0 }
};

var PRICING = null;
var pricingFile = path.join(process.env.HOME || process.env.USERPROFILE || "~", ".claude", "pricing.json");

function loadPricing() {
  try {
    var raw = fs.readFileSync(pricingFile, "utf-8");
    var loaded = JSON.parse(raw);
    if (loaded && typeof loaded === "object") {
      PRICING = loaded;
    } else {
      PRICING = DEFAULT_PRICING;
    }
  } catch (e) {
    PRICING = DEFAULT_PRICING;
  }
}

function defaultPricing() {
  return { input: 1.0, cacheRead: 0.2, output: 2.0 };
}

function calcCost(info) {
  var p = (PRICING && PRICING[info.model]) || defaultPricing();
  var cost = ((info._itok || 0) / 1e6) * p.input + ((info._ctok || 0) / 1e6) * p.cacheRead + ((info._otok || 0) / 1e6) * p.output;
  return Math.round(cost * 1000) / 1000;
}

// Load immediately
loadPricing();

module.exports = {
  getPricing: function() { return PRICING; },
  loadPricing: loadPricing,
  defaultPricing: defaultPricing,
  calcCost: calcCost
};

```

### File: routes\open.js
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
  var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
  var configFile = shared.sessionConfigMap.get(batId);

  // 如果 sessionConfigMap 里没有，查 CCL 会话记录（按项目路径匹配）
  if (!configFile && batCached && batCached.cwd) {
    configFile = shared.cclProjectMap.get(batCached.cwd);
    if (configFile) console.log("[open] CCL 匹配: " + batId + " → " + configFile);
  }

  // P0-003: 验证 configFile 格式
  if (configFile && !isValidConfigName(configFile)) {
    console.error("[open] 无效的 configName，已忽略: " + configFile);
    configFile = null;
  }

  var cliArgs = ["--resume", batId];
  if (configFile) {
    cliArgs.push("--settings", path.join(homeDir, ".claude", configFile));
  }

  spawnDirect(claudeExe, cliArgs, configFile, batCwd || undefined);

  res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify({ ok: true }));
}

function launchSession(target, openId, res, queryConfig) {
  var cwd = target && target.cwd ? target.cwd : (target && target._file ? path.dirname(target._file) : "");
  var result = { ok: false, actions: [] };
  var npmBin = process.env.APPDATA ? path.join(process.env.APPDATA, "npm") : null;
  var claudeExe = npmBin ? path.join(npmBin, "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe") : "claude";
  var child_process = require("child_process");
  var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";

  var configFile = shared.sessionConfigMap.get(openId);

  // 如果 sessionConfigMap 里没有，查 CCL 会话记录（按项目路径匹配）
  if (!configFile && target && target.cwd) {
    configFile = shared.cclProjectMap.get(target.cwd);
    if (configFile) console.log("[open] CCL 匹配: " + openId + " → " + configFile);
  }

  // 前端传来的 config 参数（用户手动选择）
  if (!configFile && queryConfig) {
    configFile = queryConfig;
    console.log("[open] 用户选择: " + openId + " → " + configFile);
  }

  // P0-003: 验证 configFile 格式
  if (configFile && !isValidConfigName(configFile)) {
    console.error("[open] 无效的 configName，已忽略: " + configFile);
    configFile = null;
  }

  // 不修改 settings.json，通过 --settings CLI 参数注入配置
  var cliArgs = ["--resume", openId];
  if (configFile) {
    cliArgs.push("--settings", path.join(homeDir, ".claude", configFile));
  }
  cliArgs.push("--ide");

  var launched = spawnDirect(claudeExe, cliArgs, configFile, cwd);

  if (!launched) {
    // fallback: 用 VSCode 打开 JSONL 文件
    try {
      var child2 = child_process.spawn("cmd", ["/c", "start", "\"\"", "code", target._file], { detached: true, stdio: "ignore" });
      child2.unref();
      launched = true;
      result.actions.push("code-file");
    } catch (ee) {}
  }
  if (!launched) {
    try {
      var child3 = child_process.spawn("cmd", ["/c", "start", "\"\"", "code", cwd, "--reuse-window"], { detached: true, stdio: "ignore" });
      child3.unref();
      launched = true;
      result.actions.push("code-cwd");
    } catch (ee) {}
  }

  result.ok = launched;
  if (result.ok) { result.sessionId = openId; result.title = target ? target.title : ""; }
  res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify(result.ok ? result : { ok: false, error: "无法启动会话" }));
}

// P0-001: 引入写入锁，防止并发写入 settings.json 竞态条件
var _settingsWriteLock = false;
var _settingsRefCounts = {};

function swapSettingsJson(configFile) {
  var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
  var defaultSettingsPath = path.join(homeDir, ".claude", "settings.json");
  if (!configFile) return;

  // P0-003: 验证 configFile 格式
  if (!isValidConfigName(configFile)) {
    console.error("[open] swapSettingsJson: 无效的 configName: " + configFile);
    return;
  }

  // 引用计数：记录当前有多少会话在使用此配置
  if (!_settingsRefCounts[configFile]) _settingsRefCounts[configFile] = 0;
  _settingsRefCounts[configFile]++;

  // 如果已在写入中，跳过（后续会话会使用 --settings 参数，不需要 swap）
  if (_settingsWriteLock) {
    console.log("[open] settings.json 写入中，跳过 swap (" + configFile + ")");
    return;
  }

  _settingsWriteLock = true;
  try {
    var targetConfigPath = path.join(homeDir, ".claude", configFile);
    if (fs.existsSync(targetConfigPath) && fs.existsSync(defaultSettingsPath)) {
      var currentSettings = fs.readFileSync(defaultSettingsPath, "utf-8");
      var targetSettings = fs.readFileSync(targetConfigPath, "utf-8");
      if (currentSettings !== targetSettings) {
        fs.writeFileSync(defaultSettingsPath, targetSettings, "utf-8");
        shared.currentSettingsConfig = configFile;
        console.log("[open] settings.json → " + configFile);
      }
    }
  } catch (ee) {
    console.error("[open] settings.json 写入失败:", ee.message);
  } finally {
    _settingsWriteLock = false;
  }
}

module.exports = makeOpenRouter;

makeOpenRouter.launchSessionDirect = function(configFile, sessionId, cwd) {
  var pathModule = require("path");
  var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";
  var result = { ok: false };
  var npmBin = process.env.APPDATA ? pathModule.join(process.env.APPDATA, "npm") : null;
  var claudeExe = npmBin ? pathModule.join(npmBin, "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe") : "claude";

  // P0-003: 验证 configFile 格式
  if (configFile && !isValidConfigName(configFile)) {
    console.error("[open] launchSessionDirect: 无效的 configName，已忽略: " + configFile);
    configFile = null;
  }

  // 不修改 settings.json——通过 --settings CLI 参数 + env vars 注入配置
  var cliArgs = ["--resume", sessionId];
  if (configFile) {
    cliArgs.push("--settings", pathModule.join(homeDir, ".claude", configFile));
  }
  cliArgs.push("--ide");

  spawnDirect(claudeExe, cliArgs, configFile, cwd || "C:\\Users\\Administrator");

  result.ok = true;
  result.sessionId = sessionId;
  return result;
};

makeOpenRouter.swapSettingsJson = swapSettingsJson;

```

### File: routes\session.js
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
    status: scanner.getStatus(relTarget.fileMtimeMs, relTarget.lastMeaningfulTimestamp, relTarget.lastMeaningfulStopReason),
    model: relTarget.model, tokenHeat: relTarget.tokenHeat, cost: pricing.calcCost(relTarget),
    startTime: relTarget.lastTimestamp, fileMtime: relTarget.fileMtime
  });

  // Parse parent file for Agent/Task dispatch events
  var parentDir = path.dirname(relTarget._file);
  try {
    var pContent = fs.readFileSync(relTarget._file, "utf-8");
    var pLines = pContent.trim().split("\n");
    for (var pi = 0; pi < pLines.length; pi++) {
      var pObj = scanner.parseLine(pLines[pi]);
      if (!pObj || pObj.type !== "assistant" || !pObj.message || !pObj.message.content) continue;
      for (var pj = 0; pj < pObj.message.content.length; pj++) {
        var block = pObj.message.content[pj];
        if (block.type === "tool_use" && (block.name === "Agent" || block.name === "Task" || block.name === "TeamCreate")) {
          dispatchCalls.push({
            time: pObj.timestamp || null,
            line: pi,
            tool: block.name,
            description: (block.input && block.input.description) || "",
            subagent_type: (block.input && block.input.subagent_type) || "",
            prompt: (block.input && block.input.prompt ? block.input.prompt.slice(0, 200) : "") || ""
          });
        }
      }
    }
  } catch (e) {}

  // Parse sub-agents
  var subDirs = [path.join(parentDir, relId, "subagents"), path.join(parentDir, "subagents")];
  var subAgentMap = {};
  for (var sd = 0; sd < subDirs.length; sd++) {
    if (!fs.existsSync(subDirs[sd])) continue;
    var saFiles = fs.readdirSync(subDirs[sd]).filter(function(f) { return f.startsWith("agent-") && f.endsWith(".jsonl"); });
    for (var sa = 0; sa < saFiles.length; sa++) {
      var saPath = path.join(subDirs[sd], saFiles[sa]);
      var saAgentId = saFiles[sa].replace(".jsonl", "");
      var saStat = fs.statSync(saPath);
      var saInfo = {
        id: saAgentId, type: "sub-agent", title: saAgentId, status: "idle",
        model: null, cost: 0, startTime: null, _itok: 0, _otok: 0, toolCallCount: 0
      };
      try {
        var saContent = fs.readFileSync(saPath, "utf-8");
        var saLines = saContent.trim().split("\n");
        var firstUserFound = false;
        for (var sl = 0; sl < saLines.length; sl++) {
          var saObj = scanner.parseLine(saLines[sl]);
          if (!saObj) continue;
          if (!firstUserFound && saObj.type === "user" && saObj.message && saObj.message.content) {
            for (var sk = 0; sk < saObj.message.content.length; sk++) {
              if (saObj.message.content[sk].type === "text" && saObj.message.content[sk].text) {
                saInfo.title = saObj.message.content[sk].text.slice(0, 100).replace(/\n/g, " ");
                firstUserFound = true;
                break;
              }
            }
          }
          if (!saInfo.startTime && saObj.timestamp) saInfo.startTime = saObj.timestamp;
          if (saObj.type === "assistant" && saObj.message && saObj.message.usage) {
            saInfo._itok += (saObj.message.usage.input_tokens || 0);
            saInfo._otok += (saObj.message.usage.output_tokens || 0);
            if (!saInfo.model && saObj.message.model) saInfo.model = saObj.message.model;
          }
          if (saObj.type === "assistant" && saObj.message && saObj.message.stop_reason) {
            saInfo.lastStopReason = saObj.message.stop_reason;
          }
          if (saObj.type === "assistant" && saObj.message && saObj.message.content) {
            for (var sc = 0; sc < saObj.message.content.length; sc++) {
              if (saObj.message.content[sc].type === "tool_use") saInfo.toolCallCount++;
            }
          }
        }
        saInfo.status = saInfo.lastStopReason === "end_turn" ? "completed" : saInfo.lastStopReason === "tool_use" ? (Date.now() - saStat.mtimeMs < 10 * 60 * 1000 ? "running" : "异常") : "idle";
        var p2 = (pricing.getPricing() && pricing.getPricing()[saInfo.model]) || pricing.defaultPricing();
        saInfo.cost = Math.round(((saInfo._itok / 1e6) * p2.input + (saInfo._otok / 1e6) * p2.output) * 1000) / 1000;
      } catch (e) {}
      nodes.push(saInfo);
      subAgentMap[saAgentId] = saInfo;
    }
  }

  // Match dispatch calls to sub-agents by time proximity
  var sortedCalls = dispatchCalls.filter(function(c) { return c.time; }).sort(function(a, b) { return a.time.localeCompare(b.time); });
  var sortedAgents = nodes.filter(function(n) { return n.type === "sub-agent" && n.startTime; }).sort(function(a, b) { return a.startTime.localeCompare(b.startTime); });
  var usedAgents = {};

  for (var ci = 0; ci < sortedCalls.length; ci++) {
    var call = sortedCalls[ci];
    var bestMatch = null, bestDist = Infinity;
    for (var ai = 0; ai < sortedAgents.length; ai++) {
      if (usedAgents[sortedAgents[ai].id]) continue;
      var dist = Math.abs(new Date(call.time).getTime() - new Date(sortedAgents[ai].startTime).getTime());
      if (dist < bestDist && dist < 60000) { bestDist = dist; bestMatch = sortedAgents[ai]; }
    }
    if (bestMatch) {
      usedAgents[bestMatch.id] = true;
      var nameCfg = agentsMod.loadAgentNames();
      if (nameCfg.agents && nameCfg.agents[bestMatch.id]) {
        bestMatch.title = nameCfg.agents[bestMatch.id];
      } else {
        var autoName = agentsMod.buildAgentName(call.subagent_type, call.description, bestMatch.title);
        if (autoName && autoName.length > 3) bestMatch.title = autoName;
      }
      edges.push({ from: relId, to: bestMatch.id, time: call.time, description: call.description, subagent_type: call.subagent_type, tool: call.tool });
    } else {
      edges.push({ from: relId, to: null, time: call.time, description: call.description, subagent_type: call.subagent_type, tool: call.tool, unmatched: true });
    }
  }
  for (var ui = 0; ui < sortedAgents.length; ui++) {
    if (!usedAgents[sortedAgents[ui].id]) {
      edges.push({ from: relId, to: sortedAgents[ui].id, time: sortedAgents[ui].startTime, description: sortedAgents[ui].title, subagent_type: "", tool: "Agent" });
    }
  }

  // Phase detection
  var PHASE_GAP_MS = 10 * 60 * 1000;
  var PARALLEL_WIN_MS = 4 * 60 * 1000;

  var matchedEdges = edges.filter(function(e) { return e.time && e.to && !e.unmatched; })
    .sort(function(a, b) { return a.time.localeCompare(b.time); });

  var userMessages = [];
  try {
    for (var pi2 = 0; pi2 < pLines.length; pi2++) {
      var pObj2 = scanner.parseLine(pLines[pi2]);
      if (pObj2 && pObj2.type === "user" && pObj2.message && pObj2.message.content && pObj2.timestamp) {
        for (var pk = 0; pk < pObj2.message.content.length; pk++) {
          if (pObj2.message.content[pk].type === "text" && pObj2.message.content[pk].text) {
            userMessages.push({ time: pObj2.timestamp, text: pObj2.message.content[pk].text.slice(0, 120).replace(/\n/g, " ") });
            break;
          }
        }
      }
    }
  } catch (e) {}

  var phases = [];
  var currentPhase = null;

  for (var ei = 0; ei < matchedEdges.length; ei++) {
    var edge = matchedEdges[ei];
    var edgeTime = new Date(edge.time).getTime();

    var phaseLabel = "";
    for (var ui2 = userMessages.length - 1; ui2 >= 0; ui2--) {
      if (new Date(userMessages[ui2].time).getTime() <= edgeTime) { phaseLabel = userMessages[ui2].text.slice(0, 60); break; }
    }

    var startNewPhase = !currentPhase || (edgeTime - currentPhase._lastTime) > PHASE_GAP_MS;

    if (startNewPhase) {
      currentPhase = { index: phases.length + 1, label: phaseLabel || ("阶段" + (phases.length + 1)), startTime: edge.time, endTime: edge.time, _lastTime: edgeTime, _label: phaseLabel, groups: [], agentCount: 0 };
      phases.push(currentPhase);
      currentPhase.groups.push({ type: "sequential", agentIds: [edge.to], startTime: edge.time, endTime: edge.time, label: edge.description ? edge.description.slice(0, 40) : "" });
      currentPhase.agentCount = 1;
    } else {
      currentPhase.endTime = edge.time;
      currentPhase.agentCount++;
      var timeSinceGroupStart = edgeTime - new Date(currentPhase.groups[currentPhase.groups.length - 1].startTime).getTime();
      if (timeSinceGroupStart < PARALLEL_WIN_MS) {
        var cg = currentPhase.groups[currentPhase.groups.length - 1];
        cg.agentIds.push(edge.to);
        cg.endTime = edge.time;
        if (cg.agentIds.length > 1) cg.type = "parallel";
      } else {
        currentPhase.groups.push({ type: "sequential", agentIds: [edge.to], startTime: edge.time, endTime: edge.time, label: edge.description ? edge.description.slice(0, 40) : "" });
      }
      currentPhase._lastTime = edgeTime;
    }
  }

  // Waterfall trace
  var waterfallSpans = [];
  var wfFirstTs = null;
  var wfParentStack = [];

  for (var wi = 0; wi < pLines.length; wi++) {
    var wObj = scanner.parseLine(pLines[wi]);
    if (!wObj || !wObj.timestamp) continue;
    var wTs = new Date(wObj.timestamp).getTime();
    if (wfFirstTs === null) wfFirstTs = wTs;
    var relStart = wTs - wfFirstTs;
    var span = { id: waterfallSpans.length, ts: wObj.timestamp, relStart: relStart, depth: 0 };

    if (wObj.type === "user") {
      span.type = "user";
      span.name = "提问";
      if (wObj.message && wObj.message.content && Array.isArray(wObj.message.content)) {
        for (var wk = 0; wk < wObj.message.content.length; wk++) {
          if (wObj.message.content[wk].type === "text" && wObj.message.content[wk].text) {
            span.text = wObj.message.content[wk].text.slice(0, 120);
            break;
          }
        }
      }
      span.duration = 0;
      wfParentStack = [];
    } else if (wObj.type === "assistant") {
      span.type = "assistant";
      span.stopReason = (wObj.message && wObj.message.stop_reason) || null;
      span.name = span.stopReason === "tool_use" ? "工具调用" : span.stopReason === "end_turn" ? "回复" : "响应";
      span.tokens = wObj.message && wObj.message.usage ? { input: wObj.message.usage.input_tokens || 0, output: wObj.message.usage.output_tokens || 0 } : null;
      span.model = (wObj.message && wObj.message.model) || null;
      span.duration = 0;
      wfParentStack = [];
      if (wObj.message && wObj.message.content && Array.isArray(wObj.message.content)) {
        for (var wj = 0; wj < wObj.message.content.length; wj++) {
          var wBlock = wObj.message.content[wj];
          if (wBlock.type === "tool_use") {
            var toolSpan = { id: waterfallSpans.length + 1, type: "tool_use", name: wBlock.name || "unknown", ts: wObj.timestamp, relStart: relStart, depth: 1, duration: 0, parentId: span.id, toolInput: wBlock.input ? JSON.stringify(wBlock.input).slice(0, 120) : "" };
            waterfallSpans.push(toolSpan);
            span.duration = 0;
          }
        }
      }
    } else if (wObj.type === "attachment" || wObj.type === "tool_result") {
      span.type = "tool_result";
      span.name = "结果";
      span.depth = 1;
      span.duration = 0;
    } else {
      continue;
    }

    waterfallSpans.push(span);
  }

  for (var wd = 0; wd < waterfallSpans.length - 1; wd++) {
    if (waterfallSpans[wd].type === "assistant" || waterfallSpans[wd].type === "tool_use") {
      var nextRel = waterfallSpans[wd + 1].relStart;
      if (nextRel > waterfallSpans[wd].relStart) {
        waterfallSpans[wd].duration = nextRel - waterfallSpans[wd].relStart;
      }
    }
    if (waterfallSpans[wd].type === "user") {
      waterfallSpans[wd].duration = 2000;
    }
  }
  var lastWf = waterfallSpans[waterfallSpans.length - 1];
  if (lastWf && lastWf.duration === 0 && (lastWf.type === "assistant" || lastWf.type === "tool_use")) {
    lastWf.duration = 1000;
  }

  if (waterfallSpans.length > 200) {
    waterfallSpans = waterfallSpans.slice(-200);
    var reAnchor = waterfallSpans[0].relStart;
    for (var wt = 0; wt < waterfallSpans.length; wt++) {
      waterfallSpans[wt].id = wt;
      waterfallSpans[wt].relStart -= reAnchor;
    }
  }

  res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify({ sessionId: relId, nodes: nodes, edges: edges, dispatchCount: dispatchCalls.length, phases: phases, waterfall: waterfallSpans }));
}

module.exports = makeSessionRouter;

```

### File: routes\sessions.js
```
var shared = require("../shared");
var scanner = require("../scanner");
var agents = require("../agents");
var pricing = require("../pricing");

function makeSessionsRouter() {
  return function handle(req, res) {
    // API: all sessions with sub-agents
    if (req.url === "/api/sessions") {
      scanner.scanSessions(shared.PROJECTS_DIR, []).then(function(sessions) {
        agents.scanSubAgents(sessions);
        sessions.sort(function(a, b) { return (b.lastTimestamp || "0").localeCompare(a.lastTimestamp || "0"); });

        for (var i = 0; i < sessions.length; i++) {
          var s = sessions[i];
          s.status = scanner.getStatus(s.fileMtimeMs, s.lastMeaningfulTimestamp, s.lastMeaningfulStopReason);
          s.activity = scanner.getActivity(s.recentUserMsgs || 0);
          s.tokenHeat = scanner.getTokenHeat((s._itok || 0) + (s._otok || 0));
          s.cost = pricing.calcCost(s);
          s.type = "main";
          s.filePath = s._file;
          s.subAgents = [];
          delete s._file;
          delete s.fileMtimeMs;
          delete s._dirty;

          shared.subAgentCache.forEach(function(agent, key) {
            if (key.indexOf(s.id + "::") === 0) {
              agent.status = scanner.getStatus(agent.fileMtimeMs, agent.lastMeaningfulTimestamp, agent.lastMeaningfulStopReason);
              agent.cost = pricing.calcCost(agent);
              s.subAgents.push(agent);
            }
          });
        }

        res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify(sessions));
      });
      return true;
    }

    // API: flat grid of all agents (main + sub)
    if (req.url === "/api/agents") {
      scanner.scanSessions(shared.PROJECTS_DIR, []).then(function(allSessions) {
        agents.scanSubAgents(allSessions);
        var agentList = [];

        for (var i = 0; i < allSessions.length; i++) {
          var ms = allSessions[i];
          ms.status = scanner.getStatus(ms.fileMtimeMs, ms.lastMeaningfulTimestamp, ms.lastMeaningfulStopReason);
          ms.activity = scanner.getActivity(ms.recentUserMsgs || 0);
          ms.tokenHeat = scanner.getTokenHeat((ms._itok || 0) + (ms._otok || 0));
          ms.cost = pricing.calcCost(ms);
          ms.type = "main";
          delete ms._file;
          delete ms.fileMtimeMs;
          agentList.push(ms);

          shared.subAgentCache.forEach(function(agent, key) {
            if (key.indexOf(ms.id + "::") === 0) {
              agent.status = scanner.getStatus(agent.fileMtimeMs, agent.lastMeaningfulTimestamp, agent.lastMeaningfulStopReason);
              agent.cost = pricing.calcCost(agent);
              agentList.push(agent);
            }
          });
        }

        agentList.sort(function(a, b) {
          var sa = a.status === "running" ? 0 : 1;
          var sb = b.status === "running" ? 0 : 1;
          if (sa !== sb) return sa - sb;
          return (b.lastTimestamp || "0").localeCompare(a.lastTimestamp || "0");
        });

        res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
        res.end(JSON.stringify(agentList));
      });
      return true;
    }

    return false;
  };
}

module.exports = makeSessionsRouter;

```

### File: routes\snapshots.js
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
      if (!/^[a-zA-Z0-9_\-]+$/.test(snapId)) { res.writeHead(400); res.end(JSON.stringify({ error: "invalid snapshot id" })); return true; }
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
      if (!/^[a-zA-Z0-9_\-]+$/.test(delId)) { res.writeHead(400); res.end(JSON.stringify({ error: "invalid snapshot id" })); return true; }
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

### File: scanner.js
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
      if (!info.firstUserMsg && obj.message && obj.message.content && Array.isArray(obj.message.content)) {
        for (var j = 0; j < obj.message.content.length; j++) {
          if (obj.message.content[j].type === "text" && obj.message.content[j].text) {
            var t = obj.message.content[j].text.trim();
            if (t.indexOf("<ide_opened_file>") === -1 && !/^File (created|modified|deleted)/.test(t)) {
              info.firstUserMsg = t.slice(0, 500);
              break;
            }
          }
        }
      }
    }

    if (obj.type === "assistant") {
      info.assistantMsgCount++;
      if (obj.timestamp && new Date(obj.timestamp).getTime() > recentCutoff) info.recentMsgTotal++;
      if (obj.message && obj.message.stop_reason) info.lastStopReason = obj.message.stop_reason;
      if (obj.message && obj.message.usage) {
        info._itok += (obj.message.usage.input_tokens || 0);
        info._otok += (obj.message.usage.output_tokens || 0);
        info._ctok += (obj.message.usage.cache_read_input_tokens || 0);
      }
      if (!info.model && obj.message && obj.message.model) info.model = obj.message.model;

      if (obj.message && obj.message.content && Array.isArray(obj.message.content)) {
        for (var k = 0; k < obj.message.content.length; k++) {
          var block = obj.message.content[k];
          if (block.type === "tool_use") {
            info.toolCallCount++;
            var dec = { timestamp: obj.timestamp || null, tool: block.name || "unknown", input: block.input ? JSON.stringify(block.input).slice(0, 200) : "", type: "tool_call" };
            if (block.name === "write_to_file" || block.name === "write" || block.name === "Edit" || block.name === "Write") {
              info.fileWriteCount++;
              dec.type = "file_write";
            }
            info.keyDecisions.push(dec);
          }
        }
      }
    }

    if (obj.type === "user" || obj.type === "assistant") {
      info.lastMeaningfulTimestamp = obj.timestamp || info.lastMeaningfulTimestamp;
      if (obj.type === "assistant" && obj.message && obj.message.stop_reason) {
        info.lastMeaningfulStopReason = obj.message.stop_reason;
      } else if (obj.type === "user" && isNewUserMsg) {
        info.lastMeaningfulStopReason = null; // only genuine new user msg resets stop_reason
      }
    }
    info.lastEntryType = obj.type;
    if (obj.type === "system" && obj.subtype) info.lastEntrySubtype = obj.subtype;
    if (obj.timestamp) info.lastTimestamp = obj.timestamp;
  }

  if (startOffset === 0) {
    info.totalLines = lineCount;
    info.title = info.customTitle || info.aiTitle || (info.firstUserMsg ? info.firstUserMsg.slice(0, 80) : null) || "(无标题)";
  }
  return info;
}

// Merge incremental delta into cached session
function mergeSessionData(cached, delta) {
  if (!delta || !cached) return cached;
  cached.lastTimestamp = delta.lastTimestamp || cached.lastTimestamp;
  cached.lastStopReason = delta.lastStopReason || cached.lastStopReason;
  cached.lastEntryType = delta.lastEntryType || cached.lastEntryType;
  cached.lastEntrySubtype = delta.lastEntrySubtype || cached.lastEntrySubtype;
  cached.lastMeaningfulTimestamp = delta.lastMeaningfulTimestamp || cached.lastMeaningfulTimestamp;
  if (delta.lastMeaningfulStopReason !== undefined) cached.lastMeaningfulStopReason = delta.lastMeaningfulStopReason;
  cached._itok += (delta._itok || 0);
  cached._otok += (delta._otok || 0);
  cached._ctok += (delta._ctok || 0);
  cached.userMsgCount += (delta.userMsgCount || 0);
  cached.assistantMsgCount += (delta.assistantMsgCount || 0);
  cached.recentUserMsgs += (delta.recentUserMsgs || 0);
  cached.recentMsgTotal += (delta.recentMsgTotal || 0);
  cached.totalLines += (delta.totalLines || 0);
  if (delta._seenPromptIds) {
    if (!cached._seenPromptIds) cached._seenPromptIds = {};
    for (var pid2 in delta._seenPromptIds) {
      if (delta._seenPromptIds.hasOwnProperty(pid2)) cached._seenPromptIds[pid2] = true;
    }
  }
  cached.fileMtime = delta.fileMtime || cached.fileMtime;
  cached.fileMtimeMs = delta.fileMtimeMs || cached.fileMtimeMs;
  cached.fileSize = delta.fileSize || cached.fileSize;
  cached.toolCallCount += (delta.toolCallCount || 0);
  cached.fileWriteCount += (delta.fileWriteCount || 0);
  if (delta.model && !cached.model) cached.model = delta.model;
  if (delta.cwd && !cached.cwd) cached.cwd = delta.cwd;
  if (delta.title && delta.title !== "(无标题)") cached.title = delta.title;
  if (delta.aiTitle) { cached.aiTitle = delta.aiTitle; if (!cached.customTitle) cached.title = delta.aiTitle; }
  if (delta.customTitle) { cached.customTitle = delta.customTitle; cached.title = delta.customTitle; }
  if (delta.firstUserMsg && !cached.firstUserMsg) cached.firstUserMsg = delta.firstUserMsg;
  if (delta.keyDecisions && delta.keyDecisions.length > 0) {
    if (!cached.keyDecisions) cached.keyDecisions = [];
    cached.keyDecisions = cached.keyDecisions.concat(delta.keyDecisions);
    if (cached.keyDecisions.length > 100) cached.keyDecisions = cached.keyDecisions.slice(-100);
  }
  cached._dirty = true;
  return cached;
}

// ============ Async Session Scanning ============

async function dirExists(dirPath) {
  try { await fsp.access(dirPath); return true; } catch (e) { return false; }
}

async function scanSessions(dir, results, parentSessionId) {
  if (!results) results = [];
  if (!(await dirExists(dir))) return results;

  var entries;
  try { entries = await fsp.readdir(dir, { withFileTypes: true }); } catch (e) { return results; }

  for (var i = 0; i < entries.length; i++) {
    var full = path.join(dir, entries[i].name);
    var isAgent = entries[i].name.startsWith("agent-");

    if (entries[i].isDirectory() && entries[i].name !== "memory" && entries[i].name !== "subagents" && entries[i].name !== "tool-results" && !isAgent) {
      await scanSessions(full, results, parentSessionId);
    } else if (entries[i].isFile() && entries[i].name.endsWith(".jsonl") && !isAgent) {
      var sessionId = entries[i].name.replace(".jsonl", "");
      var cached = shared.sessionCache.get(sessionId);
      var offInfo = shared.fileOffsets.get(full);
      var info;

      if (cached && offInfo && offInfo.offset > 0) {
        var delta = parseSessionChunk(full, offInfo.offset, cached._seenPromptIds);
        if (delta) {
          if (delta._truncated) {
            // Truncated: full re-parse (still sync since parseSessionChunk uses sync APIs)
            info = parseSessionChunk(full, 0);
            if (info && info.id) {
              shared.fileOffsets.set(full, { offset: info.fileSize || 0, mtime: info.fileMtimeMs });
              shared.sessionCache.set(info.id, info);
            }
          } else {
            info = mergeSessionData(cached, delta);
            shared.fileOffsets.set(full, { offset: info.fileSize || 0, mtime: info.fileMtimeMs });
            shared.sessionCache.set(info.id, info);
          }
        } else {
          // No new data, use cached — but refresh fileMtimeMs from current stat
          info = cached;
          try {
            var st = await fsp.stat(full);
            info.fileMtimeMs = st.mtimeMs;
            info.fileSize = st.size;
          } catch (e) {}
        }
      } else {
        info = parseSessionChunk(full, 0);
        if (info && info.id) {
          shared.fileOffsets.set(full, { offset: info.fileSize || 0, mtime: info.fileMtimeMs });
          shared.sessionCache.set(info.id, info);
        }
      }

      if (info && info.id) {
        info._file = full;
        results.push(info);
      }
    }
  }
  return results;
}

module.exports = {
  getStatus: getStatus,
  getActivity: getActivity,
  getTokenHeat: getTokenHeat,
  parseLine: parseLine,
  parseSessionFull: parseSessionFull,
  parseSessionChunk: parseSessionChunk,
  mergeSessionData: mergeSessionData,
  scanSessions: scanSessions
};

```

### File: shared.js
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

### File: snapshot.js
```
var fs = require("fs");
var path = require("path");
var shared = require("./shared");

function loadSnapshotsFromDisk() {
  try {
    if (!fs.existsSync(shared.SNAPSHOTS_DIR)) { fs.mkdirSync(shared.SNAPSHOTS_DIR, { recursive: true }); return; }
    var files = fs.readdirSync(shared.SNAPSHOTS_DIR).filter(function(f) { return f.endsWith(".json"); }).sort();
    shared.snapshotList = [];
    for (var i = 0; i < files.length; i++) {
      try {
        var data = JSON.parse(fs.readFileSync(path.join(shared.SNAPSHOTS_DIR, files[i]), "utf-8"));
        shared.snapshotList.push({ id: files[i].replace(".json", ""), file: files[i], data: data, timestamp: data.timestamp || "" });
      } catch (e) { /* skip corrupt */ }
    }
  } catch (e) { console.error("[CC面板] loadSnapshots:", e.message); }
}

function saveSnapshot(id, sessions) {
  var timestamp = new Date().toISOString();
  var snapshot = {
    id: id, timestamp: timestamp, sessionCount: sessions.length,
    sessions: sessions.map(function(s) {
      return {
        id: s.id, title: s.title, status: s.status, activity: s.activity, tokenHeat: s.tokenHeat,
        _itok: s._itok || 0, _otok: s._otok || 0, model: s.model,
        lastTimestamp: s.lastTimestamp, fileMtime: s.fileMtime,
        lastStopReason: s.lastStopReason, userMsgCount: s.userMsgCount,
        assistantMsgCount: s.assistantMsgCount, cwd: s.cwd,
        keyDecisions: (s.keyDecisions || []).slice(-20)
      };
    })
  };

  var filePath = path.join(shared.SNAPSHOTS_DIR, id + ".json");
  try {
    fs.writeFileSync(filePath, JSON.stringify(snapshot, null, 2), "utf-8");
    shared.snapshotList.push({ id: id, file: id + ".json", data: snapshot, timestamp: timestamp });
    // Keep max 30 auto-snapshots
    var autos = shared.snapshotList.filter(function(s) { return s.id.indexOf("auto-") === 0; });
    if (autos.length > 30) {
      autos.sort(function(a, b) { return a.timestamp.localeCompare(b.timestamp); });
      var toDel = autos.slice(0, autos.length - 30);
      for (var d = 0; d < toDel.length; d++) {
        try { fs.unlinkSync(path.join(shared.SNAPSHOTS_DIR, toDel[d].id + ".json")); } catch (e) {}
        shared.snapshotList = shared.snapshotList.filter(function(s) { return s.id !== toDel[d].id; });
      }
    }
    return snapshot;
  } catch (e) { return null; }
}

function deleteSnapshot(id) {
  try { fs.unlinkSync(path.join(shared.SNAPSHOTS_DIR, id + ".json")); } catch (e) {}
  shared.snapshotList = shared.snapshotList.filter(function(s) { return s.id !== id; });
}

module.exports = {
  loadSnapshotsFromDisk: loadSnapshotsFromDisk,
  saveSnapshot: saveSnapshot,
  deleteSnapshot: deleteSnapshot
};

```

### File: sse.js
```
var shared = require("./shared");

function broadcastSSE(data) {
  if (shared.sseClients.length === 0) return;
  var msg = "data: " + JSON.stringify(data) + "\n\n";
  var dead = [];
  for (var i = 0; i < shared.sseClients.length; i++) {
    try { shared.sseClients[i].write(msg); } catch (e) { dead.push(i); }
  }
  for (var j = dead.length - 1; j >= 0; j--) {
    shared.sseClients.splice(dead[j], 1);
  }
}

function addSSEClient(res) {
  if (shared.sseClients.length >= shared.SSE_MAX_CLIENTS) {
    try { shared.sseClients.shift().end(); } catch (e) {}
  }
  shared.sseClients.push(res);
}

function removeSSEClient(res) {
  var idx = shared.sseClients.indexOf(res);
  if (idx >= 0) shared.sseClients.splice(idx, 1);
}

function handleSSE(req, res) {
  if (req.url !== "/api/events") return false;
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no"
  });
  res.write(": connected\n\n");
  addSSEClient(res);
  var keepalive = setInterval(function() {
    try { res.write(": hb\n\n"); } catch (e) { clearInterval(keepalive); removeSSEClient(res); }
  }, 15000);
  req.on("close", function() { clearInterval(keepalive); removeSSEClient(res); });
  return true;
}

function cleanupSSE() {
  for (var i = 0; i < shared.sseClients.length; i++) {
    try { shared.sseClients[i].end(); } catch (e) {}
  }
  shared.sseClients.length = 0;
}

module.exports = {
  broadcastSSE: broadcastSSE,
  addSSEClient: addSSEClient,
  removeSSEClient: removeSSEClient,
  handleSSE: handleSSE,
  cleanupSSE: cleanupSSE
};

```

### File: watcher.js
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

# 审查规则
# Claude-BugHunter — Usage Guide

A practical guide to using the 51-skill Claude-BugHunter bundle for bug hunting (bounty programs, authorized pentesting, CTFs, vuln research) **and external red-team engagements** against enterprise targets. This document covers what's in the bundle, how it composes, and how to use it on a real engagement from intake through paid bounty (or final client deliverable).

> Built and validated through authorized red-team and bug-bounty engagements — exposed four bug-bounty capability gaps and five additional gaps around platform attack chains, mid-engagement IR detection, and client-facing reporting. The final stack documented here addresses both modes.

---

## 0. Brand new? Start here

This section is for people who have **never used the bundle before, never used Claude Code, or never done bug hunting**. If you're already comfortable with any of those, skim to Section 1.

### What is this bundle, in plain English?

It's a collection of 51 markdown files (called **skills**) that turn Claude Code into a methodical bug-hunting assistant.

Without the bundle, asking Claude *"is this XSS?"* gets you a generic answer. With the bundle installed, the same question loads the `hunt-xss` skill — which contains specific detection patterns from 574+ disclosed reports, the exact payloads that have worked, and a validation gate that prevents you from filing a false-positive bug report.

You don't "learn" the bundle. You install it once, then describe what you're testing in plain English, and the relevant skill auto-loads. You read it together with Claude and follow the steps.

### What you DO need before starting

1. **A laptop running macOS or Linux** (Windows users: WSL2 Ubuntu works).
2. **Claude Code installed** (from https://claude.ai/download) — this is the CLI app, not Claude.ai in your browser.
3. **A Claude paid plan** (Pro/Team/Max) or an Anthropic API key with credit. Free Claude.ai doesn't include Claude Code.
4. **The terminal app open** and the willingness to copy-paste 3 commands.
5. **A target you're authorized to test** — meaning either: (a) you own it, (b) it's on a bug bounty program's in-scope list, (c) you have a signed pentest engagement letter, or (d) it's a deliberately-vulnerable practice site (OWASP Juice Shop, Vulnweb, HackTheBox, etc.).

### What you DON'T need

- ❌ You don't need to know how to write exploits. The skills include working payloads.
- ❌ You don't need to know Burp Suite. It's optional. Skills work with curl + browser.
- ❌ You don't need a bug bounty account yet. You can practice on OWASP Juice Shop first.
- ❌ You don't need to read all 51 skills. They auto-load when relevant.
- ❌ You don't need Python beyond `python3 --version` working.

### Your first 30 minutes

Open your terminal. Copy-paste this entire block:

```bash
# 1. Get the bundle
mkdir -p ~/security-research && cd ~/security-research
git clone https://github.com/elementalsouls/Claude-BugHunter.git
cd Claude-BugHunter

# 2. In

# 输出格式要求
你必须严格按照以下 JSON Schema 输出审查结果。**只输出 JSON，不要输出任何 JSON 以外的文本。**

```json
{
  "agent_id": "B",
  "skill": "Claude-BugHunter",
  "philosophy": "你是'攻击者思维'的安全审计专家。你审查代码时的默认假设是：有恶意攻击者会仔细阅读这段代码，寻找任何可能的突破口。你不是...",
  "review_scope": {
    "files": ["文件路径列表"],
    "lines_total": 0
  },
  "findings": [
    {
      "id": "B-001",
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
      "file": "文件路径",
      "line": 0,
      "comment": "值得称赞的代码实践"
    }
  ]
}
```

# 审查要求
1. 只报告你**高度确信**的问题。置信度 < 0.7 的发现不要输出。
2. 每个发现必须包含**具体的修复建议**，不能只说"这里有问题"。
3. 优先报告安全漏洞和功能正确性问题，其次才是风格问题。
4. 如果代码中有值得称赞的实践，请在 `praise` 数组中提及。
5. **严格遵守 JSON 格式**，不要输出任何 JSON 以外的文本。
6. Finding ID 格式为 `B-{3位序号}`，从 001 开始连续编号。
7. severity 使用各技能原生等级体系。
8. category 必须是以下之一：security | bug | performance | correctness | maintainability。
