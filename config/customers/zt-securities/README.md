# zt-securities Customer Config

本目录存放中天证券 POC 的非敏感客户私有配置。

## Rules

- API Key、Token、密码只放本地 `.env` 或部署环境变量, 不写入本目录。
- 根目录 `config/*.yaml` 是默认模板, 本目录同名 YAML 是客户覆盖层。
- `.env` 中显式配置的路径或运行开关优先级高于本目录 YAML。
- 大屏控制仍只能使用 `action_id` 白名单, 不执行模型生成 JavaScript。
- 问数默认保持 `excel` 稳定演示模式; 可通过 `ASK_METRICS_MODE=dora|excel|auto` 切换。

## Files

- `runtime.yaml`: 客户 ID、问数模式和运行时非敏感开关。
- `screen-actions.yaml`: FVS 页面动作白名单。
- `ask-metrics.yaml`: Excel 问数模式、数据目录和工作簿映射。
- `demo-cases.yaml`: Mock Dora 和演示问题。
- `wake-words.yaml`: 唤醒词和连续追问参数。
- `dora.yaml`: Dora Agent 非敏感配置。
- `ragflow.yaml`: RAGFlow / MCP 地址配置。
- `voice.yaml`: ASR / TTS 非敏感参数。
- `fvs.yaml`: FVS iframe 地址和页面参数。
- `customer.env.example`: 客户环境变量样例。
