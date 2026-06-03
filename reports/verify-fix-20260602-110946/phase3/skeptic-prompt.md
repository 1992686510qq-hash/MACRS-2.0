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

### M-018 - launchSessionDirect calls undefined function spawnWithBat — will throw ReferenceError
- Severity: P0 BLOCKING
- File: server/routes/open.js lines [172, 208]
- Description: N/A
- Suggestion: Replace the call to `spawnWithBat` with `spawnDirect` which is the correctly defined function in this file:

```javascript
// Line 203: change from
spawnWithBat(claudeExe, cliArgs, configFile, cwd || "C:\\Users\\Administrator");
// to
spawnDirect(claudeExe, cliArgs, configFile, cwd || "C:\\Users\\Ad

Source code context:
```
(file not found)
```
### M-016 - Path Traversal in /api/create-and-open via unsanitized configName parameter
- Severity: P0 BLOCKING
- File: server/index.js lines [100, 107]
- Description: N/A
- Suggestion: Add strict validation for configName before using it in any path construction. Validate that the resolved path is within the expected directory:

```javascript
var configName = urlObj.searchParams.get('config');
if (!configName || !/^setting-[a-zA-Z0-9_-]+\.json$/.test(configName)) {
  res.writeHead

Source code context:
```
(file not found)
```
### M-017 - Path Traversal in swapSettingsJson allows arbitrary file read and settings.json overwrite
- Severity: P0 BLOCKING
- File: server/routes/open.js lines [150, 168]
- Description: N/A
- Suggestion: Validate that `configFile` resolves to a path within the expected `.claude` directory before reading:

```javascript
function swapSettingsJson(configFile) {
  if (!configFile) return;
  // Strict whitelist validation
  if (!/^setting-[a-zA-Z0-9_-]+\.json$/.test(configFile)) {
    console.error('[ope

Source code context:
```
(file not found)
```
### M-001 - settings.json 并发写入竞态条件，多会话启动会互相覆盖
- Severity: P0 BLOCKING
- File: routes\open.js lines [204, 215]
- Description: N/A
- Suggestion: 引入写入锁或引用计数机制。用一个 Map 记录当前活跃的配置写入请求，只有最后一个请求完成且无新请求时才恢复原始配置。或者改用 per-session settings 路径（通过 --settings 参数传递），避免修改全局 settings.json。

Source code context:
```
var path = require("path");
var fs = require("fs");
var shared = require("../shared");
var scanner = require("../scanner");

// NOTE: 不再需要 settings.json 快照——所有启动路径都通过 --settings CLI 参数注入配置，不修改默认 settings.json

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

  var cliArgs = ["--resume", batId];
  if (configFile) {
    cliArgs.push("--settings", path.join(homeDir, ".claude", configFile));
  }

  spawnDirect(claudeExe, cliArgs, configFile, batCwd || undefined);

  res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify({ ok: true }));
}

function launchSession(target, openId, res) {
  var cwd = target && target.cwd ? target.cwd : (target && target._file ? path.dirname(target._file) : "");
  var result = { ok: false, actions: [] };
  var npmBin = process.env.APPDATA ? path.join(process.env.APPDATA, "npm") : null;
  var claudeExe = npmBin ? path.join(npmBin, "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe") : "claude";
  var child_process = require("child_process");
  var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";

  var configFile = shared.sessionConfigMap.get(openId);

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
      var child3 = child_process.spawn("cmd", ["/c", "start", "
```
### M-023 - settings.json restore references undefined ORIGINAL_SETTINGS — restore never executes
- Severity: P1 CRITICAL
- File: server/routes/open.js lines [181, 194]
- Description: N/A
- Suggestion: Either restore the ORIGINAL_SETTINGS snapshot mechanism, or remove the dead restore code entirely and document that settings.json is permanently modified. If the intent is to not modify settings.json, then `swapSettingsJson` should not be called at all:

```javascript
// Option A: Remove the broken 

Source code context:
```
(file not found)
```
### M-028 - XSS漏洞：未转义的用户数据直接注入HTML
- Severity: P0 BLOCKING
- File: index.js lines [54, 63]
- Description: N/A
- Suggestion: 使用DOM API动态创建元素，或至少对JSON字符串进行HTML实体转义后再嵌入。建议将HTML移至独立模板文件，使用安全的模板引擎。

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
      res.end('<!DOCTYPE html><html><head><meta charset="utf-8"><title>迁移 localStorage 3100→5022</title><style>body{font-family:system-ui;max-width:500px;margin:80px auto;padding:20px;background:#0b0f14;color:#e0e0e0;text-align:center}h2{color:#ff6b35}.btn{display:inline-block;padding:14px 36px;background:#ff6b35;color:#fff;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:700;margin:16px 8px}.btn:hover{opacity:0.85}.ok{color:#4caf50}.err{color:#f44336}.info{font-size:13px;color:#888;margin-top:24px}#log{margin-top:16px;font-size:13px;color:#aaa}</style></head><body><h2>localStorage 迁移</h2><p>从 <code>localhost:3100</code> 迁移到 <code>localhost:5022</code></p><p><button class="btn" onclick="doMigrate()">开始迁移</button></p><div id="log"></div><p class="info">迁移完成后<a href="/">返回面板</a></p><script>function log(m,c){var d=document.getElementById("log");d.innerHTML+=m+"<br>";if(c)d.style.color=c}function doMigrate(){log("正在从 3100 读取…");var ifr=document.createElement("iframe");ifr.style.display="none";ifr.src="http://localhost:3100/";ifr.onload=function(){setTimeout(function(){try{var raw=ifr.contentDocument.body.textContent;var data=JSON.parse(raw);var keys=Object.keys(data);log("读取到 "+keys.length+" 个键");var ok=0,fail=0;for(var i=0;i<keys.length;i++){try{localStorage.setItem(keys[i],data[keys[i]]);ok++}catch(e){fail++;log(keys[i]+" 写入失败: "+e.message,"#f44336")}}log("迁移完成: "+ok+" 成功, "+fail+" 失败","#4caf50");log("3秒后跳转面板…");setTimeout(function(){location.href="/"},3000)}catch(e){log("读取失败，请确认 3100 端口的旧面板正在运行。错误: "+e.message,"#f44336")}},500)};docume
```
### M-007 - pLines 变量在 try 块内定义，phase detection 代码在 try 块外引用可能 undefined
- Severity: P1 CRITICAL
- File: routes\session.js lines [155, 175]
- Description: N/A
- Suggestion: 将 pLines 的声明提升到 try 块之前（var pLines = []），或在后续使用前检查 pLines 是否已定义。更好的方案是将文件读取结果通过函数返回值传递，而非依赖闭包变量。

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
### M-004 - delete s._file 污染 sessionCache，后续请求无法定位会话文件
- Severity: P1 CRITICAL
- File: routes\sessions.js lines [18, 30]
- Description: N/A
- Suggestion: 在序列化响应前，创建 session 对象的浅拷贝再删除内部字段：var out = Object.assign({}, s); delete out._file; delete out._dirty; 或使用 map 创建新对象数组。

Source code context:
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
### M-002 - Math.random() 生成 session ID，可预测且存在碰撞风险
- Severity: P1 CRITICAL
- File: index.js lines [110, 120]
- Description: N/A
- Suggestion: 使用 crypto.randomUUID()（Node.js 14.17+）或 crypto.randomBytes() 替代 Math.random()。对于 sessionId 这种需要全局唯一的标识符，可预测性是安全隐患。

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
      res.end('<!DOCTYPE html><html><head><meta charset="utf-8"><title>迁移 localStorage 3100→5022</title><style>body{font-family:system-ui;max-width:500px;margin:80px auto;padding:20px;background:#0b0f14;color:#e0e0e0;text-align:center}h2{color:#ff6b35}.btn{display:inline-block;padding:14px 36px;background:#ff6b35;color:#fff;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:700;margin:16px 8px}.btn:hover{opacity:0.85}.ok{color:#4caf50}.err{color:#f44336}.info{font-size:13px;color:#888;margin-top:24px}#log{margin-top:16px;font-size:13px;color:#aaa}</style></head><body><h2>localStorage 迁移</h2><p>从 <code>localhost:3100</code> 迁移到 <code>localhost:5022</code></p><p><button class="btn" onclick="doMigrate()">开始迁移</button></p><div id="log"></div><p class="info">迁移完成后<a href="/">返回面板</a></p><script>function log(m,c){var d=document.getElementById("log");d.innerHTML+=m+"<br>";if(c)d.style.color=c}function doMigrate(){log("正在从 3100 读取…");var ifr=document.createElement("iframe");ifr.style.display="none";ifr.src="http://localhost:3100/";ifr.onload=function(){setTimeout(function(){try{var raw=ifr.contentDocument.body.textContent;var data=JSON.parse(raw);var keys=Object.keys(data);log("读取到 "+keys.length+" 个键");var ok=0,fail=0;for(var i=0;i<keys.length;i++){try{localStorage.setItem(keys[i],data[keys[i]]);ok++}catch(e){fail++;log(keys[i]+" 写入失败: "+e.message,"#f44336")}}log("迁移完成: "+ok+" 成功, "+fail+" 失败","#4caf50");log("3秒后跳转面板…");setTimeout(function(){location.href="/"},3000)}catch(e){log("读取失败，请确认 3100 端口的旧面板正在运行。错误: "+e.message,"#f44336")}},500)};docume
```
### M-020 - No authentication — any local process can access all API endpoints
- Severity: P1 CRITICAL
- File: server/index.js lines [21, 25]
- Description: N/A
- Suggestion: Add at minimum a shared secret token authentication:

```javascript
var API_TOKEN = process.env.CC_PANEL_TOKEN || require('crypto').randomBytes(32).toString('hex');
console.log('[CC-Panel] API Token: ' + API_TOKEN);

var server = http.createServer(function(req, res) {
  // Skip auth for static asset

Source code context:
```
(file not found)
```
### M-030 - God Function反模式：单个请求处理函数承担过多职责
- Severity: P1 CRITICAL
- File: index.js lines [127, 155]
- Description: N/A
- Suggestion: 将路由分发重构为中间件模式，每个路由模块自行注册。HTML模板移至独立文件，使用express或koa等框架简化路由管理。

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
      res.end('<!DOCTYPE html><html><head><meta charset="utf-8"><title>迁移 localStorage 3100→5022</title><style>body{font-family:system-ui;max-width:500px;margin:80px auto;padding:20px;background:#0b0f14;color:#e0e0e0;text-align:center}h2{color:#ff6b35}.btn{display:inline-block;padding:14px 36px;background:#ff6b35;color:#fff;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:700;margin:16px 8px}.btn:hover{opacity:0.85}.ok{color:#4caf50}.err{color:#f44336}.info{font-size:13px;color:#888;margin-top:24px}#log{margin-top:16px;font-size:13px;color:#aaa}</style></head><body><h2>localStorage 迁移</h2><p>从 <code>localhost:3100</code> 迁移到 <code>localhost:5022</code></p><p><button class="btn" onclick="doMigrate()">开始迁移</button></p><div id="log"></div><p class="info">迁移完成后<a href="/">返回面板</a></p><script>function log(m,c){var d=document.getElementById("log");d.innerHTML+=m+"<br>";if(c)d.style.color=c}function doMigrate(){log("正在从 3100 读取…");var ifr=document.createElement("iframe");ifr.style.display="none";ifr.src="http://localhost:3100/";ifr.onload=function(){setTimeout(function(){try{var raw=ifr.contentDocument.body.textContent;var data=JSON.parse(raw);var keys=Object.keys(data);log("读取到 "+keys.length+" 个键");var ok=0,fail=0;for(var i=0;i<keys.length;i++){try{localStorage.setItem(keys[i],data[keys[i]]);ok++}catch(e){fail++;log(keys[i]+" 写入失败: "+e.message,"#f44336")}}log("迁移完成: "+ok+" 成功, "+fail+" 失败","#4caf50");log("3秒后跳转面板…");setTimeout(function(){location.href="/"},3000)}catch(e){log("读取失败，请确认 3100 端口的旧面板正在运行。错误: "+e.message,"#f44336")}},500)};docume
```
### M-006 - buildRelationsResponse 函数 220+ 行，混合了图构建、阶段检测、瀑布流计算三个独立关注点
- Severity: P1 CRITICAL
- File: routes\session.js lines [95, 320]
- Description: N/A
- Suggestion: 拆分为三个独立函数：buildGraphNodes(target) → detectPhases(edges, userMessages) → buildWaterfall(pLines)。将魔法数字提取为命名常量并添加注释。避免重复读取文件——将 pLines 作为参数传递。

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
### M-005 - parseSessionChunk 函数 110+ 行，承担了 JSONL 解析、token 统计、消息提取等 5 项职责
- Severity: P1 CRITICAL
- File: scanner.js lines [90, 200]
- Description: N/A
- Suggestion: 拆分为：readFileChunk(offset) → parseLines(content) → extractMetadata(entries) → accumulateTokens(entries) → extractDecisions(entries)。每个函数可以独立测试，主函数变为管道式调用。

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
### M-022 - Information Disclosure — full filesystem paths exposed in API responses
- Severity: P1 CRITICAL
- File: server/routes/session.js lines [104, 104]
- Description: N/A
- Suggestion: Strip the filesystem path from API responses, or return only a relative/basename:

```javascript
// Instead of:
filePath: fpath
// Use:
filePath: path.basename(fpath)
// Or remove entirely if not needed by the frontend
```

Source code context:
```
(file not found)
```
### M-032 - 阻塞I/O：请求处理路径中使用同步文件操作
- Severity: P1 CRITICAL
- File: scanner.js lines [95, 130]
- Description: N/A
- Suggestion: 将parseSessionChunk改为async函数，使用fs.promises.readFile。对于大文件，实现流式解析（逐行读取），避免一次性加载到内存。

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
### M-003 - /import-localstorage 路由通过字符串拼接注入用户数据到 HTML，存在 XSS 风险
- Severity: P1 CRITICAL
- File: index.js lines [48, 70]
- Description: N/A
- Suggestion: 1. 将数据通过独立 API 端点返回 JSON，前端 fetch 获取后再写入 localStorage，避免将数据内嵌到 HTML。2. 添加至少 localhost 限制或简单的 token 认证。3. 如果必须内嵌，使用 CSP nonce 保护 script 标签。

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
      res.end('<!DOCTYPE html><html><head><meta charset="utf-8"><title>迁移 localStorage 3100→5022</title><style>body{font-family:system-ui;max-width:500px;margin:80px auto;padding:20px;background:#0b0f14;color:#e0e0e0;text-align:center}h2{color:#ff6b35}.btn{display:inline-block;padding:14px 36px;background:#ff6b35;color:#fff;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:700;margin:16px 8px}.btn:hover{opacity:0.85}.ok{color:#4caf50}.err{color:#f44336}.info{font-size:13px;color:#888;margin-top:24px}#log{margin-top:16px;font-size:13px;color:#aaa}</style></head><body><h2>localStorage 迁移</h2><p>从 <code>localhost:3100</code> 迁移到 <code>localhost:5022</code></p><p><button class="btn" onclick="doMigrate()">开始迁移</button></p><div id="log"></div><p class="info">迁移完成后<a href="/">返回面板</a></p><script>function log(m,c){var d=document.getElementById("log");d.innerHTML+=m+"<br>";if(c)d.style.color=c}function doMigrate(){log("正在从 3100 读取…");var ifr=document.createElement("iframe");ifr.style.display="none";ifr.src="http://localhost:3100/";ifr.onload=function(){setTimeout(function(){try{var raw=ifr.contentDocument.body.textContent;var data=JSON.parse(raw);var keys=Object.keys(data);log("读取到 "+keys.length+" 个键");var ok=0,fail=0;for(var i=0;i<keys.length;i++){try{localStorage.setItem(keys[i],data[keys[i]]);ok++}catch(e){fail++;log(keys[i]+" 写入失败: "+e.message,"#f44336")}}log("迁移完成: "+ok+" 成功, "+fail+" 失败","#4caf50");log("3秒后跳转面板…");setTimeout(function(){location.href="/"},3000)}catch(e){log("读取失败，请确认 3100 端口的旧面板正在运行。错误: "+e.message,"#f44336")}},500)};docume
```
### M-008 - subAgentCache.forEach 遍历全部缓存只为筛选属于当前 session 的 agent，O(n×m) 复杂度
- Severity: P1 CRITICAL
- File: routes\sessions.js lines [28, 40]
- Description: N/A
- Suggestion: 改用嵌套 Map 结构：subAgentCache = Map<sessionId, Map<agentId, agentInfo>>，按 sessionId 直接索引，避免全量遍历。或者在 scanSubAgents 时建立 sessionId → agentIds 的反向索引。

Source code context:
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
### M-021 - XSS in /import-localstorage — JSON content injected into HTML without escaping
- Severity: P1 CRITICAL
- File: server/index.js lines [38, 40]
- Description: N/A
- Suggestion: HTML-encode the JSON data before embedding in the HTML response, or use a safer injection method:

```javascript
var importData = fs.readFileSync(importFile, 'utf8');
// Validate it's safe JSON, then HTML-encode for embedding
var safeData = importData
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;

Source code context:
```
(file not found)
```
### M-031 - 全局可变状态：shared模块作为隐式依赖注入
- Severity: P1 CRITICAL
- File: shared.js lines [20, 45]
- Description: N/A
- Suggestion: 引入依赖注入模式，将shared重构为Context类，通过构造函数传入各模块。或至少将状态分为独立的Store类（SessionStore, EventBus等）。

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
### M-034 - 竞态条件：settings.json的写入-读取-恢复存在并发风险
- Severity: P1 CRITICAL
- File: routes/open.js lines [140, 170]
- Description: N/A
- Suggestion: 使用文件锁（proper-lockfile）或引入请求级别的配置覆盖机制（通过--settings参数传递，不修改全局文件）。

Source code context:
```
var path = require("path");
var fs = require("fs");
var shared = require("../shared");
var scanner = require("../scanner");

// NOTE: 不再需要 settings.json 快照——所有启动路径都通过 --settings CLI 参数注入配置，不修改默认 settings.json

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

  var cliArgs = ["--resume", batId];
  if (configFile) {
    cliArgs.push("--settings", path.join(homeDir, ".claude", configFile));
  }

  spawnDirect(claudeExe, cliArgs, configFile, batCwd || undefined);

  res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify({ ok: true }));
}

function launchSession(target, openId, res) {
  var cwd = target && target.cwd ? target.cwd : (target && target._file ? path.dirname(target._file) : "");
  var result = { ok: false, actions: [] };
  var npmBin = process.env.APPDATA ? path.join(process.env.APPDATA, "npm") : null;
  var claudeExe = npmBin ? path.join(npmBin, "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe") : "claude";
  var child_process = require("child_process");
  var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";

  var configFile = shared.sessionConfigMap.get(openId);

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
      var child3 = child_process.spawn("cmd", ["/c", "start", "
```
### M-009 - fakePid 用 Math.random 生成 6 位数，碰撞概率不可忽略
- Severity: P1 CRITICAL
- File: index.js lines [174, 182]
- Description: N/A
- Suggestion: 使用递增计数器（从一个随机起始值开始）或直接用 sessionId 作为文件名而非 PID。如果必须用 PID，使用 crypto.randomInt() 并检查文件是否已存在。

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
      res.end('<!DOCTYPE html><html><head><meta charset="utf-8"><title>迁移 localStorage 3100→5022</title><style>body{font-family:system-ui;max-width:500px;margin:80px auto;padding:20px;background:#0b0f14;color:#e0e0e0;text-align:center}h2{color:#ff6b35}.btn{display:inline-block;padding:14px 36px;background:#ff6b35;color:#fff;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:700;margin:16px 8px}.btn:hover{opacity:0.85}.ok{color:#4caf50}.err{color:#f44336}.info{font-size:13px;color:#888;margin-top:24px}#log{margin-top:16px;font-size:13px;color:#aaa}</style></head><body><h2>localStorage 迁移</h2><p>从 <code>localhost:3100</code> 迁移到 <code>localhost:5022</code></p><p><button class="btn" onclick="doMigrate()">开始迁移</button></p><div id="log"></div><p class="info">迁移完成后<a href="/">返回面板</a></p><script>function log(m,c){var d=document.getElementById("log");d.innerHTML+=m+"<br>";if(c)d.style.color=c}function doMigrate(){log("正在从 3100 读取…");var ifr=document.createElement("iframe");ifr.style.display="none";ifr.src="http://localhost:3100/";ifr.onload=function(){setTimeout(function(){try{var raw=ifr.contentDocument.body.textContent;var data=JSON.parse(raw);var keys=Object.keys(data);log("读取到 "+keys.length+" 个键");var ok=0,fail=0;for(var i=0;i<keys.length;i++){try{localStorage.setItem(keys[i],data[keys[i]]);ok++}catch(e){fail++;log(keys[i]+" 写入失败: "+e.message,"#f44336")}}log("迁移完成: "+ok+" 成功, "+fail+" 失败","#4caf50");log("3秒后跳转面板…");setTimeout(function(){location.href="/"},3000)}catch(e){log("读取失败，请确认 3100 端口的旧面板正在运行。错误: "+e.message,"#f44336")}},500)};docume
```
### M-019 - No session ID validation on /api/terminal-bat/ and /api/open-session/ endpoints
- Severity: P1 CRITICAL
- File: server/routes/open.js lines [11, 37]
- Description: N/A
- Suggestion: Add UUID format validation before processing:

```javascript
if (req.url.startsWith('/api/terminal-bat/') && req.method === 'GET') {
  var batId = decodeURI(req.url.split('/api/terminal-bat/')[1]);
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(batId)) {
    res.writeH

Source code context:
```
(file not found)
```
### M-029 - 命令注入风险：用户输入直接拼接到bat文件命令
- Severity: P0 BLOCKING
- File: routes/open.js lines [75, 95]
- Description: N/A
- Suggestion: 对configFile进行严格白名单验证（只允许字母数字和连字符），或使用child_process.execFile直接传递参数而非写入bat文件。

Source code context:
```
var path = require("path");
var fs = require("fs");
var shared = require("../shared");
var scanner = require("../scanner");

// NOTE: 不再需要 settings.json 快照——所有启动路径都通过 --settings CLI 参数注入配置，不修改默认 settings.json

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

  var cliArgs = ["--resume", batId];
  if (configFile) {
    cliArgs.push("--settings", path.join(homeDir, ".claude", configFile));
  }

  spawnDirect(claudeExe, cliArgs, configFile, batCwd || undefined);

  res.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  res.end(JSON.stringify({ ok: true }));
}

function launchSession(target, openId, res) {
  var cwd = target && target.cwd ? target.cwd : (target && target._file ? path.dirname(target._file) : "");
  var result = { ok: false, actions: [] };
  var npmBin = process.env.APPDATA ? path.join(process.env.APPDATA, "npm") : null;
  var claudeExe = npmBin ? path.join(npmBin, "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe") : "claude";
  var child_process = require("child_process");
  var homeDir = process.env.HOME || process.env.USERPROFILE || "C:\\Users\\Administrator";

  var configFile = shared.sessionConfigMap.get(openId);

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
      var child3 = child_process.spawn("cmd", ["/c", "start", "
```
### M-033 - CORS配置过宽：允许任意localhost端口
- Severity: P1 CRITICAL
- File: index.js lines [102, 107]
- Description: N/A
- Suggestion: 将CORS origin限制为面板自身端口（http://localhost:5022），或通过环境变量配置允许的origin列表。

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
      res.end('<!DOCTYPE html><html><head><meta charset="utf-8"><title>迁移 localStorage 3100→5022</title><style>body{font-family:system-ui;max-width:500px;margin:80px auto;padding:20px;background:#0b0f14;color:#e0e0e0;text-align:center}h2{color:#ff6b35}.btn{display:inline-block;padding:14px 36px;background:#ff6b35;color:#fff;border:none;border-radius:10px;font-size:16px;cursor:pointer;font-weight:700;margin:16px 8px}.btn:hover{opacity:0.85}.ok{color:#4caf50}.err{color:#f44336}.info{font-size:13px;color:#888;margin-top:24px}#log{margin-top:16px;font-size:13px;color:#aaa}</style></head><body><h2>localStorage 迁移</h2><p>从 <code>localhost:3100</code> 迁移到 <code>localhost:5022</code></p><p><button class="btn" onclick="doMigrate()">开始迁移</button></p><div id="log"></div><p class="info">迁移完成后<a href="/">返回面板</a></p><script>function log(m,c){var d=document.getElementById("log");d.innerHTML+=m+"<br>";if(c)d.style.color=c}function doMigrate(){log("正在从 3100 读取…");var ifr=document.createElement("iframe");ifr.style.display="none";ifr.src="http://localhost:3100/";ifr.onload=function(){setTimeout(function(){try{var raw=ifr.contentDocument.body.textContent;var data=JSON.parse(raw);var keys=Object.keys(data);log("读取到 "+keys.length+" 个键");var ok=0,fail=0;for(var i=0;i<keys.length;i++){try{localStorage.setItem(keys[i],data[keys[i]]);ok++}catch(e){fail++;log(keys[i]+" 写入失败: "+e.message,"#f44336")}}log("迁移完成: "+ok+" 成功, "+fail+" 失败","#4caf50");log("3秒后跳转面板…");setTimeout(function(){location.href="/"},3000)}catch(e){log("读取失败，请确认 3100 端口的旧面板正在运行。错误: "+e.message,"#f44336")}},500)};docume
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