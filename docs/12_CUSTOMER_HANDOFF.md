# 客户移交说明

本文档面向客户或后续交付团队, 用于解释系统能力、部署方式、当前限制和后续建议。

## 系统能力

本系统提供党建大屏语音交互能力:

- 语音唤醒。
- 中文 ASR 识别。
- Dora Agent 问答和问数。
- RAGFlow 知识库问答。
- 大屏动作白名单控制。
- TTS 语音播报。
- 字幕、状态动效、回复窗口。
- 会话日志和耗时记录。
- 本地脱敏 Excel 问数演示。

## 部署方式

目标部署方式:

- 本地 Windows + Docker Desktop + WSL2。
- 数字人前端和后端由本项目 Docker Compose 启动。
- RAGFlow 使用官方 Docker Compose 独立部署; 当前 V0.5 本地路径为 `D:\Project\ragflow`, Web 为 `http://127.0.0.1:18089`, MCP 为 `http://127.0.0.1:19382/mcp` / `http://127.0.0.1:19382/sse`。`zt_party_building_demo` dataset 已导入 8 份测试资料并解析完成; Dora 已通过公网 MCP 调用该知识库并返回自然语言答案。本地 MCP server 已做 POC 返回量瘦身, 以减少 Dora 工具结果处理负担。
- Dora、ASR、TTS 使用客户确认的外部服务。
- FVS 优先由数字人前端主页面 iframe 嵌入客户现有大屏, 数字人前端负责语音、字幕、浮层和白名单动作消息发送。
- V0.7 问数默认由 Gateway 本地 Excel Adapter 读取 `docs/demo_data/ask_metrics/` 下三份脱敏样例, Docker 中路径为 `/app/docs/demo_data/ask_metrics`。

## 启动命令

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

访问:

```text
http://localhost:18000
http://localhost:18080/api/health
```

## 停止命令

```powershell
docker compose down
```

## 日志位置

目标路径:

```text
logs/
data/sessions.db
```

## 外部依赖

- Dora 平台。
- RAGFlow。
- FVS 看板。
- 国产 ASR。
- 国产 TTS。
- 网络连通和 API Key。

## 安全边界

- 大模型不得直接输出并执行 JavaScript。
- 大屏控制只允许使用白名单 `action_id`。
- 后端负责校验动作合法性。
- 前端不保存或暴露 API Key。
- 生产或正式 POC 前需确认云模型、数据范围、脱敏策略和合规边界。

## 当前限制

- 当前已实现前端、后端和 Docker Compose, 默认仍优先使用 Mock 模式保证演示稳定。
- Dora OpenClaw Adapter 已可调用真实 Agent 并返回归一化回答。
- 当前真实 Dora Agent `中天证券党建大屏语音助手` 已可返回 `screen_control` 控屏动作, 并通过后端白名单校验。
- 语义唤醒不是严格本地 KWS。
- RAGFlow 检索质量需要结合真实文档调优。
- 当前 TTS 低延迟优化为分段 TTS 文件播放, 不是供应商音频字节级真流式; 真实演示仍需确认浏览器自动播放权限。
- FVS iframe host、同源代理和 `page_number=1/2/3/4` 四页切换已通过 V0.6 人工验收; 分页以外的组件级控制 API 仍需等待后续接口确认。
- V0.7 已完成本地脱敏 Excel 问数链路, 但正式客户问数仍需要确认真实数据源、指标口径和授权范围。

## 常见问题

### 问数结果从哪里来

V0.7 本地 POC 的问数结果来自 `docs/demo_data/ask_metrics/` 下三份脱敏 Excel。Gateway 在调用 Dora 前先匹配固定问数意图, 命中后直接读 Excel 返回, 并在回答中标明数据来源。

这不是通用 BI 问数引擎, 也不会执行模型生成的 SQL / Python / JavaScript。正式客户数据可在后续切换为 Dora 问数、FineBI / FVS 数据源或数据库查询 Provider。

### Dora 无法访问本地 RAGFlow MCP

本地 `localhost` 对 Dora 服务器不可见。可选方案:

- 使用 Windows 局域网 IP。
- 使用 FRP / Cloudflare Tunnel / ngrok。
- 将 RAGFlow 部署到 Dora 可访问的服务器。

当前 V0.5 已完成本机 RAGFlow MCP 启动, 临时公网 MCP 已可检索测试 dataset chunk; Dora 真实问答已通过 Agent 侧文本/API 验收, POC Gateway 已支持 `/api/chat/stream` 和分段 TTS, 且用户已完成人工验收。V0.6 FVS iframe host、四页切换、悬浮语音层和等待提示音打断体验也已完成人工验收。后续正式演示前仍需确认公网映射或内网穿透的安全方案。

### FVS iframe 嵌入

V0.6 已验收的推荐方式是打开数字人前端主页面, 由主页面 iframe 加载 FVS 看板 URL。这样麦克风和数字人交互不再运行在 FVS 网页框中。

若 FVS 看板无法显示, 优先检查 FVS 是否设置 `X-Frame-Options` 或 CSP `frame-ancestors` 禁止嵌入。本机测试看板返回 `X-Frame-Options: SAMEORIGIN`, 已通过数字人前端 Nginx 同源代理 `/webroot/ -> http://host.docker.internal:8075/webroot/` 解决。

### 大屏控制失败

优先检查:

- `action_id` 是否在白名单中。
- 数字人前端是否以 `VITE_FVS_INTEGRATION_MODE=iframe` 构建, 或是否通过 `?fvs_url=` 临时指定 FVS 地址。
- FVS 看板是否允许 iframe 嵌入; 若仅因 `SAMEORIGIN` 跨端口被拦截, 优先确认同源代理是否生效。
- FVS 看板是否已预埋标准 `message` 监听或 FVS Adapter。
- 是否存在跨域、iframe 加载或 FVS 模板事件配置限制。

## 后续建议

- V0.8 下一步: 先完成 Dora 通用问数 + Excel fallback、TTS 字节级真流式、运维监控 / 日志看板、客户私有配置目录。
- V0.9 再做交付前优化: 预检脚本、一键启停、日志导出、演示模式和异常体验优化。
- V1.0 最后输出正式验收报告、部署方案、用户手册、运维手册、配置手册和测试报告。
- 分页以外的 FVS `postMessage` / FVS Adapter 控制能力作为后续增强项, 不影响当前 V0.6 验收结论。
- 正式上线前进行合规、安全、网络和运维评审。
