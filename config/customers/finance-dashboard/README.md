# finance-dashboard Customer Config

本目录存放企业财务综合驾驶舱客户实例的非敏感配置。主项目定位是通用可配置数字人, 本目录通过配置覆盖实现财务驾驶舱场景。

## Rules

- API Key、Token、密码只放本地 `.env` 或部署环境变量, 不写入本目录。
- 根目录 `config/*.yaml` 是默认模板, 本目录同名 YAML 是客户覆盖层。
- `.env` 中显式配置的路径或运行开关优先级高于本目录 YAML。
- 大屏控制仍只能使用 `action_id` 白名单, 不执行模型生成 JavaScript。
- 问数默认使用 `excel` 模式, 基于 `docs/demo_data/ask_metrics/finance/` 下的脱敏 Excel。

## Files

- `runtime.yaml`: 客户 ID、项目展示信息和运行时非敏感开关。
- `screen-actions.yaml`: FVS 财务驾驶舱页面动作白名单（总览/财务指标/成本分析/预算执行）。
- `ask-metrics.yaml`: Excel 问数映射, 覆盖收入、利润、成本、资产、预算、现金流等财务指标。
- `demo-cases.yaml`: Mock Dora 财务问答演示用例和演示问题。
- `wake-words.yaml`: 唤醒词（小财小财/你好小财）。
- `dora.yaml`: Dora Agent 非敏感配置。
- `ragflow.yaml`: RAGFlow / MCP 地址配置（默认 mock）。
- `voice.yaml`: ASR / TTS 参数（默认真实阿里云）。
- `fvs.yaml`: FVS iframe 地址和页面映射。
- `customer.env.example`: 客户环境变量样例，ASR/TTS 使用真实 API。
