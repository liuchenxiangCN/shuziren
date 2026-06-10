# 开发计划

## 总原则

- 文档先行: 先写清目标、边界、验收, 再开发。
- Mock 先行: 外部依赖先用 Mock 跑通主链路。
- Adapter 化: Dora、ASR、TTS、FVS、RAGFlow 都通过适配层接入。
- 可恢复: 每轮完成后更新 `DEV_LOG.md`、`NEXT_ACTIONS.md`、`CHANGELOG.md`。
- 可移交: 交付物必须让客户能读懂当前能力、部署方式、限制和后续路线。

## 阶段路线

| 阶段 | 名称 | 目标 |
| --- | --- | --- |
| V0.0 | 文档体系 | 建立跨对话上下文和交付文档体系 |
| V0.1 | Mock 闭环 | 文本输入 -> Mock Dora -> Mock FVS -> 前端展示 -> 日志 |
| V0.2 | Dora 接入 | 接入真实 Dora Agent 和 SSE 输出 |
| V0.3 | TTS / ASR | 接入 TTS 播报和 ASR 识别 |
| V0.4 | 语义唤醒 | VAD + ASR 判断唤醒词 |
| V0.5 | RAGFlow MCP | Dora 通过 MCP 调用 RAGFlow 知识库 |
| V0.6 | FVS 真实集成 | FVS iframe / postMessage / Adapter 联调 |
| V0.7 | POC 稳定版 | 演示脚本、测试报告、移交文档 |

## V0.0 文档体系

### Goal

建立项目长期记忆系统, 让 Codex 和后续开发人员可跨对话继续。

### Scope

- 创建文档总入口。
- 创建项目蓝图、架构、开发计划、接口契约、数据契约。
- 创建 ADR 决策记录。
- 创建集成说明和客户资料目录。
- 创建开发日志、下一步、风险清单。

### Acceptance

- `docs/CODEX_CONTEXT.md` 可作为新对话入口。
- `docs/NEXT_ACTIONS.md` 明确下一阶段任务。
- `docs/DEV_LOG.md` 已记录文档体系初始化。

### Status

In Progress。

## V0.1 Mock 闭环

### Goal

初始化可 Docker 启动的最小工程, 先跑通文本 Mock 主链路。

### Scope

- 初始化项目结构。
- 创建 FastAPI 后端。
- 创建 Vue 3 前端。
- 增加 Docker Compose。
- 增加 `.env.example`。
- 增加 `/api/health`。
- 增加 `/api/chat` Mock Dora。
- 增加 `/api/screen/actions`。
- 增加 `/api/screen/execute`。
- 前端实现文本输入、状态展示、回复窗口、Mock 大屏动作。
- SQLite 或文件方式记录基础会话日志。

### Non-Scope

- 不接真实 Dora。
- 不接真实 ASR。
- 不接真实 TTS。
- 不部署真实 RAGFlow。
- 不真实调用 FVS JS。

### Acceptance

```text
docker compose up -d --build
前端 http://localhost:18000 可访问
后端 http://localhost:18080/api/health 返回 ok
POST /api/chat 输入“切换到组织建设”返回 screen_control JSON
GET /api/screen/actions 返回动作列表
POST /api/screen/execute 合法 action 成功
非法 action 被拒绝
前端可输入文字、展示回复、触发 Mock FVS 动作
```

## V0.2 Dora 接入

### Goal

在保留 Mock 的前提下接入真实 Dora Agent。

### Scope

- Dora Client。
- Dora SSE 解析。
- Dora 输出 JSON 容错。
- Markdown 包裹 JSON 提取。
- 自然语言包装为 `answer`。
- `screen_control` 强制白名单校验。

### Acceptance

```text
ENABLE_MOCK_DORA=false
真实调用 Dora Agent
前端能展示 Dora 返回内容
Dora 输出非法 action_id 时后端拒绝执行
```

## V0.3 TTS / ASR

### Goal

接入可演示的语音输入和语音播报。

### Scope

- TTS Adapter。
- Mock TTS。
- 前端音频播放。
- ASR Adapter。
- Mock ASR。
- 前端录音上传。

### Acceptance

```text
输入 speak_text 可返回音频 URL 或音频流
前端可播放
声波随播放音频变化
用户说一句话后前端显示 ASR 文本
ASR 文本可进入 chat 流程
```

## V0.4 语义唤醒

### Goal

通过 VAD + ASR 判断唤醒词, 完成第一阶段唤醒体验。

### Scope

- 前端 VAD。
- 短音频片段识别。
- 唤醒词 YAML 配置。
- 命中唤醒词进入 listening。
- 未命中不进入正式对话。

### Acceptance

```text
说“小天小天”进入 listening
说“你好小天”进入 listening
普通闲聊不触发正式对话
```

## V0.5 RAGFlow MCP

### Goal

让 Dora 可通过 MCP 调用 RAGFlow 测试知识库。

### Scope

- 整理 RAGFlow 本地部署说明。
- 准备测试知识库文档。
- 启用 MCP Server。
- Dora 配置外接 MCP。
- 知识库问答测试。

### Acceptance

```text
RAGFlow Web 可访问
MCP 地址可访问
Dora 可配置 MCP
至少 4 个党建知识库问题可返回答案
```

## V0.6 FVS 真实集成

### Goal

将 Mock FVS 动作替换为真实 FVS 页面或 Tab 控制。

### Scope

- FVS iframe 验证。
- FVS 跨域策略验证。
- postMessage 或 FVS 侧 Adapter。
- 动作白名单映射真实函数。

### Acceptance

```text
语音指令 -> action_id -> Gateway 校验 -> 前端执行 -> FVS 页面切换
至少 3 个动作可稳定执行
```

## V0.7 POC 稳定版

### Goal

形成可交付客户的 POC 稳定版本。

### Scope

- 标准演示脚本。
- 10+ 测试问题。
- 会话日志样例。
- 本地部署说明。
- 客户移交文档。
- 风险清单。
- 联调测试报告。

### Acceptance

```text
完整链路至少跑通:
1. 领导欢迎语
2. 党建文档问答
3. 党建问数
4. 大屏切换
```

