# FVS 集成说明

> Lifecycle: `AS_BUILT_POC`。本文描述当前 POC FVS 集成，不是 P1 多屏绑定、设备身份或发布契约。

## 目标

让数字人前端能够嵌入或联动 FVS 看板, 并通过白名单动作控制页面或 Tab 切换。

## 当前推荐方向

V0.6 已验收的主线方案为“数字人前端作为主页面, iframe 嵌入 FVS 看板”:

```text
数字人前端主页面
-> iframe 加载 FVS 看板 URL
-> 用户语音 / 文本进入数字人前端
-> Gateway 校验 action_id 白名单
-> 数字人前端按白名单动作控制 FVS iframe
-> 简单分页动作优先改写 iframe URL 的 page_number
-> 复杂动作再使用 iframe.contentWindow.postMessage(...)
-> FVS 看板页面监听消息或使用 FVS Adapter
-> FVS 看板按 action_id 映射真实页面 / Tab 控制
```

选择该方向的原因:

- 麦克风权限留在数字人主页面, 不再受 FVS 网页框 iframe microphone 权限限制。
- 数字人、字幕、语音球和交互浮层更容易覆盖在 FVS 看板之上。
- FVS 看板只作为展示 iframe, 数字人体验和故障兜底由本项目掌控。

帆软网页框通信方案仍作为备用方向保留。依据帆软文档:

- `FVS网页框与页面通信接口`: https://help.fanruan.com/finereport/doc-view-5249.html
- `JS实现FVS网页框通信`: https://help.fanruan.com/finereport/doc-view-5270.html
- `FVS页面接口`: https://help.fanruan.com/finereport/doc-view-4941.html

关键约束:

- 主线方案需要先验证 FVS 看板是否允许被本项目页面 iframe 嵌入。
- 若 FVS 通过 `X-Frame-Options: SAMEORIGIN` 禁止跨端口嵌入, 优先使用同源反向代理; 若仍被 CSP `frame-ancestors` 等策略阻止, 再回退到 FVS 网页框嵌数字人方案或调整 FVS 侧策略。
- FVS 看板若需要接收动作消息, 仍应只按 `action_id` 固定映射。
- 本项目发出的消息只来自后端白名单校验后的 `action_id`, 不执行模型生成 JavaScript。

## V0.6 测试看板分页映射

当前用户提供的 FVS 测试看板支持 URL 参数 `page_number`。帆软 FVS 页面接口文档中, 新版分页参数 `page_number` 从 1 开始计数。因此 V0.6 第一轮先采用“改写 iframe URL 分页参数”的方式完成真实看板切页冒烟, 不要求先在 FVS 页面内预埋脚本。

| action_id | 测试页面 | page_number |
| --- | --- | --- |
| `SWITCH_HOME` | 总览 | 1 |
| `SWITCH_TAB_ORG` | 成品库存 | 2 |
| `SWITCH_TAB_STUDY` | 生产管理 | 3 |
| `SWITCH_TAB_ACTIVITY` | 设备分析 | 4 |

当前本地测试 URL 示例:

```text
http://localhost:8075/webroot/decision/view/duchamp?viewlet=...食品工厂管理看板.fvs&page_number=1
```

前端 Adapter 收到后端确认过的 `action_id` 后, 若动作配置中存在 `params.pageNumber`, 会将 FVS iframe 的 `src` 更新为对应 `page_number`。若动作没有 `pageNumber`, 才回退为向 FVS iframe 发送 `FVS_ACTION` 消息。

## 同源代理

本机 FVS 服务响应头包含 `X-Frame-Options: SAMEORIGIN`。由于浏览器同源判断包含端口, 直接把 `http://localhost:8075` 嵌入 `http://localhost:18000` 会被拦截。

V0.6 本地联调通过前端 Nginx 代理解决:

```text
http://localhost:18000/webroot/... -> http://host.docker.internal:8075/webroot/...
```

本地 `.env` 推荐使用相对路径:

```env
VITE_FVS_INTEGRATION_MODE=iframe
VITE_FVS_URL=/webroot/decision/view/duchamp?viewlet=...食品工厂管理看板.fvs&page_number=1
VITE_FVS_TARGET_ORIGIN=
```

这样浏览器看到父页面和 iframe 都是 `http://localhost:18000`, FVS 的 `SAMEORIGIN` 规则可以通过。该决策记录见 [ADR-0008](../decisions/ADR-0008-fvs-same-origin-proxy.md)。

## 第一阶段

本地开发优先使用 Mock FVS:

- 页面中展示 Mock 大屏或 iframe 占位。
- 执行动作时打印日志或改变 Mock 页面状态。
- 不依赖真实 FVS 接口。

## 第二阶段

接入真实 FVS:

- 优先验证数字人前端能否 iframe 加载 FVS 看板 URL。
- 如果 FVS 允许 iframe, 在本项目页面中覆盖数字人交互层。
- 如果 FVS 跨端口 iframe 被 `X-Frame-Options: SAMEORIGIN` 拦截, 优先使用同源代理; 如果仍不允许 iframe, 回退到 FVS 网页框嵌入数字人页面。
- 简单分页先使用 `page_number` URL 参数切页。
- FVS 看板侧如需响应更复杂动作消息, 预埋 `message` 监听或 FVS Adapter, 只识别本项目约定消息。
- 将 `action_id` 映射到 FVS 真实页面 / Tab 控制能力。
- 保留数字人独立运行时的 Mock FVS 回退。

## Mock Adapter 示例

```ts
export async function executeFvsAction(action: ScreenAction) {
  console.log("Mock execute FVS action", action);
  return {
    success: true,
    message: `Mock executed ${action.id}`
  };
}
```

## 数字人前端发送消息

当前前端 Adapter 发出的消息结构:

```json
{
  "type": "FVS_ACTION",
  "source": "configurable-digital-human",
  "action_id": "SWITCH_TAB_ORG",
  "actionId": "SWITCH_TAB_ORG",
  "functionName": "gotoPage",
  "params": {
    "pageNumber": 2
  }
}
```

说明:

- `action_id` / `actionId`: 真实执行时的主键, FVS 侧应优先使用它做白名单映射。
- `functionName` / `params`: 来自 `config/screen-actions.yaml`, 仅作为已校验动作的配置字段, 不应由 FVS 侧直接动态执行。当前测试看板使用 `gotoPage` + `pageNumber`。
- `source`: 用于 FVS 侧过滤其他消息。

主线 iframe 方案中, 数字人前端若识别到 `params.pageNumber`, 会优先改写 iframe URL 的 `page_number`; 没有 `pageNumber` 的动作才向 `iframe.contentWindow` 发送上述消息。

## FVS 主体悬浮语音层

V0.6 已验收的 UI 方案以 FVS iframe 为页面主体。2026-06-11 起, 按大屏展示优先原则进一步精简悬浮层:

- `iframe` 模式下, FVS 看板铺满整个浏览器视口。
- 未唤醒、未处理语音时, 页面右下角只显示一个小型低透明麦克风入口, 不做常驻脉冲动画。
- 点击入口后仍由数字人主页面申请麦克风权限, 不依赖 FVS 网页框权限。
- 唤醒词判定中、未命中唤醒词、监听冷却时不展开悬浮层。
- 仅在正式录音、连续追问、思考、TTS 加载或播报时, 右下角展开半透明评论流。
- 评论流只显示最近识别到的用户文本和数字人回复文本, 不显示来源、`action_id`、音频控件或调试状态。
- 主画布模式隐藏文本表单、Mock ASR 输入、Demo 按钮和直接控屏调试栏; 这些调试入口只在非 FVS 主画布模式保留。
- 运维看板不再挂在 FVS 主画布悬浮层上, 统一通过前端独立路径 `/ops` 访问。
- V0.9 起, 前端会对 FVS iframe 加载做超时 / 失败兜底提示, 便于现场区分 FVS 服务不可达、同源代理异常和 iframe 策略拦截。

语音响应策略:

- 命中唤醒词后, 前端立即播报固定唤醒反馈: `您好。`
- 正式指令或连续追问进入处理后, 前端立即播报固定等待提示: `收到, 正在为您查找信息。`
- `您好。` 和等待提示均优先使用预热的后端 TTS 音频; 若尚未就绪, 使用浏览器 `speechSynthesis` 做本地兜底。
- 若唤醒句中已包含指令, 指令处理不会等待 `您好。` 播放结束, 但等待提示会排在 `您好。` 后播放。
- AI 结果 TTS 与短提示共用播放通道。AI 结果音频一旦开始播放, 会清理并打断短提示, 保证最终回答优先。

## FVS 看板监听草案

如果 FVS 看板页面支持标准 `message` 监听, 可在 FVS 看板中预埋:

```js
window.addEventListener("message", function (event) {
  var message = event.data;
  if (!message || message.type !== "FVS_ACTION" || message.source !== "configurable-digital-human") {
    return;
  }

  var actionId = message.action_id || message.actionId;
  var params = message.params || {};

  if (actionId === "SWITCH_HOME") {
    // TODO: 切换到总览, page_number=1。
    return;
  }
  if (actionId === "SWITCH_TAB_ORG") {
    // TODO: 切换到成品库存, page_number=2。
    return;
  }
  if (actionId === "SWITCH_TAB_STUDY") {
    // TODO: 切换到生产管理, page_number=3。
    return;
  }
  if (actionId === "SWITCH_TAB_ACTIVITY") {
    // TODO: 切换到设备分析, page_number=4。
    return;
  }

  console.warn("Blocked unsupported digital human action:", actionId, params);
});
```

正式联调时把各分支中的 `return` 替换为 FVS 真实页面 / Tab 控制 API。FVS 侧也必须使用固定 `action_id` 分支或本地白名单映射, 不要根据 `functionName` 动态拼接 / 执行 JavaScript。

## 备用: FVS 网页框嵌数字人

如果后续仍要让 FVS 主模板网页框嵌数字人, 在 FVS 主模板页面加载结束事件中配置通信来源:

```js
duchamp.onlyCommunicateWithOrigins(["http://localhost:18000"]);
```

在 FVS 主模板初始化事件中监听数字人网页框消息:

```js
duchamp.addPostMessageListener(function (message) {
  if (!message || message.type !== "FVS_ACTION" || message.source !== "configurable-digital-human") {
    return;
  }

  var actionId = message.action_id || message.actionId;
  var params = message.params || {};

  if (actionId === "SWITCH_HOME") {
    // TODO: 调用 FVS 真实切页能力, 切换到总览。
    return;
  }

  if (actionId === "SWITCH_TAB_ORG") {
    // TODO: 切换到成品库存。
    return;
  }

  if (actionId === "SWITCH_TAB_STUDY") {
    // TODO: 切换到生产管理。
    return;
  }

  if (actionId === "SWITCH_TAB_ACTIVITY") {
    // TODO: 切换到设备分析。
    return;
  }

  console.warn("Blocked unsupported digital human action:", actionId, params);
});
```

但该备用方案下, 浏览器麦克风可能受 FVS 网页框 iframe 权限策略限制。

## 数字人前端配置

主线 iframe host 模式:

```env
VITE_FVS_INTEGRATION_MODE=iframe
VITE_FVS_URL=https://your-fvs-url
VITE_FVS_TARGET_ORIGIN=https://your-fvs-origin
```

说明:

- `iframe` 表示数字人前端作为主页面, iframe 嵌入 FVS。
- `VITE_FVS_URL` 是 FVS 看板访问地址。
- `VITE_FVS_TARGET_ORIGIN` 建议配置为 FVS 看板 origin。为空时前端会根据 `VITE_FVS_URL` 自动推断。

为了减少反复重建, 也可直接用 URL 参数临时指定 FVS 地址:

```text
http://localhost:18000/?fvs_url=https%3A%2F%2Fyour-fvs-url
```

如果需要同时指定目标 origin:

```text
http://localhost:18000/?fvs_url=https%3A%2F%2Fyour-fvs-url&fvs_origin=https%3A%2F%2Fyour-fvs-origin
```

备用模式:

```env
VITE_FVS_INTEGRATION_MODE=parent
VITE_FVS_TARGET_ORIGIN=https://your-fvs-origin
VITE_FVS_URL=
```

该模式用于 FVS 网页框反向嵌入数字人。

## 待确认

- FVS 看板 URL / origin。
- FVS 是否允许被本项目页面 iframe 嵌入。
- FVS 是否设置 `X-Frame-Options` 或 CSP `frame-ancestors`。
- FVS 看板中页面 / Tab 切换的真实 JS API 或组件控制方式。
- 页面 / Tab 的真实 ID。
- 是否需要 FVS 看板向数字人前端回传动作执行成功 / 失败回执。
