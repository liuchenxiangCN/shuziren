# 技术选型

## 选型总览

| 类型 | 选型 | 说明 |
| --- | --- | --- |
| 操作系统 | Windows 10 / 11 | 本地开发环境 |
| 容器环境 | Docker Desktop + WSL2 | 统一启动前后端和代理 |
| 前端 | Vue 3 + TypeScript + Vite | 数字人交互界面 |
| 后端 | Python FastAPI | 语音、Dora、TTS、动作白名单统一网关 |
| 前端动效 | Canvas 2D + Web Audio API + CSS | 语音球、声波、字幕、状态动效 |
| 图表渲染 | ECharts | Dora 返回结构化图表时前端渲染 |
| 前端包管理 | pnpm | 通过 Corepack 或独立安装提供 |
| 后端包管理 | uv | 统一管理 Python 依赖和虚拟环境 |
| 后端 Python | Python 3.12 | Docker 内固定 3.12; 本地开发允许 3.11/3.12 |
| 配置管理 | `.env` + YAML | 模型、Dora、RAGFlow、FVS 动作配置 |
| 会话存储 | SQLite | 本地开发阶段足够 |
| 缓存 | Redis 可选 | 第二阶段用于缓存和加速 |
| 反向代理 | Caddy 或 Nginx | 本地 HTTPS、统一代理路径 |
| 知识库 | RAGFlow Docker | 测试文档问答 |
| Agent 平台 | Dora | 主路由、问数、MCP 调用 |
| ASR | 阿里云百炼 Paraformer 或其他国产 ASR | 云语音识别 |
| TTS | 阿里云百炼 Qwen-TTS / CosyVoice 或其他国产 TTS | 云语音合成 |
| LLM | Dora 内置模型为主; Gateway 可选 Qwen / DeepSeek | Gateway 只做兜底和格式修复 |

## 国产模型策略

本项目要求语音和大模型均优先采用国产厂商。

默认建议:

- ASR: 阿里云百炼 Paraformer 实时语音识别。
- TTS: 阿里云百炼 Qwen-TTS Realtime 或 CosyVoice。
- LLM: Dora 内部配置国产模型; Gateway 如需独立 LLM, 优先 Qwen, 备选 DeepSeek。

备选:

- ASR: 科大讯飞 / 火山引擎。
- TTS: 科大讯飞 / 火山引擎。
- LLM: DeepSeek / 智谱 GLM / 豆包 / Qwen。

## 设计原则

- 不把 ASR、TTS、LLM 强行绑定到同一家厂商。
- Gateway 中通过 Adapter 模式封装供应商差异。
- `.env` 中通过 `ASR_PROVIDER`、`TTS_PROVIDER`、`LLM_PROVIDER` 切换。
- 前端不暴露模型 API Key。
- 所有模型调用统一走后端 Gateway。

## 包管理决策

项目标准固定为:

- 前端: `pnpm`
- 后端: `uv`
- 后端运行时: Docker 内使用 Python 3.12

本机环境快照, 记录于 2026-06-10:

| 工具 | 状态 |
| --- | --- |
| Git | 已安装, `2.54.0.windows.1` |
| Docker | 已安装且服务可用, Server `29.5.2` |
| Node.js | 已安装, `v24.16.0` |
| npm | 已安装, `11.13.0` |
| Corepack | 已安装, `0.35.0` |
| pnpm | 未在 PATH 中找到 |
| uv | 未在 PATH 中找到 |
| Python | PATH 上为 `3.14.5`, 不作为本项目后端运行时 |

处理方式:

- V0.1 Docker 化开发可在容器内安装并使用 pnpm / uv。
- 如需本机非 Docker 开发, 需先安装 pnpm、uv 和 Python 3.12 或 3.11。
- 不应因为本机存在 npm 或 Python 3.14 而改变项目标准。

## 为什么 Mock 优先

真实 Dora、ASR、TTS、RAGFlow、FVS 都依赖外部环境和账号权限。Mock 优先能保证:

- 本地开发不被外部服务阻塞。
- 演示流程先成型。
- 合同、网络、账号、合规未准备好时仍可推进。
- 后续替换真实服务有明确接口契约。
