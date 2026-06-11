# 测试计划

## 测试原则

- 每个阶段都有独立验收。
- Mock 阶段不依赖外部平台。
- 真实集成阶段保留 Mock 回退路径。
- POC 前必须形成可重复演示脚本和测试问题清单。

## V0.1 Mock 闭环测试

| 编号 | 输入 | 期望 |
| --- | --- | --- |
| M-001 | `GET /api/health` | 返回 `status=ok` |
| M-002 | 输入“切换到成品库存” | 返回 `screen_control` 和 `SWITCH_TAB_ORG` |
| M-003 | 输入“打开生产管理” | 返回 `SWITCH_TAB_STUDY` |
| M-004 | 输入“张书记” | 返回领导欢迎语 |
| M-005 | 输入“学习完成率” | 返回问数 Mock 结果 |
| M-006 | 输入“入党流程” | 返回知识库 Mock 回答 |
| M-007 | 输入无法识别内容 | 返回 fallback |
| M-008 | 执行非法 action_id | 后端拒绝 |

## V0.2 Dora Adapter 测试

| 编号 | 输入 | 期望 |
| --- | --- | --- |
| DORA-001 | `ENABLE_MOCK_DORA=true` 后调用 `/api/chat` | 继续返回 V0.1 Mock 结果 |
| DORA-002 | `ENABLE_MOCK_DORA=false` 且 `DORA_AGENT_ID` 为空 | 按 `DORA_AGENT_NAME` 自动发现唯一已发布 Agent |
| DORA-003 | 调用 Dora OpenClaw `list_agents` | 返回 Agent 列表, 不输出 API Key |
| DORA-004 | 调用 Dora OpenClaw SSE chat | 能收敛 `messages` chunk 并归一为 `/api/chat` 响应 |
| DORA-005 | Dora 返回标准 JSON | 直接解析为 `answer` / `screen_control` / `fallback` |
| DORA-006 | Dora 返回 Markdown JSON | 提取代码块 JSON 后解析 |
| DORA-007 | Dora 返回自然语言 | 包装为 `answer` |
| DORA-008 | Dora 返回非法 `screen_control.action.id` | 返回 `fallback`, error.code 为 `ACTION_NOT_ALLOWED` |
| DORA-009 | Dora 超时或请求失败 | 返回安全 `fallback`, 不暴露密钥或底层堆栈 |
| DORA-010 | Dora 后台发布当前控屏 Prompt 后输入“请切换到成品库存页面” | 真实 Dora 返回 `screen_control` 和 `SWITCH_TAB_ORG`, 后端白名单放行 |

## V0.3 ASR / TTS 测试

| 编号 | 输入 | 期望 |
| --- | --- | --- |
| VOICE-001 | `ENABLE_MOCK_ASR=true` 后调用 `/api/asr/transcribe` | Mock ASR 返回 `success=true` 和识别文本 |
| VOICE-002 | `ENABLE_MOCK_TTS=true` 后调用 `/api/tts` | Mock TTS 返回音频 URL, 前端可播放 |
| VOICE-003 | `ENABLE_MOCK_ASR=false` 且无音频调用 `/api/asr/transcribe` | 返回 `ASR_AUDIO_REQUIRED` |
| VOICE-004 | `ENABLE_MOCK_TTS=false` 调用 `/api/tts` | 阿里云 CosyVoice 返回 mp3 音频 URL |
| VOICE-005 | 浏览器麦克风录入“请切换到成品库存页面” | 阿里云 Fun-ASR 返回文本, 文本进入 `/api/chat`, Dora 返回 `SWITCH_TAB_ORG` |
| VOICE-006 | 数字人回复后点击播报 | 前端可播放真实 TTS 音频 |
| VOICE-007 | 调用 `POST /api/chat/stream` 输入“入党流程是什么” | 返回 `dora_delta`、最终 `answer` 和多个分段 `tts_ready`; 前端按 `index` 顺序播放 |
| VOICE-008 | 唤醒后说出正式指令或连续追问 | 前端立即播报“收到, 正在为您查找信息。”一类等待提示, 同时进入 `/api/chat/stream` |
| VOICE-009 | 等待提示播放中 AI 结果 TTS 已生成 | 前端打断等待提示, 优先播放 AI 结果音频 |

## 语音唤醒测试

| 编号 | 输入 | 期望 |
| --- | --- | --- |
| W-001 | `GET /api/wake/config` | 返回 `小天小天`、`中天小天`、`你好小天` 和 VAD 设置 |
| W-002 | 点击“后台监听” | 浏览器请求麦克风授权, 前端进入 `monitoring` |
| W-003 | 说“小天小天” | ASR 命中唤醒词, 前端立即播报“您好。”, 并进入 `recording` 等待正式指令 |
| W-004 | 说“你好小天” | ASR 命中唤醒词, 前端立即播报“您好。”, 并进入 `recording` 等待正式指令 |
| W-005 | 说“小天小天, 请切换到成品库存页面” | 前端先播报“您好。”, 再播报“收到, 正在为您查找信息。”, 去掉唤醒词后自动进入 `/api/chat` -> TTS |
| W-006 | 普通闲聊无唤醒词 | 短片段进入 `cooldown`, 不进入 `/api/chat` |
| W-007 | 唤醒后超过 `command_timeout_ms` 无指令 | 回到监听冷却, 不报错 |
| W-008 | 关闭“后台监听” | 释放麦克风, 回到 `idle`, 手动录音按钮可继续使用 |
| W-009 | Mock ASR 文本设为“小天小天，请切换到成品库存页面”后开启后台监听 | 可用 Mock 路径演示唤醒词 + 指令链路 |
| W-010 | 唤醒对话播报结束后, 在 `followup_window_ms` 内直接说“党员学习完成率是多少” | 不需要再次说唤醒词, 自动进入 `/api/chat` |
| W-011 | 连续追问超过 `max_followup_turns` | 前端退出连续对话窗口, 冷却后回到唤醒监听 |
| W-012 | 播报结束后超过 `followup_window_ms` 不说话 | 前端退出连续对话窗口, 冷却后回到唤醒监听 |

## V0.5 RAGFlow MCP 测试

| 编号 | 输入 | 期望 |
| --- | --- | --- |
| RAG-001 | `GET http://127.0.0.1:18089/` | 返回 HTTP 200, 页面标题为 `RAGFlow` |
| RAG-002 | `GET http://127.0.0.1:18089/api/v1/system/healthz` | 返回 `db` / `doc_engine` / `redis` / `storage` / `status` 均为 `ok` |
| RAG-003 | `GET http://127.0.0.1:19382/sse` | 返回 HTTP 200 和 `text/event-stream` |
| RAG-004 | `GET http://127.0.0.1:19382/mcp` | 返回 MCP 端点响应; 普通 GET 可返回 406, 但应提示客户端需要 `Accept: text/event-stream` |
| RAG-005 | 在 RAGFlow Web 创建 `zt_party_building_demo` dataset 并上传 `docs/demo_knowledge/` | 8 份测试文档解析完成 |
| RAG-006 | 公网 MCP `tools/call ragflow_retrieval` 使用 `keyword=false` | 返回 `zt_party_building_demo` 的知识库 chunk |
| RAG-007 | Dora 配置 RAGFlow MCP `/mcp` 地址 | Dora 可调用 MCP tools, RAGFlow 日志出现 `/api/v1/retrieval` |
| RAG-008 | Dora 输入“入党流程是什么” | 返回基于 RAGFlow 知识库的 `answer` |
| RAG-009 | Dora 输入“张书记最近调研了什么” | 返回基层营业部党建调研相关 `answer` |
| RAG-010 | Dora 输入“党员学习制度有哪些要求” | 返回集中学习、学习台账、补学整改和综合评价要求 |
| RAG-011 | Dora 输入“党支部组织建设规范是什么” | 返回组织设置、三会一课、主题党日、党员发展和整改闭环要求 |
| RAG-012 | Dora 输入强约束 Prompt, 如“请严格依据知识库回答...” | 观察是否仍能生成 `answer`; 若返回 `fallback`, 记录为 Dora Prompt 稳定性问题 |
| RAG-013 | RAGFlow MCP `ragflow_retrieval` 返回 chunks | MCP 输出为精简字段, `keyword=false`, `page_size<=3`, `top_k<=16`, 不返回大段 metadata |
| RAG-014 | 真实 Dora + RAGFlow MCP + `/api/chat/stream` 输入“入党流程是什么” | 首个 `dora_delta` 和首个分段 `tts_ready` 在最终全量 TTS 前出现, 文本答案仍为知识库 `answer` |

## 领导问答测试

| 编号 | 输入 | 期望 |
| --- | --- | --- |
| L-001 | 我是张书记 | 返回张书记欢迎语 |
| L-002 | 张书记最近调研了什么 | 检索领导新闻 |
| L-003 | 我是李主任 | 返回李主任资料 |
| L-004 | 我是王书记 | 如果同名, 反问确认 |

## 党建文档问答测试

| 编号 | 输入 | 期望 |
| --- | --- | --- |
| K-001 | 入党流程是什么 | 基于知识库回答 |
| K-002 | 党员学习制度有哪些要求 | 基于知识库回答 |
| K-003 | 党支部组织建设规范是什么 | 基于知识库回答 |
| K-004 | 问知识库不存在内容 | 说明未检索到 |

## 党建问数测试

| 编号 | 输入 | 期望 |
| --- | --- | --- |
| D-001 | 当前党员学习完成率是多少 | 基于 `zt_party_study_metrics_2026.xlsx` 返回 87.5% |
| D-002 | 本月有多少人完成学习 | 基于 `zt_party_study_metrics_2026.xlsx` 返回 112 人 |
| D-003 | 哪个支部学习完成率最低 | 基于支部汇总返回最低完成率支部 |
| D-004 | 本月主题党日开展了几次 | 基于 `zt_party_org_life_metrics_2026.xlsx` 返回主题党日完成次数 |
| D-005 | 组织生活平均参会率是多少 | 基于组织生活数据返回平均参会率 |
| D-006 | 当前入党积极分子有多少人 | 基于 `zt_party_development_metrics_2026.xlsx` 返回入党积极分子人数 |
| D-007 | 本年转正党员有多少人 | 基于党员发展数据返回本年转正人数 |
| D-008 | 总结一下当前党建情况 | 综合学习、组织生活和党员发展测试数据返回总结 |
| D-009 | 整改事项闭环率是多少 | 基于组织生活 Dashboard 返回 46.7% |
| D-010 | 发展对象有多少人? 分别在哪些支部? | 返回 7 人及支部分布 |
| D-011 | 哪些党员发展材料还待补充? | 返回 3 人及所在支部 / 人员 ID |

V0.7 已实现 Gateway 本地 Excel 问数 Adapter。以上问题命中后应直接由 `/api/chat` 返回 `answer`, 不调用 Dora; `/api/chat/stream` 应至少返回 `metadata`、`dora_delta`、`answer`。

## 大屏控制测试

| 编号 | 输入 | 期望 |
| --- | --- | --- |
| S-001 | 切换到成品库存 | 返回 `SWITCH_TAB_ORG` 并执行 |
| S-002 | 打开生产管理 | 返回 `SWITCH_TAB_STUDY` 并执行 |
| S-003 | 返回总览 | 返回 `SWITCH_HOME` 并执行 |
| S-004 | 打开不存在页面 | 不执行, 返回兜底 |

## V0.6 FVS iframe Host 测试

| 编号 | 输入 | 期望 |
| --- | --- | --- |
| FVS-001 | 打开 `http://localhost:18000/?fvs_url=<encoded-fvs-url>` | 数字人主页面可加载, FVS 看板出现在 iframe 中 |
| FVS-002 | FVS URL 禁止 iframe 嵌入 | 浏览器控制台出现 frame 相关拦截, 记录为 FVS 嵌入策略问题 |
| FVS-003 | FVS 返回 `X-Frame-Options: SAMEORIGIN` | 通过同源代理 `/webroot/` 加载后, iframe 能显示 FVS 看板 |
| FVS-004 | 输入“切换到成品库存” | `/api/screen/execute` 成功后, 前端将 FVS iframe URL 切到 `page_number=2` |
| FVS-005 | 输入“打开生产管理” | 前端将 FVS iframe URL 切到 `page_number=3`, 且动作只在 Gateway 白名单校验成功后执行 |
| FVS-006 | 输入“打开不存在页面” | Gateway 返回 fallback 或 `ACTION_NOT_ALLOWED`, 前端不发送可执行动作 |
| FVS-007 | 点击直接控屏按钮 `总览`、`成品库存`、`生产管理`、`设备分析` | FVS iframe URL 分别切到 `page_number=1/2/3/4` |
| FVS-008 | `iframe` 模式打开主页面且未唤醒 | FVS 看板铺满视口, 页面上层仅显示小型低透明语音 icon, 不显示文本表单、Demo 按钮、调试控屏栏或运维入口 |
| FVS-009 | 唤醒词判定中或未命中唤醒词 | 右下角保持小型 icon, 不展开悬浮对话层, 不播报“您好。” |
| FVS-010 | 命中唤醒词、连续追问、思考或播报中 | 角落 icon 展开为半透明评论流, 只显示最近用户识别文本和数字人回复文本 |
| FVS-011 | 打开 `http://localhost:18000/ops` | 可直接进入运维看板; FVS 主画布不提供悬浮运维入口 |

## POC 准备验收

- 至少 10 个稳定演示问题。
- 至少 5 份测试知识库文档。
- 至少 3 位测试领导资料。
- 至少 3 个大屏动作。
- 响应时间能记录 ASR / Dora / TTS / 总耗时。
- 失败时不出现系统报错裸露。
- 不执行模型生成 JavaScript。

## V0.7 稳定版回归

| 编号 | 项目 | 期望 |
| --- | --- | --- |
| V07-001 | `python -m compileall apps/api/app` | 后端语法编译通过 |
| V07-002 | `corepack pnpm --dir apps/web build` | 前端类型检查和构建通过 |
| V07-003 | `docker compose up -d --build api web` | API 和 Web 容器均启动 |
| V07-004 | `GET /api/health` | 返回 `status=ok` |
| V07-005 | `/api/chat` 问数 11 题 smoke | 均返回 `type=answer`, 且数字来自 Excel |
| V07-006 | `/api/chat/stream` 输入“当前党员学习完成率是多少” | 返回 `metadata -> dora_delta -> answer`, 不等待 Dora |
| V07-007 | `入党流程是什么` 问数 Adapter 检查 | 不被问数 Adapter 拦截, 继续走知识库 / Dora 链路 |
| V07-008 | `http://127.0.0.1:18000` | 返回 HTTP 200 |

## V0.8 功能增强测试草案

| 编号 | 项目 | 期望 |
| --- | --- | --- |
| V08-CONFIG-001 | 设置 `CUSTOMER_ID=zt-securities` | 后端加载客户私有配置目录 |
| V08-CONFIG-002 | 客户级 `screen-actions.yaml` 覆盖默认配置 | `/api/screen/actions` 返回客户级动作 |
| V08-CONFIG-003 | 客户级 `fvs.yaml` 配置 FVS 地址 | 客户目录提供 FVS 地址样例; 前端仍通过 `VITE_FVS_*` 或 URL 参数获得安全配置 |
| V08-CONFIG-004 | 客户级 `ask-metrics.yaml` 覆盖默认问数映射 | Excel Adapter 使用客户级工作簿映射 |
| V08-ASK-001 | `ASK_METRICS_MODE=excel` 后运行 11 个问数 smoke | 结果与 V0.7 一致 |
| V08-ASK-002 | `ASK_METRICS_MODE=dora` 后输入问数 | 不使用 Excel 来源, 由 Dora / Mock Dora 链路承接 |
| V08-ASK-003 | `ASK_METRICS_MODE=auto` 且 Dora 可用 | 优先返回 Dora / Mock Dora 结果 |
| V08-ASK-004 | `ASK_METRICS_MODE=auto` 且 Dora 超时 / 兜底 | 回退 Excel Adapter |
| V08-ASK-005 | Dora 输出模型生成 SQL / JS / Python | Gateway 不执行, 返回安全兜底或仅作为文本处理 |
| V08-TTS-001 | `TTS_STREAMING_ENABLED=true` | 首个音频 chunk 早于完整 TTS 文件生成 |
| V08-TTS-002 | 流式 TTS Provider 失败 | 自动回退分段 TTS 文件播放 |
| V08-TTS-003 | AI 结果音频到达时等待提示仍在播放 | AI 音频打断等待提示 |
| V08-TTS-004 | `POST /api/tts/stream` 请求 `format=pcm` | 返回 `metadata -> audio_chunk* -> end`, 前端 Web Audio 可播放 PCM chunk |
| V08-TTS-005 | `TTS_STREAMING_ENABLED=false` | `/api/tts/stream` 返回 `tts_error`, 前端回退已有分段 TTS |
| V08-OPS-001 | 打开运维看板 | 能看到服务状态、依赖状态、最近会话、错误和耗时 |
| V08-OPS-002 | `GET /api/ops/dependencies` | 不返回 API Key 或敏感供应商响应 |
| V08-OPS-003 | 导出最近会话摘要 | 可用于验收记录 |

### V0.8 第一阶段已验证

- `python -m compileall apps/api/app` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `docker compose up -d --build api` 成功。
- API 容器内 `get_settings()` 确认客户目录覆盖层生效:
  - `action_whitelist_path=/app/config/customers/zt-securities/screen-actions.yaml`
  - `demo_cases_path=/app/config/customers/zt-securities/demo-cases.yaml`
  - `wake_words_path=/app/config/customers/zt-securities/wake-words.yaml`
  - `ask_metrics_config_path=/app/config/customers/zt-securities/ask-metrics.yaml`
- `ASK_METRICS_MODE=excel` 下 11 个问数 smoke 全部返回 `answer` 和 Excel 来源。
- `ASK_METRICS_MODE=excel` 下 `入党流程是什么?` 未被问数 Adapter 拦截。
- `/api/chat/stream` 问数返回 `metadata -> dora_delta -> answer -> tts_ready -> end`。
- 容器内函数级验证 `ASK_METRICS_MODE=dora` 不使用 Excel 来源。
- 容器内函数级验证 `ASK_METRICS_MODE=auto` 可在 Mock Dora 兜底时回退 Excel。

### V0.8 第二阶段已验证

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `git diff --check` 通过。
- `docker compose up -d --build api web` 成功。
- `GET /api/health` 返回 `status=ok`。
- `POST /api/tts/stream` 在真实 TTS 配置下返回 `metadata -> audio_chunk* -> end`; 抽样首个 PCM chunk 约 567ms 到达, `end.duration_ms=3387`, 共 33 个 chunk。
- `TTS_STREAMING_ENABLED=false` 时 `/api/tts/stream` 返回 `tts_error` code=`TTS_STREAMING_DISABLED` 和 `end.ok=false`, `fallback=segment`; 验证后已恢复默认开启。
- `/api/chat/stream` 输入 `当前党员学习完成率是多少?` 仍返回 4 个 `tts_ready`, 分段 TTS fallback 未退化。
- `GET http://127.0.0.1:18000` 和前端 JS / CSS 资源均返回 HTTP 200。
- 本轮 Codex Browser 控制工具未暴露, 未做截图级浏览器交互验证。

### V0.8 第三阶段已验证

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- Ops API smoke 范围:
  - `GET /api/ops/health`
  - `GET /api/ops/dependencies`
  - `GET /api/ops/sessions`
  - `GET /api/ops/errors`
  - `GET /api/ops/metrics`
  - `GET /api/ops/export`
- 前端运维看板入口: 访问 `/ops` 或在非 FVS 主画布模式使用顶部“演示 / 运维”切换后, 可查看依赖状态、最近会话、错误列表、耗时指标和日志导出按钮; FVS iframe host 模式不显示运维悬浮入口。
- Ops 接口和导出摘要不得返回 API Key、完整密钥或供应商敏感原始响应。
- 当前运行态 `GET /api/ops/dependencies` 聚合状态为 `error`, 原因为 Dora 探测超时、RAGFlow 探测失败; Ops API 本身返回正常。

## V0.9 交付优化测试

| 编号 | 项目 | 期望 |
| --- | --- | --- |
| V09-001 | 运行 `scripts/check-poc.ps1` | 检查 Docker、端口、API、Web 和外部依赖 |
| V09-002 | 运行 `scripts/check-poc.ps1 -RequireServices` | API / Web 未启动时返回 error, 已启动时返回 ok |
| V09-003 | 运行 `scripts/start-poc.ps1 -Build` | 可启动 API / Web |
| V09-004 | 运行 `scripts/start-poc.ps1 -Build -DemoStable` | API 启动时 `DEMO_STABLE_MODE=true`, 前端显示演示稳态 |
| V09-005 | 运行 `scripts/stop-poc.ps1` | 可停止 API / Web |
| V09-006 | 运行 `scripts/smoke-demo.ps1` | 固定演示问题集可返回预期 `answer` / `screen_control` |
| V09-007 | 运行 `scripts/export-logs.ps1 -Zip` | 生成包含 Ops Markdown / JSON 的日志包 |
| V09-008 | `GET /api/demo/config` | 返回演示稳态、客户 ID、问数模式、Mock 开关和固定问题 |
| V09-009 | `DEMO_STABLE_MODE=true` 且 Dora 超时 / 请求失败 | 优先回退 Excel 问数或 Mock Dora, 未命中时返回安全 fallback |
| V09-010 | Excel 问数文件缺失 | 返回 `ASK_METRICS_DATA_UNAVAILABLE` 一类安全兜底, 不暴露堆栈 |
| V09-011 | FVS iframe 加载失败或超时 | 前端给出可理解提示 |
| V09-012 | 麦克风权限失败 | 前端给出权限 / 设备排查提示 |

### V0.9 已验证

- `python -m compileall apps/api/app` 通过。
- `corepack pnpm --dir apps/web build` 通过。
- `docker compose config --services` 返回 `api`、`web`。
- `git diff --check` 通过。
- `scripts/check-poc.ps1 -SkipExternal -Json` 可输出预检 JSON, 当前 Docker daemon、Compose、API / Web 端口、`.env`、客户配置和问数数据检查通过。
- `scripts/start-poc.ps1 -Build -DemoStable` 成功重建并启动 API / Web。
- `GET /api/health` 返回 `status=ok`; `GET /api/demo/config` 返回 `stable_mode=true` 和固定演示题。
- `scripts/smoke-demo.ps1 -ExecuteScreenActions` 通过, 固定演示题和白名单控屏执行通过。
- `scripts/export-logs.ps1 -Zip` 生成 `logs/exports/zt-poc-logs-20260611-011813.zip`。
- `scripts/check-poc.ps1 -RequireServices -SkipExternal -Json` 通过。
- Codex Browser 验证 Mock 大屏模式可见“演示稳态”和动态演示题; iframe 模式无效 FVS URL 可显示超时兜底。

## V1.0 验收交付测试草案

| 编号 | 项目 | 期望 |
| --- | --- | --- |
| V10-001 | 验收报告 | 包含现场复演结果、截图、耗时和客户确认项 |
| V10-002 | 部署方案 | 覆盖 Windows + Docker Desktop + RAGFlow + FVS + Dora + ASR/TTS |
| V10-003 | 用户手册 | 覆盖唤醒、追问、问答、问数、大屏切换和兜底 |
| V10-004 | 运维手册 | 覆盖启停、预检、日志、故障排查和配置更换 |
| V10-005 | 配置手册 | 覆盖客户私有配置和 `.env` 密钥边界 |
| V10-006 | 测试报告 | 覆盖 V0.7 / V0.8 / V0.9 已验证项和客户现场待确认项 |
| V10-007 | 客户移交清单 | 覆盖交付物、环境、密钥、操作、验收场景、风险和签收 |

### V1.0 已输出

- `docs/delivery/v1.0/01_ACCEPTANCE_REPORT.md`
- `docs/delivery/v1.0/02_DEPLOYMENT_PLAN.md`
- `docs/delivery/v1.0/03_USER_MANUAL.md`
- `docs/delivery/v1.0/04_OPERATIONS_MANUAL.md`
- `docs/delivery/v1.0/05_CONFIGURATION_MANUAL.md`
- `docs/delivery/v1.0/06_TEST_REPORT.md`
- `docs/delivery/v1.0/07_CUSTOMER_HANDOFF_CHECKLIST.md`

当前 V1.0 文档测试通过标准: 交付包文件存在, `docs/00_INDEX.md` 已加入入口, `NEXT_ACTIONS` 已切换到现场验收复演, 并在验收报告中明确标注截图和真实依赖仍需客户现场补齐。
