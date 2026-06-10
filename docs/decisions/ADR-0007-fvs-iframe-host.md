# ADR-0007 FVS Iframe Host

## Status

Accepted

## Context

V0.6 初始尝试让 FVS 主模板通过网页框嵌入数字人页面, 但现场调试遇到两个问题:

- 网页框消息发送不易排查。
- 麦克风权限在 FVS 网页框 iframe 内容易受安全上下文和 permission policy 限制。

用户决定切换思路: 以本项目数字人前端为主体, iframe 嵌入 FVS 看板。

## Decision

V0.6 决策时优先采用数字人前端主页面嵌入 FVS 看板:

```text
数字人前端主页面
-> iframe 加载 FVS 看板 URL
-> 用户语音 / 文本进入数字人前端
-> Gateway 校验 action_id
-> 数字人前端向 FVS iframe 发送 FVS_ACTION
-> FVS 看板按 action_id 固定映射真实控制 API
```

`VITE_FVS_INTEGRATION_MODE=iframe` 表示启用该模式。前端同时支持运行时 URL 参数 `?fvs_url=...`, 用于临时指定 FVS 看板地址, 避免每次联调都重建前端。

本机 FVS 若返回 `X-Frame-Options: SAMEORIGIN`, 通过同源反向代理解决, 见 [ADR-0008](ADR-0008-fvs-same-origin-proxy.md)。

## Consequences

优点:

- 麦克风权限留在数字人主页面, 更容易满足浏览器安全要求。
- 数字人、字幕、语音球和后续浮层可覆盖在 FVS iframe 上方。
- 本项目继续掌控错误兜底、TTS、ASR、监听状态和交互体验。

约束:

- FVS 看板必须允许被本项目页面 iframe 嵌入。
- 若 FVS 设置 `X-Frame-Options: SAMEORIGIN`, 可优先采用同源代理; 若 CSP `frame-ancestors` 等策略仍禁止嵌入, 需要调整 FVS 侧策略或回退到 FVS 网页框嵌数字人方案。
- FVS 看板侧仍不得执行模型生成 JavaScript, 只能按 `action_id` 做固定映射。
