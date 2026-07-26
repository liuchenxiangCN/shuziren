# 功能增强与交付路线图

> Lifecycle: `ARCHIVED_POC_SNAPSHOT`。本文记录已完成的 POC V0.8-V1.0 历史路线。文中的“当前、下一步、推荐”均只表示当时状态。2026-07-27 起的结果验收驱动 P1-P5 路线见 [05_DEVELOPMENT_PLAN.md](05_DEVELOPMENT_PLAN.md)。

本文档记录 V0.7 之后的开发顺序。用户已明确: 先做功能增强, 再做交付前优化, 最后输出验收报告、部署方案、用户手册等交付材料。

## 路线总览

| 阶段 | 名称 | 目标 | 状态 |
| --- | --- | --- | --- |
| V0.8 | 功能增强版 | Dora 通用问数、TTS 字节级真流式、运维监控 / 日志看板、客户私有配置目录 | Done for current scope |
| V0.9 | 交付优化版 | 预检脚本、一键启停、日志导出、演示模式、异常体验优化 | Done for current scope |
| V1.0 | POC 验收交付版 | 验收报告、部署方案、用户手册、运维手册、配置手册、测试报告、客户移交清单 | Done for delivery package scope |

## 总体原则

- Dora / ASR / TTS / FVS / 问数继续保留 Mock 或本地 fallback。
- 大屏控制仍坚持 `action_id` + Gateway 白名单校验。
- 禁止执行模型生成的 JavaScript、SQL、Python 或 shell 命令。
- 问数可以由 Dora 承接, 但必须保留切回固定 Excel 指标匹配的方案。
- 项目本体保持通用可配置数字人, 客户私有配置从核心代码中解耦, 客户差异进入 `config/customers/<customer-id>/` 和本地 `.env`。
- 交付材料在功能增强和交付优化完成后再输出, 避免文档先行锁死尚未实现的能力。

## V0.8 功能增强版

### 1. 客户私有配置目录

目标: 把 env、大屏地址、动作映射、Dora Agent、问数模式、RAGFlow 地址、ASR/TTS 参数等客户化。

状态: Done for V0.8 第一阶段。已建立 `config/customers/zt-securities/`, 后端已接入客户级 Screen Actions、Ask Metrics、Demo Cases、Wake Words 覆盖, 并提供 Dora、RAGFlow、Voice、FVS 非敏感配置样例。

建议目录:

```text
config/customers/zt-securities/
├─ customer.env.example
├─ runtime.yaml
├─ screen-actions.yaml
├─ ask-metrics.yaml
├─ fvs.yaml
├─ dora.yaml
├─ ragflow.yaml
├─ voice.yaml
└─ demo-cases.yaml
```

建议配置加载规则:

- 根目录配置是默认模板。
- 客户目录配置作为覆盖层。
- `.env` 只放密钥、本机端口和本地部署参数。
- YAML 放非敏感客户配置。
- 前端只接收后端透出的安全配置, 不直接读取或暴露密钥。
- 新增 `CUSTOMER_ID=zt-securities` 和 `CUSTOMER_CONFIG_DIR=/app/config/customers/zt-securities`。

验收:

- 更换 FVS 地址无需改代码。
- 更换客户动作白名单无需改核心配置。
- 更换问数模式无需改代码。
- `.env.example` 和客户私有样例完整。

### 2. Dora 通用问数 + Excel fallback

目标: 让 Dora 承接真正通用问数, Gateway 保留固定 Excel 指标匹配作为稳定兜底。

状态: Done for V0.8 第一阶段。已实现 `ASK_METRICS_MODE=excel|dora|auto`; `excel` 11 个问数 smoke 通过, `dora` 不让 Excel Adapter 抢答, `auto` 可在 Dora / Mock Dora 失败或兜底时回退 Excel。真实 Dora 通用问数质量仍需后续结合客户数据源验证。

建议配置:

```env
ASK_METRICS_MODE=auto
```

模式说明:

| 模式 | 行为 |
| --- | --- |
| `excel` | 固定走当前 Gateway Excel Adapter |
| `dora` | 问数交给 Dora, Excel Adapter 不抢占 |
| `auto` | 优先 Dora; Dora 失败、超时或返回低质量兜底时再回退 Excel |

建议实现:

- 新增 AskMetrics Router / Provider 层, 统一管理 `excel`、`dora`、`auto`。
- Dora 问数仍归一为 `/api/chat` 的 `answer`。
- Dora 问数回答必须带来源、口径、时间范围或兜底说明。
- Gateway 不执行 Dora 生成的 SQL / JS / Python。
- 当前 Excel Adapter 保留为稳定演示 fallback。

验收:

- Dora 能回答至少 10 个非固定模板问数问题。
- `ASK_METRICS_MODE=excel` 时, 现有 11 个 Excel 问数问题不退化。
- `ASK_METRICS_MODE=auto` 时, Dora 不可用或返回 fallback 后可切回 Excel。
- 知识库问答和大屏控制不被问数 Router 抢占。

### 3. TTS 字节级真流式

目标: 从“Dora 文本增量 + 分段 TTS 文件播放”升级为真正边合成边播放。

状态: Done for V0.8 第二阶段。已新增 `POST /api/tts/stream`, 后端 `TtsProvider.stream_synthesize` 支持 Mock PCM chunk 和阿里云 CosyVoice WebSocket 二进制帧逐块转发; 前端使用 PCM Web Audio 播放 chunk, 并在失败时回退现有分段 TTS 文件播放。

建议配置:

```env
TTS_STREAMING_ENABLED=true
TTS_STREAMING_FALLBACK=segment
TTS_STREAMING_AUDIO_FORMAT=pcm
```

建议实现:

- 后端新增真实流式 TTS Provider 接口。
- 新增 `POST /api/tts/stream`, 或扩展 `/api/chat/stream` 推送音频 chunk。
- 前端使用 Web Audio 或 MediaSource 播放流式音频。
- 保留当前分段 TTS 文件方案作为 fallback。
- 等待提示音策略继续保留, AI 音频到达后打断等待提示。

验收:

- 首个音频 chunk 明显早于完整 TTS 文件生成。
- 流式失败自动回退分段 TTS。
- 播报、打断、连续追问不退化。

### 4. 运维监控和日志看板

目标: 客户或实施人员能看到服务状态、会话日志、错误和耗时。

状态: Done for V0.8 第三阶段。已新增只读脱敏 Ops API, 前端新增“演示 / 运维”视图切换, 看板可查看依赖状态、最近会话、错误列表、耗时指标并导出 Markdown 日志摘要。

建议后端接口:

- `GET /api/ops/health`
- `GET /api/ops/dependencies`
- `GET /api/ops/sessions`
- `GET /api/ops/session/{session_id}`
- `GET /api/ops/metrics`
- `GET /api/ops/export`

建议前端页面:

- 服务状态。
- Dora / RAGFlow / FVS / ASR / TTS 连通性。
- 最近会话。
- 错误列表。
- 平均耗时。
- 最近控屏动作。

验收:

- 能从页面看到最近 N 轮对话。
- 能看到外部依赖是否可用。
- 能导出或复制验收日志摘要。
- SQLite 日志记录 ASR / Dora / RAGFlow / TTS / FVS 的关键耗时和错误。

## V0.9 交付优化版

目标: 把 V0.8 能力整理成现场更稳、更易排障的交付形态。

状态: Done for V0.9 scope。已新增 `scripts/check-poc.ps1`、`start-poc.ps1`、`stop-poc.ps1`、`export-logs.ps1`、`smoke-demo.ps1`; 新增 `DEMO_STABLE_MODE` / `VITE_DEMO_STABLE_MODE` 和 `GET /api/demo/config`; 固化 Ops 日志包导出流程; 前端补充 FVS iframe 加载失败提示; 后端补充 Dora、Excel 问数、TTS 分段等关键异常安全兜底。

范围:

- 预检脚本: Docker、端口、API、Web、RAGFlow、Dora、FVS、ASR、TTS。
- 一键启停脚本: `scripts/start-poc.ps1`、`scripts/stop-poc.ps1`、`scripts/check-poc.ps1`。
- 日志导出: 最近会话、验收问题结果、依赖状态。
- 演示模式: `DEMO_STABLE_MODE=true`, 外部服务失败时提示 fallback。
- 异常体验优化: Excel 缺文件、Dora 超时、TTS 流式失败、FVS iframe 加载失败、麦克风权限失败。

验收:

- 新机器按文档和脚本可启动 POC。
- 预检能定位常见环境问题。
- 演示问题集可一键 smoke。
- 失败时不出现系统堆栈或裸错误。

## V1.0 POC 验收交付版

目标: 输出客户可签收和可移交的完整交付包。

状态: Done for delivery package scope。已输出 `docs/delivery/v1.0/` 交付包; 现场截图、真实依赖确认和客户签字仍需按交付包在现场补齐。

交付物:

- 验收报告。
- 部署方案。
- 用户手册。
- 运维手册。
- 配置手册。
- 演示脚本。
- 测试报告。
- 风险和后续路线。
- 客户移交清单。

验收:

- 文档能覆盖部署、启停、演示、排障、配置、数据边界和后续扩展。
- 验收报告包含现场复演结果、截图、耗时和客户确认项。
- 客户能按文档复现 POC 能力。

## 推荐 Goal 顺序

### Goal 1

```text
完成 V0.8 功能增强第一阶段: 重构客户私有配置目录, 并实现 ASK_METRICS_MODE=dora|excel|auto 的问数模式切换, 保留当前 Excel fallback, 更新相关文档和验证用例。
```

Status: Done。

### Goal 2

```text
完成 V0.8 功能增强第二阶段: 实现 TTS 字节级真流式播放, 保留分段 TTS fallback, 更新 `/api/chat/stream` 或新增 `/api/tts/stream`, 并完成前端播放、打断和回退验证。
```

Status: Done。

### Goal 3

```text
完成 V0.8 功能增强第三阶段: 新增运维监控和日志看板, 覆盖依赖健康、最近会话、错误列表、耗时指标和日志导出。
```

Status: Done。

### Goal 4

```text
完成 V0.9 交付优化: 新增预检脚本、一键启停脚本、演示模式、日志导出和关键异常兜底体验。
```

Status: Done。

### Goal 5

```text
完成 V1.0 POC 验收交付包: 输出验收报告、部署方案、用户手册、运维手册、配置手册、测试报告和客户移交清单。
```

Status: Done for delivery package scope。
