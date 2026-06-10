# Dora 集成说明

## 目标

Dora 负责 Agent 路由、问数、RAGFlow MCP 调用和结构化输出。Gateway 负责调用 Dora、解析输出、容错和动作安全校验。

## 配置项

```env
DORA_BASE_URL=https://your-dora-host
DORA_API_KEY=replace_me
DORA_AGENT_ID=replace_me
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

## Gateway 处理规则

- 标准 JSON 直接解析。
- Markdown 包裹 JSON 时提取 JSON。
- 自然语言包装为 `answer`。
- `screen_control` 必须校验动作白名单。
- 非法 action 返回兜底话术。
- Dora 超时返回服务不可用话术。

## 待确认

- Dora 当前 API 地址。
- Dora 鉴权方式。
- Dora SSE event 格式。
- Dora Agent ID 获取方式。
- Dora 外接 MCP 配置位置。
- Dora 问数能力输出格式。

