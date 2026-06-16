# Config

本目录存放通用可配置数字人项目的默认模板和客户配置覆盖层。

## Files

- `screen-actions.yaml`: 大屏动作白名单。
- `wake-words.yaml`: 第一阶段语义唤醒词、V0.4 本地 VAD / 冷却参数、V0.4.1 连续对话窗口参数和播报中长唤醒词确认打断参数。
- `demo-cases.yaml`: Mock Dora 和 POC 演示用例。
- `ask-metrics.yaml`: 根级通用问数模板。默认模板不绑定具体客户 Excel, 客户实例工作簿和 sheet 映射放在客户 profile 中。
- `dora-output-schema.json`: Dora 标准输出 JSON Schema。
- `customers/`: 客户实例配置目录。新增客户时创建 `config/customers/<customer-id>/`。

本地问数数据由 `ASK_METRICS_DATA_DIR` 指向。该目录不存放在 `config/` 下, 是因为 `.xlsx` 属于演示数据源而不是运行时密钥或动作配置; 文件名和 sheet 映射由当前生效的 `ask-metrics.yaml` 管理。

V0.8 起, 后端可按 `CUSTOMER_ID` 加载对应客户目录。启用某个客户实例时配置:

```text
config/customers/<customer-id>/
```

客户目录中的 `screen-actions.yaml`、`ask-metrics.yaml`、`demo-cases.yaml`、`wake-words.yaml` 会覆盖根目录默认配置。`dora.yaml`、`ragflow.yaml`、`voice.yaml` 和 `fvs.yaml` 存放非敏感客户参数样例。

问数模式由 `ASK_METRICS_MODE=excel|dora|auto` 控制:

- `excel`: Excel Adapter 先回答固定指标。
- `dora`: Excel Adapter 不抢答。
- `auto`: Dora / Mock Dora 失败或兜底时回退 Excel。

知识库直连由 `KNOWLEDGE_MODE=dora|local_ragflow_llm|auto` 控制:

- `dora`: 默认路径, 保持 Dora -> RAGFlow MCP -> Dora 生成最终回答。
- `local_ragflow_llm`: Gateway 本地调用 RAGFlow 检索 chunks/metadata, 再由后端受控 `source_bound_extractive` summarizer 基于来源回答。
- `auto`: 知识类问题优先尝试本地来源约束回答; 配置缺失时回到 Dora 路径。

KnowledgeDirectAdapter 规则:

- RAGFlow 只做检索, 固定 `keyword=false`, 不使用 RAGFlow chat / assistant 生成最终回答。
- Summarizer 必须 `KNOWLEDGE_REQUIRE_SOURCES=true` 且 `KNOWLEDGE_NO_EVIDENCE_POLICY=fallback`。
- 无检索结果或依据不足时返回 fallback, 不编造。
- 本阶段不启用可写 Prompt、不开放配置写入、不让模型输出或执行 SQL/Python/JavaScript/shell。

TTS 真流式由以下配置控制:

- `TTS_STREAMING_ENABLED=true`: 启用 `POST /api/tts/stream`。
- `TTS_STREAMING_FALLBACK=segment`: 真流式失败时回退 `/api/chat/stream` 的分段 TTS。
- `TTS_STREAMING_AUDIO_FORMAT=pcm`: 前端使用 PCM chunk + Web Audio 播放。

V0.9 演示稳态由以下配置控制:

- `DEMO_STABLE_MODE=true`: Dora 请求失败时优先使用本地 Excel 问数和 Mock Dora 演示兜底。
- `VITE_DEMO_STABLE_MODE=true`: 前端显示“演示稳态”标识。
- `scripts/check-poc.ps1`、`scripts/start-poc.ps1`、`scripts/export-logs.ps1` 和 `scripts/smoke-demo.ps1` 默认读取根目录 `.env`。

播报中打断由 `wake-words.yaml` 的 `barge_in_*` 控制:

- `barge_in_enabled=true`: AI 回复播报中继续监听短片段。
- `barge_in_wake_words`: 只建议放长唤醒词, 当前为“小天小天”“你好小天”, 不含短词“小天”。
- `barge_in_vad_threshold`: 播报中使用的 VAD 阈值, 建议高于普通唤醒阈值以降低外放误触发。
- `barge_in_ignore_after_tts_start_ms`: TTS 开始后短暂忽略打断, 避免刚起声时误判。

## Rules

- 不要在配置文件中写入真实 API Key。
- 客户敏感信息放入本地 `.env` 或部署环境变量, 不提交到 Git。
- 客户私有 YAML 也只能放非敏感配置; API Key、Token、密码仍只放 `.env` 或部署环境变量。
- 大屏控制只能使用 `action_id`, 不能执行模型生成的 JavaScript。
- V0.6 推荐数字人主页面 iframe 嵌入 FVS: 前端使用 `VITE_FVS_INTEGRATION_MODE=iframe`, 通过 `VITE_FVS_URL` 或 `?fvs_url=` 指定 FVS 看板地址。本机 FVS 若返回 `X-Frame-Options: SAMEORIGIN`, 推荐使用同源代理路径 `/webroot/...`, 不直接把 `http://localhost:8075` 塞入 iframe。
