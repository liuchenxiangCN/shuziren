# 开发日志

本文件记录每轮开发的事实结果。不要写愿望, 只写已经发生的变更、验证和遗留问题。

## 2026-06-10

### Completed

- 根据《中天证券党建大屏对话数字人本地开发技术方案》建立文档驱动开发体系。
- 创建项目文档总入口、Codex 跨对话上下文、项目蓝图、架构、开发计划、接口契约、数据契约、配置说明、部署说明、测试计划、演示脚本、客户移交文档、风险清单。
- 创建 ADR 决策记录目录。
- 创建 Dora、RAGFlow、FVS、ASR/TTS 集成说明。
- 创建中天证券客户资料目录。
- 创建根目录 `AGENTS.md`, 作为 Agent 阅读顺序、开发规则和文档维护规则入口。
- 初始化当前目录为 Git 仓库, 默认分支为 `main`。
- 检查本机工具链: Git、Docker、Node.js、npm、Corepack 可用; pnpm 和 uv 未安装; PATH 上 Python 为 3.14.5。
- 固定项目包管理决策: 前端使用 pnpm, 后端使用 uv, Docker 内后端运行时使用 Python 3.12。
- 创建 `.gitignore`、`.env.example` 和第一版 `config/` 配置文件。

### Changed Files

- `README.md`
- `AGENTS.md`
- `.gitignore`
- `.env.example`
- `config/`
- `data/.gitkeep`
- `logs/.gitkeep`
- `docs/`

### Verification

- 文档文件已创建。
- Git 仓库已初始化。
- Docker 服务可用, Server 版本为 `29.5.2`。
- 本地 Markdown 链接检查通过。
- 尚未创建代码工程, 无需运行前后端测试。

### Notes

- 当前阶段为 V0.0 文档体系初始化。
- 下一阶段建议进入 V0.1 Mock 闭环工程初始化。
