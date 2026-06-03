# 角色
你是一名资深代码审查专家，正在对一份代码进行系统性的代码审查。
你的审查哲学：你是'架构防腐'的代码审查专家。你不只关心单行代码的对错，更关心这段代码 在整个系统架构中的位置和长期影响。你的核心理念来自：The Pragmatic Programmer、Clean Code、Clean Architecture。你审查时的核心问题是：'这段代码会加速还是延缓系统的技术债务累积？'

# 你的身份
你是 MACRS（多智能体对抗式代码审查系统）中的 **Agent C - Architecture Reviewer**。
你的技能来源：pragmatic-clean-code-reviewer

# 审查范围
目标路径：D:\CC项目\00\ccl-launcher.js

审查文件列表 (1 个文件, 1532 行):
  - D:\CC项目\00\ccl-launcher.js

---

### File: D:\CC项目\00\ccl-launcher.js
```
(function() {
  var p = require("path"),
    f = require("fs"),
    o = require("os"),
    c = require("child_process"),
    h = p.join(o.homedir(), ".claude"),
    d = p.join(h, "node_modules"),
    b = p.join(d, "blessed", "package.json");
  if (!f.existsSync(b)) {
    f.mkdirSync(h, {
      recursive: !0
    });
    var pj = p.join(h, "package.json");
    if (!f.existsSync(pj)) f.writeFileSync(pj, "{}");
    console.log("\x1b[36m\u9996\u6b21\u8fd0\u884c\uff0c\u6b63\u5728\u5b89\u88c5 TUI \u4f9d\u8d56...\x1b[0m");
    try {
      c.execSync("npm install blessed --no-package-lock", {
        cwd: h,
        stdio: "pipe",
        timeout: 6e4
      })
    } catch (e) {
      console.error("\x1b[31m\u4f9d\u8d56\u5b89\u88c5\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u7f51\u7edc\u8fde\u63a5: " +
        e.message + "\x1b[0m");
      process.exit(1)
    }
  }
  module.paths.unshift(d)
})();
"use strict";
var Pt = Object.create;
var Pe = Object.defineProperty;
var Nt = Object.getOwnPropertyDescriptor;
var It = Object.getOwnPropertyNames;
var Lt = Object.getPrototypeOf,
  jt = Object.prototype.hasOwnProperty;
var Ft = (e, t, n, o) => {
  if (t && typeof t == "object" || typeof t == "function")
    for (let r of It(t)) !jt.call(e, r) && r !== n && Pe(e, r, {
      get: () => t[r],
      enumerable: !(o = Nt(t, r)) || o.enumerable
    });
  return e
};
var m = (e, t, n) => (n = e != null ? Pt(Lt(e)) : {}, Ft(t || !e || !e.__esModule ? Pe(n, "default", {
  value: e,
  enumerable: !0
}) : n, e));
var bt = require("child_process");
var T = m(require("fs")),
  ye = m(require("path")),
  Ie = m(require("os"));
var Ne = "https://ai.cnfan.vip";
var $t = {
    models: [],
    defaultModel: "",
    projects: [],
    defaultPermission: "bypassPermissions",
    theme: "green"
  },
  _e = ye.join(Ie.homedir(), ".claude"),
  te = ye.join(_e, "claude-launcher-config.json"),
  u;

function Le() {
  if (T.mkdirSync(_e, {
      recursive: !0
    }), !T.existsSync(te)) {
    u = JSON.parse(JSON.stringify($t)), _();
    return
  }
  let e = T.readFileSync(te, "utf-8").replace(/^\uFEFF/, "");
  u = JSON.parse(e), Array.isArray(u.models) || (u.models = []), u.defaultModel || (u.defaultModel = u.models.length >
    0 ? u.models[0].id : ""), Array.isArray(u.projects) || (u.projects = []), u.defaultPermission || (u
    .defaultPermission = "bypassPermissions"), (!u.theme || u.theme === "default") && (u.theme = "green"), _()
}

function a() {
  return u
}

function b() {
  return _e
}
var _traceStep = 0;
function _trace(e, t) {
  _traceStep++;
  var n = m(require("fs")), o = m(require("path")), r = o.join(_e, "ccl-trace.log");
  try {
    var s = new Date().toISOString().slice(11, 23);
    n.appendFileSync(r, `[${s}] #${_traceStep} [${e}] ${t}
`)
  } catch {}
}

function Se() {
  return u.models.length > 0
}

function _() {
  try {
    let e = te + ".tmp." + process.pid;
    T.writeFileSync(e, JSON.stringify(u, null, 2)), T.renameSync(e, te)
  } catch (e) {
    try {
      T.unlinkSync(te + ".tmp." + process.pid)
    } catch {}
    console.error("\u914D\u7F6E\u4FDD\u5B58\u5931\u8D25:", e.message)
  }
}

function G() {
  let e = [...u.models],
    t = u.defaultModel;
  if (t) {
    let n = e.findIndex(o => o.id === t);
    if (n > -1) {
      let [o] = e.splice(n, 1);
      e.unshift(o)
    }
  }
  return e
}

function q() {
  return [...u.projects].sort((e, t) => t.weight - e.weight)
}

function je(e) {
  return u.models.find(t => t.id === e)
}

function ie() {
  return process.env.CCL_AGENT_BASE || u.agentBase || Ne
}
var ce = [],
  ae = "",
  ne = 0,
  Ae = {};

function R() {
  return ae
}

function xe() {
  return ne
}

function Fe(e) {
  ne = e
}

function pe(e, t = 0) {
  ae = e, ne = t
}

function $e(e, t = 0) {
  ce.push({
    screen: ae,
    option: ne
  }), pe(e, t)
}

function Re() {
  if (ce.length === 0) return;
  let e = ce.pop();
  ae = e.screen, ne = e.screen === "main" ? 0 : e.option
}

function Rt() {
  ce = []
}

function oe() {
  Rt(), pe("main"), Ae = {}
}

function N(e, t) {
  Ae[e] = t
}

function O(e) {
  return Ae[e] || ""
}
var ke = m(require("blessed/lib/widgets/screen")),
  le = m(require("blessed/lib/widgets/box")),
  He = m(require("blessed/lib/widgets/list")),
  Ue = m(require("blessed/lib/widgets/textbox")),
  g, F, f, D, S, P, Y = null,
  V = null,
  k = null;

function j() {
  g.render(), setImmediate(() => {
    process.stdout.write("\x1B[?25l")
  })
}

function Be() {
  g = new ke.default({
    smartCSR: !0,
    fullUnicode: !0,
    forceUnicode: !0
  }), F = new le.default({
    top: 0,
    left: 0,
    width: "100%",
    height: 3,
    tags: !0,
    scrollable: !1
  }), f = new He.default({
    top: 3,
    left: 0,
    width: "100%",
    keys: !1,
    vi: !1,
    mouse: !1,
    tags: !0,
    scrollable: !0,
    alwaysScroll: !0,
    style: {
      selected: {
        fg: "green",
        bold: !0
      },
      item: {}
    },
    padding: {
      left: 1,
      right: 1
    }
  }), D = new le.default({
    top: 3,
    left: 0,
    width: "100%",
    height: 1,
    tags: !0
  }), P = new le.default({
    top: 3,
    left: 1,
    width: 3,
    height: 1,
    content: "{cyan-fg}> {/cyan-fg}",
    tags: !0
  }), S = new Ue.default({
    top: 3,
    left: 3,
    width: "80%",
    height: 1,
    inputOnFocus: !0,
    style: {
      fg: "cyan"
    }
  }), g.append(F), g.append(f), g.append(D), g.append(P), g.append(S), P.hide(), S.hide(), f.on("select", (e, t) => Y
    ?.(t)), f.on("cancel", () => V?.()), f.on("select item", (e, t) => k?.(t)), f.key(["up"], () => {
    let e = f.selected,
      t = f.items;
    if (t.length <= 1) return;
    let n = e <= 0 ? t.length - 1 : e - 1;
    f.select(n), k?.(n), j()
  }), f.key(["down"], () => {
    let e = f.selected,
      t = f.items;
    if (t.length <= 1) return;
    let n = e >= t.length - 1 ? 0 : e + 1;
    f.select(n), k?.(n), j()
  }), f.key(["enter", "space", "right"], () => {
    Y?.(f.selected)
  }), f.key(["escape", "q", "left"], () => {
    V?.()
  }), g.key(["C-c"], () => {
    g.destroy(), process.exit(0)
  }), j()
}

function Ke(e, t, n, o, r) {
  F.setContent(e.join(`
`)), F.height = e.length, f.top = t, S.top = t, P.top = t, D.top = e.length + n + 1, D.setContent(
    `{${r}-fg}${o}{/${r}-fg}`)
}

function we(e) {
  let {
    title: t,
    options: n,
    selected: o,
    footer: r,
    themeFg: s,
    tip: i,
    tipOverride: c,
    summaryLines: d,
    emptyMsg: l
  } = e, p = ["", `{${s}-fg}{bold}=== ${t} ==={/bold}{/${s}-fg}`];
  c ? p.push("", `{red-fg}  ${c}{/red-fg}`) : i && p.push("", `{#ffde81-fg}  ${i}{/#ffde81-fg}`), d?.length && p.push(
    "", `{${s}-fg}\u2500\u2500 \u5DF2\u9009\u62E9 \u2500\u2500{/${s}-fg}`, ...d), p.push("");
  let w;
  l && n.length === 0 ? (f.setItems([`{yellow-fg}${l}{/yellow-fg}`, "",
    `{${s}-fg}\u6309\u56DE\u8F66\u952E\u8FD4\u56DE...{/${s}-fg}`
  ]), w = 3) : (f.setItems(n), f.select(o), w = n.length), f.height = w, f.style.selected = {
    fg: s,
    bold: !0
  }, Ke(p, p.length, w, r, s), f.show(), P.hide(), S.hide(), f.focus(), j()
}

function ve(e, t, n, o, r) {
  return new Promise(s => {
    let i = Y,
      c = V,
      d = k,
      l = () => {
        Y = i, V = c, k = d
      };
    Y = p => {
      l(), s(p)
    }, V = () => {
      l(), s(null)
    }, r && (k = r), we({
      title: e,
      options: t,
      selected: 0,
      footer: o ||
        "\u4F7F\u7528\u65B9\u5411\u952E\u5BFC\u822A\uFF0C\u56DE\u8F66\u9009\u62E9\uFF0CESC\u9000\u51FA",
      themeFg: n
    })
  })
}

function Je(e, t) {
  D.setContent(`{${t}-fg}${e}{/${t}-fg}`), j()
}

function Ge(e) {
  f.style.selected = {
    fg: e,
    bold: !0
  }, D.setContent(D.getContent().replace(/\{[^}]+-fg\}/g, `{${e}-fg}`)), j()
}

function H(e, t, n, o) {
  return new Promise(r => {
    f.hide();
    let s = ["", `{${n}-fg}{bold}=== ${e} ==={/bold}{/${n}-fg}`, t],
      i = s.length;
    Ke(s, i, 1, o ||
        "\u4F7F\u7528\u65B9\u5411\u952E\u5BFC\u822A\uFF0C\u56DE\u8F66\u9009\u62E9\uFF0CESC\u9000\u51FA", n), P.top =
      i, S.top = i, P.show(), S.show(), S.clearValue(), g.render(), S.focus();
    let c = () => {
        P.hide(), S.hide(), S.removeListener("submit", d), S.removeListener("cancel", l)
      },
      d = p => {
        c(), r((p || "").trim())
      },
      l = () => {
        c(), r(null)
      };
    S.once("submit", d), S.once("cancel", l)
  })
}

function E(e, t, n) {
  return new Promise(o => {
    f.hide(), P.hide(), S.hide();
    let s = ["", `{${n}-fg}{bold}=== ${e} ==={/bold}{/${n}-fg}`, "", t, ""].join(`
`),
      i = s.split(`
`).length;
    F.setContent(s), F.height = i, D.top = i + 1, D.setContent(
      `{${n}-fg}\u4F7F\u7528\u65B9\u5411\u952E\u5BFC\u822A\uFF0C\u56DE\u8F66\u9009\u62E9\uFF0CESC\u9000\u51FA{/${n}-fg}`
      ), j();
    let c = !1,
      d = () => {
        c || (c = !0, g.unkey("enter", l), g.unkey("escape", p), g.unkey("space", l), g.unkey("right", l), g.unkey(
          "left", p))
      },
      l = () => {
        d(), o(!0)
      },
      p = () => {
        d(), o(!1)
      };
    g.key("enter", l), g.key("escape", p), g.key("space", l), g.key("right", l), g.key("left", p)
  })
}

function qe(e) {
  Y = e
}

function Ye(e) {
  V = e
}

function Ve(e) {
  k = e
}

function fe(e, t, n) {
  f.hide(), P.hide(), S.hide();
  let r = ["", `{${n}-fg}{bold}=== ${e} ==={/bold}{/${n}-fg}`, "", t, ""].join(`
`),
    s = r.split(`
`).length;
  F.setContent(r), F.height = s, D.top = s + 1, D.setContent(""), j()
}

function se() {
  if (g.destroy(), process.stdin.isTTY) {
    try {
      process.stdin.setRawMode(!0)
    } catch {}
    process.stdin.setEncoding("utf8"), process.stdin.removeAllListeners("data"), process.stdin.removeAllListeners(
      "readable"), process.stdin.resume();
    let e = Date.now() + 100;
    for (; Date.now() < e;) process.stdin.read();
    try {
      process.stdin.setRawMode(!1)
    } catch {}
    process.stdin.pause()
  }
  process.stdout.write("\x1B[?1049l\x1B[?1000l\x1B[?1002l\x1B[?1003l\x1B[?1006l\x1B[?25h\x1B[0m")
}
var We = {
    green: {
      title: "green",
      selected: "green"
    },
    cyan: {
      title: "cyan",
      selected: "cyan"
    },
    magenta: {
      title: "magenta",
      selected: "magenta"
    },
    yellow: {
      title: "yellow",
      selected: "yellow"
    }
  },
  W = ["green", "cyan", "magenta", "yellow"],
  Ze = ["\u7ECF\u5178\u7EFF", "\u5929\u9752", "\u661F\u7D2B", "\u6696\u91D1"];

function I(e) {
  return We[e] || We.green
}
var ze = m(require("http")),
  Qe = m(require("https")),
  Z = m(require("fs")),
  Xe = m(require("path")),
  et = m(require("os"));
var Te = Xe.join(et.homedir(), ".claude", ".ccl.config"),
  tt = "";

function de() {
  try {
    return JSON.parse(Z.readFileSync(Te, "utf-8"))
  } catch {
    return null
  }
}

function Oe(e) {
  try {
    let t = Te + ".tmp." + process.pid;
    Z.writeFileSync(t, JSON.stringify(e, null, 2)), Z.renameSync(t, Te)
  } catch {}
}

function nt(e) {
  let t = new Date(e).getTime();
  return Math.floor((Date.now() - t) / 864e5)
}

function ot() {
  let e = `${ie()}/api/ccl/tips?_t=${Date.now()}`,
    n = (e.startsWith("https") ? Qe.get : ze.get)(e, o => {
      let r = "";
      o.on("data", s => {
        r += s
      }), o.on("end", () => {
        try {
          let s = JSON.parse(r);
          if (!s) return;
          let i = s.force_update === !0,
            c = s.enabled === !0;
          if (i) {
            let p = de();
            p?.tips?.current_index !== void 0 && (s.tips.current_index = p.tips.current_index), Oe(s);
            return
          }
          if (!c) return;
          let d = de();
          if (d?.tips?.fetched_at) {
            let p = d.tips.protect_days || 7;
            if (nt(d.tips.fetched_at) < p) return
          }
          if (d?.tips?.version && d.tips.version === s.tips?.version) return;
          let l = de();
          l?.tips?.current_index !== void 0 && (s.tips.current_index = l.tips.current_index), Oe(s)
        } catch {}
      })
    });
  n.setTimeout(5e3, () => {
    n.destroy()
  }), n.on("error", () => {})
}

function st() {
  let e = de();
  if (!e?.tips) return;
  if (e.tips.fetched_at) {
    let o = e.tips.protect_days || 7;
    if (nt(e.tips.fetched_at) >= o) return
  }
  let t = e.tips.items;
  if (!Array.isArray(t) || t.length === 0) return;
  let n = e.tips.current_index || 0;
  n = (n + 1) % t.length, e.tips.current_index = n, Oe(e), tt = t[n] || ""
}

function rt() {
  return tt
}
var me = m(require("child_process")),
  it = m(require("path"));

function Dt(e, t) {
  var K = m(require("fs")), Q = m(require("path"));
  let n = 0;
  try {
    let o = K.readdirSync(b());
    o.forEach(r => {
      let s = r.match(/^setting-c(\d+)\.json$/);
      s && (n = Math.max(n, parseInt(s[1], 10)))
    })
  } catch {}
  let i = `setting-c${n + 1}.json`,
    o = Q.join(b(), e),
    d = Q.join(b(), i);
  if (K.existsSync(o)) {
    let r = K.readFileSync(o, "utf-8"),
      s = d + ".tmp." + process.pid;
    K.writeFileSync(s, r), K.renameSync(s, d)
  }
  if (t) {
    let r = "{}";
    if (K.existsSync(d)) try { r = K.readFileSync(d, "utf-8") } catch {}
    let s = JSON.parse(r);
    s._ccl_meta = t;
    let c = d + ".tmp." + process.pid;
    K.writeFileSync(c, JSON.stringify(s, null, 2)), K.renameSync(c, d)
  }
  let l = Q.join(b(), ".ccl-launch-log.json"),
    c = [];
  try { c = JSON.parse(K.readFileSync(l, "utf-8")) } catch {}
  c.push({ time: new Date().toISOString(), model: e, created: i });
  let u = l + ".tmp." + process.pid;
  K.writeFileSync(u, JSON.stringify(c, null, 2)), K.renameSync(u, l);
  return i
}
function Ht() {
  let e = a(),
    t = O("launch_model_id") || e.defaultModel,
    n = e.models.find(l => l.id === t),
    o = O("project_path"),
    r = O("skip_permission") || e.defaultPermission,
    i = {
      yes: "bypassPermissions",
      auto: "auto",
      ask: "default",
      plan: "plan",
      bypassPermissions: "bypassPermissions",
      acceptEdits: "acceptEdits",
      default: "default",
      dontAsk: "dontAsk"
    } [r] || "bypassPermissions",
    c = ["claude"];
  let s = n?.configFile,
    reuse = O("reuse_settings");
  if (reuse) {
    c.push("--settings", it.join(b(), reuse)), s = reuse;
    var q = O("session_uuid");
    q ? c.push("--resume", q) : c.push("--continue")
  } else if (n?.configFile) {
    let d = Dt(n.configFile, { launched_by: "CCL", launched_at: new Date().toISOString(), model_name: n.name, model_id: t, template: n.configFile, project: o });
    s = d, c.push("--settings", it.join(b(), d))
  }
  if (s) {
    var K = m(require("fs")), Q = m(require("path"));
    if (!reuse) {
      var v = Q.join(b(), ".ccl-sessions.json"), M = [];
      try { M = JSON.parse(K.readFileSync(v, "utf-8")) } catch {}
      M.push({ time: new Date().toISOString(), project: o || "", modelId: t, modelName: n?.name || "",
        settingsFile: s, sessionName: O("session_name") || "" });
      var w = v + ".tmp." + process.pid;
      K.writeFileSync(w, JSON.stringify(M, null, 2)), K.renameSync(w, v)
    }
    if (o && !reuse) try {
      var CCL_MD = Q.join(o, "CLAUDE.local.md");
      var CCL_EXIST = "";
      try { CCL_EXIST = K.readFileSync(CCL_MD, "utf-8") } catch {}
      var CCL_TAG = "\n\n## CCL Session";
      var CCL_TAG_IDX = CCL_EXIST.indexOf(CCL_TAG);
      if (CCL_TAG_IDX !== -1) CCL_EXIST = CCL_EXIST.slice(0, CCL_TAG_IDX);
      CCL_EXIST += "\n\n## CCL Session\n\n- 启动方式: CCL\n- 启动时间: " + new Date().toISOString() + "\n- 模型: " + (n?.name || "") + " (" + (n?.id || "") + ")\n- 配置文件: " + s + "\n- 模板: " + (n?.configFile || "") + "\n";
      K.writeFileSync(CCL_MD, CCL_EXIST, "utf-8");
    } catch (e) {}
  }
  return i === "auto" && c.push("--enable-auto-mode"), process.platform !== "win32" && typeof process.getuid == "function" && process.getuid() === 0 ? c
    .push("--permission-mode", "acceptEdits") : c.push("--permission-mode", i), o && c.push(o), c
}

function ct() {
  let e = Ht(),
    t = e.shift(),
    n = O("project_path"),
    i = O("reuse_settings");
  var q = Date.now();
  if (process.platform === "win32") {
    let o = {
      stdio: "inherit",
      shell: !0
    };
    n && (o.cwd = n), process.stdin.isTTY && process.stdin.setRawMode(!1);
    let r = me.spawnSync(t, e, o);
    if (!i) Zt(q, n);
    process.stdout.write("\x1B[?1049l\x1B[?25h\x1B[0m"), process.exit(r.status ?? 1)
  } else {
    process.stdin.isTTY && process.stdin.setRawMode(!1);
    let o = [t, ...e].map(d => "'" + d.replace(/'/g, "'\\''") + "'").join(" "),
      s =
      "stty sane < /dev/tty 2>/dev/null; stty echo icanon isig < /dev/tty 2>/dev/null; printf '\\033[?1049l\\033[?25h\\033[0m' > /dev/tty 2>/dev/null; clear; " +
      (n ? "cd '" + n.replace(/'/g, "'\\''") + "'; " : "") + "exec " + o;
    try {
      me.execFileSync("/bin/sh", ["-c", s], {
        stdio: "inherit"
      }), !i && Zt(q, n), process.exit(0)
    } catch (d) {
      !i && Zt(q, n), process.exit(d.status ?? 1)
    }
  }
}

function Zt(e, t) {
  var n = m(require("fs")), i = m(require("path")), o = i.join(b(), "projects"), r = "", s = 0;
  try {
    var a = t ? n.readdirSync(o).filter(function(c) {
      var d = t.replace(/[^a-zA-Z0-9]/g, "-");
      return c === d || c.indexOf(d) !== -1
    }) : n.readdirSync(o);
    a.forEach(function(c) {
      var d = i.join(o, c);
      try {
        n.readdirSync(d).forEach(function(u) {
          if (!u.endsWith(".jsonl")) return;
          var l = n.statSync(i.join(d, u));
          if (l.mtimeMs > e && l.mtimeMs > s) s = l.mtimeMs, r = u.replace(".jsonl", "")
        })
      } catch {}
    })
  } catch {}
  if (r) {
    var u = i.join(b(), ".ccl-sessions.json"), p = [];
    try { p = JSON.parse(n.readFileSync(u, "utf-8")) } catch {}
    if (p.length > 0) {
      p[p.length - 1].uuid = r;
      var f = u + ".tmp." + process.pid;
      n.writeFileSync(f, JSON.stringify(p, null, 2)), n.renameSync(f, u)
    }
  }
}
var Ct = m(require("path"));
var at = {
  title: "Claude \u542F\u52A8\u5668",
  showTip: !0,
  footer: "\u4F7F\u7528\u65B9\u5411\u952E\u5BFC\u822A\uFF0C\u56DE\u8F66\u9009\u62E9\uFF0CESC\u9000\u51FA",
  getOptions() {
    return ["\u4F7F\u7528 Claude", "\u6DFB\u52A0\u9879\u76EE", "\u79FB\u9664\u9879\u76EE",
      "\u65B0\u5EFA\u914D\u7F6E", "\u5220\u9664\u914D\u7F6E", "\u4F1A\u8BDD\u7BA1\u7406", "\u9000\u51FA"
    ]
  },
  onSelect(e) {
    switch (e) {
      case 0:
        return {
          type: "push", screen: "project"
        };
      case 1:
        return {
          type: "flow", name: "add_project"
        };
      case 2:
        return {
          type: "push", screen: "remove_project"
        };
      case 3:
        return {
          type: "flow", name: "add_model"
        };
      case 4:
        return {
          type: "push", screen: "remove_model"
        };
      case 5:
        return {
          type: "push", screen: "sessions"
        };
      case 6:
        return {
          type: "exit"
        };
      default:
        return {
          type: "none"
        }
    }
  },
  onCancel() {
    return {
      type: "exit"
    }
  }
};
var Me = m(require("fs")),
  pt = m(require("path")),
  lt = {
    title: "\u9009\u62E9\u9879\u76EE",
    showSummary: !1,
    getOptions() {
      let t = q().map(n => Me.existsSync(n.path) ? n.path : `${n.path} [\u76EE\u5F55\u4E0D\u5B58\u5728]`);
      return t.push("\u5F53\u524D\u76EE\u5F55"), t
    },
    onSelect(e) {
      let t = q(),
        n;
      if (e === t.length) n = process.cwd();
      else {
        let o = t[e];
        if (!o) return {
          type: "none"
        };
        if (!Me.existsSync(o.path)) return {
          type: "home",
          tip: `\u9879\u76EE\u76EE\u5F55\u4E0D\u5B58\u5728: ${o.path}
\u8BF7\u4F7F\u7528\u300C\u79FB\u9664\u9879\u76EE\u300D\u529F\u80FD\u5220\u9664\u65E0\u6548\u76EE\u5F55`
        };
        n = pt.resolve(o.path), a().projects.forEach(s => {
          s.path === n ? s.weight += 2 : s.weight > 10 && (s.weight -= 1)
        }), _()
      }
      return N("project_path", n), {
        type: "push",
        screen: "model"
      }
    },
    onCancel() {
      return N("project_path", ""), {
        type: "pop"
      }
    }
  };
var be = [{
  label: "\u8DF3\u8FC7\u6240\u6709\u6743\u9650\u786E\u8BA4",
  value: "bypassPermissions"
}, {
  label: "\u5371\u9669\u64CD\u4F5C\u9700\u786E\u8BA4",
  value: "auto"
}, {
  label: "\u81EA\u52A8\u63A5\u53D7\u7F16\u8F91",
  value: "acceptEdits"
}];

function ft() {
  let e = O("skip_permission") || a().defaultPermission;
  return be.findIndex(t => t.value === e)
}
var dt = {
  title: "\u6743\u9650\u786E\u8BA4",
  showSummary: !0,
  getOptions() {
    return be.map(e => e.label)
  },
  onSelect(e) {
    return N("skip_permission", be[e]?.value || "bypassPermissions"), {
      type: "flow",
      name: "name_session"
    }
  },
  onCancel() {
    return {
      type: "pop"
    }
  }
};
var mt = {
  title: "\u9009\u62E9\u914D\u7F6E",
  getOptions() {
    return G().map(e => `${e.name} (${e.id})`)
  },
  onSelect(e) {
    let t = G();
    if (!t[e]) return { type: "none" };
    var n = ce.length > 0 ? ce[ce.length - 1].screen : "";
    _trace("MODEL", `select=${e} model=${t[e]?.id} prevScreen=${n} stack=${JSON.stringify(ce.map(x=>x.screen))}`);
    if (n === "session_action") {
      var r = O("selected_session");
      var logPath = Wt.join(b(), ".ccl-sessions.json");
      var sessions = [];
      try { sessions = JSON.parse(Qt.readFileSync(logPath, "utf-8")) } catch {}
      var idx = parseInt(r);
      var session = sessions[idx];
      if (session && t[e]) {
        var srcCfg = Wt.join(b(), t[e].configFile);
        var dstCfg = Wt.join(b(), session.settingsFile);
        if (Qt.existsSync(srcCfg)) {
          var content = Qt.readFileSync(srcCfg, "utf-8");
          var cfgJson = JSON.parse(content);
          var oldMeta = {};
          if (Qt.existsSync(dstCfg)) try { var oldCfg = JSON.parse(Qt.readFileSync(dstCfg, "utf-8")); oldMeta = oldCfg._ccl_meta || {} } catch {}
          var history = oldMeta.model_history || [];
          history.push({ model_name: oldMeta.model_name || session.modelName, model_id: oldMeta.model_id || session.modelId, changed_at: new Date().toISOString() });
          cfgJson._ccl_meta = { launched_by: "CCL", launched_at: oldMeta.launched_at || session.time, model_name: t[e].name, model_id: t[e].id, template: t[e].configFile, project: session.project, model_history: history };
          var tmpDst = dstCfg + ".tmp." + process.pid;
          Qt.writeFileSync(tmpDst, JSON.stringify(cfgJson, null, 2));
          Qt.renameSync(tmpDst, dstCfg);
          session.modelId = t[e].id;
          session.modelName = t[e].name;
          var tmpLog = logPath + ".tmp." + process.pid;
          Qt.writeFileSync(tmpLog, JSON.stringify(sessions, null, 2));
          Qt.renameSync(tmpLog, logPath);
          if (session.project) try {
            var cclMdPath = Wt.join(session.project, "CLAUDE.local.md");
            var cclMdExist = "";
            try { cclMdExist = Qt.readFileSync(cclMdPath, "utf-8") } catch {}
            var cclTag = "\n\n## CCL Session";
            var tagIdx = cclMdExist.indexOf(cclTag);
            if (tagIdx !== -1) cclMdExist = cclMdExist.slice(0, tagIdx);
            cclMdExist += "\n\n## CCL Session\n\n- 启动方式: CCL\n- 启动时间: " + (oldMeta.launched_at || session.time) + "\n- 模型: " + t[e].name + " (" + t[e].id + ")\n- 配置文件: " + session.settingsFile + "\n- 模板: " + t[e].configFile + "\n- 模型变更记录: " + history.length + " 次\n";
            Qt.writeFileSync(cclMdPath, cclMdExist, "utf-8");
          } catch (ee) {}
        }
      }
      _trace("MODEL_CHANGE", `session=${idx} newModel=${t[e]?.id} config=${session?.settingsFile}`);
      return { type: "pop" };
    }
    if (n === "project") {
      N("launch_model_id", t[e].id);
      return { type: "push", screen: "permission" };
    }
    return a().defaultModel = t[e].id, _(), {
      type: "home"
    }
  },
  onCancel() {
    var n = ce.length > 0 ? ce[ce.length - 1].screen : "";
    if (n === "session_action" || n === "project") {
      return { type: "pop" };
    }
    return { type: "home" }
  }
};

var Qt = m(require("fs")), Wt = m(require("path"));
function _strWidth(e) {
  var t = 0;
  for (var n = 0; n < e.length; n++) {
    var r = e.charCodeAt(n);
    t += (r >= 0x4e00 && r <= 0x9fff) || (r >= 0x3000 && r <= 0x303f) || (r >= 0xff00 && r <= 0xffef) ? 2 : 1
  }
  return t
}
function Xt(e, t) {
  var n = (e || "").replace(/\s+/g, " ").trim();
  var r = _strWidth(n);
  if (r > t) {
    for (var i = n.length - 1; i >= 0; i--) {
      n = n.slice(0, i);
      if (_strWidth(n + "…") <= t) return n + "…"
    }
    return ""
  }
  return n + " ".repeat(t - r)
}
var sessions_screen = {
  title: "会话管理",
  emptyMsg: "还没有创建过会话，请先使用 Claude",
  getOptions() {
    var logPath = Wt.join(b(), ".ccl-sessions.json");
    var sessions = [];
    try { sessions = JSON.parse(Qt.readFileSync(logPath, "utf-8")) } catch {}
    if (sessions.length === 0) return [];
    return sessions.map((s, i) => {
      var d = new Date(s.time);
      var ts = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2,
        "0") + " " + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
      var nm = Xt(s.sessionName || "", 18);
      var md = Xt(s.modelName || "", 10);
      var sf = Xt(s.settingsFile || "", 18);
      var pj = s.project || "当前目录";
      return `[${ts}]  ${nm}${md}${sf}${pj}`;
    })
  },
  onSelect(e) {
    N("selected_session", e);
    return { type: "push", screen: "session_action" };
  },
  onCancel() {
    return { type: "home" }
  }
};
var session_action_screen = {
  title: "会话操作",
  getOptions() {
    return ["更改模型", "重新打开", "编辑配置", "删除记录"]
  },
  onSelect(e) {
    var logPath = Wt.join(b(), ".ccl-sessions.json");
    var sessions = [];
    try { sessions = JSON.parse(Qt.readFileSync(logPath, "utf-8")) } catch {}
    var idx = O("selected_session");
    var session = sessions[idx];
    if (!session) return { type: "home" };
    if (e === 0) {
      _trace("SESSION_ACTION", `change_model session=${idx} currentModel=${session.modelId} settingsFile=${session.settingsFile}`);
      N("selected_session", idx);
      return { type: "push", screen: "model" };
    }
    if (e === 1) {
      _trace("SESSION_ACTION", `reopen session=${idx} uuid=${session.uuid} model=${session.modelId}`);
      N("launch_model_id", session.modelId);
      N("project_path", session.project || "");
      N("reuse_settings", session.settingsFile);
      N("session_uuid", session.uuid || "");
      N("skip_permission", "bypassPermissions");
      N("session_name", session.sessionName || "");
      return { type: "launch" };
    }
    if (e === 2) {
      var cfgPath = Wt.join(b(), session.settingsFile);
      if (process.platform === "win32") {
        me.exec('start "" "' + cfgPath + '"', () => {})
      } else {
        me.exec('${EDITOR:-vi} "' + cfgPath + '"', () => {})
      }
      return { type: "pop" }
    }
    if (e === 3) {
      sessions.splice(idx, 1);
      var tmpPath = logPath + ".tmp." + process.pid;
      Qt.writeFileSync(tmpPath, JSON.stringify(sessions, null, 2));
      Qt.renameSync(tmpPath, logPath);
      return { type: "pop" }
    }
    return { type: "pop" }
  },
  onCancel() {
    return { type: "pop" }
  }
};
function ut() {
  let e = a().theme,
    t = W.indexOf(e);
  return t >= 0 ? t : 0
}
var gt = {
  title: "\u9009\u62E9\u4E3B\u9898",
  getOptions() {
    return Ze
  },
  onSelect(e) {
    let t = W[e] || "green";
    return a().theme = t, _(), {
      type: "home"
    }
  },
  onCancel() {
    return {
      type: "home"
    }
  }
};
var ht = m(require("fs")),
  yt = {
    title: "\u79FB\u9664\u9879\u76EE\u76EE\u5F55",
    emptyMsg: "\u8FD8\u6CA1\u6709\u6DFB\u52A0\u4EFB\u4F55\u9879\u76EE\u76EE\u5F55",
    getOptions() {
      return q().map(e => ht.existsSync(e.path) ? e.path : `${e.path} [\u76EE\u5F55\u4E0D\u5B58\u5728]`)
    },
    onSelect(e) {
      let n = q()[e];
      return n ? (N("remove_index", n.path), {
        type: "push",
        screen: "confirm_remove"
      }) : {
        type: "home"
      }
    },
    onCancel() {
      return {
        type: "home"
      }
    }
  };
var _t = {
  title: "\u786E\u8BA4\u79FB\u9664",
  getOptions() {
    return ["\u662F\uFF0C\u79FB\u9664\u5B83", "\u5426\uFF0C\u53D6\u6D88"]
  },
  onSelect(e) {
    if (e === 0) {
      let t = O("remove_index"),
        n = a().projects.findIndex(o => o.path === t);
      n >= 0 && (a().projects.splice(n, 1), _())
    }
    return {
      type: "home"
    }
  },
  onCancel() {
    return {
      type: "home"
    }
  }
};
var St = {
  title: "\u5220\u9664\u914D\u7F6E",
  emptyMsg: "\u6CA1\u6709\u53EF\u5220\u9664\u7684\u914D\u7F6E",
  getOptions() {
    return G().map(e => `${e.name} (${e.id})`)
  },
  onSelect(e) {
    let t = G();
    if (a().models.length <= 1) return {
      type: "home",
      tip: "\u81F3\u5C11\u9700\u8981\u4FDD\u7559\u4E00\u4E2A\u914D\u7F6E\u3002"
    };
    let n = t[e];
    return n ? n.id === a().defaultModel ? {
      type: "home",
      tip: `\u300C${n.id}\u300D\u662F\u5F53\u524D\u9ED8\u8BA4\u914D\u7F6E\uFF0C\u8BF7\u5148\u5207\u6362\u9ED8\u8BA4\u914D\u7F6E\u518D\u5220\u9664\u3002`
    } : (N("remove_model_index", n.id), {
      type: "push",
      screen: "confirm_remove_model"
    }) : {
      type: "home"
    }
  },
  onCancel() {
    return {
      type: "home"
    }
  }
};
var At = m(require("fs")),
  xt = m(require("path")),
  wt = {
    title: "\u786E\u8BA4\u5220\u9664\u914D\u7F6E",
    getOptions() {
      return ["\u662F\uFF0C\u5220\u9664\u5B83", "\u5426\uFF0C\u53D6\u6D88"]
    },
    onSelect(e) {
      if (e === 0) {
        let t = O("remove_model_index"),
          n = je(t);
        if (n) {
          if (n.configFile && n.configFile !== "settings.json") {
            let r = xt.join(b(), n.configFile);
            try {
              At.unlinkSync(r)
            } catch {}
          }
          let o = a().models.findIndex(r => r.id === n.id);
          if (o >= 0) return a().models.splice(o, 1), _(), {
            type: "home",
            tip: `\u914D\u7F6E\u300C${n.id}\u300D\u5DF2\u5220\u9664`,
            delay: !0
          }
        }
      }
      return {
        type: "home"
      }
    },
    onCancel() {
      return {
        type: "home"
      }
    }
  };
var z = m(require("fs")),
  ue = m(require("path"));
async function vt() {
  let e = I(a().theme).selected,
    sProjectBase = "D:\\CC\u9879\u76EE";
  let oName = await H("\u65B0\u5EFA\u9879\u76EE",
    "{cyan-fg}\u8BF7\u8F93\u5165\u9879\u76EE\u540D\u79F0\uFF08\u5982 myproject\uFF09:{/cyan-fg}", e);
  if (oName === null || !oName.trim()) return;
  let sName = oName.trim();
  let sPath = ue.join(sProjectBase, sName);
  if (z.existsSync(sPath)) {
    await E("\u9519\u8BEF", `{red-fg}\u9879\u76EE\u76EE\u5F55\u5DF2\u5B58\u5728: ${sPath}{/red-fg}`, e);
    return
  }
  try {
    z.mkdirSync(sPath, { recursive: true });
    z.mkdirSync(ue.join(sPath, ".claude"), { recursive: true });
    z.writeFileSync(ue.join(sPath, "CLAUDE.md"),
      `# ${sName}\n\n\u5728\u8FD9\u91CC\u5199\u4F60\u7684\u9879\u76EE\u89C4\u5219\u548C\u8BF4\u660E\uFF0C\u6BCF\u6B21 Claude Code \u542F\u52A8\u65F6\u4F1A\u81EA\u52A8\u8BFB\u53D6\u3002\n`);
    z.writeFileSync(ue.join(sPath, "CLAUDE.local.md"),
      `# \u79C1\u4EBA\u5DE5\u4F5C\u53F0 - ${sName}\n\n\u8FD9\u4E2A\u6587\u4EF6\u4E0D\u4F1A\u63D0\u4EA4\u5230 git\uFF0C\u53EA\u6709\u4F60\u81EA\u5DF1\u770B\u5230\u3002\n\u653E\u4F60\u7684\u4E2A\u4EBA\u504F\u597D\u548C\u4E34\u65F6\u7B14\u8BB0\u3002\n`);
    z.writeFileSync(ue.join(sPath, ".claude", "settings.json"), "{}\n");
  } catch (err) {
    await E("\u9519\u8BEF", `{red-fg}\u521B\u5EFA\u9879\u76EE\u5931\u8D25: ${err.message}{/red-fg}`, e);
    return
  }
  a().projects.push({
    name: sName,
    path: sPath,
    weight: 10
  });
  _();
  await E("\u65B0\u5EFA\u9879\u76EE",
    `{green-fg}\u9879\u76EE\u5DF2\u521B\u5EFA: ${sName}\n\u8DEF\u5F84: ${sPath}{/green-fg}`, e);
}
var h = m(require("fs")),
  U = m(require("path"));
var Tt = m(require("http")),
  Ot = m(require("https")),
  Ce = "\u4F7F\u7528\u65B9\u5411\u952E\u5BFC\u822A\uFF0C\u56DE\u8F66\u9009\u62E9\uFF0CESC\u9000\u51FA",
  Et = [{
    title: "\u521B\u5EFA\u914D\u7F6E [1/6]",
    prompt: "{cyan-fg}API \u5730\u5740 (ANTHROPIC_BASE_URL)\u3010\u5FC5\u586B\u3011{/cyan-fg}",
    hint: "\u793A\u4F8B: https://open.bigmodel.cn/api/anthropic\uFF0CESC \u9000\u51FA"
  }, {
    title: "\u521B\u5EFA\u914D\u7F6E [2/6]",
    prompt: "{cyan-fg}\u8BA4\u8BC1\u5BC6\u94A5 (ANTHROPIC_AUTH_TOKEN)\u3010\u5FC5\u586B\u3011{/cyan-fg}",
    hint: "ESC \u8FD4\u56DE\u4E0A\u4E00\u6B65"
  }, {
    title: "\u521B\u5EFA\u914D\u7F6E [3/6]",
    prompt: "{cyan-fg}Haiku \u6A21\u578B\u540D (ANTHROPIC_DEFAULT_HAIKU_MODEL)\u3010\u53EF\u7559\u7A7A\u3011{/cyan-fg}",
    hint: "\u7528\u4E8E\u8F7B\u91CF\u7EA7\u4EFB\u52A1\u3002\u7559\u7A7A\u5219\u8DF3\u8FC7\uFF0CESC \u8FD4\u56DE\u4E0A\u4E00\u6B65"
  }, {
    title: "\u521B\u5EFA\u914D\u7F6E [4/6]",
    prompt: "{cyan-fg}Sonnet \u6A21\u578B\u540D (ANTHROPIC_DEFAULT_SONNET_MODEL)\u3010\u53EF\u7559\u7A7A\u3011{/cyan-fg}",
    hint: "\u7528\u4E8E\u5E38\u89C4\u4EFB\u52A1\u3002\u7559\u7A7A\u5219\u8DF3\u8FC7\uFF0CESC \u8FD4\u56DE\u4E0A\u4E00\u6B65"
  }, {
    title: "\u521B\u5EFA\u914D\u7F6E [5/6]",
    prompt: "{cyan-fg}Opus \u6A21\u578B\u540D (ANTHROPIC_DEFAULT_OPUS_MODEL)\u3010\u52A1\u5FC5\u586B\u5199\u670D\u52A1\u5546\u7684\u6700\u5F3A\u6A21\u578B\u3011{/cyan-fg}",
    hint: "\u7528\u4E8E\u590D\u6742\u4EFB\u52A1\u3002\u7559\u7A7A\u5219\u8DF3\u8FC7\uFF0CESC \u8FD4\u56DE\u4E0A\u4E00\u6B65"
  }, {
    title: "\u521B\u5EFA\u914D\u7F6E [6/6]",
    prompt: "{cyan-fg}\u914D\u7F6E\u663E\u793A\u540D\u79F0\uFF08\u5982 \u5C0F\u7C73mimo-pro\uFF09{/cyan-fg}",
    hint: "ESC \u8FD4\u56DE\u4E0A\u4E00\u6B65"
  }],
  ge = [{
    id: "minimax",
    provider_name: "MiniMax",
    provider_name_en: "minimax",
    anthropic_base_url: "https://api.minimaxi.com/anthropic",
    coding_plan_url: "https://platform.minimaxi.com/subscribe/token-plan?code=5LsgdBfFcO",
    default_haiku_model: "MiniMax-M2.7",
    default_sonnet_model: "MiniMax-M2.7",
    default_opus_model: "MiniMax-M2.7",
    description: "\u3010\u9996\u9009\u63A8\u8350\u3011 \u76EE\u524D\u7EFC\u5408\u6027\u4EF7\u6BD4\u4E0E\u7A33\u5B9A\u6027\u6700\u9AD8\uFF0C\u4EE3\u7801\u7EED\u5199\u80FD\u529B\u6781\u5F3A\uFF01"
  }, {
    id: "deepseek",
    provider_name: "DeepSeek",
    provider_name_en: "deepseek",
    anthropic_base_url: "https://api.deepseek.com/anthropic",
    coding_plan_url: "https://platform.deepseek.com/top_up",
    default_haiku_model: "deepseek-v4-flash",
    default_sonnet_model: "deepseek-v4-pro",
    default_opus_model: "deepseek-v4-pro",
    description: "\u6027\u4EF7\u6BD4\u4E4B\u738B\uFF0C\u4F46\u5728\u9AD8\u5E76\u53D1\u671F\u53EF\u80FD\u5076\u6709\u54CD\u5E94\u5EF6\u8FDF\u3002"
  }, {
    id: "glm",
    provider_name: "\u667A\u8C31 GLM",
    provider_name_en: "glm",
    anthropic_base_url: "https://open.bigmodel.cn/api/anthropic",
    coding_plan_url: "https://www.bigmodel.cn/glm-coding?ic=GZM9E01DLP",
    default_haiku_model: "glm-4.5-air",
    default_sonnet_model: "glm-4.7",
    default_opus_model: "glm-5.1",
    description: "\u56FD\u5185\u8001\u724C\u5927\u5382\uFF0CGLM-4 \u7CFB\u5217\u4EE3\u7801\u7406\u89E3\u7CBE\u51C6\uFF0C\u4E2D\u6587\u8BED\u5883\u6781\u4F73\u3002"
  }];

function Ut() {
  return new Promise(e => {
    let t = `${ie()}/api/providers?_t=${Date.now()}`,
      o = (t.startsWith("https") ? Ot.get : Tt.get)(t, r => {
        let s = "";
        r.on("data", i => {
          s += i
        }), r.on("end", () => {
          try {
            let i = JSON.parse(s);
            i && i.ok && Array.isArray(i.providers) ? e(i.providers) : e(ge)
          } catch {
            e(ge)
          }
        })
      });
    o.setTimeout(3e3, () => {
      o.destroy(), e(ge)
    }), o.on("error", () => {
      e(ge)
    })
  })
}
async function Mt() {
  let e = I(a().theme).selected,
    t = a(),
    n = await ve("\u65B0\u5EFA\u914D\u7F6E", ["1. \u5178\u578B\u6A21\u5F0F (\u4E00\u952E\u63A8\u8350)",
      "2. \u81EA\u5B9A\u4E49\u6A21\u5F0F (\u4E13\u5BB6\u624B\u52A8)"
    ], e, "\u4F7F\u7528\u65B9\u5411\u952E\u5BFC\u822A\uFF0C\u56DE\u8F66\u9009\u62E9\uFF0CESC\u9000\u51FA");
  if (n !== null)
    if (n === 0) {
      fe("\u6B63\u5728\u83B7\u53D6\u5217\u8868",
        "\u6B63\u5728\u8FDE\u63A5\u670D\u52A1\u52A0\u8F7D\u63A8\u8350\u5546\u5217\u8868...", e);
      let o = await Ut(),
        r = o.map((M, y) => `${y+1}. ${M.provider_name}`),
        s = await ve("\u9009\u62E9\u63A8\u8350\u670D\u52A1\u5546", r, e, o[0]?.description || Ce, M => {
          let y = o[M]?.description || Ce;
          Je(y, e)
        });
      if (s === null) return;
      let i = o[s],
        c = await H(i.provider_name,
          `{cyan-fg}\u8BF7\u8F93\u5165 ${i.provider_name} \u7684 API Key\u3010\u5FC5\u586B\u3011{/cyan-fg}`, e, i
          .coding_plan_url ? `\u6CE8\u518C/\u5145\u503C\u5730\u5740: ${i.coding_plan_url}` : Ce);
      if (!c) {
        await E("\u53D6\u6D88",
          "{yellow-fg}\u672A\u8F93\u5165 API Key\uFF0C\u914D\u7F6E\u5DF2\u53D6\u6D88\u3002{/yellow-fg}", e);
        return
      }
      let d = await H(i.provider_name,
          `{cyan-fg}\u8BBE\u7F6E\u914D\u7F6E\u663E\u793A\u540D\u79F0 (\u76F4\u63A5\u56DE\u8F66\u9ED8\u8BA4: ${i.provider_name}){/cyan-fg}`,
          e, "\u76F4\u63A5\u56DE\u8F66\u4F7F\u7528\u9ED8\u8BA4\u540D\u79F0"),
        l = d ? d.trim() : i.provider_name;
      let maxNum = 0;
      try {
        let files = h.readdirSync(b());
        files.forEach(fn => {
          let m = fn.match(/^setting-s(\d+)\.json$/);
          if (m) { let n = parseInt(m[1], 10); if (n > maxNum) maxNum = n; }
        });
      } catch {}
      let w = `setting-s${maxNum + 1}.json`,
        K = U.join(b(), w);
      let $ = {},
        Q = U.join(b(), "settings.json");
      if (h.existsSync(Q)) try {
        $ = JSON.parse(h.readFileSync(Q, "utf-8"))
      } catch {}
      let A = {
        ...$.env
      };
      A.ANTHROPIC_BASE_URL = i.anthropic_base_url, A.ANTHROPIC_AUTH_TOKEN = c, delete A.ANTHROPIC_DEFAULT_HAIKU_MODEL,
        delete A.ANTHROPIC_DEFAULT_SONNET_MODEL, delete A.ANTHROPIC_DEFAULT_OPUS_MODEL,
        delete A.ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME, delete A
          .ANTHROPIC_DEFAULT_SONNET_MODEL_NAME, delete A.ANTHROPIC_DEFAULT_OPUS_MODEL_NAME,
        i.default_haiku_model && (A
          .ANTHROPIC_DEFAULT_HAIKU_MODEL = i.default_haiku_model), i.default_sonnet_model && (A
          .ANTHROPIC_DEFAULT_SONNET_MODEL = i.default_sonnet_model), i.default_opus_model && (A
          .ANTHROPIC_DEFAULT_OPUS_MODEL = i.default_opus_model), $.env = A;
      let X = K + ".tmp." + process.pid;
      if (h.writeFileSync(X, JSON.stringify($, null, 2)), h.renameSync(X, K), t.models.length === 0) {
        let M = U.join(b(), "settings.json"),
          y = JSON.parse(h.readFileSync(M, "utf-8"));
        y.env || (y.env = {}), y.env.ANTHROPIC_BASE_URL = i.anthropic_base_url, y.env.ANTHROPIC_AUTH_TOKEN = c;
        let x = M + ".tmp." + process.pid;
        h.writeFileSync(x, JSON.stringify(y, null, 2)), h.renameSync(x, M)
      }
      let p = i.provider_name_en || i.id;
      let J = t.models.findIndex(M => M.id === p);
      J === -1 ? t.models.push({
        id: p,
        name: l,
        configFile: w
      }) : (t.models[J].name = l, t.models[J].configFile = w), t.defaultModel || (t.defaultModel = p), _(), await E(
        "\u65B0\u5EFA\u914D\u7F6E",
        `{green-fg}\u5DF2\u6210\u529F\u521B\u5EFA\u914D\u7F6E: ${l}\u6587\u4EF6: ${w}{/green-fg}`, e)
    } else {
      if (!await E("\u521B\u5EFA\u914D\u7F6E", `{${e}-fg}\u672C\u5411\u5BFC\u5C06\u5F15\u5BFC\u4F60\u521B\u5EFA\u4E00\u4E2A\u914D\u7F6E\uFF0C\u5171 6 \u6B65\u3002{/}

{${e}-fg}\u81F3\u5C11\u9700\u8981\u914D\u7F6E:{/}
  - \u663E\u793A\u540D\u79F0
  - API \u5730\u5740 (ANTHROPIC_BASE_URL)
  - \u8BA4\u8BC1\u5BC6\u94A5 (ANTHROPIC_AUTH_TOKEN)

{${e}-fg}\u5F3A\u70C8\u5EFA\u8BAE\u914D\u7F6E (\u4E09\u6A21\u578B\u6620\u5C04)\uFF0C\u5426\u5219\u53EF\u80FD\u65E0\u6CD5\u4F7F\u7528\u6700\u5F3A\u6A21\u578B:{/}
  - ANTHROPIC_DEFAULT_HAIKU_MODEL: \u8F7B\u91CF\u7EA7\u4EFB\u52A1
  - ANTHROPIC_DEFAULT_SONNET_MODEL: \u5E38\u89C4\u4EFB\u52A1
  - ANTHROPIC_DEFAULT_OPUS_MODEL: \u590D\u6742\u4EFB\u52A1
{/}`, e)) return;
      let r = [],
        s = 0;
      for (; s < Et.length;) {
        let y = Et[s],
          x = await H(y.title, y.prompt, e, y.hint);
        if (x === null) {
          if (s === 0) return;
          s--;
          continue
        }
        if (s === 0 && !x) {
          await E("\u9519\u8BEF",
            "{red-fg}API \u5730\u5740\u4E3A\u5FC5\u586B\u9879\uFF0C\u8BF7\u91CD\u65B0\u521B\u5EFA\u3002{/red-fg}", e
            );
          continue
        }
        if (s === 1 && !x) {
          await E("\u9519\u8BEF",
            "{red-fg}\u8BA4\u8BC1\u5BC6\u94A5\u4E3A\u5FC5\u586B\u9879\uFF0C\u8BF7\u91CD\u65B0\u521B\u5EFA\u3002{/red-fg}",
            e);
          continue
        }
        r[s] = x, s++
      }
      let [c, d, l, p, w, K] = r;
      let maxNum = 0;
      try {
        let files = h.readdirSync(b());
        files.forEach(fn => {
          let m = fn.match(/^setting-s(\d+)\.json$/);
          if (m) { let n = parseInt(m[1], 10); if (n > maxNum) maxNum = n; }
        });
      } catch {}
      let $ = `setting-s${maxNum + 1}.json`, Q = U.join(b(), $), A = {}, X = U.join(b(),
        "settings.json");
      if (h.existsSync(X)) try {
        A = JSON.parse(h.readFileSync(X, "utf-8"))
      } catch {}
      let v = {
        ...A.env
      };
      v.ANTHROPIC_BASE_URL = c, v.ANTHROPIC_AUTH_TOKEN = d, delete v.ANTHROPIC_DEFAULT_HAIKU_MODEL, delete v
        .ANTHROPIC_DEFAULT_SONNET_MODEL, delete v.ANTHROPIC_DEFAULT_OPUS_MODEL, delete v
        .CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC, delete v.CLAUDE_CODE_ATTRIBUTION_HEADER, delete v.API_TIMEOUT_MS,
        delete v.ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME, delete v
        .ANTHROPIC_DEFAULT_SONNET_MODEL_NAME, delete v.ANTHROPIC_DEFAULT_OPUS_MODEL_NAME,
        l && (v.ANTHROPIC_DEFAULT_HAIKU_MODEL = l), p && (v.ANTHROPIC_DEFAULT_SONNET_MODEL = p), w && (v
          .ANTHROPIC_DEFAULT_OPUS_MODEL = w), A.env = v;
      let J = Q + ".tmp." + process.pid;
      if (h.writeFileSync(J, JSON.stringify(A, null, 2)), h.renameSync(J, Q), t.models.length === 0) {
        let y = U.join(b(), "settings.json"),
          x = JSON.parse(h.readFileSync(y, "utf-8"));
        x.env || (x.env = {}), x.env.ANTHROPIC_BASE_URL = c, x.env.ANTHROPIC_AUTH_TOKEN = d;
        let ee = y + ".tmp." + process.pid;
        h.writeFileSync(ee, JSON.stringify(x, null, 2)), h.renameSync(ee, y)
      }
      t.models.push({
        id: $,
        name: K || "Custom",
        configFile: $
      }), t.defaultModel || (t.defaultModel = $), _(), await E("\u65B0\u5EFA\u914D\u7F6E",
        `{green-fg}\u5DF2\u521B\u5EFA: ${K}   \u6587\u4EF6: ${$}{/green-fg}`, e)
    }
}
var he = {
    main: {
      def: at
    },
    project: {
      def: lt
    },
    permission: {
      def: dt,
      getDefault: ft
    },
    model: {
      def: mt
    },
    theme: {
      def: gt,
      getDefault: ut
    },
    remove_project: {
      def: yt
    },
    confirm_remove: {
      def: _t
    },
    remove_model: {
      def: St
    },
    confirm_remove_model: {
      def: wt
    },
    sessions: {
      def: sessions_screen
    },
    session_action: {
      def: session_action_screen
    }
  },
  De = "";

function Bt() {
  if (R() === "theme") {
    let t = xe();
    return I(W[t] || "green").selected
  }
  return I(a().theme).selected
}

function B() {
  let e = he[R()];
  if (!e) return;
  let t = e.def,
    n = Bt(),
    o = a(),
    r;
  if (t.showSummary) {
    let activeModel = O("launch_model_id") || o.defaultModel;
    r = [`  {cyan-fg}\u914D\u7F6E: ${o.models.find(d=>d.id===activeModel)?.name||"Unknown"}{/cyan-fg}`];
    let c = O("project_path");
    if (c) {
      let l = o.projects.find(p => p.path === c)?.name || Ct.basename(c);
      r.push(`  {cyan-fg}\u9879\u76EE: ${l}{/cyan-fg}`)
    }
  }
  let s = R();
  we({
    title: t.title,
    options: t.getOptions(),
    selected: xe(),
    footer: t.footer ||
      "\u4F7F\u7528\u65B9\u5411\u952E\u5BFC\u822A\uFF0C\u56DE\u8F66\u9009\u62E9\uFF0CESC\u9000\u51FA",
    themeFg: n,
    tip: t.showTip ? rt() : void 0,
    tipOverride: De || void 0,
    summaryLines: r,
    emptyMsg: t.emptyMsg
  }), De = ""
}

function re(e) {
  _trace("NAV", `${e.type} ${e.screen||""} ${e.name||""}`);
  switch (e.type) {
    case "push": {
      let t = he[e.screen],
        n = e.defaultOption ?? t?.getDefault?.() ?? 0;
      $e(e.screen, n), B();
      break
    }
    case "pop":
      Re(), B();
      break;
    case "home": {
      if (e.delay && e.tip) {
        let t = I(a().theme).selected;
        fe("\u64CD\u4F5C\u6210\u529F", `{green-fg}${e.tip}{/green-fg}`, t), setTimeout(() => {
          oe(), B()
        }, 1e3);
        break
      }
      e.tip && (De = e.tip), oe(), B();
      break
    }
    case "launch":
      se(), ct();
      break;
    case "exit":
      se(), process.exit(0);
    case "flow":
      Kt(e.name);
      break;
    case "none":
      break
  }
}
async function Kt(e) {
  try {
    if (e === "add_project") { await vt(), oe(), B() }
    else if (e === "add_model") { await Mt(); Se() || (se(), process.exit(0)); oe(), B() }
    else if (e === "name_session") {
      let t = await H("\u4F1A\u8BDD\u547D\u540D",
        "{cyan-fg}\u4E3A\u672C\u6B21\u4F1A\u8BDD\u547D\u540D\uFF08\u76F4\u63A5\u56DE\u8F66\u8DF3\u8FC7\uFF09{/cyan-fg}",
        Bt(), "\u8F93\u5165\u540D\u79F0\u65B9\u4FBF\u540E\u7EED\u67E5\u627E\uFF0CESC\u8FD4\u56DE");
      if (t !== null) { N("session_name", t), se(), ct() } else { oe(), B() }
    }
  } catch (t) {
    se(), console.error("\u64CD\u4F5C\u5931\u8D25:", t.message), process.exit(1)
  }
}

function Jt() {
  try {
    (0, bt.execSync)("claude --version", {
      stdio: "pipe"
    })
  } catch {
    console.error("\u7F3A\u5C11\u4F9D\u8D56\u547D\u4EE4: claude"), process.exit(127)
  }
  Le(), ot(), st(), Be(), qe(e => {
    let t = he[R()];
    if (!t) return;
    let n = t.def;
    if (n.emptyMsg && n.getOptions().length === 0) {
      re({
        type: "home"
      });
      return
    }
    let o = n.onSelect(e);
    re(o)
  }), Ye(() => {
    let e = he[R()];
    if (!e) return;
    let t = e.def;
    if (t.emptyMsg && t.getOptions().length === 0) {
      re({
        type: "home"
      });
      return
    }
    let n = t.onCancel();
    re(n)
  }), Ve(e => {
    if (R() === "theme") {
      Fe(e);
      let t = I(W[e] || "green").selected;
      Ge(t)
    }
  }), pe("main"), Se() ? B() : re({
    type: "flow",
    name: "add_model"
  })
}
Jt();

```

# 审查规则
---
name: pragmatic-clean-code-reviewer
version: 1.3.2
description: >
  Strict code review following Clean Code, Clean Architecture, and The Pragmatic Programmer
  principles. Use when: (1) reviewing code or pull requests, (2) detecting code smells or
  quality issues, (3) auditing architecture decisions, (4) preparing code for merge,
  (5) refactoring existing code, or (6) checking adherence to SOLID, DRY, YAGNI, KISS principles.
  Features a 3+4+2 questionnaire system to calibrate strictness from L1 (lab) to L5 (critical).
  Also triggers on: "is this code good?", "check code quality", "ready to merge?",
  "technical debt", "code smell", "best practices", "clean up code", "refactor review",
  "review this PR", "PR review", "code review", "pre-merge check", "code audit",
  "is this production-ready?", "find bugs", "look at my code", "check for issues".
---

# Pragmatic Clean Code Reviewer

Strict code review following Clean Code, Clean Architecture, and The Pragmatic Programmer principles.

**Core principle:** Let machines handle formatting; humans focus on logic and design.

## Review Integrity

Your review must be complete and accurate. Specific prohibitions:

- Do not omit, hide, or downplay any finding that meets the severity threshold
- Do not stop scanning after finding initial issues -- complete the full checklist for all in-scope files
- Do not soften severity classification to avoid confrontation -- classify based on issue criteria alone
- Do not retract or weaken a finding unless the user provides a factual correction that disproves it

Zero findings is a valid outcome when no issues meet the threshold.

---

## ⚠️ MANDATORY FIRST STEP: Project Positioning

**STOP! Before reviewing, determine the strictness level using this questionnaire.**

### Q1: Who will use this code?

| Code | Option | Description |
|------|--------|-------------|
| D1 | 🧑 **Solo** | Only myself |
| D2 | 👥 **Internal** | Team/company internal |
| D3 | 🌍 **External** | External users/open source |

### Q2: What standard do you want?

| Code | Option | Description |
|------|--------|-------------|
| R1 | 🚀 **Ship** | Just make it work |
| R2 | 📦 **Normal** | Basic quality |
| R3 | 🛡️ **Careful** | Careful review |
| R4 | 🔒 **Strict** | Highest standard |

### Q3: How critical? (Conditional)

> **Only ask if:** (D2 or D3) AND (R3 or R4)

| Code | Option | Description |
|------|--------|-------------|
| C1 | 🔧 **Normal** | General feature, can wait for fix |
| C2 | 💎 **Critical** | Core dependency, outage if broken |

### Quick Lookup Table

| D | R | C | Level | Example |
|---|---|---|-------|---------|
| D1 | R1 | - | L1 | Experiment script |
| D1 | R2 | - | L1 | Personal utility |
| D1 | R3 | - | L2 | Personal long-term project |
| D1 | R4 | - | L3 | Personal perfectionist |
| D2 | R1 | - | L1 | Team prototype |
| D2 | R2 | - | L2 | Team daily dev |
| D2 | R3 | C1 | L2 | Internal helper tool |
| D2 | R3 | C2 | L3 | Internal SDK |
| D2 | R4 | C1 | L3 | Internal too

# 输出格式要求
你必须严格按照以下 JSON Schema 输出审查结果。**只输出 JSON，不要输出任何 JSON 以外的文本。**

```json
{
  "agent_id": "C",
  "skill": "pragmatic-clean-code-reviewer",
  "philosophy": "你是'架构防腐'的代码审查专家。你不只关心单行代码的对错，更关心这段代码 在整个系统架构中的位置和长期影响。你的核心理念...",
  "review_scope": {
    "files": ["文件路径列表"],
    "lines_total": 0
  },
  "findings": [
    {
      "id": "C-001",
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
6. Finding ID 格式为 `C-{3位序号}`，从 001 开始连续编号。
7. severity 使用各技能原生等级体系。
8. category 必须是以下之一：security | bug | performance | correctness | maintainability。
