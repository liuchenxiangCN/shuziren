# Config

本目录存放本地 POC 的通用配置和客户私有配置覆盖层。

## Files

- `screen-actions.yaml`: 大屏动作白名单。
- `wake-words.yaml`: 第一阶段语义唤醒词、V0.4 本地 VAD / 冷却参数和 V0.4.1 连续对话窗口参数。
- `demo-cases.yaml`: Mock Dora 和 POC 演示用例。
- `ask-metrics.yaml`: V0.7 本地 Excel 问数工作簿和 sheet 映射。
- `dora-output-schema.json`: Dora 标准输出 JSON Schema。
- `customers/zt-securities/`: V0.8 第一阶段新增的中天证券客户私有配置目录。

V0.7 本地问数数据位于 `docs/demo_data/ask_metrics/`, 由 `ASK_METRICS_DATA_DIR` 指向。该目录不存放在 `config/` 下, 是因为三份 `.xlsx` 属于演示数据源而不是运行时密钥或动作配置; 文件名和 sheet 映射由 `ask-metrics.yaml` 管理。

V0.8 起, 后端默认会在 `CUSTOMER_ID=zt-securities` 时加载:

```text
config/customers/zt-securities/
```

客户目录中的 `screen-actions.yaml`、`ask-metrics.yaml`、`demo-cases.yaml`、`wake-words.yaml` 会覆盖根目录默认配置。`dora.yaml`、`ragflow.yaml`、`voice.yaml` 和 `fvs.yaml` 存放非敏感客户参数样例。

问数模式由 `ASK_METRICS_MODE=excel|dora|auto` 控制:

- `excel`: Excel Adapter 先回答固定指标。
- `dora`: Excel Adapter 不抢答。
- `auto`: Dora / Mock Dora 失败或兜底时回退 Excel。

TTS 真流式由以下配置控制:

- `TTS_STREAMING_ENABLED=true`: 启用 `POST /api/tts/stream`。
- `TTS_STREAMING_FALLBACK=segment`: 真流式失败时回退 `/api/chat/stream` 的分段 TTS。
- `TTS_STREAMING_AUDIO_FORMAT=pcm`: 前端使用 PCM chunk + Web Audio 播放。

V0.9 演示稳态由以下配置控制:

- `DEMO_STABLE_MODE=true`: Dora 请求失败时优先使用本地 Excel 问数和 Mock Dora 演示兜底。
- `VITE_DEMO_STABLE_MODE=true`: 前端显示“演示稳态”标识。
- `scripts/check-poc.ps1`、`scripts/start-poc.ps1`、`scripts/export-logs.ps1` 和 `scripts/smoke-demo.ps1` 默认读取根目录 `.env`。

## Rules

- 不要在配置文件中写入真实 API Key。
- 客户敏感信息放入本地 `.env` 或部署环境变量, 不提交到 Git。
- 客户私有 YAML 也只能放非敏感配置; API Key、Token、密码仍只放 `.env` 或部署环境变量。
- 大屏控制只能使用 `action_id`, 不能执行模型生成的 JavaScript。
- V0.6 推荐数字人主页面 iframe 嵌入 FVS: 前端使用 `VITE_FVS_INTEGRATION_MODE=iframe`, 通过 `VITE_FVS_URL` 或 `?fvs_url=` 指定 FVS 看板地址。本机 FVS 若返回 `X-Frame-Options: SAMEORIGIN`, 推荐使用同源代理路径 `/webroot/...`, 不直接把 `http://localhost:8075` 塞入 iframe。
