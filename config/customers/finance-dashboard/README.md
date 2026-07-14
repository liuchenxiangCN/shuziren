# finance-dashboard Customer Config

本目录存放汽车营销决策分析录屏客户实例的非敏感配置。主项目定位是通用可配置数字人, 本目录通过配置覆盖实现汽车营销经营总览和线索总览场景。

## Rules

- API Key、Token、密码只放本地 `.env` 或部署环境变量, 不写入本目录。
- 根目录 `config/*.yaml` 是默认模板, 本目录同名 YAML 是客户覆盖层。
- `.env` 中显式配置的路径或运行开关优先级高于本目录 YAML。
- 大屏控制仍只能使用 `action_id` 白名单, 不执行模型生成 JavaScript。
- 当前录屏 Mock 使用 `dora` 模式, 由 `demo-cases.yaml` 承接经营问答、线索分析和知识库制度问答。

## Files

- `runtime.yaml`: 客户 ID、项目展示信息和运行时非敏感开关。
- `screen-actions.yaml`: FVS 汽车营销页面动作白名单（公司经营总览/线索总览）。
- `ask-metrics.yaml`: 旧财务 Excel 问数映射, 当前录屏不使用。
- `demo-cases.yaml`: Mock Dora 汽车营销问答、线索制度知识库回答和演示问题。
- `wake-words.yaml`: 唤醒词（小财小财/你好小财）。
- `dora.yaml`: Dora Agent 非敏感配置。
- `ragflow.yaml`: RAGFlow / MCP 地址配置（默认 mock）。
- `voice.yaml`: ASR / TTS 参数（默认真实阿里云）。
- `fvs.yaml`: FVS iframe 地址和 page 1/page 2 页面映射。
- `customer.env.example`: 客户环境变量样例，ASR/TTS 使用真实 API。
