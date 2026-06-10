# 总体架构

## 架构目标

- 本地 Windows + Docker 可运行。
- 前端、后端、配置、外部集成解耦。
- Mock 优先, 真实服务逐个替换。
- 客户相关配置外置。
- 可记录会话日志、错误日志和关键链路耗时。

## 逻辑架构

```text
┌────────────────────────────────────────────┐
│  digital-human-web                         │
│  - 麦克风采集                              │
│  - 语义唤醒 / VAD                          │
│  - 语音球 / 声波 / 字幕                     │
│  - 回复窗口                                │
│  - FVS iframe / FVS JS Adapter             │
└────────────────────────────────────────────┘
                    │
                    │ HTTP / SSE / WebSocket
                    ▼
┌────────────────────────────────────────────┐
│  digital-human-api                         │
│  - ASR Adapter                             │
│  - TTS Adapter                             │
│  - Dora SSE Adapter                        │
│  - RAGFlow / MCP 辅助                      │
│  - 大屏动作白名单校验                       │
│  - 会话状态管理                            │
│  - 日志与异常兜底                          │
└────────────────────────────────────────────┘
                    │
                    │ Open API / SSE
                    ▼
┌────────────────────────────────────────────┐
│  Dora Agent                                │
│  - 任务路由                                │
│  - 党建问数                                │
│  - 知识库 MCP 调用                         │
│  - 大屏控制意图识别                         │
│  - 结构化输出                              │
└────────────────────────────────────────────┘
        │                         │
        │ MCP                     │ Data Agent / 数据能力
        ▼                         ▼
┌──────────────────┐      ┌──────────────────┐
│ RAGFlow 知识库    │      │ 测试党建数据       │
│ - 领导资料         │      │ - 指标             │
│ - 新闻资料         │      │ - 组织             │
│ - 党建文档         │      │ - 学习情况          │
└──────────────────┘      └──────────────────┘
        │
        ▼
┌────────────────────────────────────────────┐
│ FVS 看板                                   │
│ - 已部署看板                              │
│ - 页面 / Tab 切换 JS                       │
│ - 后续正式集成                             │
└────────────────────────────────────────────┘
```

## 服务边界

### digital-human-web

负责用户可见体验:

- 页面布局和 FVS iframe / Mock 大屏。
- 文本输入和后续语音输入。
- 语音球、声波、字幕、状态动效。
- 回复窗口和 ECharts 渲染。
- TTS 音频播放。
- FVS Adapter 动作执行。

不负责:

- 保存 API Key。
- 直接调用 Dora / ASR / TTS 供应商。
- 解析模型输出并决定是否执行未校验动作。

### digital-human-api

负责工程控制和安全边界:

- 接收文本或音频。
- 调用 ASR / TTS / Dora。
- 解析 Dora 输出。
- 校验大屏动作白名单。
- 统一返回前端展示格式。
- 记录会话日志。
- 提供 Mock 模式和异常兜底。

不负责:

- 复杂 Agent 推理。
- 编排真实业务数据模型。
- 绕过 Dora 直接编造问数结果, 除非处于 Mock 模式。

### Dora Agent

负责:

- 任务意图识别。
- 问数能力调用。
- RAGFlow MCP 调用。
- 输出统一 JSON。

### RAGFlow

负责:

- 测试知识库管理。
- 文档解析和检索。
- MCP 服务暴露给 Dora。

### FVS

负责:

- 大屏内容展示。
- 页面或 Tab 切换能力。
- 与数字人前端通过 iframe、postMessage 或预埋 Adapter 集成。

## 推荐仓库结构

```text
zt-digital-human/
├─ apps/
│  ├─ web/
│  └─ api/
├─ config/
│  ├─ screen-actions.yaml
│  ├─ wake-words.yaml
│  ├─ demo-cases.yaml
│  └─ dora-output-schema.json
├─ infra/
│  ├─ caddy/
│  ├─ ragflow/
│  └─ tunnels/
├─ docs/
├─ data/
├─ logs/
├─ docker-compose.yml
├─ .env.example
└─ README.md
```

## 端口规划

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| digital-human-web | 18000 | 数字人前端 |
| digital-human-api | 18080 | 后端 API |
| reverse-proxy HTTP | 18081 | 本地统一入口 |
| reverse-proxy HTTPS | 18443 | 本地 HTTPS 入口 |
| RAGFlow Web | 9380 | RAGFlow 页面 |
| RAGFlow MCP | 9382 | MCP Server |
| SQLite | 文件型 | 本地开发 |

