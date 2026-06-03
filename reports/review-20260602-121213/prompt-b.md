# 角色
你是一名资深代码审查专家，正在对一份代码进行系统性的代码审查。
你的审查哲学：你是'攻击者思维'的安全审计专家。你审查代码时的默认假设是：有恶意攻击者会仔细阅读这段代码，寻找任何可能的突破口。你不是在找'不优雅'的代码——你是在找'可利用'的代码。你的核心理念来自 574+ 个真实 HackerOne 漏洞报告的模式提炼。

# 你的身份
你是 MACRS（多智能体对抗式代码审查系统）中的 **Agent B - Security Hunter**。
你的技能来源：Claude-BugHunter

# 审查范围
目标路径：C:\Users\Administrator\Claude-Code\cc-tools\web-browsing-expert

审查文件列表 (28 个文件, 3674 行):
  - scripts\pw-multi.js
  - scripts\quick-test.sh
  - shared-scripts\bilibili\extract-links.js
  - shared-scripts\douyin\extract-links.js
  - shared-scripts\quark\download-file.js
  - shared-scripts\tools\fsearch.sh
  - shared-scripts\utils\playwright-helpers.js
  - shared-scripts\zlib\download-book.js
  - shared-scripts\zsxq\delete-article.js
  - shared-scripts\zsxq\publish-article.js
  - skills\scrapling\examples\01_fetcher_session.py
  - skills\scrapling\examples\02_dynamic_session.py
  - skills\scrapling\examples\03_stealthy_session.py
  - skills\scrapling\examples\04_spider.py
  - tools\browser\helpers\node-helpers.js
  - tools\browser\helpers\playwright-helpers.js
  - tools\browser\proxy\pw-multi.js
  - tools\browser\proxy\start-proxy.sh
  - tools\fetch\smart-fetch.sh
  - tools\platform\bilibili\extract-links.js
  - tools\platform\douyin\extract-links.js
  - tools\platform\quark\download-file.js
  - tools\platform\zlib\download-book.js
  - tools\platform\zsxq\delete-article.js
  - tools\platform\zsxq\publish-article.js
  - tools\search\fsearch\fsearch.sh
  - tools\vision\describe-image.py
  - tools\vision\glm-vision-mcp.py

---

### File: scripts\pw-multi.js
```
#!/usr/bin/env node
/**
 * Playwright MCP Multi-Instance Wrapper
 * 每个会话独立浏览器配置，多窗口互不干扰。
 */

const { spawn } = require('child_process');
const os = require('os');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

const sessionId = crypto.randomBytes(4).toString('hex');
const instanceTag = `pw-mcp-${sessionId}`;
process.stderr.write(`[pw-multi] session=${sessionId} platform=${process.platform} tmpdir=${os.tmpdir()}\n`);

const tempRoot = path.join(os.tmpdir(), 'pw-mcp-instances');
fs.mkdirSync(tempRoot, { recursive: true });
process.stderr.write(`[pw-multi] tempRoot=${tempRoot}\n`);

// 清理 24h+ 残留
try {
  const now = Date.now();
  for (const name of fs.readdirSync(tempRoot)) {
    const p = path.join(tempRoot, name);
    try { if (fs.statSync(p).isDirectory() && (now - fs.statSync(p).mtimeMs > 86400000)) fs.rmSync(p, { recursive: true, force: true }); } catch {}
  }
} catch {}

const instanceDir = path.join(tempRoot, instanceTag);
const userDataDir = path.join(instanceDir, 'browser-data');
const outputDir = path.join(instanceDir, 'output');
fs.mkdirSync(userDataDir, { recursive: true });
fs.mkdirSync(outputDir, { recursive: true });
process.stderr.write(`[pw-multi] userDataDir=${userDataDir}\n`);
process.stderr.write(`[pw-multi] outputDir=${outputDir}\n`);

// Windows 上通过 cmd /c 调用 npx.cmd，避免 spawn 路径引号问题
const npxPath = path.join(path.dirname(process.execPath), 'npx.cmd');
const spawnArgs = [
  '/c', npxPath,
  '@playwright/mcp@latest',
  '--headless'
];

// 修复 bash/msys 环境中 TEMP/TMP 被设为 /tmp 导致路径异常
const env = { ...process.env };
if (process.platform === 'win32') {
  env.TEMP = env.TEMP || path.join(process.env.SystemRoot || 'C:\\Windows', 'Temp');
  env.TMP = env.TEMP;
  if (env.TMPDIR === '/tmp' || !env.TMPDIR) env.TMPDIR = env.TEMP;
}

process.stderr.write(`[pw-multi] spawning: cmd ${spawnArgs.join(' ')}\n`);
process.stderr.write(`[pw-multi] env.TEMP=${env.TEMP} env.TMP=${env.TMP} env.TMPDIR=${env.TMPDIR}\n`);
const child = spawn('cmd', spawnArgs, { stdio: 'inherit', env });

child.on('error', (err) => {
  process.stderr.write(`[pw-multi] ERROR: ${err.message}\n`);
  cleanup(); process.exit(1);
});
child.on('exit', (code) => {
  cleanup(); process.exit(code ?? 0);
});

function cleanup() {
  try { fs.rmSync(instanceDir, { recursive: true, force: true }); } catch {}
}

process.on('SIGINT', () => { try { child.kill('SIGINT'); } catch {} });
process.on('SIGTERM', () => { try { child.kill('SIGTERM'); } catch {} });

```

### File: scripts\quick-test.sh
```
#!/usr/bin/env bash
# ============================================================
# quick-test.sh — 快速 URL 诊断脚本
# 一键测试 URL 能否通过浏览体系访问，输出诊断结果
# 用法: ./quick-test.sh "https://目标URL"
# ============================================================

set -o pipefail

TARGET_URL="$1"

if [ -z "$TARGET_URL" ]; then
    echo "用法: $0 <URL>" >&2
    echo "示例: $0 \"https://github.com\"" >&2
    exit 2
fi

# --- 路径配置 ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
AUTO_PROXY="${PROJECT_ROOT}/tools/browser/proxy/auto-proxy.mjs"
CDP_PORT="${CDP_PROXY_PORT:-3456}"
CDP_BASE="http://127.0.0.1:${CDP_PORT}"
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# --- 颜色 ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "============================================"
echo " quick-test — 网络浏览诊断"
echo " 目标: ${TARGET_URL}"
echo "============================================"
echo ""

# 提取域名（bash 原生 URL 解析，无需 Python）
HOSTNAME=$(echo "$TARGET_URL" | sed -E 's|https?://||' | sed -E 's|/.*||' | sed -E 's|:.*||')

if [ -z "$HOSTNAME" ] || [ "$HOSTNAME" = "$TARGET_URL" ]; then
    echo -e "${RED}无效 URL: ${TARGET_URL}${NC}"
    exit 1
fi

# --- 步骤 1: 代理探测 ---
echo -n "代理探测: "
PROXY_URL=""
if [ -f "$AUTO_PROXY" ]; then
    PROXY_RESULT=$(node "$AUTO_PROXY" --json 2>/dev/null || echo '{"proxy":null}')
    PROXY_URL=$(echo "$PROXY_RESULT" | node -e "process.stdin.on('data',d=>{try{process.stdout.write(JSON.parse(d).proxy||'')}catch(e){}})" 2>/dev/null || echo "")
fi

if [ -n "$PROXY_URL" ]; then
    echo -e "${GREEN}${PROXY_URL} ✅${NC}"
else
    echo -e "${YELLOW}未发现${NC}"
fi

# --- 步骤 2: curl 测试 ---
echo -n "curl 测试:  "
CURL_START=$(node -e "console.log(Date.now())")

CURL_ARGS=(-s -o /dev/null -w "%{http_code}" --max-time 8 -L -H "User-Agent: $UA")
if [ -n "$PROXY_URL" ]; then
    CURL_ARGS+=(--proxy "$PROXY_URL")
fi

HTTP_CODE=$(curl "${CURL_ARGS[@]}" "$TARGET_URL" 2>/dev/null || echo "000")
CURL_END=$(node -e "console.log(Date.now())")
CURL_TIME=$((CURL_END - CURL_START))

if [ "$HTTP_CODE" = "000" ]; then
    echo -e "${RED}❌ (连接失败, ${CURL_TIME}ms)${NC}"
    CURL_OK=false
elif [ "$HTTP_CODE" = "403" ]; then
    echo -e "${RED}❌ (403 Forbidden, ${CURL_TIME}ms)${NC}"
    CURL_OK=false
elif [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 400 ]; then
    echo -e "${GREEN}✅ (HTTP ${HTTP_CODE}, ${CURL_TIME}ms)${NC}"
    CURL_OK=true
else
    echo -e "${YELLOW}⚠ (HTTP ${HTTP_CODE}, ${CURL_TIME}ms)${NC}"
    CURL_OK=false
fi

# --- 步骤 3: cdp-proxy 测试 ---
echo -n "cdp-proxy:  "

# 检查 cdp-proxy 是否运行
CDP_HEALTH=$(curl -s --max-time 2 "${CDP_BASE}/health" 2>/dev/null || echo "")
if echo "$CDP_HEALTH" | grep -q '"ok"'; then
    # cdp-proxy 已运行，尝试打开目标页
    CDP_START=$(node -e "console.log(Date.now())")
    NEW_RESP=$(curl -s --max-time 8 "${CDP_BASE}/new?url=$(node -e "console.log(encodeURIComponent(process.argv[1]))" "$TARGET_URL")" 2>/dev/null || echo '{}')
    TARGET_ID=$(echo "$NEW_RESP" | node -e "process.stdin.on('data',d=>{try{process.stdout.write(JSON.parse(d).targetId||'')}catch(e){}})" 2>/dev/null || echo "")

    if [ -n "$TARGET_ID" ]; then
        # 等待加载
        sleep 3
        # 获取页面标题
        INFO=$(curl -s --max-time 5 "${CDP_BASE}/info?target=${TARGET_ID}" 2>/dev/null || echo '{}')
        PAGE_TITLE=$(echo "$INFO" | node -e "process.stdin.on('data',d=>{try{process.stdout.write(JSON.parse(d).title||'')}catch(e){}})" 2>/dev/null || echo "")
        CDP_END=$(node -e "console.log(Date.now())")
        CDP_TIME=$((CDP_END - CDP_START))

        # 关闭页面
        curl -s --max-time 3 "${CDP_BASE}/close?target=${TARGET_ID}" >/dev/null 2>&1 || true

        echo -e "${GREEN}✅ (${CDP_TIME}ms, 标题: ${PAGE_TITLE})${NC}"
        CDP_OK=true
    else
        echo -e "${RED}❌ (无法创建页面)${NC}"
        CDP_OK=false
    fi
else
    echo -e "${YELLOW}未运行${NC}"
    CDP_OK=false
fi

# --- 步骤 4: 推荐 ---
echo ""
echo "--- 诊断结果 ---"
echo "  域名:    ${HOSTNAME}"
echo "  代理:    ${PROXY_URL:-无}"

# 推荐逻辑
RECOMMEND=""
if $CURL_OK; then
    RECOMMEND="curl"
elif $CDP_OK; then
    RECOMMEND="cdp-proxy"
elif [ -n "$PROXY_URL" ]; then
    RECOMMEND="tavily (有代理但双路径均失败)"
else
    RECOMMEND="tavily (无代理, 双路径均失败)"
fi

echo ""
echo -n "  推荐:    "

case "$RECOMMEND" in
    curl*)
        echo -e "${GREEN}${RECOMMEND}${NC}"
        ;;
    cdp-proxy*)
        echo -e "${CYAN}${RECOMMEND}${NC}"
        ;;
    tavily*)
        echo -e "${YELLOW}${RECOMMEND}${NC}"
        ;;
esac

echo ""
echo "============================================"

```

### File: shared-scripts\bilibili\extract-links.js
```
/**
 * @tool: bilibili-extract-links
 * @tags: bilibili,link,extraction,playwright
 * @mcp: playwright
 * @inputs: page (Playwright Page), options { maxResults, scroll }
 * @output: Array<{href: string, title: string}>
 * @description: 从当前B站页面提取所有视频链接(BV号)，支持滚动加载更多
 *
 * 用法示例:
 *   const links = await extractBilibiliLinks(page, { maxResults: 100, scroll: true });
 *   writeToFile(linksToJson(links), 'links.json');
 *   writeToFile(linksToPlain(links), 'links.txt');
 */

/**
 * 从 B站页面提取所有视频链接
 * @param {import('playwright').Page} page - Playwright Page 对象
 * @param {{maxResults?: number, scroll?: boolean}} options
 * @returns {Promise<Array<{href: string, title: string}>>}
 */
async function extractBilibiliLinks(page, options = {}) {
  const { maxResults = 50, scroll = true } = options;
  const allLinks = [];
  let prevCount = 0;
  let staleCount = 0;

  while (allLinks.length < maxResults && staleCount < 3) {
    const newLinks = await page.evaluate(() => {
      const results = [];
      document.querySelectorAll('a[href*="/video/BV"]').forEach((a) => {
        const href = a.getAttribute('href');
        const card = a.closest('.bili-video-card');
        const titleEl = card?.querySelector('.bili-video-card__info--tit')
                     || a.querySelector('.bili-video-card__info--tit');
        const title = titleEl?.textContent?.trim() || '';
        if (href) {
          results.push({
            href: href.startsWith('http') ? href : 'https:' + href,
            title
          });
        }
      });
      return results;
    });

    for (const link of newLinks) {
      if (!allLinks.find((l) => l.href === link.href)) {
        allLinks.push(link);
      }
    }

    if (allLinks.length === prevCount) {
      staleCount++;
    } else {
      staleCount = 0;
    }
    prevCount = allLinks.length;

    if (scroll && allLinks.length < maxResults) {
      await page.evaluate(() => window.scrollBy(0, 800));
      await page.waitForTimeout(1500);
    }
  }

  return allLinks.slice(0, maxResults);
}

/**
 * 转为 JSON 字符串
 */
function linksToJson(links, source = '') {
  return JSON.stringify({
    source,
    extracted_at: new Date().toISOString().replace('T', ' ').substring(0, 19),
    total: links.length,
    videos: links
  }, null, 2);
}

/**
 * 转为纯文本链接列表
 */
function linksToPlain(links) {
  return links.map((l) => l.href).join('\n');
}

module.exports = { extractBilibiliLinks, linksToJson, linksToPlain };

```

### File: shared-scripts\douyin\extract-links.js
```
/**
 * @tool: douyin-extract-links
 * @tags: douyin,link,extraction,playwright
 * @mcp: playwright
 * @inputs: page (Playwright Page), options { maxResults, scroll, type }
 * @output: Array<{href: string, title: string, author?: string, likes?: string, duration?: number}>
 * @description: 从当前抖音页面提取所有视频链接。搜索页走API拦截(aweme-id), 用户主页走DOM提取。支持滚动翻页去重。
 *
 * 实测发现:
 * - 抖音搜索使用 Lynx 框架渲染, DOM 中无传统 <a href="/video/..."> 标签
 * - 搜索结果通过 XHR → JSON 返回, aweme_id 在 business_data 深层嵌套
 * - 需 deviceScaleFactor:3 + isMobile:true 伪装移动端, 否则反爬拦截
 * - 用户主页/视频详情页可能有 DOM 链接, 双重策略覆盖
 *
 * 用法示例:
 *   // 搜索(API拦截模式)
 *   const links = await extractDouyinLinks(page, { type: 'search', keyword: '编程', maxResults: 100 });
 *   // 用户主页(DOM模式)
 *   const links = await extractDouyinLinks(page, { type: 'user', maxResults: 50 });
 *   // 直接解析 API 响应 JSON
 *   const links = extractDouyinFromApiJson(apiResponseJson);
 */

/**
 * 从抖音页面提取视频链接 - 主入口
 * @param {import('playwright').Page} page - Playwright Page 对象
 * @param {{maxResults?: number, scroll?: boolean, type?: 'search'|'user'|'topic', keyword?: string}} options
 * @returns {Promise<Array<{href:string, title:string, author?:string, likes?:string}>>}
 */
async function extractDouyinLinks(page, options = {}) {
  const { maxResults = 50, scroll = true, type = 'search' } = options;

  if (type === 'search') {
    return extractFromSearchPage(page, { maxResults, scroll });
  }

  // user/topic: DOM 提取 + 滚动翻页
  return extractFromDom(page, { maxResults, scroll, type });
}

/**
 * 搜索页: API拦截模式
 * 拦截 aweme/v2/search/msite/general/search/single/ → 解析 JSON → 提取 aweme_id
 * 滚动触发新 API 请求 → 循环拦截 → staleCount 退出
 */
async function extractFromSearchPage(page, { maxResults = 50, scroll = true }) {
  const videos = [];
  let prevCount = 0;
  let staleCount = 0;

  while (videos.length < maxResults && staleCount < 3) {
    let searchJson = null;

    const onResponse = async (response) => {
      const url = response.url();
      if (url.includes('/aweme/v2/search/') && url.includes('/single') && response.status() === 200) {
        try {
          const text = await response.text();
          if (text.length > 10000) searchJson = JSON.parse(text);
        } catch (e) {}
      }
    };

    page.on('response', onResponse);

    try {
      // 等待 API 响应
      for (let i = 0; i < 8 && !searchJson; i++) {
        await page.waitForTimeout(1500);
      }

      if (searchJson) {
        const parsed = parseSearchApiResponse(searchJson);
        const before = videos.length;
        mergeByVideoId(videos, parsed);

        if (videos.length === before) staleCount++;
        else staleCount = 0;
      } else {
        staleCount++;
      }
    } finally {
      page.off('response', onResponse);
    }

    prevCount = videos.length;

    // 滚动触发新一批 API 请求
    if (scroll && videos.length < maxResults) {
      await page.evaluate(() => {
        window.scrollBy({ top: 600 + Math.floor(Math.random() * 400), behavior: 'smooth' });
      });
      await page.waitForTimeout(1500 + Math.floor(Math.random() * 1500));
    }
  }

  return videos.slice(0, maxResults);
}

/**
 * DOM 模式: 遍历页面 a 标签 + shadow DOM (用户主页、话题页等)
 */
async function extractFromDom(page, { maxResults = 50, scroll = true, type = 'search' }) {
  const allLinks = [];
  let prevCount = 0;
  let staleCount = 0;

  while (allLinks.length < maxResults && staleCount < 3) {
    const newLinks = await page.evaluate((pageType) => {
      const results = [];

      // 深海遍历 shadow DOM
      function deepQueryAll(root, selector) {
        let found = [...root.querySelectorAll(selector)];
        root.querySelectorAll('*').forEach((el) => {
          if (el.shadowRoot) found = found.concat(deepQueryAll(el.shadowRoot, selector));
        });
        return found;
      }

      deepQueryAll(document, 'a[href*="/video/"]').forEach((a) => {
        const href = a.getAttribute('href');
        if (!href) return;

        const card = a.closest('[class*="card"]')
                  || a.closest('[class*="item"]')
                  || a.closest('li')
                  || a.closest('div');

        const titleEl = card?.querySelector('[class*="title"]')
                     || card?.querySelector('[class*="desc"]')
                     || a.querySelector('[class*="title"]');

        const authorEl = card?.querySelector('[class*="author"]')
                      || card?.querySelector('[class*="nickname"]')
                      || card?.querySelector('[class*="name"]');

        const title = titleEl?.textContent?.trim() || '';
        const author = authorEl?.textContent?.trim() || '';

        if (href) {
          results.push({
            href: href.startsWith('http') ? href : 'https://www.douyin.com' + href,
            title,
            author
          });
        }
      });
      return results;
    }, type);

    // 去重
    for (const link of newLinks) {
      const videoId = extractVideoId(link.href);
      if (videoId && !allLinks.find((l) => extractVideoId(l.href) === videoId)) {
        allLinks.push(link);
      } else if (!videoId && !allLinks.find((l) => l.href === link.href)) {
        allLinks.push(link);
      }
    }

    if (allLinks.length === prevCount) staleCount++;
    else staleCount = 0;
    prevCount = allLinks.length;

    if (scroll && allLinks.length < maxResults) {
      await page.evaluate(() => {
        window.scrollBy({ top: 600 + Math.floor(Math.random() * 400), behavior: 'smooth' });
      });
      await page.waitForTimeout(1500 + Math.floor(Math.random() * 1500));
    }
  }

  return allLinks.slice(0, maxResults);
}

/**
 * 解析抖音搜索 API 响应 JSON，提取视频列表
 * API: aweme/v2/search/msite/general/search/single/
 */
function parseSearchApiResponse(json) {
  const seen = new Set();
  const videos = [];

  function dig(obj, depth) {
    if (!obj || depth > 15) return;
    if (Array.isArray(obj)) {
      obj.forEach((item) => dig(item, depth + 1));
    } else if (typeof obj === 'object') {
      // 找到 aweme_info → 提取视频元数据
      if (obj.aweme_id && !seen.has(obj.aweme_id)) {
        seen.add(obj.aweme_id);

        // 提取标题: desc 字段
        const title = obj.desc || '';

        // 提取作者: author 对象或 author_name 字段
        let author = '';
        if (obj.author?.nickname) author = obj.author.nickname;
        else if (obj.author_name) author = obj.author_name;

        // 提取统计: statistics 对象
        let likes = '';
        if (obj.statistics?.digg_count) {
          const n = parseInt(obj.statistics.digg_count);
          likes = n >= 10000 ? (n / 10000).toFixed(1) + '万' : String(n);
        }

        // 提取时长 (API 返回毫秒, 转秒)
        const durationMs = obj.duration || obj.video?.duration || 0;
        const duration = durationMs > 1000 ? Math.round(durationMs / 1000) : durationMs;

        videos.push({
          href: 'https://www.douyin.com/video/' + obj.aweme_id,
          title,
          author,
          likes,
          duration: duration > 0 ? duration : undefined
        });
      }
      // 继续深挖
      Object.values(obj).forEach((v) => dig(v, depth + 1));
    }
  }

  const bizData = json.business_data || json.data || [];
  dig(bizData, 0);

  return videos;
}

/**
 * 按 video_id 合并去重
 */
function mergeByVideoId(target, incoming) {
  for (const item of incoming) {
    const id = extractVideoId(item.href);
    if (id && !target.find((t) => extractVideoId(t.href) === id)) {
      target.push(item);
    }
  }
}

/**
 * 从 API JSON 直接提取（离线模式，无需 Playwright）
 * @param {object} json - 搜索 API 返回的 JSON 对象
 * @returns {Array<{href:string, title:string, author:string, likes:string}>}
 */
function extractDouyinFromApiJson(json) {
  return parseSearchApiResponse(json);
}

function extractVideoId(url) {
  const m = url.match(/\/video\/(\d+)/);
  return m ? m[1] : null;
}

function extractUserId(url) {
  const m = url.match(/\/user\/([\w-]+)/);
  return m ? m[1] : null;
}

function linksToJson(links, source = '') {
  return JSON.stringify({
    source,
    extracted_at: new Date().toISOString().replace('T', ' ').substring(0, 19),
    total: links.length,
    videos: links
  }, null, 2);
}

function linksToPlain(links) {
  return links.map((l) => l.href).join('\n');
}

function linksToText(links) {
  return links.map((l, i) =>
    `${i + 1}. ${l.title}\n   ${l.href}\n   ${l.author ? '@' + l.author + '  ' : ''}${l.likes ? l.likes + ' 点赞' : ''}`
  ).join('\n\n');
}

module.exports = {
  extractDouyinLinks,
  extractDouyinFromApiJson,
  parseSearchApiResponse,
  linksToJson,
  linksToPlain,
  linksToText,
  extractVideoId,
  extractUserId
};

```

### File: shared-scripts\quark\download-file.js
```
/**
 * @tool:      quark-download-file
 * @summary:   Download file(s) from 夸克网盘 (Quark Pan) via Playwright browser automation
 * @tags:      quark, 夸克网盘, download, playwright, browser
 * @mcp:       playwright
 * @inputs:    targetPath (string) - 目标文件/文件夹在网盘中的路径，如 "手机录屏" 或 "手机录屏/SVID_xxx.mp4"
 * @inputs:    destDir (string) - 本地目标目录，默认 ~/Desktop，可指定任意路径如 "D:/Videos"
 * @output:    array — 下载成功的文件路径列表
 *
 * 使用方式: Agent 读取此脚本中的步骤，通过 Playwright MCP 工具执行。
 * 下载完成后文件位于 .playwright-mcp/ 目录，需手动 cp 到目标位置。
 *
 * 前置条件: 用户已在夸克网盘网页版 (pan.quark.cn) 登录。
 *           Agent 在浏览器内操作，用户日常 Chrome 自带登录态。
 */

// ============================================================
// Step 0: ⚠️ 页面白屏修复（必须先检查！）
// ============================================================
// 夸克网盘依赖 g.alicdn.com 的 CDN 资源（Vue SPA）。
// Playwright 持久化浏览器 Profile 的缓存容易损坏，导致 CSS/JS 加载失败，
// 页面显示为白色空白（ERR_CACHE_READ_FAILURE）。
//
// 检测方法: browser_evaluate → () => document.body?.innerText?.substring(0, 100)
//   如果返回空字符串 → 白屏，执行修复:
//
// 修复步骤:
//   browser_run_code_unsafe →
//     const client = await page.context().newCDPSession(page);
//     await client.send('Network.clearBrowserCache');
//     await client.detach();
//     await page.goto('https://pan.quark.cn/s/XXXXX', { waitUntil: 'networkidle', timeout: 30000 });
//
// ⚠️ 不要用 browser_navigate 重新加载，必须用 page.goto + networkidle。
// ⚠️ 只清缓存不清 Cookie，登录态不会丢失。

// ============================================================
// Step 1: 导航到夸克网盘
// ============================================================
// MCP: browser_navigate → https://pan.quark.cn/
// 如果已登录，会自动跳转到 /list#/list/all
// 检查: 页面标题应为"夸克网盘"，左侧边栏可见"云文件"菜单
// 如果是分享链接 https://pan.quark.cn/s/{shareId} → 直接导航到该 URL

// ============================================================
// Step 1b (可选): 如果 targetPath 包含具体文件夹，逐级进入
// ============================================================
// 解析路径，逐级点击进入文件夹
// MCP: browser_click → getByTitle('文件夹名')
// 或: page.locator('tbody').getByTitle('文件夹名').click()

// ============================================================
// Step 2: 搜索定位目标文件/文件夹
// ============================================================
// MCP: browser_click → getByRole('textbox', { name: '搜索全部文件' })
// MCP: browser_type → 填入文件名关键词
// MCP: browser_press_key → Enter
// URL 变为 /list#/list/search?key=...

// ============================================================
// Step 3: 勾选目标文件
// ============================================================
// MCP: browser_click → 目标文件行的 checkbox (tbody 中对应行的第一个 cell)
// 勾选后顶部工具栏出现: 下载 | 分享 | 删除 | 重命名 | 移动到...
// 可使用 browser_snapshot 确认选中状态 (checkbox [checked])

// ============================================================
// Step 4: 点击工具栏"下载"按钮
// ============================================================
// MCP: browser_click → getByRole('button', { name: '下载' })
// 注意: 是勾选文件后顶部工具栏出现的下载按钮，不是文件行内的下载链接
// 触发后 Playwright 会开始下载，事件日志中显示 "Downloading file..."

// ============================================================
// Step 5: 等待下载完成并移动到目标目录
// ============================================================
// 下载文件保存在 .playwright-mcp/ 目录 (相对于项目 CWD)。
// Playwright 完成后会在控制台打印 "Download completed: <filename>"。
//
// 5a. 定位下载文件:
//   PowerShell: Get-ChildItem -Path ".playwright-mcp" -Name
//   Bash: ls -t .playwright-mcp/ | head -1
//
// 5b. 移动到 destDir:
//   destDir 默认 ~/Desktop，用户可通过 @inputs 指定自定义路径。
//   PowerShell: Move-Item -Path ".playwright-mcp/<filename>" -Destination "<destDir>/<filename>" -Force
//   Bash: mv ".playwright-mcp/<filename>" "<destDir>/<filename>"
//
// 5c. 验证:
//   PowerShell: Get-ChildItem "<destDir>/<filename>" | Select-Object Name, Length
//   Bash: ls -lh "<destDir>/<filename>"

// ============================================================
// 已知问题
// ============================================================
// 1. 账号封禁提示（页面底部"账号涉嫌违规已被封禁"）通常不影响文件浏览和下载
// 2. 下载 API (drive-pc.quark.cn) 在沙箱环境中可能 ERR_CONNECTION_CLOSED，
//    但 Playwright 的 download 事件仍可能成功获取文件
// 3. 如需上传文件，使用页面顶部"上传文件"按钮 (getByRole('button', { name: '上传文件' }))

// ============================================================
// 分享链接 vs 主站登录
// ============================================================
// 分享链接 (https://pan.quark.cn/s/{shareId}):
//   - 无需登录即可查看文件列表
//   - 页面显示"去客户端查看"按钮，下载按钮隐藏在 hover 菜单中
//   - 下载方式: hover 文件行 → 出现 .share-hover-menu-download 图标 → 点击触发下载
//   - 可用 browser_evaluate 提取文件列表信息用于展示
//
// 主站登录 (https://pan.quark.cn/ → 登录后跳转 /list):
//   - 需要用户已在浏览器登录过夸克
//   - 支持文件勾选 → 工具栏下载（会触发 Playwright download 事件）
//   - 下载文件保存到 .playwright-mcp/ 目录

// ============================================================
// 分享链接下载流程（Hover-to-Reveal 技巧）
// ============================================================
// 夸克分享链接页面的下载按钮默认隐藏，只有 hover 文件行后才出现。
// 工具栏"下载"按钮（勾选文件后出现）在分享链接页面也不可用，
// 因为未登录状态下没有勾选 checkbox。
//
// 操作步骤:
//
//   Step S1: 获取文件列表（可选，确认文件名）
//     browser_evaluate → listCurrentFiles() 或手动查看 snapshot
//
//   Step S2: Hover 文件行触发下载按钮
//     browser_run_code_unsafe →
//       const fileRow = page.locator('tr').filter({ hasText: '<文件名>' }).first();
//       await fileRow.hover();
//       await page.waitForTimeout(500);  // 等待 hover 菜单动画
//
//   Step S3: 点击下载图标
//     browser_run_code_unsafe →
//       await page.locator('.share-hover-menu-download').first().click();
//
//   Step S4: 处理可能弹出的"去客户端查看"提示
//     点击下载后可能弹出模态框引导安装客户端。关闭它:
//     browser_click → 模态框关闭按钮 (通常是 × 或"取消")
//
//   Step S5: 等待下载并移动文件 → 见下方 Step 5
//
// 注意: 分享链接下载会触发 Playwright 的 download 事件，
//       文件保存到 .playwright-mcp/ 目录。

// ============================================================
// 快捷操作: 直接用 JS 提取当前文件夹中所有文件的 URL
// ============================================================
// MCP: browser_evaluate → 执行以下 JS 获取文件列表信息
function listCurrentFiles() {
  const rows = document.querySelectorAll('tbody tr');
  const files = [];
  rows.forEach(row => {
    const nameEl = row.querySelector('td:nth-child(2)');
    const sizeEl = row.querySelector('td:nth-child(3)');
    const dateEl = row.querySelector('td:nth-child(4)');
    if (nameEl && !nameEl.textContent.includes('拖拽/粘贴')) {
      files.push({
        name: nameEl.textContent.trim().split('\n')[0],
        size: sizeEl?.textContent.trim() || '-',
        date: dateEl?.textContent.trim() || '-',
      });
    }
  });
  return files;
}

```

### File: shared-scripts\tools\fsearch.sh
```
#!/usr/bin/env bash
# @tool:      fsearch
# @summary:   多引擎交叉搜索 —— curl 直搜 中英4引擎，不走 WebSearch/WebFetch
# @tags:      search, curl, 交叉验证, 多引擎
# @usage:     bash fsearch.sh "搜索关键词"
# @date:      2026-05-18
set +e

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
KEYWORD="$*"

if [ -z "$KEYWORD" ]; then
  echo "用法: fsearch <关键词>"
  exit 1
fi

ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$KEYWORD'''))")

echo "=== fsearch: $KEYWORD ==="
echo ""

# --- 中文1: Bing (中文搜索，保持关键词简短2-3个，年份数字和长尾词易漂移) ---
echo "--- [中] Bing ---"
curl -sL --max-time 10 "https://www.bing.com/search?q=${ENCODED}" \
  -H "User-Agent: ${UA}" | \
  python3 -c "
import sys, re, html
text = sys.stdin.read()
count = 0
for m in re.finditer(r'<h2[^>]*><a[^>]*href=\"([^\"]+)\"[^>]*>(.+?)</a>', text, re.DOTALL):
    title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
    title = html.unescape(title)
    print(f'{count+1}. {title}')
    print(f'   {m.group(1)}')
    print()
    count += 1
    if count >= 8:
        break
if count == 0:
    print('  (无结果或解析失败)')
"

echo ""

# --- 外文1: Startpage (背后 Google 结果，走 Clash 代理，curl 友好) ---
echo "--- [EN] Startpage ---"
CLASH_PROXY="${CLASH_PROXY:-http://127.0.0.1:7897}"
curl -sL --max-time 10 --proxy "$CLASH_PROXY" \
  "https://www.startpage.com/sp/search?query=${ENCODED}&lang=english" \
  -H "User-Agent: ${UA}" 2>/dev/null | \
  python3 -c "
import sys, re, html as hmod
t = sys.stdin.read()
count = 0
# 提取有 URL 的链接，过滤掉导航/样式链接
seen = set()
for m in re.finditer(r'<a[^>]*href=\"(https?://[^\"]+)\"[^>]*>(.+?)</a>', t, re.DOTALL):
    url = m.group(1)
    title = hmod.unescape(re.sub(r'<[^>]+>', '', m.group(2)).strip())
    # 跳过内链、样式、空标题、CSS泄漏
    if 'startpage.com' in url or len(title) < 10 or url in seen:
        continue
    if '{' in title or '.css-' in title:
        continue
    if title.startswith('http://') or title.startswith('https://'):
        continue
    seen.add(url)
    print(f'{count+1}. {title[:120]}')
    print(f'   {url[:150]}')
    print()
    count += 1
    if count >= 8:
        break
if count == 0:
    print('  (Startpage 不可用，请确认 Clash 已开)')
"

echo ""

# --- 外文2: GitHub ---
echo "--- [EN] GitHub ---"
echo "(用 gh CLI 直搜: gh search repos --limit 10 \"$KEYWORD\")"
echo ""
echo "=== 交叉验证完成 ==="

```

### File: shared-scripts\utils\playwright-helpers.js
```
/**
 * @tool:      playwright-helpers
 * @summary:   Common Playwright browser automation helper utilities for Agent use
 * @tags:      playwright, browser, utils, helper
 * @mcp:       playwright
 * @inputs:    (various — see individual helpers below)
 * @output:    (various)
 *
 * 使用方式: Agent 调用 browser_evaluate 时，复制对应的 helper 函数代码执行。
 * 这些函数可直接在浏览器上下文中运行。
 */

// ============================================================
// angularClick(element) — 安全触发 Angular 元素点击
// 解决: Angular 的 (click) 绑定不会被原生 .click() 触发
// ============================================================
function angularClick(element) {
  element.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
  element.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
}

// ============================================================
// findByText(root, text) — 在容器内查找包含指定文本的叶子元素
// 用于: 找不到精确选择器时，通过文本定位元素
// ============================================================
function findByText(root, text) {
  return [...root.querySelectorAll('*')]
    .find(el => el.textContent.trim() === text && el.children.length === 0);
}

// ============================================================
// waitForSelector(selector, timeout) — Promise 版等待选择器
// ============================================================
function waitForSelector(selector, timeout = 5000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      const el = document.querySelector(selector);
      if (el) return resolve(el);
      if (Date.now() - start > timeout) return reject(new Error(`Timeout: ${selector}`));
      setTimeout(check, 100);
    };
    check();
  });
}

// ============================================================
// isVisible(el) — 检查元素是否在视口内可见
// ============================================================
function isVisible(el) {
  if (!el) return false;
  const style = getComputedStyle(el);
  if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
  const rect = el.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

// ============================================================
// dismissDialog(confirm) — 处理确认对话框
// ============================================================
function dismissDialog(confirm = true) {
  const btn = document.querySelector(
    confirm ? '.dialog-container .confirm' : '.dialog-container .cancel'
  );
  if (btn) btn.click();
  return !!btn;
}

```

### File: shared-scripts\zlib\download-book.js
```
/**
 * @tool:      zlib-download-book
 * @summary:   从 Z-Library 镜像站搜索并下载电子书 (PDF/EPUB/MOBI/AZW3)
 * @tags:      zlib, z-library, ebook, download, book, playwright, browser
 * @mcp:       playwright
 * @inputs:    query (string) - 书名/作者/ISBN 搜索关键词
 * @inputs:    format (string, optional) - 首选格式: pdf/epub/mobi/azw3，默认 epub
 * @inputs:    site (string, optional) - 指定站点URL，不传则自动尝试已知镜像列表
 * @output:    { success, filePath, title, format, site }
 *
 * 使用方式: Agent 读取此脚本中的步骤和 JS 代码片段，通过 Playwright MCP 工具执行。
 * 已验证站点: zh.ddd101.ru (2026-05-15)
 */

// ============================================================
// 已知 Z-Library 镜像列表（按优先级排列）
// ============================================================
const KNOWN_MIRRORS = [
  "https://zh.z-lib.today/",
  "https://zh.ddd101.ru/",
  "https://zbc.allfree.me/",
  "https://singlelogin.re/",
  "https://z-library.sk/",
];

// ============================================================
// Step 1: 选择站点并导航到首页
// ============================================================
// MCP: browser_navigate → 站点 URL（从 KNOWN_MIRRORS 依次尝试）
// 验证: 页面 title 包含 "Z-Library"
// 选择器验证:
//   - 搜索输入框: input[type="text"]
//   - 搜索按钮: button:has-text("搜索")
//   - 页面结构: 有 "最受欢迎" 区块 (含 /book/ 链接)

function step1_checkPageLoaded() {
  const hasSearchBox = !!document.querySelector('input[type="text"]');
  const hasBookLinks = !!document.querySelector('a[href*="/book/"]');
  return {
    title: document.title,
    url: location.href,
    hasSearchBox,
    hasBookLinks,
    ok: hasSearchBox && hasBookLinks
  };
}

// ============================================================
// Step 2: 执行搜索
// ============================================================
// 关键: 用 Enter 键提交，而非点击搜索按钮 (按钮点击被站点拦截)
// 方法: browser_run_code_unsafe 执行以下 JS
//
// async (page) => {
//   const searchInput = page.locator('input[type="text"]').first();
//   await searchInput.fill('<QUERY>');
//   await page.waitForTimeout(200);
//   await searchInput.press('Enter');
//   await page.waitForTimeout(4000);
// }
//
// 搜索后 URL 变为: /s/<encoded-query>
// 页面 title 变为: "<query>：在 Z-Library 上搜索"

// ============================================================
// Step 3: 解析搜索结果列表
// ============================================================
// 执行时机: 搜索后等待 3-4 秒让结果加载完成
// 结果结构:
//   - 每个结果项是一个 <a href="/book/<hash>/<slug>.html"> 包含:
//       - 书名 (generic > generic > generic: 书名)
//       - 作者 (generic > generic: 作者)
//       - 封面图 (img)
//   - 结果项下方有详细信息块:
//       - 出版社链接 (/publisher/...)
//       - 作者链接 (/author/...)
//       - 年/语言/文件大小
//   - 排序: "最受欢迎" / "列表"
//   - 分类过滤: "书籍 (N)" / "文章 (N)"

function step3_parseResults() {
  // 策略: 只提取 /book/ 链接作为结果，排除 publisher/author/category 等非书籍链接
  const bookLinks = document.querySelectorAll('a[href*="/book/"]');
  const seen = new Set();
  const books = [];

  bookLinks.forEach(a => {
    const href = a.getAttribute('href');
    // 只保留 /book/<hash>/<slug>.html 格式的主链接
    if (!href || !/^\/book\/[^/]+\//.test(href)) return;
    if (seen.has(href)) return;
    seen.add(href);

    const text = a.textContent.trim();
    // 跳过太短或明显不是书名的（如 "已下载" 这种纯状态文本）
    if (text.length < 2 || text === '已下载') return;

    // 尝试从父级/兄弟元素提取作者信息
    const parent = a.closest('[class]') || a.parentElement;
    const authorEl = parent?.querySelector('a[href*="/author/"]');
    const author = authorEl ? authorEl.textContent.trim() : '';

    // 提取文件格式信息
    const container = a.closest('generic') || parent;
    const fullText = container?.textContent || '';
    const formatMatch = fullText.match(/(EPUB|PDF|MOBI|AZW3|FB2|TXT|RTF)/gi);
    const formats = formatMatch ? [...new Set(formatMatch)] : [];
    const sizeMatch = fullText.match(/(\d+\.?\d*\s*(MB|KB|GB))/i);
    const size = sizeMatch ? sizeMatch[1] : '';

    books.push({
      title: text,
      href,
      author,
      formats,
      size,
      fullUrl: new URL(href, location.origin).href
    });
  });

  return {
    total: books.length,
    books: books.slice(0, 30),
    pageUrl: location.href
  };
}

// ============================================================
// Step 4: 进入书籍详情页，选择格式
// ============================================================
// MCP: browser_navigate → 选中的书籍 URL (完整地址)
// 详情页结构:
//   - 主下载链接: a[href*="/dl/"]  (初始显示默认格式)
//   - 格式下拉: button:has-text("Toggle Dropdown")
//   - 下拉菜单项: <a> 标签无 href，JS 驱动，格式如 "pdf 7.48 MB"
//   - "发送到" 按钮: button:has-text("发送到")
//   - "线上阅读" 链接: 含 /reader/ URL
//
// 选择格式的方法:
//   async (page, preferredFormat) => {
//     // 点击 Toggle Dropdown 展开格式列表
//     await page.locator('button:has-text("Toggle Dropdown")').click();
//     await page.waitForTimeout(500);
//     // 找到匹配格式的选项
//     const formatItem = page.locator('a').filter({ hasText: new RegExp(preferredFormat, 'i') }).first();
//     if (await formatItem.count() > 0) {
//       await formatItem.click();
//       await page.waitForTimeout(500);
//     }
//     // 获取更新后的下载链接
//     const dlLink = await page.locator('a[href*="/dl/"]').first().getAttribute('href');
//     return dlLink;
//   }

function step4_checkDetailPage() {
  const dlLink = document.querySelector('a[href*="/dl/"]');
  const toggleBtn = document.querySelector('button');
  const formatText = dlLink?.textContent?.trim() || '';

  return {
    title: document.title,
    url: location.href,
    downloadUrl: dlLink?.getAttribute('href') || '',
    currentFormat: formatText,
    hasToggleDropdown: !!document.querySelector('button:has-text("Toggle Dropdown")')
  };
}

// ============================================================
// Step 5: 触发下载
// ============================================================
// 方法1 (推荐): 直接导航到 /dl/<hash> URL
//   浏览器自动触发下载，Playwright 捕获 download 事件
//
//   async (page) => {
//     const dlHref = await page.locator('a[href*="/dl/"]').first().getAttribute('href');
//     await page.goto(new URL(dlHref, page.url()).href);
//     // 下载会自动开始，page.goto 会报 "Download is starting" 错误（正常）
//   }
//
// 方法2: 点击下载链接
//   const [download] = await Promise.all([
//     page.waitForEvent('download'),
//     page.locator('a[href*="/dl/"]').first().click()
//   ]);
//   await download.saveAs(path);
//
// 方法3: 用 fetch + 保存 (如果上述方法不适用)
//   但 fetch 可能无法携带浏览器 cookie

// ============================================================
// 辅助: 格式下拉列表解析
// ============================================================
function step4b_parseFormatDropdown() {
  // 在点击 Toggle Dropdown 后调用
  const formatItems = document.querySelectorAll('a');
  const formats = [];
  const formatPattern = /^(pdf|epub|mobi|azw3|fb2|txt|rtf)\s+([\d.]+)\s*(MB|KB|GB)/i;

  formatItems.forEach(a => {
    const text = a.textContent.trim().toLowerCase();
    const match = text.match(formatPattern);
    if (match) {
      formats.push({
        format: match[1].toUpperCase(),
        size: parseFloat(match[2]),
        unit: match[3],
        text: a.textContent.trim()
      });
    }
  });

  // 转换选项 (FB2, PDF, MOBI, TXT, RTF — 这些是转换而非原始文件)
  const convertItems = document.querySelectorAll('a[href="javascript:void(0);"]');
  const conversions = [...convertItems].map(a => a.textContent.trim()).filter(t => /^(FB2|PDF|MOBI|TXT|RTF)$/i.test(t));

  return { formats, conversions };
}

// ============================================================
// 完整流程示例代码 (Agent 使用 browser_run_code_unsafe)
// ============================================================

/*
// === 完整搜索+下载流程 ===
// 输入: query, preferredFormat

// 1. 导航到镜像站
await page.goto('https://zh.ddd101.ru/');
await page.waitForTimeout(2000);

// 2. 搜索 (如需特定格式，可在 query 中附加格式名: "三体 pdf")
const searchQuery = preferredFormat ? `${query} ${preferredFormat}` : query;
const searchInput = page.locator('input[type="text"]').first();
await searchInput.fill(searchQuery);
await page.waitForTimeout(200);
await searchInput.press('Enter');
await page.waitForTimeout(4000);

// 3. 解析结果
const results = await page.evaluate(() => {
  const bookLinks = document.querySelectorAll('a[href*="/book/"]');
  const seen = new Set();
  const books = [];
  bookLinks.forEach(a => {
    const href = a.getAttribute('href');
    if (!href || !/^\/book\/[^/]+\//.test(href)) return;
    if (seen.has(href)) return;
    seen.add(href);
    const text = a.textContent.trim();
    if (text.length < 2 || text === '已下载') return;
    books.push({ title: text, href });
  });
  return books.slice(0, 30);
});

// 4. 找到最匹配的结果 (Agent 智能选择，考量标题匹配度和格式匹配度)
const bestMatch = results[0];

// 5. 进入详情页
await page.goto(new URL(bestMatch.href, page.url()).href);
await page.waitForTimeout(2000);

// 6. 可选: 展开格式下拉查看可用格式
//    注意: 格式下拉项为混淆 JS 驱动 (onclick=_0x371adf)，自动化点击不可靠
//    如需切换格式，建议回到搜索页选择已有目标格式的书籍条目
//    await page.locator('button:has-text("Toggle Dropdown")').click();

// 7. 触发下载 (使用当前默认格式)
const dlHref = await page.locator('a[href*="/dl/"]').first().getAttribute('href');
await page.goto(new URL(dlHref, page.url()).href);
// 下载会自动开始，Playwright 捕获 download 事件
*/

```

### File: shared-scripts\zsxq\delete-article.js
```
/**
 * @tool:      zsxq-delete-article
 * @summary:   Delete a published article from 知识星球 (zsxq) via Playwright browser automation
 * @tags:      zsxq, 知识星球, delete, article, playwright, browser
 * @mcp:       playwright
 * @inputs:    groupId (string) - 星球 ID, e.g. "88882145181552"
 * @inputs:    articleId (string) - 文章 ID, e.g. "06suceh9urnx"
 * @output:    void
 *
 * 使用方式: Agent 读取此脚本中的步骤和 JS 代码片段，通过 Playwright MCP 工具执行。
 *
 * 前置条件: 已登录知识星球网页版 wx.zsxq.com
 */

// ============================================================
// Step 1: 导航到星球主页
// ============================================================
// MCP: browser_navigate → https://wx.zsxq.com/group/{groupId}
// 等待页面加载完成，确认文章标题可见

// ============================================================
// Step 2: 点击目标文章的"查看详情"按钮
// ============================================================
// MCP: browser_evaluate → 执行以下 JS
function step2_clickDetail(articleId) {
  const link = document.querySelector(`a.link-of-topic[href*="${articleId}"]`);
  if (!link) return { error: "未找到文章链接" };
  const topicContainer = link.closest('.topic-container');
  const detailBtn = [...topicContainer.querySelectorAll('*')]
    .find(el => el.textContent.trim() === '查看详情' && el.children.length === 0);
  if (!detailBtn) return { error: "未找到查看详情按钮" };
  detailBtn.click();
  return { success: true };
}

// ============================================================
// Step 3: 打开右上角管理菜单（三点图标）
// ============================================================
// 注意: .topic-detail-panel 不会出现在 Playwright accessibility snapshot 中，
// 必须用 JS 操作 DOM。
// MCP: browser_evaluate → 执行以下 JS
function step3_openMenu() {
  const panel = document.querySelector('.topic-detail-panel');
  if (!panel) return { error: "未找到详情面板，请确认 Step 2 已成功" };
  const icon = panel.querySelector('.operation-top .icon');
  if (!icon) return { error: "未找到管理菜单图标" };
  // 必须用 dispatchEvent 而非 click()，因为 Angular 事件绑定
  icon.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  icon.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
  icon.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
  return { success: true };
}
// 执行后等待 ~500ms 让 Angular 渲染下拉菜单

// ============================================================
// Step 4: 点击"删除"菜单项
// ============================================================
// MCP: browser_evaluate → 执行以下 JS
function step4_clickDelete() {
  const deleteItem = document.querySelector('.topic-operation-container .item.delete');
  if (!deleteItem) return { error: "未找到删除菜单项，菜单可能已消失" };
  deleteItem.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  deleteItem.click();
  return { success: true };
}

// ============================================================
// Step 5: 确认删除
// ============================================================
// 确认对话框 .dialog-container 会出现
// MCP: browser_click → selector: ".dialog-container .confirm"
// 或 MCP: browser_evaluate → document.querySelector('.dialog-container .confirm').click()

// ============================================================
// Step 6: 验证删除成功
// ============================================================
// MCP: browser_evaluate → 执行以下 JS
function step6_verify(articleId) {
  const gone = !document.querySelector(`a[href*="${articleId}"]`);
  return { deleted: gone };
}

```

### File: shared-scripts\zsxq\publish-article.js
```
/**
 * @tool:      zsxq-publish-article
 * @summary:   Publish a new article to 知识星球 (zsxq) via Playwright browser automation
 * @tags:      zsxq, 知识星球, publish, article, playwright, browser
 * @mcp:       playwright
 * @inputs:    groupId (string) - 星球 ID
 * @inputs:    title (string) - 文章标题，最大 60 字符
 * @inputs:    content (string) - 文章正文（Markdown 或纯文本），最大 100000 字符
 * @inputs:    tags (string[], optional) - 标签列表
 * @inputs:    useMarkdown (boolean, optional) - 是否使用 Markdown 模式，默认 false
 * @output:    {articleId: string, url: string}
 *
 * 使用方式: Agent 读取此脚本中的步骤和 JS 代码片段，通过 Playwright MCP 工具执行。
 *
 * 前置条件: 已登录知识星球网页版 wx.zsxq.com
 */

// ============================================================
// Step 1: 导航到星球主页
// ============================================================
// MCP: browser_navigate → https://wx.zsxq.com/group/{groupId}
// 等待页面加载完成

// ============================================================
// Step 2: 点击"写文章"按钮
// ============================================================
// MCP: browser_click → target: "text=写文章"
// 此操作会在新标签页打开文章编辑器
// 编辑器 URL: https://wx.zsxq.com/article?groupId={groupId}

// ============================================================
// Step 3: 切换到编辑器标签页
// ============================================================
// MCP: browser_tabs → select → index: 1 (新打开的标签页)

// ============================================================
// Step 4: 填写标题
// ============================================================
// 标题输入框选择器: textbox[placeholder="请在这里输入标题"]
// MCP: browser_type → target: 'textbox[placeholder="请在这里输入标题"]' → text: title
// 注意: 标题最大 60 字符

// ============================================================
// Step 5: 填写正文
// ============================================================
// 两种模式可选:

// --- 模式 A: 富文本模式（默认） ---
// 正文区域: .ProseMirror 或 "从这里开始输入正文"
// MCP: browser_type → target: ".ProseMirror" → text: content
// 或 MCP: browser_click → target: "text=从这里开始输入正文" → 然后 browser_type

// --- 模式 B: Markdown 模式 ---
// 先切换到 Markdown 模式:
// MCP: browser_click → target: "text=切换到 Markdown 模式"
// 然后粘贴内容:
// MCP: browser_type → target: ".ProseMirror" → text: content

// ============================================================
// Step 6: 添加标签（可选）
// ============================================================
// MCP: browser_click → target: "text=添加标签"
// 然后在弹出的标签选择器中点击对应标签

// ============================================================
// Step 7: 设置定时发布（可选）
// ============================================================
// 勾选"定时发布"复选框，设置发布时间

// ============================================================
// Step 8: 发布
// ============================================================
// MCP: browser_click → target: "text=发布"

// ============================================================
// 快捷发布路径（主页内嵌编辑器，用于需要上传附件的场景）
// ============================================================
// 入口: 主页"点击发表主题..."区域
// 特点: 支持上传文件，但不支持富文本排版和 Markdown 模式
// 添加标签: .post-topic-footer .tag (可能被预览层遮挡，需 browser_evaluate + dispatchEvent)

// ============================================================
// 验证发布结果
// ============================================================
// 发布后文章 URL 格式: https://articles.zsxq.com/id_{articleId}.html
// 可在 "我的文章" 中查看已发布列表

```

### File: skills\scrapling\examples\01_fetcher_session.py
```
"""
Example 1: Python - FetcherSession (persistent HTTP session with Chrome TLS fingerprint)

Scrapes all 10 pages of quotes.toscrape.com using a single HTTP session.
No browser launched - fast and lightweight.

Best for: static or semi-static sites, APIs, pages that don't require JavaScript.
"""

from scrapling.fetchers import FetcherSession

all_quotes = []

with FetcherSession(impersonate="chrome") as session:
    for i in range(1, 11):
        page = session.get(
            f"https://quotes.toscrape.com/page/{i}/",
            stealthy_headers=True,
        )
        quotes = page.css(".quote .text::text").getall()
        all_quotes.extend(quotes)
        print(f"Page {i}: {len(quotes)} quotes (status {page.status})")

print(f"\nTotal: {len(all_quotes)} quotes\n")
for i, quote in enumerate(all_quotes, 1):
    print(f"{i:>3}. {quote}")

```

### File: skills\scrapling\examples\02_dynamic_session.py
```
"""
Example 2: Python - DynamicSession (Playwright browser automation, visible)

Scrapes all 10 pages of quotes.toscrape.com using a persistent browser session.
The browser window stays open across all page requests for efficiency.

Best for: JavaScript-heavy pages, SPAs, sites with dynamic content loading.

Set headless=True to run the browser hidden.
Set disable_resources=True to skip loading images/fonts for a speed boost.
"""

from scrapling.fetchers import DynamicSession

all_quotes = []

with DynamicSession(headless=False, disable_resources=True) as session:
    for i in range(1, 11):
        page = session.fetch(f"https://quotes.toscrape.com/page/{i}/")
        quotes = page.css(".quote .text::text").getall()
        all_quotes.extend(quotes)
        print(f"Page {i}: {len(quotes)} quotes (status {page.status})")

print(f"\nTotal: {len(all_quotes)} quotes\n")
for i, quote in enumerate(all_quotes, 1):
    print(f"{i:>3}. {quote}")

```

### File: skills\scrapling\examples\03_stealthy_session.py
```
"""
Example 3: Python - StealthySession (Patchright stealth browser, visible)

Scrapes all 10 pages of quotes.toscrape.com using a persistent stealth browser session.
Bypasses anti-bot protections automatically (Cloudflare Turnstile, fingerprinting, etc.).

Best for: well-protected sites, Cloudflare-gated pages, sites that detect Playwright.

Set headless=True to run the browser hidden.
Add solve_cloudflare=True to auto-solve Cloudflare challenges.
"""

from scrapling.fetchers import StealthySession

all_quotes = []

with StealthySession(headless=False) as session:
    for i in range(1, 11):
        page = session.fetch(f"https://quotes.toscrape.com/page/{i}/")
        quotes = page.css(".quote .text::text").getall()
        all_quotes.extend(quotes)
        print(f"Page {i}: {len(quotes)} quotes (status {page.status})")

print(f"\nTotal: {len(all_quotes)} quotes\n")
for i, quote in enumerate(all_quotes, 1):
    print(f"{i:>3}. {quote}")

```

### File: skills\scrapling\examples\04_spider.py
```
"""
Example 4: Python - Spider (auto-crawling framework)

Scrapes ALL pages of quotes.toscrape.com by following "Next" pagination links
automatically. No manual page looping needed.

The spider yields structured items (text + author + tags) and exports them to JSON.

Best for: multi-page crawls, full-site scraping, anything needing pagination or
link following across many pages.

Outputs:
  - Live stats to terminal during crawl
  - Final crawl stats at the end
  - quotes.json in the current directory
"""

from scrapling.spiders import Spider, Response


class QuotesSpider(Spider):
    name = "quotes"
    start_urls = ["https://quotes.toscrape.com/"]
    concurrent_requests = 5  # Fetch up to 5 pages at once

    async def parse(self, response: Response):
        # Extract all quotes on the current page
        for quote in response.css(".quote"):
            yield {
                "text": quote.css(".text::text").get(),
                "author": quote.css(".author::text").get(),
                "tags": quote.css(".tags .tag::text").getall(),
            }

        # Follow the "Next" button to the next page (if it exists)
        next_page = response.css(".next a")
        if next_page:
            yield response.follow(next_page[0].attrib["href"])


if __name__ == "__main__":
    result = QuotesSpider().start()

    print(f"\n{'=' * 50}")
    print(f"Scraped : {result.stats.items_scraped} quotes")
    print(f"Requests: {result.stats.requests_count}")
    print(f"Time    : {result.stats.elapsed_seconds:.2f}s")
    print(f"Speed   : {result.stats.requests_per_second:.2f} req/s")
    print(f"{'=' * 50}\n")

    for i, item in enumerate(result.items, 1):
        print(f"{i:>3}. [{item['author']}] {item['text']}")
        if item["tags"]:
            print(f"       Tags: {', '.join(item['tags'])}")

    # Export to JSON
    result.items.to_json("quotes.json", indent=True)
    print("\nExported to quotes.json")

```

### File: tools\browser\helpers\node-helpers.js
```
/**
 * @tool:      node-helpers (CommonJS)
 * @summary:   Node.js 端辅助函数 — 供 cdp-proxy 或其他 Node 脚本 require 使用
 * @tags:      browser, utils, helper, nodejs
 * @module:    commonjs
 *
 * 注意: 本文件为 CommonJS 模块（require / module.exports），
 *       因为会被 cdp-proxy-playwright.mjs 通过 createRequire 加载。
 */

const fs = require('fs');
const path = require('path');

// ============================================================
// retryNavigation(page, url, maxRetries, delay)
// 带重试的页面导航，失败时自动重试
//
// 参数:
//   page       — Playwright Page 对象
//   url        — 目标 URL
//   maxRetries — 最大重试次数（默认 3）
//   delay      — 重试间隔毫秒数（默认 2000）
//
// 返回: Promise<void>
// 抛出: 所有重试失败后 throw 最后一次的错误
// ============================================================
async function retryNavigation(page, url, maxRetries = 3, delay = 2000) {
  let lastError = null;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      await page.goto(url, {
        waitUntil: 'domcontentloaded',
        timeout: 15000,
      });
      return; // 成功，退出
    } catch (e) {
      lastError = e;
      if (attempt < maxRetries) {
        // 等待后重试
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }

  // 所有重试均失败
  throw new Error(
    `retryNavigation 失败: 在 ${maxRetries} 次尝试后无法导航到 ${url}。最后错误: ${lastError.message}`
  );
}

// ============================================================
// randomDelay(minMs, maxMs)
// 随机延迟，模拟人类操作间隔
//
// 参数:
//   minMs — 最小延迟毫秒数（默认 500）
//   maxMs — 最大延迟毫秒数（默认 2000）
//
// 返回: Promise<void>，在随机时间后 resolve
// ============================================================
function randomDelay(minMs = 500, maxMs = 2000) {
  const delay = Math.floor(Math.random() * (maxMs - minMs + 1)) + minMs;
  return new Promise(resolve => setTimeout(resolve, delay));
}

// ============================================================
// screenshotOnError(fn)
// 高阶函数 — 包装一个 async 函数，当它抛出异常时自动截图
//
// 用法:
//   const safeFn = screenshotOnError(page, myRiskyFunction);
//   await safeFn();
//
// 参数:
//   fn   — 要包装的 async 函数
//   page — Playwright Page 对象（第一个参数，通过闭包传入）
//
// 返回: 包装后的函数，行为与 fn 相同，但在抛异常前会截图
//
// 或者直接作为装饰器使用:
//   await screenshotOnError(page, async () => { ... });
// ============================================================
function screenshotOnError(page, fn) {
  // 支持两种调用方式:
  // 1. screenshotOnError(page, fn) — 直接包装
  // 2. screenshotOnError(page)(fn) — 柯里化（先传 page，返回装饰器）
  if (typeof page === 'object' && typeof fn === 'function') {
    // 方式 1: 直接调用
    return wrapWithScreenshot(page, fn);
  }
  if (typeof page === 'object' && fn === undefined) {
    // 方式 2: 柯里化，返回接收 fn 的装饰器
    return (fn) => wrapWithScreenshot(page, fn);
  }
  throw new Error('screenshotOnError: 参数类型错误，需要 page 对象和 fn 函数');
}

/**
 * 内部实现：包装函数，出错时截图后重新 throw
 */
async function wrapWithScreenshot(page, fn) {
  try {
    return await fn();
  } catch (error) {
    // 生成截图文件名
    const timestamp = Date.now();
    const screenshotPath = path.join(
      process.platform === 'win32' ? process.env.TEMP || 'C:\\Windows\\Temp' : '/tmp',
      `error-${timestamp}.png`
    );

    // 尝试截图
    try {
      await page.screenshot({ path: screenshotPath, type: 'png' });
      console.error(`[screenshotOnError] 异常截图已保存: ${screenshotPath}`);
    } catch (screenshotError) {
      console.error(`[screenshotOnError] 截图失败: ${screenshotError.message}`);
    }

    // 重新抛出原始错误
    throw error;
  }
}

// ============================================================
// 导出
// ============================================================
module.exports = {
  retryNavigation,
  randomDelay,
  screenshotOnError,
};

```

### File: tools\browser\helpers\playwright-helpers.js
```
/**
 * @tool:      playwright-helpers
 * @summary:   Common Playwright browser automation helper utilities for Agent use
 * @tags:      playwright, browser, utils, helper
 * @mcp:       playwright
 * @inputs:    (various — see individual helpers below)
 * @output:    (various)
 *
 * 使用方式: Agent 调用 browser_evaluate 时，复制对应的 helper 函数代码执行。
 * 这些函数可直接在浏览器上下文中运行。
 */

// ============================================================
// angularClick(element) — 安全触发 Angular 元素点击
// 解决: Angular 的 (click) 绑定不会被原生 .click() 触发
// ============================================================
function angularClick(element) {
  element.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
  element.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
  element.dispatchEvent(new MouseEvent('click', { bubbles: true }));
}

// ============================================================
// findByText(root, text) — 在容器内查找包含指定文本的叶子元素
// 用于: 找不到精确选择器时，通过文本定位元素
// ============================================================
function findByText(root, text) {
  return [...root.querySelectorAll('*')]
    .find(el => el.textContent.trim() === text && el.children.length === 0);
}

// ============================================================
// waitForSelector(selector, timeout) — Promise 版等待选择器
// ============================================================
function waitForSelector(selector, timeout = 5000) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      const el = document.querySelector(selector);
      if (el) return resolve(el);
      if (Date.now() - start > timeout) return reject(new Error(`Timeout: ${selector}`));
      setTimeout(check, 100);
    };
    check();
  });
}

// ============================================================
// isVisible(el) — 检查元素是否在视口内可见
// ============================================================
function isVisible(el) {
  if (!el) return false;
  const style = getComputedStyle(el);
  if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
  const rect = el.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

// ============================================================
// dismissDialog(confirm) — 处理确认对话框
// ============================================================
function dismissDialog(confirm = true) {
  const btn = document.querySelector(
    confirm ? '.dialog-container .confirm' : '.dialog-container .cancel'
  );
  if (btn) btn.click();
  return !!btn;
}

// ============================================================
// scrollToBottom(page, step, interval) — 平滑滚动到页面底部
// 用于: 触发懒加载内容、无限滚动页面
// 参数:
//   step     — 每步滚动的像素数（默认 300）
//   interval — 每步之间的间隔毫秒数（默认 500）
// 返回: Promise，到达底部时 resolve
// ============================================================
async function scrollToBottom(page, step = 300, interval = 500, maxIterations = 100) {
  let lastHeight = await page.evaluate(() => document.body.scrollHeight);
  let iterations = 0;
  while (iterations < maxIterations) {
    iterations++;
    await page.evaluate((s) => window.scrollBy(0, s), step);
    await new Promise(resolve => setTimeout(resolve, interval));
    const newHeight = await page.evaluate(() => document.body.scrollHeight);
    if (newHeight === lastHeight) break;
    lastHeight = newHeight;
  }
  return iterations;
}

// ============================================================
// extractTable(tableSelector) — 从表格元素提取结构化数据
// 用于: 抓取数据表格、价格列表等
// 参数:
//   tableSelector — CSS 选择器，定位目标 table 元素
// 返回: { headers: string[], rows: string[][] }
// ============================================================
function extractTable(tableSelector) {
  const table = document.querySelector(tableSelector);
  if (!table) {
    throw new Error(`未找到表格元素: ${tableSelector}`);
  }

  // 提取表头（优先 thead > tr > th，其次第一个 tr > th）
  const headers = [];
  const thead = table.querySelector('thead');
  const headerRow = thead
    ? thead.querySelector('tr')
    : table.querySelector('tr');

  if (headerRow) {
    const thCells = headerRow.querySelectorAll('th');
    if (thCells.length > 0) {
      thCells.forEach(th => headers.push(th.textContent.trim()));
    } else {
      // 没有 th，用第一行的 td 作为表头
      headerRow.querySelectorAll('td').forEach(td => headers.push(td.textContent.trim()));
    }
  }

  // 提取数据行
  const rows = [];
  const tbody = table.querySelector('tbody') || table;
  const dataRows = tbody.querySelectorAll('tr');

  // 确定从哪一行开始（跳过 thead 中的 headerRow）
  let startFrom = thead ? 0 : (headers.length > 0 ? 1 : 0);
  dataRows.forEach((tr, index) => {
    if (index < startFrom) return;
    // 跳过只有 th 的行（可能是 thead 里的）
    const cells = tr.querySelectorAll('td');
    if (cells.length === 0) return;

    const row = [];
    cells.forEach(td => row.push(td.textContent.trim()));
    if (row.length > 0) rows.push(row);
  });

  return { headers, rows };
}

// ============================================================
// safeFill(selector, value, timeout) — 安全填写输入框
// 用于: 自动填表时确保值正确写入
// 参数:
//   selector — CSS 选择器，定位目标输入框
//   value    — 要填入的值
//   timeout  — 超时毫秒数（默认 10000）
// 返回: Promise，填入成功时 resolve，超时时 reject
// ============================================================
async function safeFill(selector, value, timeout = 10000) {
  const startTime = Date.now();

  // 轮询等待元素出现
  let element = null;
  while (!element) {
    element = document.querySelector(selector);
    if (element) break;
    if (Date.now() - startTime > timeout) {
      throw new Error(`safeFill 超时: 等待元素 ${selector} 超过 ${timeout}ms`);
    }
    await new Promise(r => setTimeout(r, 100));
  }

  // 聚焦元素
  element.focus();

  // 清空已有内容
  element.value = '';
  element.dispatchEvent(new Event('input', { bubbles: true }));

  // 逐字符输入（模拟人类打字，带微小延迟）
  for (const char of value) {
    element.value += char;
    element.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 10)); // 10ms 字符间延迟
  }

  // 触发 change 事件（部分框架依赖 change 而非 input）
  element.dispatchEvent(new Event('change', { bubbles: true }));

  // 验证值是否正确填入
  const finalCheckStart = Date.now();
  while (element.value !== value) {
    if (Date.now() - finalCheckStart > 2000) {
      throw new Error(`safeFill 验证失败: 期望值 "${value}", 实际值 "${element.value}"`);
    }
    // 重新尝试填入
    element.value = value;
    element.dispatchEvent(new Event('input', { bubbles: true }));
    await new Promise(r => setTimeout(r, 50));
  }
}

```

### File: tools\browser\proxy\pw-multi.js
```
#!/usr/bin/env node
/**
 * Playwright MCP Multi-Instance Wrapper
 * 每个会话独立浏览器配置，多窗口互不干扰。
 */

const { spawn } = require('child_process');
const os = require('os');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');

const sessionId = crypto.randomBytes(4).toString('hex');
const instanceTag = `pw-mcp-${sessionId}`;
process.stderr.write(`[pw-multi] session=${sessionId} platform=${process.platform} tmpdir=${os.tmpdir()}\n`);

const tempRoot = path.join(os.tmpdir(), 'pw-mcp-instances');
fs.mkdirSync(tempRoot, { recursive: true });
process.stderr.write(`[pw-multi] tempRoot=${tempRoot}\n`);

// 清理 24h+ 残留
try {
  const now = Date.now();
  for (const name of fs.readdirSync(tempRoot)) {
    const p = path.join(tempRoot, name);
    try { if (fs.statSync(p).isDirectory() && (now - fs.statSync(p).mtimeMs > 86400000)) fs.rmSync(p, { recursive: true, force: true }); } catch {}
  }
} catch {}

const instanceDir = path.join(tempRoot, instanceTag);
const userDataDir = path.join(instanceDir, 'browser-data');
const outputDir = path.join(instanceDir, 'output');
fs.mkdirSync(userDataDir, { recursive: true });
fs.mkdirSync(outputDir, { recursive: true });
process.stderr.write(`[pw-multi] userDataDir=${userDataDir}\n`);
process.stderr.write(`[pw-multi] outputDir=${outputDir}\n`);

// Windows 上通过 cmd /c 调用 npx.cmd，避免 spawn 路径引号问题
const npxPath = path.join(path.dirname(process.execPath), 'npx.cmd');
const spawnArgs = [
  '/c', npxPath,
  '@playwright/mcp@latest',
  '--headless'
];

// 修复 bash/msys 环境中 TEMP/TMP 被设为 /tmp 导致路径异常
const env = { ...process.env };
if (process.platform === 'win32') {
  env.TEMP = env.TEMP || path.join(process.env.SystemRoot || 'C:\\Windows', 'Temp');
  env.TMP = env.TEMP;
  if (env.TMPDIR === '/tmp' || !env.TMPDIR) env.TMPDIR = env.TEMP;
}

process.stderr.write(`[pw-multi] spawning: cmd ${spawnArgs.join(' ')}\n`);
process.stderr.write(`[pw-multi] env.TEMP=${env.TEMP} env.TMP=${env.TMP} env.TMPDIR=${env.TMPDIR}\n`);
const child = spawn('cmd', spawnArgs, { stdio: 'inherit', env });

child.on('error', (err) => {
  process.stderr.write(`[pw-multi] ERROR: ${err.message}\n`);
  cleanup(); process.exit(1);
});
child.on('exit', (code) => {
  cleanup(); process.exit(code ?? 0);
});

function cleanup() {
  try { fs.rmSync(instanceDir, { recursive: true, force: true }); } catch {}
}

process.on('SIGINT', () => { try { child.kill('SIGINT'); } catch {} });
process.on('SIGTERM', () => { try { child.kill('SIGTERM'); } catch {} });

```

### File: tools\browser\proxy\start-proxy.sh
```
#!/usr/bin/env bash
# ============================================================
# start-proxy.sh — 一键启动 cdp-proxy
# 自动处理代理发现、NODE_PATH 探测、端口冲突检测
# 用法:
#   ./start-proxy.sh               # 默认端口 3456, headless
#   ./start-proxy.sh 3457          # 指定端口
#   ./start-proxy.sh 3456 false    # 指定端口, 显示浏览器窗口
#   ./start-proxy.sh 3456 true     # 指定端口, headless
# ============================================================

set -e

# --- 参数解析 ---
CDP_PORT="${1:-3456}"
CDP_HEADLESS="${2:-true}"

# --- 路径 ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTO_PROXY_SCRIPT="${SCRIPT_DIR}/auto-proxy.mjs"
CDP_PROXY_SCRIPT="${SCRIPT_DIR}/cdp-proxy-playwright.mjs"
PID_FILE="/tmp/cdp-proxy-${CDP_PORT}.pid"

# --- 颜色输出 ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[start-proxy]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[start-proxy]${NC} $1"; }
log_error() { echo -e "${RED}[start-proxy]${NC} $1"; }

# --- 步骤 1: 检查端口是否被占用 ---
check_port() {
    # Windows: 使用 netstat 检查端口
    if command -v netstat &>/dev/null; then
        if netstat -ano 2>/dev/null | grep -q ":${CDP_PORT} "; then
            return 1  # 端口被占用
        fi
    elif command -v ss &>/dev/null; then
        if ss -tlnp 2>/dev/null | grep -q ":${CDP_PORT} "; then
            return 1
        fi
    fi
    return 0  # 端口空闲
}

if ! check_port; then
    # 端口被占用，检查是否是已有的健康 cdp-proxy 实例
    if curl -s --max-time 2 "http://127.0.0.1:${CDP_PORT}/health" 2>/dev/null | grep -q '"ok"'; then
        log_info "cdp-proxy 已在端口 ${CDP_PORT} 运行"
        exit 0
    else
        log_error "端口 ${CDP_PORT} 被其他进程占用"
        log_error "请先释放端口或指定其他端口: $0 <端口号>"
        exit 1
    fi
fi

# --- 步骤 2: 探测 NODE_PATH ---
detect_node_path() {
    # 探测定制 npm 全局路径
    if [ -n "$NODE_PATH" ]; then
        echo "$NODE_PATH"
        return
    fi

    # 通过 npm root -g 获取
    local global_root
    global_root=$(npm root -g 2>/dev/null || echo "")

    if [ -n "$global_root" ] && [ -d "$global_root" ]; then
        echo "$global_root"
        return
    fi

    # Windows 常见路径
    if [ -d "$HOME/AppData/Roaming/npm/node_modules" ]; then
        echo "$HOME/AppData/Roaming/npm/node_modules"
        return
    fi

    # macOS/Linux 常见路径
    if [ -d "/usr/local/lib/node_modules" ]; then
        echo "/usr/local/lib/node_modules"
        return
    fi

    echo ""
}

NODE_PATH_DETECTED=$(detect_node_path)
if [ -n "$NODE_PATH_DETECTED" ]; then
    export NODE_PATH="$NODE_PATH_DETECTED"
    log_info "NODE_PATH: ${NODE_PATH}"
else
    log_warn "未能探测 NODE_PATH，Playwright 可能加载失败"
fi

# --- 步骤 3: 自动发现代理 ---
PROXY_URL=""
if [ -f "$AUTO_PROXY_SCRIPT" ]; then
    log_info "正在探测本地代理..."
    # 使用 Python 解析 JSON 输出（auto-proxy.mjs 输出 JSON 到 stdout）
    PROXY_JSON=$(node "$AUTO_PROXY_SCRIPT" --json 2>/dev/null || echo '{"proxy":null}')
    PROXY_URL=$(echo "$PROXY_JSON" | node -e "process.stdin.on('data',d=>{try{process.stdout.write(JSON.parse(d).proxy||'')}catch(e){}})" 2>/dev/null || echo "")

    if [ -n "$PROXY_URL" ]; then
        export CDP_PROXY_SERVER="$PROXY_URL"
        log_info "发现代理: ${PROXY_URL}"
    else
        log_info "未发现本地代理，使用直连"
    fi
else
    log_warn "auto-proxy.mjs 未找到，跳过代理发现"
fi

# --- 步骤 4: 检查脚本是否存在 ---
if [ ! -f "$CDP_PROXY_SCRIPT" ]; then
    log_error "cdp-proxy 脚本不存在: ${CDP_PROXY_SCRIPT}"
    exit 1
fi

# --- 步骤 5: 启动 cdp-proxy ---
export CDP_PROXY_PORT="$CDP_PORT"
export CDP_HEADLESS="$CDP_HEADLESS"

log_info "正在启动 cdp-proxy..."
log_info "  端口:     ${CDP_PORT}"
log_info "  Headless: ${CDP_HEADLESS}"
log_info "  代理:     ${PROXY_URL:-无}"

# 后台启动 cdp-proxy
node "$CDP_PROXY_SCRIPT" &
CDP_PID=$!

# 写入 PID 文件
echo "$CDP_PID" > "$PID_FILE"

# 等待 cdp-proxy 就绪（最多等 15 秒）
log_info "等待 cdp-proxy 就绪..."
WAIT_COUNT=0
while [ $WAIT_COUNT -lt 15 ]; do
    if curl -s --max-time 2 "http://127.0.0.1:${CDP_PORT}/health" 2>/dev/null | grep -q '"ok"'; then
        log_info "cdp-proxy 已启动: http://127.0.0.1:${CDP_PORT}"
        log_info "PID: ${CDP_PID} (文件: ${PID_FILE})"
        log_info "代理: ${PROXY_URL:+有 (${PROXY_URL})}${PROXY_URL:-无}"
        exit 0
    fi
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    # 检查进程是否还活着
    if ! kill -0 "$CDP_PID" 2>/dev/null; then
        log_error "cdp-proxy 进程意外退出"
        log_error "请检查 Playwright 是否安装: npm install -g playwright && npx playwright install chromium"
        exit 1
    fi
done

log_error "cdp-proxy 启动超时（${WAIT_COUNT}s）"
log_error "请手动检查: node ${CDP_PROXY_SCRIPT}"
exit 1

```

### File: tools\fetch\smart-fetch.sh
```
#!/usr/bin/env bash
# ============================================================
# smart-fetch.sh — 智能 URL 抓取脚本
# 自动选择最快可用的抓取路径：curl（直连/代理） → cdp-proxy（浏览器渲染）
# 用法:
#   ./smart-fetch.sh "https://目标URL"              # 自动选路径
#   ./smart-fetch.sh "https://目标URL" --force-curl  # 强制用 curl
#   ./smart-fetch.sh "https://目标URL" --force-cdp    # 强制用 cdp-proxy
#   ./smart-fetch.sh "https://目标URL" --json         # JSON 格式输出
# ============================================================

set -o pipefail

# --- 配置 ---
CDP_PROXY_HOST="127.0.0.1"
CDP_PROXY_PORT="${CDP_PROXY_PORT:-3456}"
CDP_PROXY_BASE="http://${CDP_PROXY_HOST}:${CDP_PROXY_PORT}"
CURL_TIMEOUT=15
CDP_WAIT_SEC=3
USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

# 脚本所在目录，用于定位 auto-proxy.mjs
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTO_PROXY_SCRIPT="${SCRIPT_DIR}/../browser/proxy/auto-proxy.mjs"

# --- 参数解析 ---
TARGET_URL=""
FORCE_CURL=false
FORCE_CDP=false
JSON_OUTPUT=false

for arg in "$@"; do
    case "$arg" in
        --force-curl) FORCE_CURL=true ;;
        --force-cdp)  FORCE_CDP=true ;;
        --json)       JSON_OUTPUT=true ;;
        -*)           echo "未知参数: $arg" >&2; exit 2 ;;
        *)            TARGET_URL="$arg" ;;
    esac
done

if [ -z "$TARGET_URL" ]; then
    echo "用法: $0 <URL> [--force-curl|--force-cdp] [--json]" >&2
    exit 2
fi

# --- 工具函数 ---

# 输出 JSON 结果到 stdout（--json 模式），同时写 stderr 供人类阅读
output_json() {
    local path="$1"       # curl | cdp-proxy | fallback
    local status="$2"     # ok | fail
    local time_ms="$3"
    local content="$4"    # 需要 JSON 转义的正文
    local error="$5"      # 错误信息（可选）

    # 用 Node 做 JSON 转义（避免 bash 手动拼接出错）
    node -e "
const result = {
  url: process.argv[1],
  path: process.argv[2],
  status: process.argv[3],
  time_ms: parseInt(process.argv[4], 10),
  content: process.argv[5],
};
if (process.argv[6]) result.error = process.argv[6];
process.stdout.write(JSON.stringify(result, null, 2));
" "$TARGET_URL" "$path" "$status" "$time_ms" "$content" "$error"
}

# 探测本地代理（调用 auto-proxy.mjs）
detect_proxy() {
    if [ ! -f "$AUTO_PROXY_SCRIPT" ]; then
        echo ""  # 脚本不存在，返回空
        return
    fi
    local result
    result=$(node "$AUTO_PROXY_SCRIPT" --json 2>/dev/null) || true
    # 提取 proxy 字段（格式: {"proxy":"http://127.0.0.1:7897",...}）
    echo "$result" | node -e "process.stdin.on('data',d=>{try{process.stdout.write(JSON.parse(d).proxy||'')}catch(e){}})" 2>/dev/null || echo ""
}

# 检查 cdp-proxy 是否存活
cdp_proxy_alive() {
    curl -s --max-time 2 "${CDP_PROXY_BASE}/health" 2>/dev/null | node -e "process.stdin.on('data',d=>{try{const o=JSON.parse(d);if(o.status==='ok')process.stdout.write('ok')}catch(e){}})" 2>/dev/null | grep -q ok
}

# --- 路径 1: curl 抓取 ---
try_curl() {
    local proxy="$1"
    local start_time
    start_time=$(node -e "console.log(Date.now())")

    local curl_args=(-s -L --max-time "$CURL_TIMEOUT" -H "User-Agent: $USER_AGENT")
    local proxy_label="直连"

    if [ -n "$proxy" ]; then
        curl_args+=(--proxy "$proxy")
        proxy_label="代理 ${proxy}"
    fi

    local http_code
    local content

    # 先获取 HTTP 状态码和内容
    local tmpfile
    tmpfile=$(mktemp) || tmpfile="/tmp/smart-fetch-$$.tmp"
    trap "rm -f '$tmpfile'" EXIT

    http_code=$(curl -s -o "$tmpfile" -w "%{http_code}" "${curl_args[@]}" "$TARGET_URL" 2>/dev/null) || true
    content=$(cat "$tmpfile" 2>/dev/null || true)
    rm -f "$tmpfile"

    local end_time
    end_time=$(node -e "console.log(Date.now())")
    local elapsed=$((end_time - start_time))

    # 判断结果
    if [ -z "$http_code" ] || [ "$http_code" = "000" ]; then
        # curl 完全失败（连接拒绝/DNS失败等）
        if $JSON_OUTPUT; then
            output_json "curl" "fail" "$elapsed" "" "HTTP $http_code, 连接失败 (${proxy_label})"
        else
            echo "[smart-fetch] curl 失败: HTTP $http_code, 连接失败 (${proxy_label})" >&2
        fi
        return 1
    fi

    if [ "$http_code" = "403" ]; then
        if $JSON_OUTPUT; then
            output_json "curl" "fail" "$elapsed" "" "HTTP 403 Forbidden (${proxy_label})"
        else
            echo "[smart-fetch] curl 被拒: HTTP 403 (${proxy_label})" >&2
        fi
        return 1
    fi

    # 检查是否包含 CAPTCHA 关键词
    if echo "$content" | grep -qiE '(captcha|verify you are human|请点击验证|滑块验证|请输入验证码)'; then
        if $JSON_OUTPUT; then
            output_json "curl" "fail" "$elapsed" "" "检测到 CAPTCHA (${proxy_label})"
        else
            echo "[smart-fetch] curl 遇到验证码 (${proxy_label})" >&2
        fi
        return 1
    fi

    # 检查内容是否为空或过短
    if [ -z "$content" ] || [ "${#content}" -lt 100 ]; then
        if $JSON_OUTPUT; then
            output_json "curl" "fail" "$elapsed" "" "内容为空或过短 (${#content} bytes, ${proxy_label})"
        else
            echo "[smart-fetch] curl 内容过短: ${#content} bytes (${proxy_label})" >&2
        fi
        return 1
    fi

    # 成功
    if $JSON_OUTPUT; then
        output_json "curl" "ok" "$elapsed" "$content" ""
    else
        echo "OK curl ${elapsed}ms" >&2
        echo "$content"
    fi
    return 0
}

# --- 路径 2: cdp-proxy 抓取 ---
try_cdp() {
    if ! cdp_proxy_alive; then
        if $JSON_OUTPUT; then
            output_json "cdp-proxy" "fail" "0" "" "cdp-proxy 未运行 (${CDP_PROXY_BASE})"
        else
            echo "[smart-fetch] cdp-proxy 未运行，无法使用浏览器路径" >&2
        fi
        return 1
    fi

    local start_time
    start_time=$(node -e "console.log(Date.now())")

    # 第一步：创建新页面
    local new_resp
    local ENCODED_URL
    ENCODED_URL=$(node -e "process.stdout.write(encodeURIComponent(process.argv[1]))" "$TARGET_URL")
    new_resp=$(curl -s --max-time 5 "${CDP_PROXY_BASE}/new?url=${ENCODED_URL}" 2>/dev/null) || true
    local target_id
    target_id=$(echo "$new_resp" | node -e "process.stdin.on('data',d=>{try{process.stdout.write(JSON.parse(d).targetId||'')}catch(e){}})" 2>/dev/null) || true

    if [ -z "$target_id" ]; then
        if $JSON_OUTPUT; then
            output_json "cdp-proxy" "fail" "$(($(node -e "console.log(Date.now())") - start_time))" "" "无法创建页面"
        else
            echo "[smart-fetch] cdp-proxy 无法创建页面" >&2
        fi
        return 1
    fi

    # 第二步：等待页面加载
    sleep "$CDP_WAIT_SEC"

    # 第三步：获取页面信息确认加载完成
    curl -s --max-time 5 "${CDP_PROXY_BASE}/info?target=${target_id}" >/dev/null 2>&1 || true

    # 第四步：通过 /eval 获取 body.innerText
    local content
    content=$(curl -s --max-time 10 -X POST "${CDP_PROXY_BASE}/eval?target=${target_id}" \
        -d 'document.body.innerText || document.body.textContent || ""' 2>/dev/null) || true

    # 解析 /eval 返回的 JSON: {"value": "..."}
    content=$(echo "$content" | node -e "process.stdin.on('data',d=>{try{process.stdout.write(JSON.parse(d).value||'')}catch(e){}})" 2>/dev/null) || true

    local end_time
    end_time=$(node -e "console.log(Date.now())")
    local elapsed=$((end_time - start_time))

    # 清理：关闭页面
    curl -s --max-time 3 "${CDP_PROXY_BASE}/close?target=${target_id}" >/dev/null 2>&1 || true

    if [ -z "$content" ] || [ "${#content}" -lt 50 ]; then
        if $JSON_OUTPUT; then
            output_json "cdp-proxy" "fail" "$elapsed" "" "内容为空或过短 (${#content} bytes)"
        else
            echo "[smart-fetch] cdp-proxy 内容过短: ${#content} bytes" >&2
        fi
        return 1
    fi

    if $JSON_OUTPUT; then
        output_json "cdp-proxy" "ok" "$elapsed" "$content" ""
    else
        echo "OK cdp-proxy ${elapsed}ms" >&2
        echo "$content"
    fi
    return 0
}

# --- 主流程 ---
main() {
    # 探测代理（除非强制 cdp 模式）
    local proxy=""
    if ! $FORCE_CDP; then
        proxy=$(detect_proxy)
        if [ -n "$proxy" ]; then
            echo "[smart-fetch] 检测到代理: ${proxy}" >&2
        else
            echo "[smart-fetch] 未检测到代理，使用直连" >&2
        fi
    fi

    # 路径选择：强制 curl
    if $FORCE_CURL; then
        if try_curl "$proxy"; then
            return 0
        fi
        echo "[smart-fetch] --force-curl 模式，curl 失败，不降级" >&2
        return 1
    fi

    # 路径选择：强制 cdp
    if $FORCE_CDP; then
        if try_cdp; then
            return 0
        fi
        # cdp 不可用时降级到 curl
        echo "[smart-fetch] cdp-proxy 不可用，降级到 curl" >&2
        if try_curl "$proxy"; then
            return 0
        fi
        echo "[smart-fetch] 所有路径均失败" >&2
        return 1
    fi

    # 自动路径：先 curl，失败再 cdp
    if try_curl "$proxy"; then
        return 0
    fi

    # curl 失败，尝试 cdp-proxy
    if cdp_proxy_alive; then
        echo "[smart-fetch] curl 失败，尝试 cdp-proxy" >&2
        if try_cdp; then
            return 0
        fi
    else
        echo "[smart-fetch] cdp-proxy 未运行，仅 curl 路径可用" >&2
    fi

    echo "[smart-fetch] 所有路径均失败: ${TARGET_URL}" >&2
    return 1
}

main

```

### File: tools\platform\bilibili\extract-links.js
```
/**
 * @tool: bilibili-extract-links
 * @tags: bilibili,link,extraction,playwright
 * @mcp: playwright
 * @inputs: page (Playwright Page), options { maxResults, scroll }
 * @output: Array<{href: string, title: string}>
 * @description: 从当前B站页面提取所有视频链接(BV号)，支持滚动加载更多
 *
 * 用法示例:
 *   const links = await extractBilibiliLinks(page, { maxResults: 100, scroll: true });
 *   writeToFile(linksToJson(links), 'links.json');
 *   writeToFile(linksToPlain(links), 'links.txt');
 */

/**
 * 从 B站页面提取所有视频链接
 * @param {import('playwright').Page} page - Playwright Page 对象
 * @param {{maxResults?: number, scroll?: boolean}} options
 * @returns {Promise<Array<{href: string, title: string}>>}
 */
async function extractBilibiliLinks(page, options = {}) {
  const { maxResults = 50, scroll = true } = options;
  const allLinks = [];
  let prevCount = 0;
  let staleCount = 0;

  while (allLinks.length < maxResults && staleCount < 3) {
    const newLinks = await page.evaluate(() => {
      const results = [];
      document.querySelectorAll('a[href*="/video/BV"]').forEach((a) => {
        const href = a.getAttribute('href');
        const card = a.closest('.bili-video-card');
        const titleEl = card?.querySelector('.bili-video-card__info--tit')
                     || a.querySelector('.bili-video-card__info--tit');
        const title = titleEl?.textContent?.trim() || '';
        if (href) {
          results.push({
            href: href.startsWith('http') ? href : 'https:' + href,
            title
          });
        }
      });
      return results;
    });

    for (const link of newLinks) {
      if (!allLinks.find((l) => l.href === link.href)) {
        allLinks.push(link);
      }
    }

    if (allLinks.length === prevCount) {
      staleCount++;
    } else {
      staleCount = 0;
    }
    prevCount = allLinks.length;

    if (scroll && allLinks.length < maxResults) {
      await page.evaluate(() => window.scrollBy(0, 800));
      await page.waitForTimeout(1500);
    }
  }

  return allLinks.slice(0, maxResults);
}

/**
 * 转为 JSON 字符串
 */
function linksToJson(links, source = '') {
  return JSON.stringify({
    source,
    extracted_at: new Date().toISOString().replace('T', ' ').substring(0, 19),
    total: links.length,
    videos: links
  }, null, 2);
}

/**
 * 转为纯文本链接列表
 */
function linksToPlain(links) {
  return links.map((l) => l.href).join('\n');
}

module.exports = { extractBilibiliLinks, linksToJson, linksToPlain };

```

### File: tools\platform\douyin\extract-links.js
```
/**
 * @tool: douyin-extract-links
 * @tags: douyin,link,extraction,playwright
 * @mcp: playwright
 * @inputs: page (Playwright Page), options { maxResults, scroll, type }
 * @output: Array<{href: string, title: string, author?: string, likes?: string, duration?: number}>
 * @description: 从当前抖音页面提取所有视频链接。搜索页走API拦截(aweme-id), 用户主页走DOM提取。支持滚动翻页去重。
 *
 * 实测发现:
 * - 抖音搜索使用 Lynx 框架渲染, DOM 中无传统 <a href="/video/..."> 标签
 * - 搜索结果通过 XHR → JSON 返回, aweme_id 在 business_data 深层嵌套
 * - 需 deviceScaleFactor:3 + isMobile:true 伪装移动端, 否则反爬拦截
 * - 用户主页/视频详情页可能有 DOM 链接, 双重策略覆盖
 *
 * 用法示例:
 *   // 搜索(API拦截模式)
 *   const links = await extractDouyinLinks(page, { type: 'search', keyword: '编程', maxResults: 100 });
 *   // 用户主页(DOM模式)
 *   const links = await extractDouyinLinks(page, { type: 'user', maxResults: 50 });
 *   // 直接解析 API 响应 JSON
 *   const links = extractDouyinFromApiJson(apiResponseJson);
 */

/**
 * 从抖音页面提取视频链接 - 主入口
 * @param {import('playwright').Page} page - Playwright Page 对象
 * @param {{maxResults?: number, scroll?: boolean, type?: 'search'|'user'|'topic', keyword?: string}} options
 * @returns {Promise<Array<{href:string, title:string, author?:string, likes?:string}>>}
 */
async function extractDouyinLinks(page, options = {}) {
  const { maxResults = 50, scroll = true, type = 'search' } = options;

  if (type === 'search') {
    return extractFromSearchPage(page, { maxResults, scroll });
  }

  // user/topic: DOM 提取 + 滚动翻页
  return extractFromDom(page, { maxResults, scroll, type });
}

/**
 * 搜索页: API拦截模式
 * 拦截 aweme/v2/search/msite/general/search/single/ → 解析 JSON → 提取 aweme_id
 * 滚动触发新 API 请求 → 循环拦截 → staleCount 退出
 */
async function extractFromSearchPage(page, { maxResults = 50, scroll = true }) {
  const videos = [];
  let prevCount = 0;
  let staleCount = 0;

  while (videos.length < maxResults && staleCount < 3) {
    let searchJson = null;

    const onResponse = async (response) => {
      const url = response.url();
      if (url.includes('/aweme/v2/search/') && url.includes('/single') && response.status() === 200) {
        try {
          const text = await response.text();
          if (text.length > 10000) searchJson = JSON.parse(text);
        } catch (e) {}
      }
    };

    page.on('response', onResponse);

    try {
      // 等待 API 响应
      for (let i = 0; i < 8 && !searchJson; i++) {
        await page.waitForTimeout(1500);
      }

      if (searchJson) {
        const parsed = parseSearchApiResponse(searchJson);
        const before = videos.length;
        mergeByVideoId(videos, parsed);

        if (videos.length === before) staleCount++;
        else staleCount = 0;
      } else {
        staleCount++;
      }
    } finally {
      page.off('response', onResponse);
    }

    prevCount = videos.length;

    // 滚动触发新一批 API 请求
    if (scroll && videos.length < maxResults) {
      await page.evaluate(() => {
        window.scrollBy({ top: 600 + Math.floor(Math.random() * 400), behavior: 'smooth' });
      });
      await page.waitForTimeout(1500 + Math.floor(Math.random() * 1500));
    }
  }

  return videos.slice(0, maxResults);
}

/**
 * DOM 模式: 遍历页面 a 标签 + shadow DOM (用户主页、话题页等)
 */
async function extractFromDom(page, { maxResults = 50, scroll = true, type = 'search' }) {
  const allLinks = [];
  let prevCount = 0;
  let staleCount = 0;

  while (allLinks.length < maxResults && staleCount < 3) {
    const newLinks = await page.evaluate((pageType) => {
      const results = [];

      // 深海遍历 shadow DOM
      function deepQueryAll(root, selector) {
        let found = [...root.querySelectorAll(selector)];
        root.querySelectorAll('*').forEach((el) => {
          if (el.shadowRoot) found = found.concat(deepQueryAll(el.shadowRoot, selector));
        });
        return found;
      }

      deepQueryAll(document, 'a[href*="/video/"]').forEach((a) => {
        const href = a.getAttribute('href');
        if (!href) return;

        const card = a.closest('[class*="card"]')
                  || a.closest('[class*="item"]')
                  || a.closest('li')
                  || a.closest('div');

        const titleEl = card?.querySelector('[class*="title"]')
                     || card?.querySelector('[class*="desc"]')
                     || a.querySelector('[class*="title"]');

        const authorEl = card?.querySelector('[class*="author"]')
                      || card?.querySelector('[class*="nickname"]')
                      || card?.querySelector('[class*="name"]');

        const title = titleEl?.textContent?.trim() || '';
        const author = authorEl?.textContent?.trim() || '';

        if (href) {
          results.push({
            href: href.startsWith('http') ? href : 'https://www.douyin.com' + href,
            title,
            author
          });
        }
      });
      return results;
    }, type);

    // 去重
    for (const link of newLinks) {
      const videoId = extractVideoId(link.href);
      if (videoId && !allLinks.find((l) => extractVideoId(l.href) === videoId)) {
        allLinks.push(link);
      } else if (!videoId && !allLinks.find((l) => l.href === link.href)) {
        allLinks.push(link);
      }
    }

    if (allLinks.length === prevCount) staleCount++;
    else staleCount = 0;
    prevCount = allLinks.length;

    if (scroll && allLinks.length < maxResults) {
      await page.evaluate(() => {
        window.scrollBy({ top: 600 + Math.floor(Math.random() * 400), behavior: 'smooth' });
      });
      await page.waitForTimeout(1500 + Math.floor(Math.random() * 1500));
    }
  }

  return allLinks.slice(0, maxResults);
}

/**
 * 解析抖音搜索 API 响应 JSON，提取视频列表
 * API: aweme/v2/search/msite/general/search/single/
 */
function parseSearchApiResponse(json) {
  const seen = new Set();
  const videos = [];

  function dig(obj, depth) {
    if (!obj || depth > 15) return;
    if (Array.isArray(obj)) {
      obj.forEach((item) => dig(item, depth + 1));
    } else if (typeof obj === 'object') {
      // 找到 aweme_info → 提取视频元数据
      if (obj.aweme_id && !seen.has(obj.aweme_id)) {
        seen.add(obj.aweme_id);

        // 提取标题: desc 字段
        const title = obj.desc || '';

        // 提取作者: author 对象或 author_name 字段
        let author = '';
        if (obj.author?.nickname) author = obj.author.nickname;
        else if (obj.author_name) author = obj.author_name;

        // 提取统计: statistics 对象
        let likes = '';
        if (obj.statistics?.digg_count) {
          const n = parseInt(obj.statistics.digg_count);
          likes = n >= 10000 ? (n / 10000).toFixed(1) + '万' : String(n);
        }

        // 提取时长 (API 返回毫秒, 转秒)
        const durationMs = obj.duration || obj.video?.duration || 0;
        const duration = durationMs > 1000 ? Math.round(durationMs / 1000) : durationMs;

        videos.push({
          href: 'https://www.douyin.com/video/' + obj.aweme_id,
          title,
          author,
          likes,
          duration: duration > 0 ? duration : undefined
        });
      }
      // 继续深挖
      Object.values(obj).forEach((v) => dig(v, depth + 1));
    }
  }

  const bizData = json.business_data || json.data || [];
  dig(bizData, 0);

  return videos;
}

/**
 * 按 video_id 合并去重
 */
function mergeByVideoId(target, incoming) {
  for (const item of incoming) {
    const id = extractVideoId(item.href);
    if (id && !target.find((t) => extractVideoId(t.href) === id)) {
      target.push(item);
    }
  }
}

/**
 * 从 API JSON 直接提取（离线模式，无需 Playwright）
 * @param {object} json - 搜索 API 返回的 JSON 对象
 * @returns {Array<{href:string, title:string, author:string, likes:string}>}
 */
function extractDouyinFromApiJson(json) {
  return parseSearchApiResponse(json);
}

function extractVideoId(url) {
  const m = url.match(/\/video\/(\d+)/);
  return m ? m[1] : null;
}

function extractUserId(url) {
  const m = url.match(/\/user\/([\w-]+)/);
  return m ? m[1] : null;
}

function linksToJson(links, source = '') {
  return JSON.stringify({
    source,
    extracted_at: new Date().toISOString().replace('T', ' ').substring(0, 19),
    total: links.length,
    videos: links
  }, null, 2);
}

function linksToPlain(links) {
  return links.map((l) => l.href).join('\n');
}

function linksToText(links) {
  return links.map((l, i) =>
    `${i + 1}. ${l.title}\n   ${l.href}\n   ${l.author ? '@' + l.author + '  ' : ''}${l.likes ? l.likes + ' 点赞' : ''}`
  ).join('\n\n');
}

module.exports = {
  extractDouyinLinks,
  extractDouyinFromApiJson,
  parseSearchApiResponse,
  linksToJson,
  linksToPlain,
  linksToText,
  extractVideoId,
  extractUserId
};

```

### File: tools\platform\quark\download-file.js
```
/**
 * @tool:      quark-download-file
 * @summary:   Download file(s) from 夸克网盘 (Quark Pan) via Playwright browser automation
 * @tags:      quark, 夸克网盘, download, playwright, browser
 * @mcp:       playwright
 * @inputs:    targetPath (string) - 目标文件/文件夹在网盘中的路径，如 "手机录屏" 或 "手机录屏/SVID_xxx.mp4"
 * @inputs:    destDir (string) - 本地目标目录，默认 ~/Desktop，可指定任意路径如 "D:/Videos"
 * @output:    array — 下载成功的文件路径列表
 *
 * 使用方式: Agent 读取此脚本中的步骤，通过 Playwright MCP 工具执行。
 * 下载完成后文件位于 .playwright-mcp/ 目录，需手动 cp 到目标位置。
 *
 * 前置条件: 用户已在夸克网盘网页版 (pan.quark.cn) 登录。
 *           Agent 在浏览器内操作，用户日常 Chrome 自带登录态。
 */

// ============================================================
// Step 0: ⚠️ 页面白屏修复（必须先检查！）
// ============================================================
// 夸克网盘依赖 g.alicdn.com 的 CDN 资源（Vue SPA）。
// Playwright 持久化浏览器 Profile 的缓存容易损坏，导致 CSS/JS 加载失败，
// 页面显示为白色空白（ERR_CACHE_READ_FAILURE）。
//
// 检测方法: browser_evaluate → () => document.body?.innerText?.substring(0, 100)
//   如果返回空字符串 → 白屏，执行修复:
//
// 修复步骤:
//   browser_run_code_unsafe →
//     const client = await page.context().newCDPSession(page);
//     await client.send('Network.clearBrowserCache');
//     await client.detach();
//     await page.goto('https://pan.quark.cn/s/XXXXX', { waitUntil: 'networkidle', timeout: 30000 });
//
// ⚠️ 不要用 browser_navigate 重新加载，必须用 page.goto + networkidle。
// ⚠️ 只清缓存不清 Cookie，登录态不会丢失。

// ============================================================
// Step 1: 导航到夸克网盘
// ============================================================
// MCP: browser_navigate → https://pan.quark.cn/
// 如果已登录，会自动跳转到 /list#/list/all
// 检查: 页面标题应为"夸克网盘"，左侧边栏可见"云文件"菜单
// 如果是分享链接 https://pan.quark.cn/s/{shareId} → 直接导航到该 URL

// ============================================================
// Step 1b (可选): 如果 targetPath 包含具体文件夹，逐级进入
// ============================================================
// 解析路径，逐级点击进入文件夹
// MCP: browser_click → getByTitle('文件夹名')
// 或: page.locator('tbody').getByTitle('文件夹名').click()

// ============================================================
// Step 2: 搜索定位目标文件/文件夹
// ============================================================
// MCP: browser_click → getByRole('textbox', { name: '搜索全部文件' })
// MCP: browser_type → 填入文件名关键词
// MCP: browser_press_key → Enter
// URL 变为 /list#/list/search?key=...

// ============================================================
// Step 3: 勾选目标文件
// ============================================================
// MCP: browser_click → 目标文件行的 checkbox (tbody 中对应行的第一个 cell)
// 勾选后顶部工具栏出现: 下载 | 分享 | 删除 | 重命名 | 移动到...
// 可使用 browser_snapshot 确认选中状态 (checkbox [checked])

// ============================================================
// Step 4: 点击工具栏"下载"按钮
// ============================================================
// MCP: browser_click → getByRole('button', { name: '下载' })
// 注意: 是勾选文件后顶部工具栏出现的下载按钮，不是文件行内的下载链接
// 触发后 Playwright 会开始下载，事件日志中显示 "Downloading file..."

// ============================================================
// Step 5: 等待下载完成并移动到目标目录
// ============================================================
// 下载文件保存在 .playwright-mcp/ 目录 (相对于项目 CWD)。
// Playwright 完成后会在控制台打印 "Download completed: <filename>"。
//
// 5a. 定位下载文件:
//   PowerShell: Get-ChildItem -Path ".playwright-mcp" -Name
//   Bash: ls -t .playwright-mcp/ | head -1
//
// 5b. 移动到 destDir:
//   destDir 默认 ~/Desktop，用户可通过 @inputs 指定自定义路径。
//   PowerShell: Move-Item -Path ".playwright-mcp/<filename>" -Destination "<destDir>/<filename>" -Force
//   Bash: mv ".playwright-mcp/<filename>" "<destDir>/<filename>"
//
// 5c. 验证:
//   PowerShell: Get-ChildItem "<destDir>/<filename>" | Select-Object Name, Length
//   Bash: ls -lh "<destDir>/<filename>"

// ============================================================
// 已知问题
// ============================================================
// 1. 账号封禁提示（页面底部"账号涉嫌违规已被封禁"）通常不影响文件浏览和下载
// 2. 下载 API (drive-pc.quark.cn) 在沙箱环境中可能 ERR_CONNECTION_CLOSED，
//    但 Playwright 的 download 事件仍可能成功获取文件
// 3. 如需上传文件，使用页面顶部"上传文件"按钮 (getByRole('button', { name: '上传文件' }))

// ============================================================
// 分享链接 vs 主站登录
// ============================================================
// 分享链接 (https://pan.quark.cn/s/{shareId}):
//   - 无需登录即可查看文件列表
//   - 页面显示"去客户端查看"按钮，下载按钮隐藏在 hover 菜单中
//   - 下载方式: hover 文件行 → 出现 .share-hover-menu-download 图标 → 点击触发下载
//   - 可用 browser_evaluate 提取文件列表信息用于展示
//
// 主站登录 (https://pan.quark.cn/ → 登录后跳转 /list):
//   - 需要用户已在浏览器登录过夸克
//   - 支持文件勾选 → 工具栏下载（会触发 Playwright download 事件）
//   - 下载文件保存到 .playwright-mcp/ 目录

// ============================================================
// 分享链接下载流程（Hover-to-Reveal 技巧）
// ============================================================
// 夸克分享链接页面的下载按钮默认隐藏，只有 hover 文件行后才出现。
// 工具栏"下载"按钮（勾选文件后出现）在分享链接页面也不可用，
// 因为未登录状态下没有勾选 checkbox。
//
// 操作步骤:
//
//   Step S1: 获取文件列表（可选，确认文件名）
//     browser_evaluate → listCurrentFiles() 或手动查看 snapshot
//
//   Step S2: Hover 文件行触发下载按钮
//     browser_run_code_unsafe →
//       const fileRow = page.locator('tr').filter({ hasText: '<文件名>' }).first();
//       await fileRow.hover();
//       await page.waitForTimeout(500);  // 等待 hover 菜单动画
//
//   Step S3: 点击下载图标
//     browser_run_code_unsafe →
//       await page.locator('.share-hover-menu-download').first().click();
//
//   Step S4: 处理可能弹出的"去客户端查看"提示
//     点击下载后可能弹出模态框引导安装客户端。关闭它:
//     browser_click → 模态框关闭按钮 (通常是 × 或"取消")
//
//   Step S5: 等待下载并移动文件 → 见下方 Step 5
//
// 注意: 分享链接下载会触发 Playwright 的 download 事件，
//       文件保存到 .playwright-mcp/ 目录。

// ============================================================
// 快捷操作: 直接用 JS 提取当前文件夹中所有文件的 URL
// ============================================================
// MCP: browser_evaluate → 执行以下 JS 获取文件列表信息
function listCurrentFiles() {
  const rows = document.querySelectorAll('tbody tr');
  const files = [];
  rows.forEach(row => {
    const nameEl = row.querySelector('td:nth-child(2)');
    const sizeEl = row.querySelector('td:nth-child(3)');
    const dateEl = row.querySelector('td:nth-child(4)');
    if (nameEl && !nameEl.textContent.includes('拖拽/粘贴')) {
      files.push({
        name: nameEl.textContent.trim().split('\n')[0],
        size: sizeEl?.textContent.trim() || '-',
        date: dateEl?.textContent.trim() || '-',
      });
    }
  });
  return files;
}

```

### File: tools\platform\zlib\download-book.js
```
/**
 * @tool:      zlib-download-book
 * @summary:   从 Z-Library 镜像站搜索并下载电子书 (PDF/EPUB/MOBI/AZW3)
 * @tags:      zlib, z-library, ebook, download, book, playwright, browser
 * @mcp:       playwright
 * @inputs:    query (string) - 书名/作者/ISBN 搜索关键词
 * @inputs:    format (string, optional) - 首选格式: pdf/epub/mobi/azw3，默认 epub
 * @inputs:    site (string, optional) - 指定站点URL，不传则自动尝试已知镜像列表
 * @output:    { success, filePath, title, format, site }
 *
 * 使用方式: Agent 读取此脚本中的步骤和 JS 代码片段，通过 Playwright MCP 工具执行。
 * 已验证站点: zh.ddd101.ru (2026-05-15)
 */

// ============================================================
// 已知 Z-Library 镜像列表（按优先级排列）
// ============================================================
const KNOWN_MIRRORS = [
  "https://zh.z-lib.today/",
  "https://zh.ddd101.ru/",
  "https://zbc.allfree.me/",
  "https://singlelogin.re/",
  "https://z-library.sk/",
];

// ============================================================
// Step 1: 选择站点并导航到首页
// ============================================================
// MCP: browser_navigate → 站点 URL（从 KNOWN_MIRRORS 依次尝试）
// 验证: 页面 title 包含 "Z-Library"
// 选择器验证:
//   - 搜索输入框: input[type="text"]
//   - 搜索按钮: button:has-text("搜索")
//   - 页面结构: 有 "最受欢迎" 区块 (含 /book/ 链接)

function step1_checkPageLoaded() {
  const hasSearchBox = !!document.querySelector('input[type="text"]');
  const hasBookLinks = !!document.querySelector('a[href*="/book/"]');
  return {
    title: document.title,
    url: location.href,
    hasSearchBox,
    hasBookLinks,
    ok: hasSearchBox && hasBookLinks
  };
}

// ============================================================
// Step 2: 执行搜索
// ============================================================
// 关键: 用 Enter 键提交，而非点击搜索按钮 (按钮点击被站点拦截)
// 方法: browser_run_code_unsafe 执行以下 JS
//
// async (page) => {
//   const searchInput = page.locator('input[type="text"]').first();
//   await searchInput.fill('<QUERY>');
//   await page.waitForTimeout(200);
//   await searchInput.press('Enter');
//   await page.waitForTimeout(4000);
// }
//
// 搜索后 URL 变为: /s/<encoded-query>
// 页面 title 变为: "<query>：在 Z-Library 上搜索"

// ============================================================
// Step 3: 解析搜索结果列表
// ============================================================
// 执行时机: 搜索后等待 3-4 秒让结果加载完成
// 结果结构:
//   - 每个结果项是一个 <a href="/book/<hash>/<slug>.html"> 包含:
//       - 书名 (generic > generic > generic: 书名)
//       - 作者 (generic > generic: 作者)
//       - 封面图 (img)
//   - 结果项下方有详细信息块:
//       - 出版社链接 (/publisher/...)
//       - 作者链接 (/author/...)
//       - 年/语言/文件大小
//   - 排序: "最受欢迎" / "列表"
//   - 分类过滤: "书籍 (N)" / "文章 (N)"

function step3_parseResults() {
  // 策略: 只提取 /book/ 链接作为结果，排除 publisher/author/category 等非书籍链接
  const bookLinks = document.querySelectorAll('a[href*="/book/"]');
  const seen = new Set();
  const books = [];

  bookLinks.forEach(a => {
    const href = a.getAttribute('href');
    // 只保留 /book/<hash>/<slug>.html 格式的主链接
    if (!href || !/^\/book\/[^/]+\//.test(href)) return;
    if (seen.has(href)) return;
    seen.add(href);

    const text = a.textContent.trim();
    // 跳过太短或明显不是书名的（如 "已下载" 这种纯状态文本）
    if (text.length < 2 || text === '已下载') return;

    // 尝试从父级/兄弟元素提取作者信息
    const parent = a.closest('[class]') || a.parentElement;
    const authorEl = parent?.querySelector('a[href*="/author/"]');
    const author = authorEl ? authorEl.textContent.trim() : '';

    // 提取文件格式信息
    const container = a.closest('generic') || parent;
    const fullText = container?.textContent || '';
    const formatMatch = fullText.match(/(EPUB|PDF|MOBI|AZW3|FB2|TXT|RTF)/gi);
    const formats = formatMatch ? [...new Set(formatMatch)] : [];
    const sizeMatch = fullText.match(/(\d+\.?\d*\s*(MB|KB|GB))/i);
    const size = sizeMatch ? sizeMatch[1] : '';

    books.push({
      title: text,
      href,
      author,
      formats,
      size,
      fullUrl: new URL(href, location.origin).href
    });
  });

  return {
    total: books.length,
    books: books.slice(0, 30),
    pageUrl: location.href
  };
}

// ============================================================
// Step 4: 进入书籍详情页，选择格式
// ============================================================
// MCP: browser_navigate → 选中的书籍 URL (完整地址)
// 详情页结构:
//   - 主下载链接: a[href*="/dl/"]  (初始显示默认格式)
//   - 格式下拉: button:has-text("Toggle Dropdown")
//   - 下拉菜单项: <a> 标签无 href，JS 驱动，格式如 "pdf 7.48 MB"
//   - "发送到" 按钮: button:has-text("发送到")
//   - "线上阅读" 链接: 含 /reader/ URL
//
// 选择格式的方法:
//   async (page, preferredFormat) => {
//     // 点击 Toggle Dropdown 展开格式列表
//     await page.locator('button:has-text("Toggle Dropdown")').click();
//     await page.waitForTimeout(500);
//     // 找到匹配格式的选项
//     const formatItem = page.locator('a').filter({ hasText: new RegExp(preferredFormat, 'i') }).first();
//     if (await formatItem.count() > 0) {
//       await formatItem.click();
//       await page.waitForTimeout(500);
//     }
//     // 获取更新后的下载链接
//     const dlLink = await page.locator('a[href*="/dl/"]').first().getAttribute('href');
//     return dlLink;
//   }

function step4_checkDetailPage() {
  const dlLink = document.querySelector('a[href*="/dl/"]');
  const toggleBtn = document.querySelector('button');
  const formatText = dlLink?.textContent?.trim() || '';

  return {
    title: document.title,
    url: location.href,
    downloadUrl: dlLink?.getAttribute('href') || '',
    currentFormat: formatText,
    hasToggleDropdown: !!document.querySelector('button:has-text("Toggle Dropdown")')
  };
}

// ============================================================
// Step 5: 触发下载
// ============================================================
// 方法1 (推荐): 直接导航到 /dl/<hash> URL
//   浏览器自动触发下载，Playwright 捕获 download 事件
//
//   async (page) => {
//     const dlHref = await page.locator('a[href*="/dl/"]').first().getAttribute('href');
//     await page.goto(new URL(dlHref, page.url()).href);
//     // 下载会自动开始，page.goto 会报 "Download is starting" 错误（正常）
//   }
//
// 方法2: 点击下载链接
//   const [download] = await Promise.all([
//     page.waitForEvent('download'),
//     page.locator('a[href*="/dl/"]').first().click()
//   ]);
//   await download.saveAs(path);
//
// 方法3: 用 fetch + 保存 (如果上述方法不适用)
//   但 fetch 可能无法携带浏览器 cookie

// ============================================================
// 辅助: 格式下拉列表解析
// ============================================================
function step4b_parseFormatDropdown() {
  // 在点击 Toggle Dropdown 后调用
  const formatItems = document.querySelectorAll('a');
  const formats = [];
  const formatPattern = /^(pdf|epub|mobi|azw3|fb2|txt|rtf)\s+([\d.]+)\s*(MB|KB|GB)/i;

  formatItems.forEach(a => {
    const text = a.textContent.trim().toLowerCase();
    const match = text.match(formatPattern);
    if (match) {
      formats.push({
        format: match[1].toUpperCase(),
        size: parseFloat(match[2]),
        unit: match[3],
        text: a.textContent.trim()
      });
    }
  });

  // 转换选项 (FB2, PDF, MOBI, TXT, RTF — 这些是转换而非原始文件)
  const convertItems = document.querySelectorAll('a[href="javascript:void(0);"]');
  const conversions = [...convertItems].map(a => a.textContent.trim()).filter(t => /^(FB2|PDF|MOBI|TXT|RTF)$/i.test(t));

  return { formats, conversions };
}

// ============================================================
// 完整流程示例代码 (Agent 使用 browser_run_code_unsafe)
// ============================================================

/*
// === 完整搜索+下载流程 ===
// 输入: query, preferredFormat

// 1. 导航到镜像站
await page.goto('https://zh.ddd101.ru/');
await page.waitForTimeout(2000);

// 2. 搜索 (如需特定格式，可在 query 中附加格式名: "三体 pdf")
const searchQuery = preferredFormat ? `${query} ${preferredFormat}` : query;
const searchInput = page.locator('input[type="text"]').first();
await searchInput.fill(searchQuery);
await page.waitForTimeout(200);
await searchInput.press('Enter');
await page.waitForTimeout(4000);

// 3. 解析结果
const results = await page.evaluate(() => {
  const bookLinks = document.querySelectorAll('a[href*="/book/"]');
  const seen = new Set();
  const books = [];
  bookLinks.forEach(a => {
    const href = a.getAttribute('href');
    if (!href || !/^\/book\/[^/]+\//.test(href)) return;
    if (seen.has(href)) return;
    seen.add(href);
    const text = a.textContent.trim();
    if (text.length < 2 || text === '已下载') return;
    books.push({ title: text, href });
  });
  return books.slice(0, 30);
});

// 4. 找到最匹配的结果 (Agent 智能选择，考量标题匹配度和格式匹配度)
const bestMatch = results[0];

// 5. 进入详情页
await page.goto(new URL(bestMatch.href, page.url()).href);
await page.waitForTimeout(2000);

// 6. 可选: 展开格式下拉查看可用格式
//    注意: 格式下拉项为混淆 JS 驱动 (onclick=_0x371adf)，自动化点击不可靠
//    如需切换格式，建议回到搜索页选择已有目标格式的书籍条目
//    await page.locator('button:has-text("Toggle Dropdown")').click();

// 7. 触发下载 (使用当前默认格式)
const dlHref = await page.locator('a[href*="/dl/"]').first().getAttribute('href');
await page.goto(new URL(dlHref, page.url()).href);
// 下载会自动开始，Playwright 捕获 download 事件
*/

```

### File: tools\platform\zsxq\delete-article.js
```
/**
 * @tool:      zsxq-delete-article
 * @summary:   Delete a published article from 知识星球 (zsxq) via Playwright browser automation
 * @tags:      zsxq, 知识星球, delete, article, playwright, browser
 * @mcp:       playwright
 * @inputs:    groupId (string) - 星球 ID, e.g. "88882145181552"
 * @inputs:    articleId (string) - 文章 ID, e.g. "06suceh9urnx"
 * @output:    void
 *
 * 使用方式: Agent 读取此脚本中的步骤和 JS 代码片段，通过 Playwright MCP 工具执行。
 *
 * 前置条件: 已登录知识星球网页版 wx.zsxq.com
 */

// ============================================================
// Step 1: 导航到星球主页
// ============================================================
// MCP: browser_navigate → https://wx.zsxq.com/group/{groupId}
// 等待页面加载完成，确认文章标题可见

// ============================================================
// Step 2: 点击目标文章的"查看详情"按钮
// ============================================================
// MCP: browser_evaluate → 执行以下 JS
function step2_clickDetail(articleId) {
  const link = document.querySelector(`a.link-of-topic[href*="${articleId}"]`);
  if (!link) return { error: "未找到文章链接" };
  const topicContainer = link.closest('.topic-container');
  const detailBtn = [...topicContainer.querySelectorAll('*')]
    .find(el => el.textContent.trim() === '查看详情' && el.children.length === 0);
  if (!detailBtn) return { error: "未找到查看详情按钮" };
  detailBtn.click();
  return { success: true };
}

// ============================================================
// Step 3: 打开右上角管理菜单（三点图标）
// ============================================================
// 注意: .topic-detail-panel 不会出现在 Playwright accessibility snapshot 中，
// 必须用 JS 操作 DOM。
// MCP: browser_evaluate → 执行以下 JS
function step3_openMenu() {
  const panel = document.querySelector('.topic-detail-panel');
  if (!panel) return { error: "未找到详情面板，请确认 Step 2 已成功" };
  const icon = panel.querySelector('.operation-top .icon');
  if (!icon) return { error: "未找到管理菜单图标" };
  // 必须用 dispatchEvent 而非 click()，因为 Angular 事件绑定
  icon.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  icon.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
  icon.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
  return { success: true };
}
// 执行后等待 ~500ms 让 Angular 渲染下拉菜单

// ============================================================
// Step 4: 点击"删除"菜单项
// ============================================================
// MCP: browser_evaluate → 执行以下 JS
function step4_clickDelete() {
  const deleteItem = document.querySelector('.topic-operation-container .item.delete');
  if (!deleteItem) return { error: "未找到删除菜单项，菜单可能已消失" };
  deleteItem.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  deleteItem.click();
  return { success: true };
}

// ============================================================
// Step 5: 确认删除
// ============================================================
// 确认对话框 .dialog-container 会出现
// MCP: browser_click → selector: ".dialog-container .confirm"
// 或 MCP: browser_evaluate → document.querySelector('.dialog-container .confirm').click()

// ============================================================
// Step 6: 验证删除成功
// ============================================================
// MCP: browser_evaluate → 执行以下 JS
function step6_verify(articleId) {
  const gone = !document.querySelector(`a[href*="${articleId}"]`);
  return { deleted: gone };
}

```

### File: tools\platform\zsxq\publish-article.js
```
/**
 * @tool:      zsxq-publish-article
 * @summary:   Publish a new article to 知识星球 (zsxq) via Playwright browser automation
 * @tags:      zsxq, 知识星球, publish, article, playwright, browser
 * @mcp:       playwright
 * @inputs:    groupId (string) - 星球 ID
 * @inputs:    title (string) - 文章标题，最大 60 字符
 * @inputs:    content (string) - 文章正文（Markdown 或纯文本），最大 100000 字符
 * @inputs:    tags (string[], optional) - 标签列表
 * @inputs:    useMarkdown (boolean, optional) - 是否使用 Markdown 模式，默认 false
 * @output:    {articleId: string, url: string}
 *
 * 使用方式: Agent 读取此脚本中的步骤和 JS 代码片段，通过 Playwright MCP 工具执行。
 *
 * 前置条件: 已登录知识星球网页版 wx.zsxq.com
 */

// ============================================================
// Step 1: 导航到星球主页
// ============================================================
// MCP: browser_navigate → https://wx.zsxq.com/group/{groupId}
// 等待页面加载完成

// ============================================================
// Step 2: 点击"写文章"按钮
// ============================================================
// MCP: browser_click → target: "text=写文章"
// 此操作会在新标签页打开文章编辑器
// 编辑器 URL: https://wx.zsxq.com/article?groupId={groupId}

// ============================================================
// Step 3: 切换到编辑器标签页
// ============================================================
// MCP: browser_tabs → select → index: 1 (新打开的标签页)

// ============================================================
// Step 4: 填写标题
// ============================================================
// 标题输入框选择器: textbox[placeholder="请在这里输入标题"]
// MCP: browser_type → target: 'textbox[placeholder="请在这里输入标题"]' → text: title
// 注意: 标题最大 60 字符

// ============================================================
// Step 5: 填写正文
// ============================================================
// 两种模式可选:

// --- 模式 A: 富文本模式（默认） ---
// 正文区域: .ProseMirror 或 "从这里开始输入正文"
// MCP: browser_type → target: ".ProseMirror" → text: content
// 或 MCP: browser_click → target: "text=从这里开始输入正文" → 然后 browser_type

// --- 模式 B: Markdown 模式 ---
// 先切换到 Markdown 模式:
// MCP: browser_click → target: "text=切换到 Markdown 模式"
// 然后粘贴内容:
// MCP: browser_type → target: ".ProseMirror" → text: content

// ============================================================
// Step 6: 添加标签（可选）
// ============================================================
// MCP: browser_click → target: "text=添加标签"
// 然后在弹出的标签选择器中点击对应标签

// ============================================================
// Step 7: 设置定时发布（可选）
// ============================================================
// 勾选"定时发布"复选框，设置发布时间

// ============================================================
// Step 8: 发布
// ============================================================
// MCP: browser_click → target: "text=发布"

// ============================================================
// 快捷发布路径（主页内嵌编辑器，用于需要上传附件的场景）
// ============================================================
// 入口: 主页"点击发表主题..."区域
// 特点: 支持上传文件，但不支持富文本排版和 Markdown 模式
// 添加标签: .post-topic-footer .tag (可能被预览层遮挡，需 browser_evaluate + dispatchEvent)

// ============================================================
// 验证发布结果
// ============================================================
// 发布后文章 URL 格式: https://articles.zsxq.com/id_{articleId}.html
// 可在 "我的文章" 中查看已发布列表

```

### File: tools\search\fsearch\fsearch.sh
```
#!/usr/bin/env bash
# @tool:      fsearch
# @summary:   多引擎交叉搜索 —— curl 直搜 中英4引擎，不走 WebSearch/WebFetch
# @tags:      search, curl, 交叉验证, 多引擎
# @usage:     bash fsearch.sh "搜索关键词"
# @date:      2026-05-18
set +e

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
KEYWORD="$*"

if [ -z "$KEYWORD" ]; then
  echo "用法: fsearch <关键词>"
  exit 1
fi

ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$KEYWORD'''))")

echo "=== fsearch: $KEYWORD ==="
echo ""

# --- 中文1: Bing (中文搜索，保持关键词简短2-3个，年份数字和长尾词易漂移) ---
echo "--- [中] Bing ---"
curl -sL --max-time 10 "https://www.bing.com/search?q=${ENCODED}" \
  -H "User-Agent: ${UA}" | \
  python3 -c "
import sys, re, html
text = sys.stdin.read()
count = 0
for m in re.finditer(r'<h2[^>]*><a[^>]*href=\"([^\"]+)\"[^>]*>(.+?)</a>', text, re.DOTALL):
    title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
    title = html.unescape(title)
    print(f'{count+1}. {title}')
    print(f'   {m.group(1)}')
    print()
    count += 1
    if count >= 8:
        break
if count == 0:
    print('  (无结果或解析失败)')
"

echo ""

# --- 外文1: Startpage (背后 Google 结果，走 Clash 代理，curl 友好) ---
echo "--- [EN] Startpage ---"
CLASH_PROXY="${CLASH_PROXY:-http://127.0.0.1:7897}"
curl -sL --max-time 10 --proxy "$CLASH_PROXY" \
  "https://www.startpage.com/sp/search?query=${ENCODED}&lang=english" \
  -H "User-Agent: ${UA}" 2>/dev/null | \
  python3 -c "
import sys, re, html as hmod
t = sys.stdin.read()
count = 0
# 提取有 URL 的链接，过滤掉导航/样式链接
seen = set()
for m in re.finditer(r'<a[^>]*href=\"(https?://[^\"]+)\"[^>]*>(.+?)</a>', t, re.DOTALL):
    url = m.group(1)
    title = hmod.unescape(re.sub(r'<[^>]+>', '', m.group(2)).strip())
    # 跳过内链、样式、空标题、CSS泄漏
    if 'startpage.com' in url or len(title) < 10 or url in seen:
        continue
    if '{' in title or '.css-' in title:
        continue
    if title.startswith('http://') or title.startswith('https://'):
        continue
    seen.add(url)
    print(f'{count+1}. {title[:120]}')
    print(f'   {url[:150]}')
    print()
    count += 1
    if count >= 8:
        break
if count == 0:
    print('  (Startpage 不可用，请确认 Clash 已开)')
"

echo ""

# --- 外文2: GitHub ---
echo "--- [EN] GitHub ---"
echo "(用 gh CLI 直搜: gh search repos --limit 10 \"$KEYWORD\")"
echo ""
echo "=== 交叉验证完成 ==="

```

### File: tools\vision\describe-image.py
```
#!/usr/bin/env python3
"""图片视觉描述 - 智谱 GLM-4V-Flash (免费)
用法: python describe-image.py <图片路径> [--prompt 提示词]
环境变量: ZHIPU_API_KEY
"""
import argparse, base64, io, os, sys
from pathlib import Path

MIME_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif",
    ".webp": "image/webp", ".bmp": "image/bmp",
}

DEFAULT_PROMPT = (
    "请详细描述这张图片的内容，包括："
    "文字内容、颜色、形状、元素位置和空间关系、"
    "UI布局（如适用）、图表数据（如适用）。"
)

MAX_DIM = 1280
MAX_DATA_URL = 200_000  # ~200KB data URL, keep under API limit
JPEG_QUALITY = 80


def preprocess(path):
    """Resize/compress image if needed to stay under API size limits."""
    from PIL import Image

    data = Path(path).read_bytes()
    suf = Path(path).suffix.lower()
    mime = MIME_MAP.get(suf, "image/png")

    # Estimate base64 data URL size
    estimated = len(data) * 4 / 3 + 100
    if estimated <= MAX_DATA_URL:
        return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"

    img = Image.open(io.BytesIO(data))
    w, h = img.size

    # Resize if too large
    if max(w, h) > MAX_DIM:
        ratio = MAX_DIM / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    # Compress as JPEG
    buf = io.BytesIO()
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    compressed = buf.getvalue()
    return f"data:image/jpeg;base64,{base64.b64encode(compressed).decode('ascii')}"


def describe(image_path, prompt, api_key):
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://open.bigmodel.cn/api/paas/v4/")
    resp = client.chat.completions.create(
        model="GLM-4V-Flash",
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": preprocess(image_path)}},
            {"type": "text", "text": prompt},
        ]}],
        max_tokens=1024,  # GLM-4V-Flash free tier limit
    )
    return resp.choices[0].message.content


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("image", help="图片路径")
    p.add_argument("--prompt", "-p", default=DEFAULT_PROMPT, help="自定义提示词")
    p.add_argument("--api-key", "-k", default="", help="智谱 API Key")
    args = p.parse_args()
    key = args.api_key or os.environ.get("ZHIPU_API_KEY", "")
    if not key:
        sys.exit("请设置 ZHIPU_API_KEY 环境变量或传 --api-key")
    print(describe(args.image, args.prompt, key))

```

### File: tools\vision\glm-vision-mcp.py
```
#!/usr/bin/env python3
"""GLM-5V-Turbo 视觉识别 MCP Server
通过 MCP stdio 协议暴露图像识别能力，供 DeepSeek 等主模型调用。
"""
import sys, json, base64, io, os
from pathlib import Path

MIME_MAP = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif",
    ".webp": "image/webp", ".bmp": "image/bmp",
}

MAX_DIM = 1280
MAX_BASE64 = 200_000
JPEG_QUALITY = 80


def preprocess(path: str) -> str:
    """Resize/compress image to base64 data URL within API limits."""
    from PIL import Image

    data = Path(path).read_bytes()
    suf = Path(path).suffix.lower()
    mime = MIME_MAP.get(suf, "image/png")

    if len(data) * 4 / 3 + 100 <= MAX_BASE64:
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"

    img = Image.open(io.BytesIO(data))
    w, h = img.size
    if max(w, h) > MAX_DIM:
        ratio = MAX_DIM / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    buf = io.BytesIO()
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"


def analyze_image(image_path: str, question: str = "请详细描述这张图片的内容") -> str:
    from openai import OpenAI

    api_key = os.environ.get("ZHIPU_API_KEY", "")
    if not api_key:
        return "错误：未设置 ZHIPU_API_KEY 环境变量"

    client = OpenAI(api_key=api_key, base_url="https://open.bigmodel.cn/api/paas/v4/")
    resp = client.chat.completions.create(
        model="GLM-5V-Turbo",
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": preprocess(image_path)}},
            {"type": "text", "text": question},
        ]}],
        max_tokens=4096,  # GLM-5V-Turbo 是推理模型，需留足思考token
    )
    return resp.choices[0].message.content


def handle(req: dict) -> dict | None:
    method = req.get("method", "")
    req_id = req.get("id")

    # 1. initialize
    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "glm-vision", "version": "1.0.0"},
                "capabilities": {"tools": {}},
            }
        }

    # 2. tools/list
    if method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {"tools": [{
                "name": "analyze_image",
                "description": "用智谱 GLM-5V-Turbo 识别图片内容。可读取截图中的文字、描述UI界面、分析图表数据、识别物体场景等。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "本地图片的完整路径，如 C:\\screenshot.png"
                        },
                        "question": {
                            "type": "string",
                            "description": "针对图片的具体问题，如'这张图里的表格数据是什么'、'截图中的报错信息是什么'。不填则返回完整描述。"
                        }
                    },
                    "required": ["image_path"],
                }
            }]}
        }

    # 3. tools/call
    if method == "tools/call":
        args = req.get("params", {}).get("arguments", {})
        image_path = args.get("image_path", "")
        question = args.get("question", "请详细描述这张图片的内容")

        if not image_path or not Path(image_path).exists():
            return {
                "jsonrpc": "2.0", "id": req_id,
                "result": {"content": [{"type": "text", "text": f"错误：图片文件不存在 - {image_path}"}]}
            }

        result = analyze_image(image_path, question)
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {"content": [{"type": "text", "text": result}]}
        }

    # 4. notifications (no id, no response)
    if req_id is None:
        return None

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as e:
            sys.stderr.write(f"MCP Error: {e}\n")
            sys.stderr.flush()


if __name__ == "__main__":
    main()

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
