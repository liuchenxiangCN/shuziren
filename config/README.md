# Config

本目录存放本地 POC 的第一版通用配置。

## Files

- `screen-actions.yaml`: 大屏动作白名单。
- `wake-words.yaml`: 第一阶段语义唤醒词、V0.4 本地 VAD / 冷却参数和 V0.4.1 连续对话窗口参数。
- `demo-cases.yaml`: Mock Dora 和 POC 演示用例。
- `ask-metrics.yaml`: V0.7 本地 Excel 问数工作簿和 sheet 映射。
- `dora-output-schema.json`: Dora 标准输出 JSON Schema。

V0.7 本地问数数据位于 `docs/demo_data/ask_metrics/`, 由 `ASK_METRICS_DATA_DIR` 指向。该目录不存放在 `config/` 下, 是因为三份 `.xlsx` 属于演示数据源而不是运行时密钥或动作配置; 文件名和 sheet 映射由 `ask-metrics.yaml` 管理。

## Rules

- 不要在配置文件中写入真实 API Key。
- 客户敏感信息放入本地 `.env` 或客户私有配置, 不提交到 Git。
- 大屏控制只能使用 `action_id`, 不能执行模型生成的 JavaScript。
- V0.6 推荐数字人主页面 iframe 嵌入 FVS: 前端使用 `VITE_FVS_INTEGRATION_MODE=iframe`, 通过 `VITE_FVS_URL` 或 `?fvs_url=` 指定 FVS 看板地址。本机 FVS 若返回 `X-Frame-Options: SAMEORIGIN`, 推荐使用同源代理路径 `/webroot/...`, 不直接把 `http://localhost:8075` 塞入 iframe。
