# Dora 集成说明

> Lifecycle: `AS_BUILT_POC`。本文描述当前 POC Dora 接入，不是多屏产品 Provider 目标契约。

## 目标

Dora 负责 Agent 路由、问数、RAGFlow MCP 调用和结构化输出。Gateway 负责调用 Dora、解析输出、容错和动作安全校验。

## 配置项

```env
DORA_BASE_URL=https://your-dora-host
DORA_API_KEY=replace_me
DORA_AGENT_ID=
DORA_AGENT_NAME=中天证券党建大屏语音助手
DORA_CHANNEL_TYPE=feishu
DORA_CHAT_MODE=sse
DORA_TIMEOUT_SECONDS=60
ENABLE_MOCK_DORA=true
```

## 接入阶段

V0.1:

- 使用 Mock Dora。

V0.2:

- 接入 Dora API。
- 支持 SSE。
- 解析 Dora 输出。
- 保留 `ENABLE_MOCK_DORA`。

当前实现:

- `ENABLE_MOCK_DORA=true`: `/api/chat` 继续走 V0.1 Mock Dora。
- `ENABLE_MOCK_DORA=false`: `/api/chat` 调用 Dora OpenClaw SSE。
- V0.8 已新增 `ASK_METRICS_MODE=excel|dora|auto`: `excel` 保持 Gateway Excel Adapter 优先, `dora` 让 Dora / Mock Dora 承接问数, `auto` 在 Dora / Mock Dora 失败或返回 `fallback` 时回退 Excel。
- V0.9 已新增 `DEMO_STABLE_MODE=true`: Dora 请求失败时, Gateway 会优先尝试本地 Excel 问数和 Mock Dora 演示兜底; 未命中时仍返回安全 `fallback`。
- `POST /api/chat/stream`: V0.5 新增流式路径, 直接消费 Dora OpenClaw SSE, 向前端输出 `dora_delta`、最终 `answer` 和分段 `tts_ready`。
- Dora Client 位于 `apps/api/app/services/dora_client.py`。
- Dora 输出归一化位于 `apps/api/app/services/dora_normalizer.py`。

## OpenClaw 接入方式

根据 Dora 开放集成文档和 `fine-dora` skill 约定, V0.2 Gateway 直接调用 Dora OpenClaw API, 不把 `fine-dora` skill 安装进产品运行时。

### 鉴权

```http
Authorization: Bearer ${DORA_API_KEY}
Content-Type: application/json
Accept: text/event-stream
```

### 发现 Agent

当 `DORA_AGENT_ID` 为空时, Gateway 使用 `DORA_AGENT_NAME` 查找已发布 Agent:

```text
GET ${DORA_BASE_URL}/external/api/openclaw/agents
```

匹配规则:

- `name == DORA_AGENT_NAME`
- `published == true`
- `agentStatus == PUBLISHED`
- 如果匹配 0 个, 返回 `fallback`
- 如果匹配多个, 要求显式配置 `DORA_AGENT_ID`

### SSE Chat

```text
POST ${DORA_BASE_URL}/external/api/openclaw/sse/chat
```

请求体:

```json
{
  "publishedAgentId": "<DORA_AGENT_ID>",
  "externalSessionKey": "<session_id>",
  "queryId": "<message_id_or_uuid>",
  "userMessage": "用户问题",
  "channelType": "feishu",
  "traceId": "<uuid>"
}
```

V0.2 先使用 `DORA_CHANNEL_TYPE=feishu`; 该参数作为 Dora OpenClaw 会话渠道透传, 后续如客户环境要求其他值, 只改 `.env`。

### 当前 SSE Event 形态

2026-06-10 本地连通性验证中观察到的 Dora OpenClaw SSE 形态:

```text
id:<stream-id>
event:metadata
data:{...}

id:<stream-id>
event:values
data:{...}

id:<stream-id>
event:messages
data:[{"content":"...","type":"AIMessageChunk",...}, {...}]
```

Gateway V0.2 处理方式:

- 忽略 SSE `id`、`retry`、注释行。
- 忽略 `metadata` / `values` 事件, 避免把运行元数据或上下文写入最终回答。
- 从 `messages` 事件中的 `content` chunk 收敛最终文本。
- 忽略 `type=tool` / `ToolMessage` / `ToolMessageChunk`, 避免把 MCP 工具原始 chunks 当成最终回答。
- 如果收敛结果是 JSON 或 Markdown JSON, 继续按项目数据契约解析。
- 如果收敛结果是自然语言, 包装为 `answer`。

V0.5 流式路径额外处理:

- 从 `AIMessageChunk.content` 中尝试增量提取最终 JSON 的 `speak_text` 字段。
- 将提取到的文本作为 `dora_delta` 推给前端, 并按短句切分后并发提交 TTS。
- 如果 Dora 未提供稳定增量, 仍在最终 `answer` 后对 `speak_text` 做分段 TTS。

### History Fallback

当 SSE 已收到部分事件但无法稳定收敛最终回答时, 可按 Dora 约定查询历史:

```text
POST ${DORA_BASE_URL}/external/api/openclaw/history
```

请求体:

```json
{
  "publishedAgentId": "<DORA_AGENT_ID>",
  "externalSessionKey": "<session_id>",
  "channelType": "feishu"
}
```

## Gateway 处理规则

- 标准 JSON 直接解析。
- Markdown 包裹 JSON 时提取 JSON。
- 自然语言包装为 `answer`。
- Dora `clarify` 在 V0.2 先包装为 `answer` 展示。
- `screen_control` 必须校验动作白名单。
- 非法 action 返回兜底话术。
- Dora 超时返回服务不可用话术。
- 演示稳态只用于固定演示保底, 不能替代真实 Dora 依赖验收。

## 已验证

- `GET /external/api/openclaw/agents` 连通。
- `DORA_AGENT_ID` 为空时, 可按 `DORA_AGENT_NAME=中天证券党建大屏语音助手` 自动发现已发布 Agent。
- `POST /external/api/openclaw/sse/chat` 连通。
- 后端 `/api/chat` 在 `ENABLE_MOCK_DORA=false` 时可调用 Dora 并返回归一化 `answer`。
- 验证输出未记录 Dora API Key 或完整 Agent ID。
- Gateway 白名单路径已本地验证: 合法 `SWITCH_TAB_ORG` 可归一为 `screen_control`, 非法 `UNKNOWN_ACTION` 返回 `fallback/ACTION_NOT_ALLOWED`。
- 2026-06-10 真实控屏端到端验证通过: “中天证券党建大屏语音助手”可返回 `SWITCH_HOME`、`SWITCH_TAB_ORG`、`SWITCH_TAB_STUDY`、`SWITCH_TAB_ACTIVITY`; 后端 `/api/chat` 可归一为 `screen_control`, `/api/screen/execute` 可执行合法动作。
- 2026-06-10 非法页面验证通过: “打开风险预警页面”返回 `fallback`, 不执行控屏动作。
- 2026-06-10 RAGFlow MCP 问答验证通过: `ENABLE_MOCK_DORA=false` 时, Dora Agent 通过公网 MCP 调用 RAGFlow `ragflow_retrieval(keyword=false)`, 可返回张书记近期调研、入党流程、党员学习制度、党支部组织建设规范等知识库 `answer`。
- 2026-06-10 修复 Dora SSE 工具消息解析: Dora `messages` 流中会包含 MCP ToolMessage 原始 JSON chunks, Gateway 现在会忽略 `type=tool` / `ToolMessage` / `ToolMessageChunk`, 避免把工具返回的 `{"chunks": ...}` 误解析为最终回答。
- 2026-06-10 新增 `/api/chat/stream` 验证: `入党流程是什么?` 本轮抽样中首个 `dora_delta` 约 8.5s 到 17.6s, 首个分段 `tts_ready` 约 11.6s 到 19.8s, 最终 `answer` 约 12.0s 到 21.3s, 全部分段 TTS 约 15.1s 到 27.1s 就绪。

## 待确认

- 客户现场 Dora API 地址。
- 客户现场 Dora Key 权限是否长期包含 `openclaw:agents:list` 和 `openclaw:chat:sse`。
- `DORA_CHANNEL_TYPE` 在客户环境是否仍使用 `feishu`。
- Dora 外接 MCP 配置长期固化方式和访问控制策略。
- Dora 问数能力输出格式。
