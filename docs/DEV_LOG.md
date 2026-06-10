# 开发日志

本文件记录每轮开发的事实结果。不要写愿望, 只写已经发生的变更、验证和遗留问题。

## 2026-06-10

### V0.8 / V0.9 / V1.0 路线文档调整

#### Completed

- 根据用户要求调整后续路线: 先做功能增强, 再做交付前优化, 最后输出验收报告、部署方案和用户手册等交付材料。
- 新增 `docs/14_ENHANCEMENT_ROADMAP.md`, 记录 V0.8 / V0.9 / V1.0 的目标、范围、验收和推荐 goal 顺序。
- 新增 ADR-0011, 记录“先功能增强再交付优化”的阶段决策。
- `docs/05_DEVELOPMENT_PLAN.md` 增加 V0.8 功能增强版、V0.9 交付优化版、V1.0 POC 验收交付版。
- `docs/NEXT_ACTIONS.md` 当前阶段改为 V0.8 功能增强版准备, 并写入第一推荐 goal: 客户私有配置目录 + `ASK_METRICS_MODE=dora|excel|auto`。
- `docs/CODEX_CONTEXT.md` 更新跨对话恢复上下文和推荐启动提示。
- `docs/06_API_CONTRACT.md` 增加 V0.8 Draft: `ASK_METRICS_MODE`、`POST /api/tts/stream`、Ops APIs。
- `docs/07_DATA_CONTRACT.md` 增加 V0.8 Draft: Ask Metrics Mode、Streamed Audio Chunk、Ops Status、Customer Config Overlay。
- `docs/08_CONFIG_GUIDE.md` 增加 V0.8 Draft: 客户私有配置目录、`CUSTOMER_ID`、`CUSTOMER_CONFIG_DIR`、`ASK_METRICS_MODE`、TTS 真流式配置。
- `docs/10_TEST_PLAN.md` 增加 V0.8 / V0.9 / V1.0 测试草案。
- `docs/13_RISKS_AND_TODO.md` 增加 Dora 通用问数、TTS 真流式、运维看板敏感信息、客户配置覆盖层风险。
- `docs/12_CUSTOMER_HANDOFF.md` 的后续建议同步为 V0.8 -> V0.9 -> V1.0。

#### Changed Files

- `docs/00_INDEX.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/14_ENHANCEMENT_ROADMAP.md`
- `docs/CODEX_CONTEXT.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`
- `docs/CHANGELOG.md`
- `docs/decisions/ADR-0011-enhancement-before-handoff.md`

#### Verification

- 本轮仅更新文档, 未修改运行时代码。
- `git diff --check` 通过。

#### Notes

- 下一轮推荐用 goal 方式执行 V0.8 第一阶段。
- 正式验收报告、部署方案和用户手册延后到 V1.0, 以 V0.8 / V0.9 的真实实现和验证结果为准。

### V0.7 POC 稳定版问数 Adapter 与演示包准备

#### Completed

- 新增 `apps/api/app/services/ask_metrics.py`, 实现 Gateway 本地只读 Excel 问数 Adapter。
- 新增 `config/ask-metrics.yaml`, 管理 V0.7 本地问数工作簿文件名和 sheet 映射。
- Adapter 使用 Python 标准库解析 `.xlsx`, 不新增后端依赖, 读取 `docs/demo_data/ask_metrics/` 下三份脱敏样例:
  - `zt_party_study_metrics_2026.xlsx`
  - `zt_party_org_life_metrics_2026.xlsx`
  - `zt_party_development_metrics_2026.xlsx`
- `/api/chat` 在调用 Mock Dora / 真实 Dora 前优先匹配问数意图, 命中后直接返回标准 `answer`, 并在 `display.source` 和 bullets 中标明数据来源。
- `/api/chat/stream` 问数命中后直接返回 `metadata`、`dora_delta`、`answer`, 并继续复用现有分段 TTS 逻辑。
- Docker API 镜像已复制 `docs/demo_data`, Compose 已新增只读挂载 `./docs/demo_data:/app/docs/demo_data:ro`、`ASK_METRICS_DATA_DIR=/app/docs/demo_data/ask_metrics` 和 `ASK_METRICS_CONFIG_PATH=/app/config/ask-metrics.yaml`。
- 新增 ADR-0010, 记录 V0.7 采用本地 Excel Adapter 承接问数的决策。
- 同步更新 API 契约、数据契约、配置说明、部署说明、测试计划、POC 演示脚本、客户移交、客户验收清单、客户演示用例、风险清单、下一步和跨对话上下文。

#### Changed Files

- `.env.example`
- `apps/api/Dockerfile`
- `apps/api/app/config.py`
- `apps/api/app/main.py`
- `apps/api/app/services/ask_metrics.py`
- `config/ask-metrics.yaml`
- `docker-compose.yml`
- `config/README.md`
- `docs/00_INDEX.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/09_LOCAL_DEPLOY.md`
- `docs/10_TEST_PLAN.md`
- `docs/11_POC_DEMO_SCRIPT.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/CODEX_CONTEXT.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`
- `docs/customers/zt-securities/DEMO_CASES.md`
- `docs/decisions/ADR-0010-local-excel-ask-metrics-adapter.md`
- `docs/demo_data/ask_metrics/README.md`

#### Verification

- `python -m compileall apps/api/app` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `docker compose up -d --build api` 成功。
- API 容器内 `uv run python -m compileall app` 通过。
- `GET http://127.0.0.1:18080/api/health` 返回 `status=ok`。
- `/api/chat` 问数 smoke 通过 11 题:
  - `当前党员学习完成率是多少?` -> `answer`, 87.5%, 128 人, 112 人。
  - `本月有多少人完成学习?` -> `answer`, 112 人。
  - `哪个支部学习完成率最低?` -> `answer`, 信息技术支部, 83.3%。
  - `本月主题党日开展了几次?` -> `answer`, 34 次。
  - `组织生活平均参会率是多少?` -> `answer`, 83.9%。
  - `整改事项闭环率是多少?` -> `answer`, 46.7%。
  - `当前入党积极分子有多少人?` -> `answer`, 12 人。
  - `发展对象有多少人? 分别在哪些支部?` -> `answer`, 7 人及支部分布。
  - `本年转正党员有多少人?` -> `answer`, 3 人。
  - `哪些党员发展材料还待补充?` -> `answer`, 3 人及支部 / 人员 ID。
  - `总结一下当前党建工作整体情况` -> `answer`, 综合学习、组织生活和党员发展指标。
- 服务级检查确认 `入党流程是什么?` 不被问数 Adapter 拦截。
- `/api/chat/stream` 输入 `当前党员学习完成率是多少?` 返回事件顺序 `metadata`、`dora_delta`、`answer`。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose up -d --build web` 成功, API 和 Web 容器均启动。
- `GET http://127.0.0.1:18000` 返回 HTTP 200。

#### Notes

- 当前问数能力是本地 POC 稳定演示方案, 不是通用 BI 问数引擎。
- 正式客户问数仍需确认真实数据源、指标口径、刷新频率和授权范围。
- Adapter 不执行模型生成 SQL、Python 或 JavaScript; 未命中问数意图时继续走 Dora / Mock Dora 原链路。

### V0.6 FVS 网页框真实集成准备

#### Completed

- 用户确认 V0.6 先尝试把数字人前端作为 FVS 网页框嵌入大屏, 并提供帆软 FVS 网页框通信文档。
- 已核对帆软文档中的关键通信路径:
  - FVS 主模板使用 `duchamp.onlyCommunicateWithOrigins([...])` 指定允许通信的网页框来源。
  - 数字人网页框可通过 `window.parent.postMessage(message, targetOrigin)` 向 FVS 主模板发送消息。
  - FVS 主模板使用 `duchamp.addPostMessageListener(callback)` 接收网页框消息。
- 新增 `apps/web/src/fvsAdapter.ts`, 支持 `mock`、`iframe`、`parent` 三类模式; `web-frame` / `fvs-web-frame` 作为 `parent` 别名。
- 前端在 `VITE_FVS_INTEGRATION_MODE=parent` 时按 FVS 网页框模式运行, 使用单列嵌入友好布局, 不再优先展示内部 Mock 大屏。
- 前端只在 `/api/screen/execute` 返回 `success=true` 后发送 `FVS_ACTION` 消息给父 FVS 页面。
- `FVS_ACTION` 消息包含 `type=FVS_ACTION`、`source=zt-digital-human`、`action_id`、`actionId`、`functionName` 和 `params`; FVS 侧应以 `action_id` 做固定映射。
- 增强前端麦克风失败提示, 可区分非安全上下文、网页框未授予 microphone 权限、浏览器拒绝、设备不存在或设备占用等常见原因。
- 根据用户现场反馈, V0.6 推荐方向从“FVS 网页框嵌入数字人”切换为“数字人前端主页面 iframe 嵌入 FVS 看板”。
- `apps/web/src/fvsAdapter.ts` 新增运行时 URL 参数支持: `?fvs_url=...`、`?fvs_origin=...` 和 `?fvs_mode=...`, 便于不重建前端直接测试 FVS URL。
- 本地 `.env` 已将 `VITE_FVS_INTEGRATION_MODE` 从 `parent` 切换为 `iframe`。
- 新增 ADR-0007, 并将 ADR-0006 标记为 Superseded。
- `docker-compose.yml` 和 `apps/web/Dockerfile` 已透出 `VITE_FVS_URL`、`VITE_FVS_INTEGRATION_MODE`、`VITE_FVS_TARGET_ORIGIN` 构建参数。
- 本地 `.env` 已将 FVS 配置从占位 `iframe` 切到 `parent` 网页框通信模式。
- 新增 ADR-0006, 记录 FVS 网页框通信集成方向。
- 同步更新 FVS 集成说明、配置说明、API / 数据契约、测试计划、客户动作清单、客户移交、风险、下一步和变更记录。

#### Changed Files

- `.env`
- `.env.example`
- `apps/web/Dockerfile`
- `apps/web/src/App.vue`
- `apps/web/src/fvsAdapter.ts`
- `apps/web/src/style.css`
- `docker-compose.yml`
- `config/README.md`
- `docs/00_INDEX.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_CONTEXT.md`
- `docs/NEXT_ACTIONS.md`
- `docs/customers/zt-securities/SCREEN_ACTIONS.md`
- `docs/decisions/ADR-0006-fvs-web-frame-communication.md`
- `docs/integrations/FVS_INTEGRATION.md`

#### Verification

- `corepack pnpm --dir apps/web build` 通过。
- 增强麦克风失败提示后, `corepack pnpm --dir apps/web build` 再次通过。
- `python -m compileall apps/api/app` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `docker compose up -d --build web` 成功, API 和 Web 容器均已重建并启动。
- 增强麦克风失败提示后, `docker compose up -d --build web` 再次成功。
- iframe host 方向调整后, `corepack pnpm --dir apps/web build` 通过。
- iframe host 方向调整后, `docker compose up -d --build web` 成功。
- Codex 内置浏览器使用 `http://127.0.0.1:18000/?fvs_url=http%3A%2F%2F127.0.0.1%3A18080%2Fapi%2Fhealth` 验证运行时 FVS URL 参数生效: 页面显示 `FVS iframe`, iframe `src` 正确, 内部 Mock 屏未出现, 控制台无 error。
- `GET http://127.0.0.1:18080/api/health` 返回 `status=ok`。
- `GET http://127.0.0.1:18000` 返回 HTTP 200。
- Codex 内置浏览器验证 `http://127.0.0.1:18000`: 当前构建为 `workspace fvs-web-frame` 单列布局, 页面显示 `FVS 通信已就绪`, 内部 Mock 大屏未出现, 文本输入可见, 控制台无 error。
- `POST /api/screen/execute` 执行 `SWITCH_TAB_ORG` 返回 `success=true`。
- `POST /api/screen/execute` 执行 `UNKNOWN_ACTION` 返回 `success=false` 和 `ACTION_NOT_ALLOWED`。

#### Notes

- 本轮尚未接到真实 FVS 页面 / Tab 控制 API。
- 下一步需要在真实 FVS 主模板中添加网页框组件, 加载数字人前端 URL, 配置 `duchamp.onlyCommunicateWithOrigins` 和 `duchamp.addPostMessageListener`, 再映射 3 个以上动作。
- FVS 侧也不得根据 `functionName` 动态执行脚本, 只能按 `action_id` 固定映射。

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

### V0.1 Mock 闭环初始化

#### Completed

- 创建 `apps/api` FastAPI 后端工程, 使用 uv 管理依赖, Docker 内运行 Python 3.12。
- 创建 `apps/web` Vue 3 + TypeScript + Vite 前端工程, 使用 pnpm 管理依赖。
- 创建根目录 `docker-compose.yml`, 暴露前端 `18000` 和后端 `18080`。
- 后端读取现有 `config/screen-actions.yaml`、`config/demo-cases.yaml`、`config/wake-words.yaml`。
- 实现 `GET /api/health`、`POST /api/chat`、`GET /api/screen/actions`、`POST /api/screen/execute`。
- `/api/chat` 已支持 Mock Dora 的 `answer`、`screen_control`、`fallback` 返回。
- `/api/screen/execute` 已通过后端白名单校验 `action_id`, 合法动作成功, 非法动作返回 `ACTION_NOT_ALLOWED`。
- 前端已实现文本输入、Mock 回复展示、Mock FVS 当前页面/最近动作展示。
- 增加 SQLite 会话日志写入, 数据库路径为 `data/sessions.db`。
- 生成并提交 `apps/web/pnpm-lock.yaml` 和 `apps/api/uv.lock`, Docker 构建使用 frozen install。
- 更新 `.env.example` 和配置说明中的 `DEMO_CASES_PATH`、`WAKE_WORDS_PATH`。

#### Changed Files

- `.env.example`
- `README.md`
- `apps/api/`
- `apps/web/`
- `docker-compose.yml`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/09_LOCAL_DEPLOY.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/13_RISKS_AND_TODO.md`

#### Verification

- `docker compose config` 通过。
- `docker compose up -d --build` 通过, 前后端容器均保持运行。
- `GET http://localhost:18080/api/health` 返回 `status=ok`。
- `GET http://localhost:18080/api/screen/actions` 返回 4 个白名单动作。
- `POST /api/chat` 输入“请切换到组织建设页面”返回 `type=screen_control` 和 `SWITCH_TAB_ORG`。
- `POST /api/chat` 输入“张书记”和“入党流程是什么”返回 `type=answer`。
- `POST /api/chat` 输入未命中内容返回 `type=fallback`。
- `POST /api/screen/execute` 执行 `SWITCH_TAB_ORG` 返回 `success=true`。
- `POST /api/screen/execute` 执行 `UNKNOWN_ACTION` 返回 `success=false` 和 `ACTION_NOT_ALLOWED`。
- `GET http://localhost:18000` 返回 HTTP 200。
- Codex 内置浏览器验证前端可输入“请切换到组织建设页面”, 展示数字人回复和 `SWITCH_TAB_ORG`, Mock FVS 切换到“组织建设”, 控制台无 error。

#### Notes

- V0.1 未接入真实 Dora、ASR、TTS、RAGFlow、FVS。
- PowerShell 直接发送中文 JSON 时本地终端可能出现编码显示干扰; 使用浏览器和 Unicode escape JSON 验证链路正常。

### V0.2 Dora 配置准备

#### Completed

- 创建本地 `.env`, 写入 Dora 环境地址、Dora Key、Agent 名称和 `DORA_CHANNEL_TYPE=feishu`; `.env` 已被 `.gitignore` 排除。
- 更新 `.env.example`, 增加 `DORA_AGENT_NAME` 和 `DORA_CHANNEL_TYPE`, 并允许 `DORA_AGENT_ID` 为空。
- 更新 `docker-compose.yml`, 将 Dora 配置变量传入后端容器。
- 更新后端 Settings, 增加 Dora Base URL、Key、Agent ID、Agent Name、Channel Type、Chat Mode 和 Timeout 配置字段。
- 更新 Dora 集成说明, 明确 V0.2 使用 Dora OpenClaw API, 支持按 Agent 名称自动发现已发布 Agent。

#### Verification

- 尚未调用真实 Dora; 当前仅完成 V0.2 配置文件准备。
- 真实接入时先通过 `GET /external/api/openclaw/agents` 查找 `DORA_AGENT_NAME` 对应的已发布 Agent。

#### Notes

- 当前 `DORA_CHANNEL_TYPE` 暂用 `feishu`, 如客户环境要求其他渠道值, 只需修改 `.env`。
- Dora Key 只应保存在本地 `.env`, 不应写入前端、文档或 Git。

### V0.2 Dora Adapter 实现

#### Completed

- 增加 `apps/api/app/services/dora_client.py`, 实现 Dora OpenClaw `list_agents`、`resolve_agent_id` 和 `sse_chat`。
- 增加 `apps/api/app/services/dora_normalizer.py`, 支持 Dora 标准 JSON、Markdown JSON、自然语言输出归一化。
- `/api/chat` 已根据 `ENABLE_MOCK_DORA` 分流: `true` 继续走 V0.1 Mock, `false` 调用 Dora OpenClaw SSE。
- `DORA_BASE_URL`、`DORA_API_KEY`、`DORA_AGENT_ID`、`DORA_AGENT_NAME`、`DORA_CHANNEL_TYPE`、`DORA_TIMEOUT_SECONDS` 均从 `.env` / 环境变量读取。
- 当 `DORA_AGENT_ID` 为空时, 已按 `DORA_AGENT_NAME=战区业绩分析Agent-刘峰` 自动发现已发布 Agent。
- Dora SSE 解析已适配当前 OpenClaw event 形态: 忽略 `metadata` / `values`, 从 `messages` chunk 中收敛回答文本。
- Dora 输出统一返回 `answer` / `screen_control` / `fallback`; Dora `clarify` 在 V0.2 中先转为 `answer` 展示。
- `screen_control` 仍只透出白名单中的 `action.id`, 非法 action 返回 `fallback` 和 `ACTION_NOT_ALLOWED`。
- 增加后端依赖 `httpx`, 并刷新 `apps/api/uv.lock`。
- `.env.example` 中 `DORA_AGENT_NAME` 示例更新为 `战区业绩分析Agent-刘峰`。

#### Verification

- `docker compose build api` 通过, `uv sync --frozen --no-dev` 安装 `httpx` 成功。
- `python -m compileall app` 通过。
- 容器内归一化 smoke tests 通过: Markdown JSON、自然语言、合法 `screen_control`、非法 `screen_control` 均符合预期。
- V0.1 回归通过: `GET /api/health`、Mock `answer` / `screen_control` / `fallback`、动作白名单、合法动作执行、非法动作拒绝、前端 HTTP 200。
- Dora 连通性验证通过: `list_agents` 返回可用列表, `resolve_agent_id` 成功匹配本地 `.env` 中的已发布 Agent, `sse_chat` 返回内容并归一为 `answer`。
- 临时设置 `ENABLE_MOCK_DORA=false` 后, `POST /api/chat` 真实调用 Dora 并返回归一化 `answer`; 验证后已将运行态恢复为 `ENABLE_MOCK_DORA=true`。

#### Notes

- 未接入真实 ASR、TTS、RAGFlow、FVS。
- 真实 Dora 当前连接的是“战区业绩分析Agent-刘峰”, 已验证问答连通性; 真实 `screen_control` 还需在 Dora Agent Prompt 对齐项目动作白名单后验证。
- PowerShell 管道直接传中文到容器时仍可能出现编码替换; HTTP JSON 使用 Unicode escape 验证正常。

### V0.2 Dora Prompt 对齐与控屏探测

#### Completed

- 更新 `docs/integrations/DORA_AGENT_PROMPT.md`, 将 Dora Agent Prompt 收紧为 V0.2 可复制到 Dora 后台的专用版本。
- Prompt 已写入 4 个白名单动作: `SWITCH_HOME`、`SWITCH_TAB_ORG`、`SWITCH_TAB_STUDY`、`SWITCH_TAB_ACTIVITY`。
- Prompt 已明确禁止 Dora 输出 JavaScript、函数名、FVS 参数、HTML 或脚本。
- Prompt 已补充非法页面请求的 `fallback` 输出要求。
- 更新 `docs/customers/zt-securities/SCREEN_ACTIONS.md`, 补充 Dora 对每个动作应输出的 JSON 示例。
- 更新 `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`, 标记 Docker、前端 Mock、Dora Adapter、基础日志、错误兜底等当前状态。
- 更新 `docs/12_CUSTOMER_HANDOFF.md`, 修正“尚未实现代码工程”的过期描述。

#### Verification

- 真实 Dora 控屏探测已执行 3 组问题: 普通“切换到组织建设”、强约束角色/JSON 指令、非法 action JSON 指令。
- 当前已发布 Agent “战区业绩分析Agent-刘峰”均未返回项目 `screen_control` JSON, 而是坚持战区业绩分析职责边界并返回自然语言 `answer`。
- Gateway 白名单路径本地验证通过: Dora-like 合法 `SWITCH_TAB_ORG` JSON 归一为 `screen_control`, Dora-like 非法 `UNKNOWN_ACTION` JSON 归一为 `fallback/ACTION_NOT_ALLOWED`。
- `/api/screen/execute` 复验通过: `SWITCH_TAB_ORG` 执行成功, `UNKNOWN_ACTION` 被拒绝。

#### Notes

- V0.2 代码侧已具备真实 Dora `screen_control` 接收和白名单校验能力。
- 真实 Dora 控屏端到端验证当前受阻于远端 Agent Prompt 未发布为党建大屏专用版本。
- 下一步需要在 Dora 后台发布 `docs/integrations/DORA_AGENT_PROMPT.md` 中的 Prompt, 或将 `.env` 指向一个已发布的党建大屏专用 Agent。

### V0.2 Dora 真实控屏联调完成

#### Completed

- 用户已在 Dora 后台发布专用 Agent: `中天证券党建大屏语音助手`。
- 独立 URL 已确认对应 OpenClaw agents 列表中的已发布 Agent `id=e969ca51-e898-440e-8ceb-b814d7fb83f6`。
- 本地 `.env` 已将 `DORA_AGENT_NAME` 从 `战区业绩分析Agent-刘峰` 切换为 `中天证券党建大屏语音助手`, `DORA_AGENT_ID` 保持为空。
- `.env.example` 已同步更新为 `DORA_AGENT_NAME=中天证券党建大屏语音助手`。
- 真实 Dora SSE 已验证 4 个白名单控屏动作: `SWITCH_TAB_ORG`、`SWITCH_TAB_STUDY`、`SWITCH_HOME`、`SWITCH_TAB_ACTIVITY`。
- 真实 Dora 非法页面“风险预警页面”返回 `fallback`, 未产生可执行 action。
- 真实 `/api/chat` HTTP 路径已验证 `screen_control` 返回和 `/api/screen/execute` 合法动作执行。

#### Verification

- `list_agents` 返回 313 个 Agent, 可精确匹配 `中天证券党建大屏语音助手`, 状态为 `PUBLISHED`。
- `resolve_agent_id` 在 `DORA_AGENT_ID` 为空时解析到新 Agent。
- 直接 Dora SSE 验证:
  - “请切换到组织建设页面” -> `screen_control` / `SWITCH_TAB_ORG`
  - “打开党员学习” -> `screen_control` / `SWITCH_TAB_STUDY`
  - “返回首页” -> `screen_control` / `SWITCH_HOME`
  - “请切换到党建活动页面” -> `screen_control` / `SWITCH_TAB_ACTIVITY`
  - “请打开风险预警页面” -> `fallback`
  - “入党流程是什么？” -> `answer`
- 临时设置 `ENABLE_MOCK_DORA=false` 后, `POST /api/chat` 输入“请切换到组织建设页面”返回 `screen_control` / `SWITCH_TAB_ORG`, 随后 `/api/screen/execute` 执行成功。
- 验证完成后已恢复运行态 `ENABLE_MOCK_DORA=true`, Mock smoke 通过。

#### Notes

- PowerShell / Docker CLI 直接传中文环境变量仍可能变成问号; 使用 `.env` 文件或 Unicode escape 可正常验证。
- PowerShell 控制台显示中文 JSON 时可能乱码; API 返回结构和类型校验正常。
- V0.2 Dora 接入阶段完成。下一阶段建议进入 V0.3 TTS / ASR。

### V0.3 TTS / ASR Adapter 最小实现准备

#### Completed

- 增加 `apps/api/app/services/asr_provider.py`, 定义 `AsrProvider`、`MockAsrProvider` 和真实 Provider 未配置时的安全兜底。
- 增加 `apps/api/app/services/tts_provider.py`, 定义 `TtsProvider`、`MockTtsProvider` 和真实 Provider 未配置时的安全兜底。
- `POST /api/asr/transcribe` 已支持 `mock_text` 和可选 `audio_base64` JSON 输入, Mock ASR 返回最终识别文本。
- `POST /api/tts` 已支持 Mock TTS 合成, 生成 WAV 文件并返回 `/api/tts/audio/{audio_id}`。
- `GET /api/tts/audio/{audio_id}` 已支持读取后端生成的 Mock TTS 音频, 并校验安全音频 ID。
- 前端增加语音输入面板, 支持浏览器录音、Mock ASR 文本提交、识别后自动进入 `/api/chat`。
- 前端在数字人回答后后台准备 TTS 音频, 展示“播报”按钮和原生音频控件; JS 播放路径使用 Web Audio API 更新语音能量条。
- `docker-compose.yml` 已补充 ASR / TTS 配置环境变量和 `TTS_CACHE_DIR`。
- 增加根目录 `.dockerignore`, 避免本机 `apps/web/node_modules` 污染 Docker build 上下文。
- 同步更新 `.env.example`、API 契约、数据契约、配置说明和 ASR/TTS 集成说明。

#### Changed Files

- `.dockerignore`
- `.env.example`
- `docker-compose.yml`
- `apps/api/app/config.py`
- `apps/api/app/main.py`
- `apps/api/app/models.py`
- `apps/api/app/services/asr_provider.py`
- `apps/api/app/services/tts_provider.py`
- `apps/web/src/App.vue`
- `apps/web/src/api.ts`
- `apps/web/src/style.css`
- `apps/web/src/types.ts`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/integrations/ASR_TTS_INTEGRATION.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/13_RISKS_AND_TODO.md`

#### Verification

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web install --frozen-lockfile` 完成依赖恢复。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config` 通过。
- `docker compose up -d --build` 通过, 前后端容器均已启动。
- `GET /api/health` 返回 `status=ok`。
- `POST /api/asr/transcribe` 返回 `success=true`。
- `POST /api/tts` 返回 `success=true` 和 `format=wav`; `GET /api/tts/audio/{audio_id}` 下载到 28844 字节 WAV。
- `POST /api/chat` 使用 ASR 文本“返回首页”返回 `screen_control` / `SWITCH_HOME`。
- Codex 内置浏览器验证前端可点击“识别并发送”, 生成用户消息、数字人回复、`SWITCH_TAB_ORG` 动作和 TTS 原生音频控件; 控制台无 error。

#### Notes

- 当前未接入真实 ASR / TTS 供应商; `ENABLE_MOCK_ASR=false` 或 `ENABLE_MOCK_TTS=false` 时返回安全未配置错误。
- 浏览器自动播放策略可能阻止 JS 主动播放音频; 前端已改为后台准备音频并展示手动播报按钮和原生音频控件。
- PowerShell 控制台显示中文 JSON 时仍可能乱码; 结构化字段和浏览器链路验证正常。

### V0.3 阿里云百炼 ASR / TTS 真实配置

#### Completed

- 用户已完成人工验收 Mock 语音闭环。
- 用户已完成人工验收真实浏览器麦克风 ASR / TTS 语音闭环。
- 已确认 `compatible-mode/v1` 不是本项目 ASR / TTS 语音链路入口, 语音使用阿里云百炼 WebSocket `wss://dashscope.aliyuncs.com/api-ws/v1/inference`。
- 已根据阿里云文档选定 ASR `fun-asr-realtime` 和 TTS `cosyvoice-v3-flash`。
- 本地 `.env` 已配置阿里云百炼 ASR / TTS Key, 并切换 `ENABLE_MOCK_ASR=false`、`ENABLE_MOCK_TTS=false`; `.env` 不进入 Git。
- 后端新增阿里云 Fun-ASR WebSocket Provider, 支持 `run-task`、音频二进制上传、`finish-task` 和 `result-generated` 文本收敛。
- 后端新增阿里云 CosyVoice WebSocket Provider, 支持 `run-task`、`continue-task`、`finish-task`, 并将返回的二进制音频缓存为本地 mp3 / wav 等文件。
- 前端录音从 MediaRecorder WebM 改为 Web Audio 采集并编码 16k 单声道 WAV, 以适配 Fun-ASR。
- Docker / `.env.example` / 配置文档已补充 ASR / TTS WebSocket URL、模型、采样率、超时和音色配置。

#### Changed Files

- `.env.example`
- `apps/api/app/config.py`
- `apps/api/app/main.py`
- `apps/api/app/services/asr_provider.py`
- `apps/api/app/services/tts_provider.py`
- `apps/api/pyproject.toml`
- `apps/api/uv.lock`
- `apps/web/src/App.vue`
- `docker-compose.yml`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/integrations/ASR_TTS_INTEGRATION.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/13_RISKS_AND_TODO.md`

#### Verification

- 官方文档核对:
  - CosyVoice WebSocket API 使用 `wss://dashscope.aliyuncs.com/api-ws/v1/inference`, 鉴权头为 `Authorization: Bearer <api_key>`, 交互为 `run-task` -> `continue-task` -> 二进制音频 -> `finish-task`。
  - Fun-ASR WebSocket API 使用同一 WebSocket URL, `model=fun-asr-realtime`, 支持 `wav` / `mp3` 等音频格式。
  - CosyVoice `cosyvoice-v3-flash` 支持系统音色 `longanyang`。
- `docker run ... uv lock` 已刷新 `apps/api/uv.lock`。
- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose up -d --build` 通过。
- `GET /api/health` 返回 `status=ok`。
- 真实 TTS 英文和中文 UTF-8 请求验证通过, 返回 `success=true`, `provider=aliyun`, `format=mp3`; 中文 mp3 下载大小为 56515 字节。
- 真实 ASR 无音频请求返回 `ASR_AUDIO_REQUIRED`, 行为符合预期。
- 使用真实 TTS mp3 回灌 ASR 时, Fun-ASR 返回 `FLOW:AUDIO_DECODE_ERROR`; 判断为回灌音频编码不适合作 ASR 验证, 后续改用浏览器麦克风 16k WAV 实录验收。
- 用户人工验收通过: 浏览器麦克风 16k WAV 真实 ASR 可进入现有 `/api/chat` 和 TTS 链路。
- Codex 内置浏览器验证前端页面可渲染语音输入、录音、识别并发送控件, 控制台无 error。

#### Notes

- V0.3 阿里云百炼 ASR / TTS 最小真实接入已完成人工验收。
- 当前交互仍是按钮式录音 / 识别, 下一阶段进入 V0.4 语义唤醒 / 后台监听, 通过 VAD + 唤醒词减少后续点击。
- API Key 已出现在对话上下文中; 客户移交或正式演示前建议在阿里云百炼控制台轮换一次 Key。

### V0.4 语义唤醒 / 后台监听最小实现

#### Completed

- 增加 `apps/api/app/services/wake_words.py`, 从 `config/wake-words.yaml` 读取唤醒词配置。
- 增加 `GET /api/wake/config`, 返回唤醒词、VAD 阈值、短片段范围、冷却时间和唤醒后指令超时。
- `config/wake-words.yaml` 补充 `silence_ms`、`command_timeout_ms` 和 `vad_threshold`。
- 前端增加“后台监听”显式开关, 只在用户开启后请求麦克风权限。
- 前端增加 `idle` / `monitoring` / `wake_checking` / `recording` / `thinking` / `speaking` / `cooldown` 状态机展示。
- 前端增加本地 RMS 音量阈值 VAD, 只截取短音频片段并编码为 16k 单声道 WAV 后调用 `/api/asr/transcribe`。
- 唤醒词命中后, 如果同一句中已包含正式指令, 会去掉唤醒词后直接进入 `/api/chat`; 如果只有唤醒词, 会进入一次正式指令录音。
- 未命中唤醒词的短片段会丢弃并进入冷却, 不进入 `/api/chat`。
- 后台监听路径复用既有 ASR -> `/api/chat` -> TTS 链路, 并保留手动录音 / Mock ASR / 手动播报回退。
- 前端增加 Mock ASR “小天小天，请切换到组织建设页面”演示按钮。
- 同步更新 API 契约、数据契约、配置说明、测试计划、ASR/TTS 集成说明、风险和下一步文档。

#### Changed Files

- `config/wake-words.yaml`
- `config/README.md`
- `apps/api/app/main.py`
- `apps/api/app/models.py`
- `apps/api/app/services/wake_words.py`
- `apps/web/src/App.vue`
- `apps/web/src/api.ts`
- `apps/web/src/style.css`
- `apps/web/src/types.ts`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/integrations/ASR_TTS_INTEGRATION.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/13_RISKS_AND_TODO.md`

#### Verification

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config` 通过。
- `docker compose up -d --build` 通过, 前后端容器均已启动。
- `GET /api/health` 返回 `status=ok`。
- `GET /api/wake/config` 返回 `version=0.1.0`、`mode=semantic`、3 个唤醒词和 VAD 设置。
- 通过 Python Unicode escape 检查确认接口返回中文唤醒词为 `小天小天`、`中天小天`、`你好小天`。
- `GET http://localhost:18000` 返回 HTTP 200, 前端 JS / CSS 静态资源返回 HTTP 200。
- 容器日志未见启动错误。

#### Notes

- 当前会话未暴露 Codex in-app Browser 控制工具, Playwright 也未安装, 因此未完成浏览器控制台截图验证。
- 本轮未进行真实麦克风唤醒人工验收; 下一步需要在浏览器中点击“后台监听”, 用真实语音验证 VAD 阈值、唤醒命中率和浏览器自动播放策略。
- V0.4 仍不接 RAGFlow 和真实 FVS, 未改变 Dora / ASR / TTS / FVS Mock 开关。

### V0.4.1 连续对话窗口

#### Completed

- 用户已完成人工验收: V0.4 后台监听可唤醒后正常对话。
- `config/wake-words.yaml` 新增 `followup_enabled`、`followup_window_ms`、`max_followup_turns`。
- 后端 `WakeSettings` 新增连续对话窗口字段, `GET /api/wake/config` 可透出配置。
- 前端新增 `followup_listening` 状态, TTS 播报结束后进入短时追问窗口。
- 在 `followup_window_ms` 内用户可直接说下一句, 不需要再次说唤醒词。
- 达到 `max_followup_turns` 或追问窗口超时后, 前端进入冷却并回到唤醒监听。
- 自动播放被浏览器拦截、TTS 播放失败或 TTS 合成失败时, 已显示文字 / 音频控件并尽量进入追问窗口或安全回到监听。
- 监听卡片展示连续对话轮数, 便于现场验收。
- 同步更新 API 契约、数据契约、配置说明、测试计划、ASR/TTS 集成说明、风险和下一步文档。
- 用户已完成人工验收: V0.4.1 连续对话窗口可在播报结束后直接追问, 并能按超时 / 最大轮数退出。
- 文档状态已推进到 V0.5 RAGFlow MCP。

#### Changed Files

- `config/wake-words.yaml`
- `config/README.md`
- `apps/api/app/models.py`
- `apps/web/src/App.vue`
- `apps/web/src/style.css`
- `apps/web/src/types.ts`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/integrations/ASR_TTS_INTEGRATION.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/13_RISKS_AND_TODO.md`

#### Verification

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config` 通过。
- `docker compose up -d --build` 通过, 前后端容器均已启动。
- `GET /api/health` 返回 `status=ok`。
- `GET /api/wake/config` 返回 `followup_enabled=true`、`followup_window_ms=12000`、`max_followup_turns=3`。
- `GET http://localhost:18000` 返回 HTTP 200。

#### Notes

- 本轮未接 RAGFlow 和真实 FVS。
- 当前运行态 `/api/chat` 仍是 `ENABLE_MOCK_DORA=true` 的 Mock Dora。
- 下一步进入 V0.5 RAGFlow MCP; 如需验证 Dora 调用 RAGFlow, 需要显式切换真实 Dora。

### V0.5 RAGFlow MCP 本地部署准备

#### Completed

- 用户提供远端服务器部署信息后, 先探测服务器 Docker / Compose / 内存 / 磁盘 / `vm.max_map_count`。
- 远端服务器 Docker 可用, 但内存约 7.5GiB, 低于 RAGFlow 官方建议的 16GiB; 初次尝试按 RAGFlow `v0.25.6` 拉起 CPU 版时发现默认端口冲突和 Elasticsearch profile 未启动问题。
- 用户中断远端部署并要求改为本地部署后, 已清理远端服务器本轮创建的 RAGFlow 容器、卷、网络和目录; 清理后目标目录不存在, RAGFlow 容器和卷无残留。
- 在本地 `D:\Project\ragflow` 克隆 RAGFlow 官方仓库 `v0.25.6`。
- 修改本地 RAGFlow `docker/.env`, 使用高位端口避免与当前 POC 前后端冲突: Web `18089`, API `19380`, MCP `19382`, MySQL `13306`, Redis `16379`, Elasticsearch `11200`, MinIO `19000/19001`。
- 通过 Docker Desktop 启动 RAGFlow CPU + Elasticsearch profile, 容器包括 `ragflow-cpu`、`es01`、`mysql`、`redis`、`minio`。
- 创建本地 RAGFlow 测试用户, 生成 self-host MCP API token, 并将 `RAGFLOW_MCP_HOST_API_KEY` 写入 `D:\Project\ragflow\docker\.env`; token 未写入本项目 Git 文档。
- 修改本地 RAGFlow `docker-compose.yml`, 在 `ragflow-cpu` 中启用 `--enable-mcpserver`、`--mcp-mode=self-host` 和 `/mcp` / `/sse` 传输。
- 新增 `docs/demo_knowledge/` 8 份最小党建知识库测试资料, 覆盖 3 位领导、2 篇新闻、3 份党建制度 / 流程文档。
- 更新 RAGFlow 集成说明, 记录本地路径、端口、MCP 地址、启动命令、验证结果和 Dora 远程可达性边界。
- 用户将临时公网域名映射到本机 MCP 端口后, 已验证 `http://liuchenxiang.uk:19382/mcp` 可完成 MCP 初始化和工具列表获取。

#### Changed Files

- `docs/demo_knowledge/`
- `docs/integrations/RAGFLOW_INTEGRATION.md`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/customers/zt-securities/KNOWLEDGE_BASE_PLAN.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`
- `docs/CHANGELOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`

#### Verification

- 远端清理验证: `/tmp/zfsv3/nvme12/18722229125/data/Docker/ragflow` 删除成功; 本轮创建的 RAGFlow 容器和卷无残留。
- 本地 Docker Desktop 可用: Docker Server `29.5.2`, Compose `v5.1.3`, Docker Desktop 内存约 16.5GB。
- `docker compose -f docker-compose.yml --profile cpu --profile elasticsearch config --services` 返回 `mysql`、`ragflow-cpu`、`redis`、`es01`、`minio`。
- `docker compose -f docker-compose.yml --profile cpu --profile elasticsearch up -d` 成功启动本地 RAGFlow。
- `GET http://127.0.0.1:18089/` 返回 HTTP 200, 页面标题为 `RAGFlow`。
- `GET http://127.0.0.1:18089/api/v1/system/healthz` 返回 HTTP 200, `db` / `doc_engine` / `redis` / `storage` / `status` 均为 `ok`。
- RAGFlow MCP 日志显示 `Streamable HTTP endpoint available at /mcp` 和 `Uvicorn running on http://0.0.0.0:9382`。
- `GET http://127.0.0.1:19382/sse` 返回 HTTP 200 和 `text/event-stream`。
- `GET http://127.0.0.1:19382/mcp` 返回 HTTP 406, 提示客户端需要 `Accept: text/event-stream`, 说明 `/mcp` 端点已监听但需 MCP client 正确握手。
- `POST http://liuchenxiang.uk:19382/mcp` 的 MCP `initialize` 返回 HTTP 200, server 为 `ragflow-mcp-server`, protocolVersion 为 `2025-03-26`。
- `POST http://liuchenxiang.uk:19382/mcp` 的 MCP `tools/list` 返回 `ragflow_retrieval` 工具。
- `tools/call ragflow_retrieval` 当前返回 `No accessible datasets found.`, 与尚未导入 RAGFlow dataset 的状态一致。

#### Notes

- 本轮尚未在 RAGFlow Web 中导入 `docs/demo_knowledge/` 到 dataset, 也未创建 chat / assistant。
- 本轮尚未验证 Dora 通过 MCP 调用 RAGFlow 返回知识库答案; 当前 MCP 链路已通, 但 RAGFlow 还没有可访问 dataset。
- 本轮未修改项目后端 / 前端代码, 未接真实 FVS。

### V0.5 RAGFlow Dataset 导入和解析

#### Completed

- 在本地 RAGFlow 中创建 dataset `zt_party_building_demo`, ID 为 `d7481bc0649311f18b616324ad8eb1c0`。
- 上传 `docs/demo_knowledge/` 下 8 份测试 Markdown, 排除目录说明 `README.md`。
- 首次触发解析后 8 份文档均失败, 失败原因为 `No default embedding model is set.`。
- 使用本地 `.env` 中已有阿里云百炼 / DashScope Key, 在 RAGFlow 中验证并配置默认 Embedding `text-embedding-v3@Tongyi-Qianwen`; Key 未写入项目文档或 Git。
- 将 `zt_party_building_demo` 的 Embedding 更新为 `text-embedding-v3@Tongyi-Qianwen`。
- 为最小 Markdown 解析关闭 `zt_party_building_demo` 的 RAPTOR / GraphRAG, 避免额外依赖默认 Chat 模型。
- 重新触发解析后, 8 份测试文档全部解析完成, 均为 `DONE`。
- 通过本地 MCP 和临时公网 MCP 验证 `ragflow_retrieval` 可返回知识库 chunk。

#### Changed Files

- `docs/integrations/RAGFLOW_INTEGRATION.md`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/customers/zt-securities/KNOWLEDGE_BASE_PLAN.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`
- `docs/CHANGELOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`

#### Verification

- RAGFlow healthz 仍返回 `db` / `doc_engine` / `redis` / `storage` / `status` 全部 `ok`。
- `zt_party_building_demo` dataset 创建成功。
- 8 份文档解析结果:
  - `leader_zhang.md`: `DONE`, 1 chunk, 233 tokens。
  - `leader_li.md`: `DONE`, 1 chunk, 165 tokens。
  - `leader_wang.md`: `DONE`, 1 chunk, 149 tokens。
  - `news_2026_party_research.md`: `DONE`, 1 chunk, 189 tokens。
  - `news_2026_org_building.md`: `DONE`, 1 chunk, 171 tokens。
  - `party_study_policy.md`: `DONE`, 1 chunk, 221 tokens。
  - `join_party_process.md`: `DONE`, 1 chunk, 229 tokens。
  - `branch_org_building_standard.md`: `DONE`, 1 chunk, 229 tokens。
- 本地 MCP `tools/call ragflow_retrieval` 输入“张书记最近调研了什么?”返回 `leader_zhang.md` / `news_2026_party_research.md` 相关 chunk。
- 公网 MCP `tools/call ragflow_retrieval` 输入“入党流程是什么?”返回 `join_party_process.md` 相关 chunk。

#### Notes

- 当前 RAGFlow 尚未配置默认 Chat 模型, 因此 `ragflow_retrieval` 使用 `keyword=false` 可正常向量检索; 使用 `keyword=true` 会报 `No default chat model is set.`。
- 尚未创建 RAGFlow chat / assistant。
- 尚未验证 Dora Agent 通过 MCP 调用 RAGFlow 后返回最终自然语言知识库答案。
- 本轮未修改项目后端 / 前端代码, 未接真实 FVS。

### V0.5 Dora 通过 MCP 调用 RAGFlow 知识库验证

#### Completed

- 根据用户确认的边界调整 V0.5 方案: Dora 负责最终回答, RAGFlow 负责检索, MCP 调用固定 `keyword=false`。
- 将本地 `.env` 切换为 `ENABLE_MOCK_DORA=false`, 并重建 `zt-digital-human-api` 容器。
- 通过 `/api/chat` 调用真实 Dora OpenClaw SSE, Dora Agent 已接入公网 MCP `http://liuchenxiang.uk:19382/mcp`。
- 验证 Dora 可通过 MCP 调用 RAGFlow `zt_party_building_demo` dataset, 并返回项目契约中的 `answer`。
- 明确 RAGFlow 默认 Chat 模型和 chat / assistant 不再作为 V0.5 必需项; 仅在启用 `keyword=true`、TOC enhance、KG retrieval 或 RAGFlow 自答时需要。

#### Changed Files

- `.env`
- `docs/integrations/RAGFLOW_INTEGRATION.md`
- `docs/integrations/DORA_AGENT_PROMPT.md`
- `docs/CODEX_CONTEXT.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/customers/zt-securities/KNOWLEDGE_BASE_PLAN.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`
- `docs/CHANGELOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`

#### Verification

- `docker compose up -d --force-recreate api` 成功重建 API 容器。
- API 容器环境确认 `ENABLE_MOCK_DORA=false`, `DORA_AGENT_NAME=中天证券党建大屏语音助手`。
- `GET http://127.0.0.1:18080/api/health` 返回 `status=ok`。
- `GET http://127.0.0.1:18089/api/v1/system/healthz` 返回 `db` / `doc_engine` / `redis` / `storage` / `status` 全部 `ok`。
- `/api/chat` 输入 `张书记最近调研了什么?` 返回 `answer`, 内容包括基层营业部党建调研、党员学习、组织生活和党建引领业务发展。
- `/api/chat` 输入 `入党流程是什么?` 返回 `answer`, 内容包括递交申请、谈话、积极分子、培养考察、发展对象、政治审查、预备党员和转正。
- `/api/chat` 输入 `党员学习制度有哪些要求?` 返回 `answer`, 内容包括按月集中学习、计划 / 签到 / 台账、学习内容、补学整改和综合评价。
- `/api/chat` 输入 `党支部组织建设规范是什么?` 返回 `answer`, 内容包括组织设置、职责分工、三会一课、主题党日、党员发展、党费收缴和整改闭环。
- RAGFlow 日志在 Dora 测试期间出现 `POST /mcp` 和 `POST /api/v1/retrieval` 成功记录。

#### Notes

- 首次脚本验证时受 PowerShell 中文编码影响, Dora 收到问号乱码并返回编码提示; 已改用 Unicode escape 构造 JSON 后验证通过。
- `我是张书记, 请给我欢迎语。` 可返回欢迎语, 但未明显引用领导资料中的近期关注方向, 后续可通过 Dora Prompt 单独优化。
- `请严格依据知识库回答: 党支部组织建设规范是什么?` 触发了 RAGFlow retrieval, 但 Dora 最终返回 `fallback`; 记录为 Dora Agent 工具结果转回答的 Prompt 稳定性边角问题。
- 本轮未修改项目后端 / 前端代码, 未接真实 FVS。

### V0.5 Dora MCP 工具消息解析修复

#### Completed

- 复现用户在前端问“入党流程是什么?”和“张书记最近调研了什么?”时返回兜底话术的问题。
- 通过 `session_logs` 确认前端问题已进入 `/api/chat`, Dora 返回被 Gateway 归一为 `DORA_OUTPUT_INVALID: Dora output type is unsupported`。
- 通过 RAGFlow 日志确认同一时间已有 `POST /mcp` 和 `POST /api/v1/retrieval -> 200`, 说明 MCP 和 RAGFlow 检索成功。
- 抓取 Dora SSE 原始事件后定位原因: Dora 的 `messages` 流会先输出 MCP ToolMessage 原始 JSON chunks, 再输出最终回答; Gateway 旧逻辑把工具 JSON 和最终回答拼接后优先解析到前面的 `{"chunks": ...}`, 导致 unsupported fallback。
- 修改 `DoraClient._extract_text`, 忽略 `type=tool` / `ToolMessage` / `ToolMessageChunk` 的工具原始消息, 只收集最终 AI 回答内容。
- 重建 API 容器并复测通过。

#### Changed Files

- `apps/api/app/services/dora_client.py`
- `docs/DEV_LOG.md`
- `docs/CHANGELOG.md`
- `docs/integrations/DORA_INTEGRATION.md`
- `docs/integrations/RAGFLOW_INTEGRATION.md`
- `docs/NEXT_ACTIONS.md`

#### Verification

- `docker compose up -d --build api` 成功。
- `docker exec zt-digital-human-api uv run python -m compileall app` 通过。
- `GET http://127.0.0.1:18080/api/health` 返回 `status=ok`。
- 新 session 输入 `入党流程是什么?` 返回 `type=answer`, 内容为 8 个入党流程环节。
- 新 session 输入 `张书记最近调研了什么?` 返回 `type=answer`, 内容为 2026 年 5 月基层营业部党建调研和 2026 年 6 月党建引领业务发展专题会议。
- 用户前端实际 session `demo-session-1781074089384` 复测以上两个问题也均返回 `type=answer`。

#### Notes

- 该问题不是 RAGFlow 未检索到, 而是 Gateway 解析 Dora SSE 时误把工具原始 JSON 当成最终回答解析。
- 当前修复不改变 API 契约, 只增强 Dora SSE 事件收敛逻辑。

### V0.5 RAGFlow MCP 返回量瘦身与分段 TTS 流式优化

#### Completed

- 根据用户要求, 暂不改 Dora 侧配置, 改为在本地 RAGFlow MCP server 和本地 POC Gateway / 前端优化慢交互。
- 修改 `D:\Project\ragflow\mcp\server\server.py`, 对 `ragflow_retrieval` 做 POC 返回量瘦身:
  - 强制 `keyword=false`。
  - 限制 `page_size<=3`、`top_k<=16`、`similarity_threshold>=0.35`。
  - 单 chunk content 最长 1200 字符。
  - chunk 只返回 `content`、`document_name`、`document_id`、`dataset_id`、`similarity`。
  - 去掉每次 retrieval 额外拉取 document / dataset metadata cache 的步骤。
- 修改 `D:\Project\ragflow\docker\docker-compose.yml`, 将 `../mcp/server/server.py` 只读挂载到 `ragflow-cpu` 容器内 `/ragflow/mcp/server/server.py`。
- 重建 `ragflow-cpu`, 验证容器内已使用瘦身后的 MCP server 脚本。
- 新增后端 `POST /api/chat/stream`, 在真实 Dora 模式下消费 Dora OpenClaw SSE, 输出 `metadata`、`dora_delta`、`tts_ready`、`tts_error`、`answer`、`end`。
- 后端流式路径会从 Dora 最终回答 JSON 的 `speak_text` 中增量提取文本, 并按短段并发调用现有 TTS Provider。
- 若 Dora 某次只给最终 answer, 后端仍会把最终 `speak_text` 分段合成, 避免整段 TTS 阻塞。
- 前端优先调用 `/api/chat/stream`, 收到 `tts_ready` 后按 `index` 顺序播放分段音频; 流式失败时回退到原 `/api/chat` + `/api/tts`。
- 修复分段播放锁: 前端消息 ID 保持稳定, 避免 answer 事件到达后改 ID 导致重复拉起播放队列。
- 修复并发分段 TTS 到达顺序问题: 原生音频控件始终指向当前最早分段。

#### Changed Files

- `apps/api/app/main.py`
- `apps/api/app/services/dora_client.py`
- `apps/web/src/App.vue`
- `apps/web/src/api.ts`
- `apps/web/src/types.ts`
- `docs/06_API_CONTRACT.md`
- `docs/07_DATA_CONTRACT.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/10_TEST_PLAN.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/integrations/ASR_TTS_INTEGRATION.md`
- `docs/integrations/DORA_INTEGRATION.md`
- `docs/integrations/RAGFLOW_INTEGRATION.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`
- `D:\Project\ragflow\mcp\server\server.py`
- `D:\Project\ragflow\docker\docker-compose.yml`

#### Verification

- `docker compose -f D:\Project\ragflow\docker\docker-compose.yml --profile cpu --profile elasticsearch config --services` 通过。
- `docker compose -f D:\Project\ragflow\docker\docker-compose.yml --profile cpu --profile elasticsearch up -d --force-recreate ragflow-cpu` 成功。
- RAGFlow healthz 返回 `db` / `doc_engine` / `redis` / `storage` / `status` 全部 `ok`。
- 容器内 `grep` 验证 `/ragflow/mcp/server/server.py` 包含 `POC_MAX_PAGE_SIZE` 和精简 chunk payload 注释。
- `docker exec zt-digital-human-api uv run python -m compileall app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config --services` 通过。
- `docker compose up -d --build api web` 通过, API 和 Web 容器均为 `running`。
- `GET http://127.0.0.1:18080/api/health` 返回 `status=ok`。
- `GET http://127.0.0.1:18000` 返回 HTTP 200。
- `GET http://127.0.0.1:18089/api/v1/system/healthz` 返回全部 `ok`。
- 普通 `/api/chat` 输入 `入党流程是什么?` 返回 `type=answer`, 耗时约 20.0s。
- `/api/chat/stream` 输入 `入党流程是什么?` 验证通过: 本轮抽样中首个 `dora_delta` 约 8.5s 到 17.6s, 首个分段 `tts_ready` 约 11.6s 到 19.8s, 最终 `answer` 约 12.0s 到 21.3s, 全部分段 TTS 约 15.1s 到 27.1s 就绪。

#### Notes

- 当前优化不是音频字节级真流式 TTS, 而是“Dora 文本增量 + 短文本分段 TTS 文件 + 前端按段播放”。
- 当前最大剩余耗时仍在 Dora 工具调用前决策和工具结果后的回答生成; RAGFlow 检索自身通常不是主要瓶颈。
- 本轮未修改 Dora 侧 MCP 配置, 未接真实 FVS。

### V0.5 / V0.6 问数测试 Excel 数据准备

#### Completed

- 新增 `docs/demo_data/ask_metrics/` 目录, 存放党建问数功能测试用脱敏 Excel 样例数据。
- 生成 3 份 `.xlsx`:
  - `zt_party_study_metrics_2026.xlsx`: 党员学习数据, 覆盖党员总数、学习完成率、支部完成率、学习时长、测试成绩和心得提交情况。Dashboard 口径为党员总数 128 人、已完成学习 112 人、完成率 87.5%。
  - `zt_party_org_life_metrics_2026.xlsx`: 组织生活与党建活动数据, 覆盖活动完成率、主题党日次数、参会率、整改事项和闭环率。
  - `zt_party_development_metrics_2026.xlsx`: 党员发展流程数据, 覆盖申请人、入党积极分子、发展对象、预备党员、本年转正、材料状态和政审状态。
- 每份 Excel 均包含 Dashboard、明细 / 汇总表和字段说明, 并包含适合问数测试的示例问题。
- 新增 `docs/demo_data/ask_metrics/README.md`, 记录文件清单、典型问数问题和口径说明。

#### Changed Files

- `docs/demo_data/ask_metrics/README.md`
- `docs/demo_data/ask_metrics/zt_party_study_metrics_2026.xlsx`
- `docs/demo_data/ask_metrics/zt_party_org_life_metrics_2026.xlsx`
- `docs/demo_data/ask_metrics/zt_party_development_metrics_2026.xlsx`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/10_TEST_PLAN.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`

#### Verification

- 三份 Excel 文件均已生成到 `docs/demo_data/ask_metrics/`。
- 使用 spreadsheet runtime 重新导入三份 Excel, 检查 Dashboard 关键区域可读取。
- 三份 Excel 均完成公式错误扫描, 未发现 `#REF!`、`#DIV/0!`、`#VALUE!`、`#NAME?` 或 `#N/A`。
- 对每份工作簿的 Dashboard 和主要表头区域完成渲染预览检查。

#### Notes

- 本轮只准备问数测试数据源, 尚未实现 Dora / Gateway 对 Excel 的真实问数解析或查询链路。
- Excel 内容为脱敏演示样例, 不包含真实客户或员工数据。

### V0.5 人工验收确认

#### Completed

- 用户确认 V0.5 RAGFlow MCP 阶段人工验收完成。
- V0.5 验收范围已覆盖:
  - 本地 RAGFlow Docker Desktop 部署和健康检查。
  - `zt_party_building_demo` dataset 导入 8 份测试资料并解析完成。
  - Dora Agent 通过公网 MCP 调用 RAGFlow `ragflow_retrieval(keyword=false)`。
  - Gateway 忽略 Dora SSE 中 MCP ToolMessage 原始 chunks, 避免误解析工具结果。
  - RAGFlow MCP 返回量瘦身。
  - `/api/chat/stream` 与前端分段 TTS 播放优化。
  - 前端 / 语音链路人工体验验收。
- 项目阶段推进到 V0.6 FVS 真实集成准备。

#### Changed Files

- `docs/CODEX_CONTEXT.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`
- `docs/CHANGELOG.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`

#### Verification

- 人工验收结论来自用户确认: “V0.5确认验收，我人工验收完成了”。
- 本轮未新增代码变更, 无需重新构建前后端。

#### Notes

- V0.5 关闭后, 下一阶段默认进入 V0.6 FVS 真实集成。
- FVS 真实集成必须继续使用 `action_id` + 后端白名单校验, 不允许执行模型生成 JavaScript。

### V0.6 FVS iframe page_number 切页准备

#### Completed

- 用户提供本机 FVS 测试看板 URL, 入口参数为 `page_number=1`。
- 直接请求本机 FVS URL 返回 HTTP 200, 但响应头包含 `X-Frame-Options: SAMEORIGIN`, 跨端口 iframe 会被浏览器拦截。
- 新增 Web Nginx `/webroot/` 同源反向代理, 将请求转发到 `http://host.docker.internal:8075/webroot/`。
- 本地 `.env` 的 `VITE_FVS_URL` 改为相对路径 `/webroot/decision/view/duchamp?...&page_number=1`, `VITE_FVS_TARGET_ORIGIN` 置空。
- 新增 ADR-0008 记录 FVS 同源代理决策。
- 确认测试看板页面映射:
  - 1: 总览
  - 2: 成品库存
  - 3: 生产管理
  - 4: 设备分析
- `config/screen-actions.yaml` 已同步为 `gotoPage` + `pageNumber=1/2/3/4`。
- 前端 FVS Adapter 在 iframe 模式下优先识别 `params.pageNumber`, 并改写 FVS iframe URL 的 `page_number` 参数。
- 前端新增直接控屏按钮, 点击后仍调用 `/api/screen/execute` 做后端白名单校验, 不绕过安全路径。
- 示例输入按钮改名为 `输入总览`、`输入库存`、`输入生产`, 避免与直接控屏按钮同名。
- Dora Prompt、数据契约、API 契约、测试计划、FVS 集成说明和客户动作清单已同步当前四页测试映射。

#### Verification

- `GET /api/screen/actions` 可返回四个 `gotoPage` 动作及 `pageNumber=1/2/3/4`。
- `POST /api/screen/execute` 合法动作 `SWITCH_TAB_ORG` 返回 `success=true`。
- `corepack pnpm --dir apps/web build` 通过。
- `python -m compileall apps/api/app` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `docker compose up -d --build web` 成功。
- `GET http://127.0.0.1:18000` 返回 HTTP 200。
- `GET http://127.0.0.1:18000/webroot/decision/view/duchamp?...&page_number=1` 经同源代理返回 HTTP 200。
- Codex 内置浏览器验证 FVS iframe 使用同源 `/webroot/...` 地址后看板可见。
- Codex 内置浏览器验证直接控屏按钮 `总览`、`成品库存`、`生产管理`、`设备分析` 分别切到 `page_number=1/2/3/4`, 最近动作显示 `iframe:gotoPage`, 控制台无 error。

#### Notes

- 当前方案优先使用 FVS URL 分页参数, 不要求 FVS 页面先预埋 `message` 监听脚本。
- 如果后续要控制分页以外的组件状态, 再走 `postMessage` / FVS 侧固定 `action_id` 映射。
- 正式环境需要确认是否部署同源代理, 或由 FVS 侧调整 iframe 允许策略。

### V0.6 FVS 主画布悬浮语音层与等待提示音

#### Completed

- 按用户要求将 FVS iframe host 模式调整为 FVS 主体画布, FVS iframe 铺满整个浏览器视口。
- 未唤醒 / 未处理语音时, 页面上层只保留右下角圆形麦克风语音交互入口。
- 唤醒、正式录音、连续追问、思考、TTS 加载或播报时, 右下角展开为悬浮语音面板。
- FVS 主画布展开态只保留语音监听状态、波形动画和对话文字记录; 文本表单、Mock ASR 输入、Demo 按钮和直接控屏调试栏已隐藏。
- 正式指令或连续追问进入处理后, 前端立即播报等待提示语音 `收到, 正在为您查找信息。`。
- 等待提示优先使用后端 TTS 预热音频; 如音频尚未就绪, 使用浏览器 `speechSynthesis` 本地兜底。
- AI 结果 TTS 与等待提示共用播放通道; AI 结果音频开始播放时会清理并打断等待提示, 优先播报最终回答。
- 新增 ADR-0009, 记录 FVS 主画布悬浮语音层和等待提示音打断策略。

#### Changed Files

- `apps/web/src/App.vue`
- `apps/web/src/style.css`
- `docs/00_INDEX.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/10_TEST_PLAN.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/DEV_LOG.md`
- `docs/NEXT_ACTIONS.md`
- `docs/CHANGELOG.md`
- `docs/CODEX_CONTEXT.md`
- `docs/decisions/ADR-0009-fvs-floating-voice-overlay.md`
- `docs/integrations/ASR_TTS_INTEGRATION.md`
- `docs/integrations/FVS_INTEGRATION.md`

#### Verification

- `corepack pnpm --dir apps/web build` 通过。
- `python -m compileall apps/api/app` 通过。
- `docker compose up -d --build web` 成功, API 和 Web 容器均已重建并启动。
- Codex 内置浏览器打开 `http://127.0.0.1:18000` 验证: FVS iframe 使用同源 `/webroot/...` 地址, 视口内铺满 1280x720。
- Codex 内置浏览器验证未唤醒状态: `.conversation-panel.compact` 为 76x76, 右下角只显示麦克风入口; `voice-monitor`、`fvs-log`、`screen-action-row`、`chat-form`、`demo-row` 和 Mock ASR 输入均不可见; 控制台无 error。

#### Notes

- 本轮未在浏览器中接受麦克风权限, 因此真实唤醒展开、等待提示音自动播放和 AI 结果打断等待提示仍需用户现场人工验收。
- FVS 页面底部的 FineVis 未注册提示来自 FVS 本身, 不是本项目悬浮语音层。

### V0.6 人工验收确认

#### Completed

- 用户确认 V0.6 FVS 真实集成阶段人工验收完成。
- V0.6 验收范围已覆盖:
  - 数字人前端主页面 iframe 嵌入 FVS 看板。
  - Web Nginx `/webroot/` 同源代理加载本机 FVS。
  - `page_number=1/2/3/4` 对应 `总览`、`成品库存`、`生产管理`、`设备分析` 四页切换。
  - FVS 主画布未唤醒时仅显示角落语音 icon。
  - 唤醒 / 连续追问 / 思考 / 播报时展开悬浮语音动画和文字记录。
  - 等待提示音和 AI 结果 TTS 优先打断策略。
- 项目阶段推进到 V0.7 POC 稳定版。

#### Changed Files

- `docs/CODEX_CONTEXT.md`
- `docs/NEXT_ACTIONS.md`
- `docs/DEV_LOG.md`
- `docs/CHANGELOG.md`
- `docs/05_DEVELOPMENT_PLAN.md`
- `docs/08_CONFIG_GUIDE.md`
- `docs/09_LOCAL_DEPLOY.md`
- `docs/12_CUSTOMER_HANDOFF.md`
- `docs/13_RISKS_AND_TODO.md`
- `docs/decisions/ADR-0007-fvs-iframe-host.md`
- `docs/customers/zt-securities/ACCEPTANCE_CHECKLIST.md`
- `docs/customers/zt-securities/SCREEN_ACTIONS.md`
- `docs/integrations/FVS_INTEGRATION.md`

#### Verification

- 人工验收结论来自用户确认: “0.6验收完成”。
- 本轮未新增代码变更, 无需重新构建前后端。

#### Notes

- V0.7 默认不再扩展新的外部系统能力, 优先形成稳定 POC 包和验收交付资料。
- 分页以外的 FVS 组件级控制仍作为后续增强项, 不影响 V0.6 验收结论。
