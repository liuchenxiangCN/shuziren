# Config

本目录存放本地 POC 的第一版通用配置。

## Files

- `screen-actions.yaml`: 大屏动作白名单。
- `wake-words.yaml`: 第一阶段语义唤醒词。
- `demo-cases.yaml`: Mock Dora 和 POC 演示用例。
- `dora-output-schema.json`: Dora 标准输出 JSON Schema。

## Rules

- 不要在配置文件中写入真实 API Key。
- 客户敏感信息放入本地 `.env` 或客户私有配置, 不提交到 Git。
- 大屏控制只能使用 `action_id`, 不能执行模型生成的 JavaScript。

