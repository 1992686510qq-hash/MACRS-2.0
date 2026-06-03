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

### M-011 - shared-scripts/ 与 tools/ 下 7 对文件完全重复，违反 DRY 原则
- Severity: P0 BLOCKING
- File: shared-scripts/ (全目录) vs tools/ (全目录) lines [0, 0]
- Description: N/A
- Suggestion: 选择一个权威来源（建议 tools/ 目录），删除 shared-scripts/ 中的重复文件，改为 symlink 或在 shared-scripts/ 中仅保留 re-export 模块。或者统一目录结构，消除双源维护。

Source code context:
```
(file not found)
```
### M-012 - scripts/pw-multi.js 与 tools/browser/proxy/pw-multi.js 完全重复
- Severity: P0 BLOCKING
- File: scripts/pw-multi.js lines [37, 37]
- Description: N/A
- Suggestion: 保留 tools/browser/proxy/pw-multi.js 作为权威版本，scripts/pw-multi.js 改为 require 或直接 symlink。

Source code context:
```
(file not found)
```
### M-001 - python3 -c 代码注入：用户输入通过三引号字符串插值导致 RCE
- Severity: P0 BLOCKING
- File: tools/search/fsearch/fsearch.sh lines [22, 24]
- Description: N/A
- Suggestion: 使用 sys.argv 传参替代字符串插值：ENCODED=$(python3 -c "import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1]))" "$KEYWORD")

Source code context:
```
(file not found)
```
### M-002 - MCP Server 任意文件读取：image_path 参数无路径校验
- Severity: P0 BLOCKING
- File: tools/vision/glm-vision-mcp.py lines [75, 85]
- Description: N/A
- Suggestion: 1) 添加允许的目录白名单（如用户桌面、下载目录）；2) 使用 os.path.realpath() 解析符号链接后检查路径前缀；3) 拒绝包含 .. 的路径；4) 限制文件大小（如 50MB）防止内存耗尽。

Source code context:
```
(file not found)
```
### M-013 - preprocess() 函数在两个文件中重复，且描述文件仍在使用已废弃的 GLM-4V-Flash
- Severity: P1 CRITICAL
- File: tools/vision/describe-image.py lines [22, 40]
- Description: N/A
- Suggestion: 将 preprocess() 提取为共享工具模块（如 vision-utils.py），两个入口 import 同一份。统一模型版本到 GLM-5V-Turbo，或明确标注 describe-image.py 为轻量版/兼容版。

Source code context:
```
(file not found)
```
### M-014 - angularClick 事件顺序不一致：click 在 mousedown 之前触发
- Severity: P1 CRITICAL
- File: shared-scripts/utils/playwright-helpers.js lines [17, 21]
- Description: N/A
- Suggestion: 统一为 mousedown → mouseup → click 的正确顺序，且消除重复文件（见 C-001）。

Source code context:
```
(file not found)
```
### M-004 - SSRF：TARGET_URL 未校验直接传入 curl 和 cdp-proxy
- Severity: P1 CRITICAL
- File: scripts/quick-test.sh lines [12, 68]
- Description: N/A
- Suggestion: 1) 校验 URL 协议只允许 http/https；2) 使用 Python/Node 解析 URL 后检查 host 不是私有 IP（10.x, 172.16-31.x, 192.168.x, 127.x, 169.254.x）；3) 至少在日志中警告内网目标。

Source code context:
```
(file not found)
```
### M-015 - zsxq delete-article 中 click 事件调用冗余且顺序矛盾
- Severity: P1 CRITICAL
- File: shared-scripts/zsxq/delete-article.js lines [49, 53]
- Description: N/A
- Suggestion: 与 step3_openMenu 保持一致，只用 dispatchEvent 系列（mousedown → mouseup → click），去掉原生 .click() 调用。

Source code context:
```
(file not found)
```
### M-017 - fsearch.sh 存在命令注入风险：用户输入未经转义直接嵌入 Python 字符串
- Severity: P1 CRITICAL
- File: shared-scripts/tools/fsearch.sh lines [30, 34]
- Description: N/A
- Suggestion: 使用环境变量传递 KEYWORD 到 Python，而非字符串插值：`KEYWORD="$KEYWORD" python3 -c "import os; KEYWORD=os.environ['KEYWORD']; ..."`。或使用 Python 的 shlex.quote()。

Source code context:
```
(file not found)
```
### M-005 - SSRF：smart-fetch.sh 允许 curl 请求任意内网地址
- Severity: P1 CRITICAL
- File: tools/fetch/smart-fetch.sh lines [120, 140]
- Description: N/A
- Suggestion: 在 main() 函数入口添加 URL 协议和目标 IP 校验，阻断私有地址段。

Source code context:
```
(file not found)
```
### M-006 - 拒绝服务：无文件大小限制可导致内存耗尽
- Severity: P1 CRITICAL
- File: tools/vision/glm-vision-mcp.py lines [30, 40]
- Description: N/A
- Suggestion: 在 read_bytes() 之前先检查文件大小，超过阈值（如 50MB）直接拒绝。

Source code context:
```
(file not found)
```
### M-003 - 任意文件读取：image_path 参数无路径校验（CLI 版本）
- Severity: P0 BLOCKING
- File: tools/vision/describe-image.py lines [33, 42]
- Description: N/A
- Suggestion: 添加路径规范化和目录白名单校验，限制文件大小。

Source code context:
```
(file not found)
```
### M-016 - 抖音搜索 API 拦截模式存在事件监听器累积泄漏
- Severity: P1 CRITICAL
- File: shared-scripts/douyin/extract-links.js lines [52, 57]
- Description: N/A
- Suggestion: 将 onResponse 的注册移到循环外部，或在每次迭代开头显式清理 searchJson 并确保只有一个活跃的 response listener。更好的方案是用 page.waitForResponse() 替代手动 on/off 模式。

Source code context:
```
(file not found)
```
### M-007 - URL 注入：从不可信 DOM 构造完整 URL 可能触发 javascript: 协议
- Severity: P1 CRITICAL
- File: tools/platform/zlib/download-book.js lines [120, 135]
- Description: N/A
- Suggestion: 在构造 URL 前验证 href 以 / 或 http 开头，拒绝 javascript:、data:、vbscript: 等协议。

Source code context:
```
(file not found)
```
### M-008 - CSS 选择器注入：articleId 未转义直接拼入 querySelector
- Severity: P1 CRITICAL
- File: tools/platform/zsxq/delete-article.js lines [43, 50]
- Description: N/A
- Suggestion: 使用 CSS.escape() 转义 articleId，或改用 Array.from(document.querySelectorAll('a.link-of-topic')).filter(a => a.href.includes(articleId))。

Source code context:
```
(file not found)
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