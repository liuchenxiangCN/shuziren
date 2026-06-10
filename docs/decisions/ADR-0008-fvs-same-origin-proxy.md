# ADR-0008 FVS Same-Origin Proxy

## Status

Accepted

## Context

V0.6 采用“数字人前端主页面 iframe 嵌入 FVS 看板”。用户提供的本机 FVS URL 位于:

```text
http://localhost:8075/webroot/decision/view/duchamp?...&page_number=1
```

直接从 `http://localhost:18000` iframe 加载该 URL 时, FVS 响应头包含:

```text
X-Frame-Options: SAMEORIGIN
```

浏览器的 same-origin 判断包含端口, 因此 `localhost:18000` 与 `localhost:8075` 不同源, iframe 区域无法正常渲染。

## Decision

本地 V0.6 采用前端 Nginx 同源反向代理:

```text
http://localhost:18000/webroot/... -> http://host.docker.internal:8075/webroot/...
```

前端配置使用相对路径:

```env
VITE_FVS_INTEGRATION_MODE=iframe
VITE_FVS_URL=/webroot/decision/view/duchamp?viewlet=...&page_number=1
VITE_FVS_TARGET_ORIGIN=
```

浏览器看到父页面和 iframe 都来自 `http://localhost:18000`, 因而 FVS 的 `X-Frame-Options: SAMEORIGIN` 不再阻止嵌入。

## Consequences

- 本地联调不需要修改 FVS 看板模板或服务器响应头。
- Web 容器需要能够访问 Docker Desktop 主机名 `host.docker.internal`。
- 生产部署时应由正式网关或同源反向代理承接同样能力, 或由 FVS 侧调整允许嵌入策略。
- `page_number` 分页控制继续由前端 Adapter 改写 iframe URL 完成。
- 分页以外的组件级动作仍需 FVS 侧固定 `action_id` 监听或 Adapter。
