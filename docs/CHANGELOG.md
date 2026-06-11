# Changelog

## Unreleased

### Added

- 新增 V1.0 验收交付包目录 `docs/delivery/v1.0/`。
- 新增 V1.0 交付包索引、验收报告、部署方案、用户手册、运维手册、配置手册、测试报告和客户移交清单。
- 新增 V0.9 PowerShell 交付脚本: `scripts/check-poc.ps1`、`scripts/start-poc.ps1`、`scripts/stop-poc.ps1`、`scripts/export-logs.ps1`、`scripts/smoke-demo.ps1` 和公共 helper `scripts/poc-common.ps1`。
- 新增 `DEMO_STABLE_MODE` / `VITE_DEMO_STABLE_MODE` 演示稳态开关。
- 新增 `GET /api/demo/config`, 返回演示稳态、客户 ID、问数模式、Mock 开关和固定演示问题。
- 新增前端“演示稳态”状态标识、FVS iframe 加载超时 / 失败提示和动态演示题按钮。
- 新增 ADR-0015, 记录 V0.9 交付脚本、日志包和演示稳态模式决策。
- 新增 FVS 唤醒成功语音反馈: 命中唤醒词后立即播报“您好。”。
- 新增前端独立运维路径 `/ops`, 复用现有 Ops API 和前端服务。
- 新增 ADR-0016, 记录 FVS 极简悬浮层、独立运维路径和唤醒成功语音反馈决策。
- 新增客户私有配置目录 `config/customers/zt-securities/`, 包含 `runtime.yaml`、`screen-actions.yaml`、`ask-metrics.yaml`、`demo-cases.yaml`、`wake-words.yaml`、`dora.yaml`、`ragflow.yaml`、`voice.yaml`、`fvs.yaml` 和 `customer.env.example`。
- 新增 `CUSTOMER_ID`、`CUSTOMER_CONFIG_DIR` 和 `ASK_METRICS_MODE=excel|dora|auto` 后端配置。
- 新增 ADR-0012, 记录客户配置覆盖层和问数模式路由决策。
- 新增 `TTS_STREAMING_ENABLED`、`TTS_STREAMING_FALLBACK` 和 `TTS_STREAMING_AUDIO_FORMAT` 配置。
- 新增 `POST /api/tts/stream`, 通过 SSE 返回 TTS `audio_chunk`。
- 新增 `TtsProvider.stream_synthesize`, Mock TTS 可输出 PCM chunk, 阿里云 CosyVoice 可逐块转发 WebSocket 二进制音频帧。
- 新增前端 PCM Web Audio 真流式播放器, 支持 AI 音频打断等待提示音并在失败时回退分段 TTS。
- 新增 ADR-0013, 记录 TTS 字节级真流式采用 PCM chunk + Web Audio 的决策。
- 新增只读脱敏 Ops API: `/api/ops/health`、`/api/ops/dependencies`、`/api/ops/sessions`、`/api/ops/session/{session_id}`、`/api/ops/errors`、`/api/ops/metrics`、`/api/ops/export`。
- 新增前端“演示 / 运维”视图切换, 运维看板覆盖依赖状态、最近会话、错误列表、耗时指标和 Markdown 日志导出。
- 新增 ADR-0014, 记录只读脱敏运维监控和日志看板决策。

### Changed

- `docs/00_INDEX.md` 增加 V1.0 验收交付包入口。
- `NEXT_ACTIONS` 当前阶段更新为 V1.0 POC 验收交付包已输出, 下一推荐 goal 改为客户现场验收复演、补齐截图附件、确认真实依赖并完成签收。
- `docs/12_CUSTOMER_HANDOFF.md` 补充 V1.0 交付包路径和现场签收建议。
- `docs/13_RISKS_AND_TODO.md` 增加 V1.0 现场截图、真实依赖和签字待补齐风险。
- `DEMO_STABLE_MODE=true` 时, Dora 请求失败会优先尝试本地 Excel 问数和 Mock Dora 演示兜底; 未命中时仍返回安全 fallback。
- Excel 问数数据缺失、Dora 流式异常和 TTS 分段异常不再向前端暴露系统堆栈或供应商异常原文。
- 现场日志包导出流程固化为 `scripts/export-logs.ps1`, 默认只导出脱敏 Ops Markdown / JSON 和 Compose 状态; Docker 原生日志需显式 `-IncludeDockerLogs`。
- FVS iframe host 默认语音入口改为小型低透明 icon; 唤醒词判定中、未命中和冷却状态不展开对话浮层。
- FVS iframe host 展开态改为半透明评论流, 仅显示最近用户识别文本和数字人回复文本。
- FVS iframe host 不再显示右上角“运维”悬浮入口; 运维看板通过 `/ops` 访问。
- 调整 V0.7 之后路线: 先 V0.8 功能增强, 再 V0.9 交付优化, 最后 V1.0 验收交付。
- 新增 `docs/14_ENHANCEMENT_ROADMAP.md`, 记录 Dora 通用问数、TTS 字节级真流式、运维监控 / 日志看板、客户私有配置目录和交付材料路线。
- 新增 ADR-0011, 记录“先功能增强再交付优化”的阶段决策。
- 先前 `NEXT_ACTIONS` 已进入 V1.0 准备阶段; 本轮已进一步更新为 V1.0 交付包已输出。
- API / 数据 / 配置 / 测试 / 风险 / 客户移交文档补充 V0.8 Draft 和 V0.9 / V1.0 草案。
- 后端启动时会加载客户目录覆盖层; 旧 `.env` 中等于根目录默认路径的配置项不再阻止客户目录覆盖, 真正自定义路径仍优先。
- `/api/chat` 和 `/api/chat/stream` 的问数链路改为按 `ASK_METRICS_MODE` 路由: `excel` 保持 V0.7 行为, `dora` 不让 Excel 抢答, `auto` 在 Dora 失败或兜底时回退 Excel。
- Docker Compose 不再硬编码根目录 YAML 路径, 由后端配置解析器选择默认配置或客户配置。
- 前端播报按钮和语音自动播报路径优先尝试 `/api/tts/stream`; 真流式失败后继续使用 `/api/chat/stream` 的 `tts_ready` 分段音频或完整 `/api/tts` 文件。
- `SessionLogStore` 新增最近会话、单会话明细、错误列表和耗时聚合查询, 并对导出摘要做截断和常见密钥模式脱敏。

### Verified

- V1.0 交付包引用 `logs/smoke/smoke-demo-20260611-011803.md`, 5 条固定演示题均为 `True`。
- V1.0 交付包引用 `logs/exports/zt-poc-logs-20260611-011813.zip` 作为最近日志包证据。
- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `git diff --check` 通过。
- `scripts/check-poc.ps1 -SkipExternal -Json` 可输出预检 JSON。
- `scripts/start-poc.ps1 -Build -DemoStable` 成功重建并启动 API / Web。
- `GET /api/health` 返回 `status=ok`; `GET /api/demo/config` 返回 `stable_mode=true`。
- `scripts/smoke-demo.ps1 -ExecuteScreenActions` 通过, 固定演示题和白名单控屏执行成功。
- `scripts/export-logs.ps1 -Zip` 生成日志包。
- `scripts/check-poc.ps1 -RequireServices -SkipExternal -Json` 通过。
- Codex Browser 验证前端“演示稳态”、动态演示题和 FVS iframe 超时兜底。
- `python -m compileall apps/api/app` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `docker compose up -d --build api` 成功。
- API 容器内确认有效配置指向 `/app/config/customers/zt-securities/*.yaml`。
- `GET /api/health` 返回 `status=ok`。
- `ASK_METRICS_MODE=excel` 下 `/api/chat` 11 个问数 smoke 均通过, 且回答包含 Excel 来源。
- `ASK_METRICS_MODE=excel` 下 `入党流程是什么?` 未被问数 Adapter 抢占。
- `/api/chat/stream` 问数返回 `metadata -> dora_delta -> answer -> tts_ready -> end`。
- 容器内函数级验证 `ASK_METRICS_MODE=dora` 不使用 Excel 来源。
- 容器内函数级验证 `ASK_METRICS_MODE=auto` 在 Mock Dora 兜底时回退 Excel。
- `corepack pnpm --dir apps/web build` 通过。
- `git diff --check` 通过。
- `docker compose up -d --build api web` 成功。
- `POST /api/tts/stream` 在真实 TTS 配置下返回 `metadata -> audio_chunk* -> end`; 抽样首个 PCM chunk 约 567ms 到达, `end.duration_ms=3387`, 共 33 个 chunk。
- `TTS_STREAMING_ENABLED=false` 时 `/api/tts/stream` 返回 `TTS_STREAMING_DISABLED` 和 `end.ok=false`, `fallback=segment`。
- `/api/chat/stream` 问数链路仍返回 `tts_ready`, 分段 TTS fallback 未退化。
- `GET http://127.0.0.1:18000` 和前端 JS / CSS 资源均返回 HTTP 200。
- `GET /api/ops/health`、`/api/ops/dependencies`、`/api/ops/sessions`、`/api/ops/errors`、`/api/ops/metrics`、`/api/ops/export` 返回成功。
- `/api/ops/export` 密钥模式扫描未命中 `api_key` 明文、`Bearer ...`、`sk-*` 或 `ak-*`。
- Codex Browser 验证 FVS iframe host 模式和 `?fvs_mode=mock` 模式均可进入运维看板, 依赖状态、最近会话、错误列表和耗时指标可见。

### Not Done

- 现场截图、真实客户网络、麦克风 / 播放权限、Dora / RAGFlow 连通性和客户签字仍需在客户现场补齐。
- Dora 通用问数质量仍需结合客户真实数据源和 Dora 工具能力继续验证。

## 0.7.0 - 2026-06-10

### Added

- 新增 Gateway 本地只读 Excel 问数 Adapter `apps/api/app/services/ask_metrics.py`。
- 新增 `config/ask-metrics.yaml`, 管理本地问数工作簿和 sheet 映射。
- 新增 `ASK_METRICS_DATA_DIR`, 默认指向 `/app/docs/demo_data/ask_metrics`。
- 新增 `ASK_METRICS_CONFIG_PATH`, 默认指向 `/app/config/ask-metrics.yaml`。
- Docker API 镜像复制 `docs/demo_data`, Compose 只读挂载 `./docs/demo_data:/app/docs/demo_data:ro`。
- 新增 ADR-0010, 记录 V0.7 本地 Excel Adapter 承接问数的决策。
- POC 演示脚本扩展到 20 个稳定演示问题。

### Changed

- `/api/chat` 在调用 Mock Dora / 真实 Dora 前优先匹配本地问数意图。
- `/api/chat/stream` 对问数命中直接返回 `metadata`、`dora_delta` 和 `answer`, 并继续复用分段 TTS。
- API / 数据 / 配置 / 部署 / 测试 / 客户移交 / 风险 / 下一步文档同步 V0.7 问数链路。

### Verified

- `python -m compileall apps/api/app` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `docker compose up -d --build api web` 成功, API 和 Web 容器均启动。
- API 容器内 `uv run python -m compileall app` 通过。
- `GET /api/health` 返回 `status=ok`。
- `/api/chat` 11 个问数 smoke 均返回 `type=answer`, 数字来自三份脱敏 Excel。
- 服务级检查确认 `入党流程是什么?` 不被问数 Adapter 拦截。
- `/api/chat/stream` 问数 smoke 返回 `metadata -> dora_delta -> answer`。
- `corepack pnpm --dir apps/web build` 通过。
- `GET http://127.0.0.1:18000` 返回 HTTP 200。

### Not Done

- 尚未输出正式验收报告。
- 真实客户问数数据源、指标口径、刷新频率和授权范围仍需确认。

## 0.6.0 - 2026-06-10

### Added

- 新增前端 FVS Adapter 准备层 `apps/web/src/fvsAdapter.ts`。
- 新增 `VITE_FVS_INTEGRATION_MODE=parent` / `web-frame` / `fvs-web-frame` 模式, 支持数字人前端作为 FVS 网页框运行时向父页面发送 `FVS_ACTION` 消息。
- 新增 `VITE_FVS_INTEGRATION_MODE=iframe` host 模式, 支持数字人主页面 iframe 嵌入 FVS 看板。
- 新增 `VITE_FVS_TARGET_ORIGIN` 前端构建配置, 用于限制 `postMessage` 目标 origin。
- 新增运行时 URL 参数 `?fvs_url=...` 和 `?fvs_origin=...`, 便于不重建前端直接测试不同 FVS 看板地址。
- 新增 ADR-0006, 记录 V0.6 优先采用 FVS 网页框嵌入数字人页面的集成方向。
- 新增 ADR-0007, 记录 V0.6 方向切换为数字人主页面 iframe 嵌入 FVS 看板。
- 新增 FVS iframe `page_number` 切页能力: 白名单动作配置 `params.pageNumber` 后, 前端在 `/api/screen/execute` 成功后改写 FVS iframe URL。
- 新增前端直接控屏按钮, 用于本地联调 `总览`、`成品库存`、`生产管理`、`设备分析` 四个页面。
- 新增 Web Nginx `/webroot/` 同源代理, 将本机 FVS 请求转发到 `http://host.docker.internal:8075/webroot/`。
- 新增 ADR-0008, 记录 FVS `X-Frame-Options: SAMEORIGIN` 下采用同源代理的决策。
- 新增 FVS 主画布悬浮语音层: 未唤醒时只显示角落麦克风入口, 唤醒 / 连续追问 / 思考 / 播报时展开语音状态、动画和文字记录。
- 新增等待提示音策略: 正式指令或连续追问进入处理后立即播报“收到, 正在为您查找信息。”, AI 结果 TTS 开始时打断等待提示并优先播报最终回答。
- 新增 ADR-0009, 记录 FVS 主画布悬浮语音层和等待提示音打断策略。

### Changed

- V0.6 方向先尝试“FVS 网页框嵌数字人”, 后根据现场调试反馈改为“数字人主页面 iframe 嵌 FVS”。
- 前端在 `parent` 模式下仍保留网页框友好的单列布局, 作为备用方案。
- Docker Web 构建参数透出 `VITE_FVS_URL`、`VITE_FVS_INTEGRATION_MODE` 和 `VITE_FVS_TARGET_ORIGIN`。
- 本地 `.env` 的 `VITE_FVS_INTEGRATION_MODE` 当前为 `iframe`。
- FVS 集成、配置、数据契约、测试计划、客户动作清单、风险和下一步文档同步 iframe host 方案。
- 本机 FVS 测试看板映射为 `总览=page_number=1`、`成品库存=2`、`生产管理=3`、`设备分析=4`。
- `.env.example` 的 FVS URL 示例改为同源相对路径 `/webroot/...`。
- ADR-0006 状态改为 Superseded。
- FVS iframe host 模式改为 FVS 铺满视口; 主画布模式隐藏文本表单、Mock ASR 输入、Demo 按钮和直接控屏调试栏。
- 等待提示优先使用后端 TTS 预热音频, 音频未就绪时用浏览器 `speechSynthesis` 兜底。
- `NEXT_ACTIONS` 在用户人工验收确认后推进为 V0.7 POC 稳定版。

### Verified

- `corepack pnpm --dir apps/web build` 通过。
- `python -m compileall apps/api/app` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `docker compose up -d --build web` 成功, API 和 Web 容器均已重建并启动。
- `GET /api/health` 返回 `status=ok`。
- `GET http://127.0.0.1:18000` 返回 HTTP 200。
- Codex 内置浏览器验证前端曾在 `parent` 模式下为 FVS 网页框单列布局, 显示 `FVS 通信已就绪`, 无控制台 error。
- `/api/screen/execute` 合法动作 `SWITCH_TAB_ORG` 返回 `success=true`; 非法动作 `UNKNOWN_ACTION` 返回 `ACTION_NOT_ALLOWED`。
- iframe host 方向调整后, `corepack pnpm --dir apps/web build` 通过。
- iframe host 方向调整后, `docker compose up -d --build web` 成功。
- 使用 `?fvs_url=http%3A%2F%2F127.0.0.1%3A18080%2Fapi%2Fhealth` 验证运行时 FVS URL 参数生效, 页面显示 `FVS iframe`, iframe `src` 正确, 控制台无 error。
- `GET /api/screen/actions` 返回 `gotoPage` + `pageNumber=1/2/3/4` 的动作白名单。
- `/api/screen/execute` 合法动作 `SWITCH_TAB_ORG` 返回 `success=true`。
- 直接请求 `http://localhost:8075/webroot/...` 确认 FVS 返回 `X-Frame-Options: SAMEORIGIN`。
- 通过 `http://127.0.0.1:18000/webroot/...` 同源代理请求 FVS 返回 HTTP 200。
- Codex 内置浏览器验证 iframe 使用同源 `/webroot/...` 地址后, FVS 看板可见, 直接控屏按钮可切换 `page_number=1/2/3/4`, 控制台无 error。
- Codex 内置浏览器验证 FVS 主画布未唤醒状态: iframe 铺满 1280x720, 右下角仅显示 76x76 麦克风入口, 文本表单、Demo 按钮、直接控屏调试栏均不可见, 控制台无 error。
- 用户人工验收通过: FVS 四页内容、语音 / 文本指令链路、真实麦克风唤醒展开、等待提示音自动播放和 AI 结果打断等待提示体验均归入 V0.6 验收范围。

### Not Done

- 正式环境仍需确认采用同源代理还是调整 FVS iframe 允许策略。
- 尚未接入分页以外的 FVS 组件级控制 API。

## 0.5.0 - 2026-06-10

### Added

- 新增 `docs/demo_knowledge/` 最小党建知识库资料, 包含 3 位领导资料、2 篇新闻资料、3 份党建制度 / 流程文档。
- 新增 `docs/demo_data/ask_metrics/` 党建问数测试 Excel 数据, 包含党员学习、组织生活与党建活动、党员发展流程 3 份 `.xlsx`。
- 本地部署 RAGFlow `v0.25.6` 到 `D:\Project\ragflow`, 使用 Docker Desktop CPU + Elasticsearch profile。
- 启用 RAGFlow MCP self-host, 提供本地 `/mcp` 和 `/sse` 端点。
- RAGFlow 集成说明补充本地部署路径、端口、启动命令、MCP 配置和 Dora 可达性边界。
- 验证临时公网 MCP 地址 `http://liuchenxiang.uk:19382/mcp` 可完成 MCP 初始化和工具列表获取。
- 创建 RAGFlow dataset `zt_party_building_demo`, 上传并解析 8 份 V0.5 测试 Markdown。
- 验证 Dora Agent 通过公网 MCP 调用 RAGFlow 真实知识库, 并由 Dora 生成最终 `/api/chat` 的 `answer`。
- 新增 `POST /api/chat/stream`, 支持 Dora SSE 增量文本、最终 answer 和分段 TTS `tts_ready` 事件。

### Changed

- 按用户要求停止远端服务器部署方向, 并清理远端服务器本轮创建的 RAGFlow 容器、卷、网络和目录。
- RAGFlow 本地端口改为高位端口: Web `18089`, API `19380`, MCP `19382`, MySQL `13306`, Redis `16379`, Elasticsearch `11200`, MinIO `19000/19001`。
- `NEXT_ACTIONS` 在用户人工验收确认后推进为 V0.6 FVS 真实集成准备。
- 配置 RAGFlow 默认 Embedding 为 `text-embedding-v3@Tongyi-Qianwen`; 该模型 Key 只来自本地 `.env`, 不进入 Git 文档。
- 为最小 Markdown 解析关闭 `zt_party_building_demo` 的 RAPTOR / GraphRAG。
- 明确 V0.5 边界: Dora 负责最终回答, RAGFlow 只负责 `keyword=false` 向量检索; RAGFlow 默认 Chat 模型和 chat / assistant 不作为当前必需项。
- 修复 Dora SSE 解析: 忽略 MCP ToolMessage 原始 JSON chunks, 避免 Gateway 把 `{"chunks": ...}` 当作最终回答并返回 unsupported fallback。
- 本地 RAGFlow MCP server 做 POC 返回量瘦身: 固定 `keyword=false`, 限制 `page_size<=3`、`top_k<=16`、`similarity_threshold>=0.35`, 精简 chunk 字段和 content 长度。
- 前端优先调用 `/api/chat/stream`, 按 `tts_ready.index` 顺序播放分段音频; 流式失败时回退到原 `/api/chat` + `/api/tts`。

### Verified

- 远端清理后目标目录不存在, RAGFlow 容器和卷无残留。
- 本地 `GET http://127.0.0.1:18089/` 返回 HTTP 200。
- 本地 `GET http://127.0.0.1:18089/api/v1/system/healthz` 返回 `db` / `doc_engine` / `redis` / `storage` / `status` 全部 ok。
- 本地 `GET http://127.0.0.1:19382/sse` 返回 HTTP 200 `text/event-stream`。
- 本地 `GET http://127.0.0.1:19382/mcp` 返回 406, 提示 MCP client 需要 `Accept: text/event-stream`, 说明端点已监听。
- 公网 `POST http://liuchenxiang.uk:19382/mcp` 的 `initialize` 返回 `ragflow-mcp-server` 和 `protocolVersion=2025-03-26`。
- 公网 `tools/list` 返回 `ragflow_retrieval` 工具。
- 公网 `tools/call ragflow_retrieval` 在 dataset 导入前返回 `No accessible datasets found.`, 导入后可返回 `zt_party_building_demo` 检索 chunk。
- `zt_party_building_demo` 创建成功, dataset ID 为 `d7481bc0649311f18b616324ad8eb1c0`。
- `leader_zhang.md`、`leader_li.md`、`leader_wang.md`、`news_2026_party_research.md`、`news_2026_org_building.md`、`party_study_policy.md`、`join_party_process.md`、`branch_org_building_standard.md` 均解析为 `DONE`。
- 本地 MCP `ragflow_retrieval` 输入“张书记最近调研了什么?”可返回 `leader_zhang.md` / `news_2026_party_research.md` chunk。
- 公网 MCP `ragflow_retrieval` 输入“入党流程是什么?”可返回 `join_party_process.md` chunk。
- `/api/chat` 在 `ENABLE_MOCK_DORA=false` 下调用 Dora OpenClaw SSE 成功, Dora Agent 经公网 MCP 访问 RAGFlow 后返回知识库回答。
- Dora 知识库问答已覆盖: “张书记最近调研了什么?”、“入党流程是什么?”、“党员学习制度有哪些要求?”、“党支部组织建设规范是什么?”。
- RAGFlow 日志在 Dora 测试期间出现 `POST /mcp` 和 `POST /api/v1/retrieval` 成功记录。
- 修复后, 用户前端实际 session `demo-session-1781074089384` 复测“入党流程是什么?”和“张书记最近调研了什么?”均返回 `type=answer`。
- RAGFlow MCP 瘦身脚本已通过 `ragflow-cpu` 容器挂载验证, healthz 全部 ok。
- `/api/chat/stream` 输入“入党流程是什么?”验证通过: 本轮抽样中首个 `dora_delta` 约 8.5s 到 17.6s, 首个分段 `tts_ready` 约 11.6s 到 19.8s, 最终 `answer` 约 12.0s 到 21.3s, 全部分段 TTS 约 15.1s 到 27.1s 就绪。
- `docker exec zt-digital-human-api uv run python -m compileall app`、`corepack pnpm --dir apps/web build`、`docker compose config --services`、`GET /api/health`、`GET http://127.0.0.1:18000` 均通过。
- 三份问数测试 Excel 已通过重新导入、Dashboard 抽样读取、公式错误扫描和渲染预览检查。
- 用户已完成人工验收并确认 V0.5 通过。

### Not Done

- 尚未创建 RAGFlow chat / assistant; 当前 V0.5 不需要该能力。
- 尚未配置默认 Chat 模型; `ragflow_retrieval` 使用 `keyword=false` 可检索, 使用 `keyword=true` 会要求默认 Chat 模型。
- 尚未实现基于这三份 Excel 的真实问数解析 / 查询链路; 当前仅完成测试数据准备。
- 尚未接入真实 FVS; 下一阶段进入 V0.6 FVS 真实集成。

## 0.4.1 - 2026-06-10

### Added

- `config/wake-words.yaml` 增加 `followup_enabled`、`followup_window_ms`、`max_followup_turns`。
- 后端 `GET /api/wake/config` 透出连续对话窗口配置。
- 前端新增 `followup_listening` 状态, 播报结束后可在短时窗口内直接追问, 不需要再次说唤醒词。
- 连续对话窗口支持超时退出和最大追问轮数退出, 退出后回到唤醒监听。
- 监听卡片显示连续对话轮数, 便于现场验收。

### Changed

- V0.4 唤醒人工验收和 V0.4.1 连续对话窗口人工验收均已完成, 文档状态更新为 V0.5 RAGFlow MCP。
- TTS 自动播放结束、播放失败或被浏览器拦截时, 后台监听会优先进入追问窗口; 超出窗口后再回到唤醒监听。

### Verified

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config` 通过。
- `docker compose up -d --build` 通过。
- `GET /api/health` 返回 `status=ok`。
- `GET /api/wake/config` 返回 `followup_enabled=true`、`followup_window_ms=12000`、`max_followup_turns=3`。
- `GET http://localhost:18000` 返回 HTTP 200。
- 用户人工验收通过: 播报结束后可直接追问, 并可按超时 / 最大轮数退出连续对话。

## 0.4.0 - 2026-06-10

### Added

- 增加 `GET /api/wake/config`, 从 `config/wake-words.yaml` 返回唤醒词和 VAD / 冷却参数。
- 前端增加“后台监听”显式开关, 用户授权后才开启麦克风。
- 前端增加 `idle` / `monitoring` / `wake_checking` / `recording` / `thinking` / `speaking` / `cooldown` 监听状态机。
- 前端增加本地音量阈值 VAD, 只截取短音频片段提交 ASR 判断唤醒词。
- 命中唤醒词后支持同句剩余文本直接进入 `/api/chat`, 或进入一次正式指令录音。
- 未命中唤醒词的短片段会丢弃, 不进入 `/api/chat`。
- 增加 Mock ASR 唤醒演示按钮, 便于 Mock 环境验证“唤醒词 + 指令”路径。

### Changed

- `config/wake-words.yaml` 补充 `silence_ms`、`command_timeout_ms` 和 `vad_threshold`。
- 前端后台监听复用 V0.3 的 16k 单声道 WAV 编码、ASR、chat 和 TTS 链路, 保留手动录音回退。
- API / 数据 / 配置 / 测试文档同步 V0.4 唤醒契约。

### Verified

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config` 通过。
- `docker compose up -d --build` 通过。
- `GET /api/health` 返回 `status=ok`。
- `GET /api/wake/config` 返回唤醒词和 VAD 设置; Unicode escape 检查确认中文唤醒词正确。
- `GET http://localhost:18000`、前端 JS / CSS 静态资源均返回 HTTP 200。
- 当前会话未暴露 Codex in-app Browser 控制工具, 且未执行真实麦克风唤醒人工验收; 下一步需要在浏览器中点击“后台监听”并实测阈值。

## 0.3.0 - 2026-06-10

### Added

- 增加 ASR Provider 接口、Mock ASR 和真实 Provider 未配置兜底。
- 增加 TTS Provider 接口、Mock TTS WAV 生成和真实 Provider 未配置兜底。
- 增加 `POST /api/asr/transcribe`、`POST /api/tts`、`GET /api/tts/audio/{audio_id}`。
- 前端增加语音输入面板, 支持浏览器录音、Mock ASR 文本识别并进入 `/api/chat`。
- 前端增加 TTS 播报按钮、原生音频控件和语音能量条。
- 增加 `.dockerignore`, 避免本机依赖目录进入 Docker build 上下文。
- 增加阿里云 Fun-ASR WebSocket Provider。
- 增加阿里云 CosyVoice WebSocket Provider。
- 前端录音改为 16k 单声道 WAV, 适配真实 ASR。
- 增加后端依赖 `websockets`。

### Changed

- `docker-compose.yml` 补充 ASR / TTS 配置环境变量和 `TTS_CACHE_DIR`。
- `.env.example` 补充 `TTS_CACHE_DIR`。
- API / 数据 / 配置 / ASR-TTS 集成文档同步 V0.3 最小契约。
- `.env.example` 将 ASR 默认模型更新为 `fun-asr-realtime`, TTS 默认模型更新为 `cosyvoice-v3-flash`, 默认音色更新为 `longanyang`。
- 项目文档记录 V0.3 真实语音人工验收通过, 下一阶段进入 V0.4 语义唤醒 / 后台监听。

### Verified

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose up -d --build` 通过。
- ASR Mock、TTS Mock、TTS 音频下载、ASR 文本进入 `/api/chat` 均通过接口验证。
- Codex 内置浏览器验证 ASR 到对话、TTS 就绪、原生音频控件展示, 控制台无 error。
- 真实阿里云 CosyVoice TTS 验证通过, 可生成并下载 mp3。
- 真实阿里云 Fun-ASR Provider 已连通; 浏览器麦克风实录 ASR 已通过人工验收。

## 0.2.0 - 2026-06-10

### Added

- 增加 Dora OpenClaw Adapter: `list_agents`、`resolve_agent_id`、`sse_chat`。
- 增加 Dora 输出归一化: 标准 JSON、Markdown JSON、自然语言、非法控屏兜底。
- 增加 `httpx` 后端依赖并刷新 `uv.lock`。
- 增加 Dora 后台专用 Prompt, 对齐党建大屏 JSON 契约和 4 个白名单控屏动作。
- 增加客户侧 Dora 控屏 JSON 示例和当前验收状态说明。

### Changed

- `/api/chat` 根据 `ENABLE_MOCK_DORA` 分流: 默认 Mock 不变, `false` 时调用 Dora。
- `DORA_AGENT_ID` 为空时按 `DORA_AGENT_NAME` 自动发现已发布 Agent。
- `.env.example` 将 `DORA_AGENT_NAME` 示例更新为 `中天证券党建大屏语音助手`。

### Security

- Dora API Key 只从后端 `.env` / 环境变量读取, 不进入前端。
- Dora `screen_control` 只透出通过后端白名单校验的 `action.id`; 非法 action 返回 `ACTION_NOT_ALLOWED` 兜底。

### Verified

- V0.1 Mock 回归通过。
- Dora `list_agents`、按名称解析 Agent、SSE chat 和真实 `/api/chat` 路径验证通过。
- Gateway 白名单路径验证通过: 合法 Dora-like `screen_control` 放行, 非法 action 返回 `ACTION_NOT_ALLOWED`。
- 真实 Dora Agent `中天证券党建大屏语音助手` 控屏端到端验证通过: `SWITCH_HOME`、`SWITCH_TAB_ORG`、`SWITCH_TAB_STUDY`、`SWITCH_TAB_ACTIVITY` 均可归一为 `screen_control`, 非法页面返回 `fallback`。

## 0.1.0 - 2026-06-10

### Added

- 创建 `apps/web` Vue 3 + TypeScript + Vite + pnpm 前端工程。
- 创建 `apps/api` FastAPI + uv 后端工程, Docker 内使用 Python 3.12。
- 创建 `docker-compose.yml`, 支持前端 `18000` 和后端 `18080` 本地启动。
- 实现 V0.1 Mock API: `GET /api/health`、`POST /api/chat`、`GET /api/screen/actions`、`POST /api/screen/execute`。
- 后端读取 `config/screen-actions.yaml`、`config/demo-cases.yaml`、`config/wake-words.yaml`。
- 增加 action 白名单校验, 非法 `action_id` 返回 `ACTION_NOT_ALLOWED`。
- 前端实现文本输入、Mock Dora 回复展示、Mock FVS 动作展示。
- 增加 SQLite 会话日志写入。
- 增加 `pnpm-lock.yaml` 和 `uv.lock`, Docker 构建使用 frozen install。

### Verified

- `docker compose up -d --build` 通过。
- 后端健康检查、Mock chat、动作白名单、合法动作执行、非法动作拒绝均通过。
- 前端 HTTP 200, 浏览器内完成“切换到组织建设页面”Mock 闭环验证。

### Changed

- 为 V0.2 Dora 接入准备本地 `.env` 和容器环境变量映射。
- 增加 `DORA_AGENT_NAME` 与 `DORA_CHANNEL_TYPE` 配置, 支持后续在不知道 Agent ID 时按名称发现。
- Dora 集成文档补充 OpenClaw API 路径、SSE Chat 请求体和 History fallback 约定。

## 0.0.1 - 2026-06-10

### Added

- 初始化文档驱动开发体系。
- 增加根目录 `AGENTS.md`, 定义 Agent 阅读顺序、开发规则、文档维护规则和完成检查项。
- 增加 Codex 跨对话上下文。
- 增加项目蓝图、架构、开发计划、接口契约、数据契约、配置说明、部署说明、测试计划、演示脚本、客户移交文档、风险清单。
- 增加 ADR 决策记录。
- 增加集成说明和客户资料目录。
- 初始化 Git 仓库。
- 增加 `.gitignore`。
- 增加 `.env.example`。
- 增加第一版 `config/` 配置文件。
- 固定包管理决策: 前端 pnpm, 后端 uv, Docker 后端 Python 3.12。
