# 风险与遗留事项

本文档记录项目风险、限制和待确认事项。风险状态应随着开发和联调持续更新。

## 风险清单

| 编号 | 风险 | 影响 | 控制措施 | 状态 |
| --- | --- | --- | --- | --- |
| R-001 | Dora 无法访问本地 RAGFlow MCP | 知识库链路不通 | 本地 RAGFlow MCP 已在 `127.0.0.1:19382` 启动; 临时公网 `http://liuchenxiang.uk:19382/mcp` 已通过 MCP initialize、tools/list、retrieval 和 Dora Agent 真实知识库问答验证 | Closed |
| R-002 | FVS 禁止被数字人主页面 iframe 嵌入 | 当前推荐方案无法显示真实 FVS 看板 | 本机 FVS 返回 `X-Frame-Options: SAMEORIGIN`, 已通过 Web Nginx 同源代理 `/webroot/ -> http://host.docker.internal:8075/webroot/` 解决本地跨端口 iframe; 生产环境仍需确认正式同源代理或 FVS 侧嵌入策略 | Mitigated |
| R-003 | FVS iframe 动作通信未预埋监听 | 分页以外的组件级动作无法控制 | 当前四个测试页先通过 `page_number` URL 参数切换, 不依赖 FVS 侧监听; 组件级控制再预埋 `message` 监听或 Adapter, 只按 `action_id` 固定映射真实控制 API | Open |
| R-004 | 云 ASR 识别不准 | 语音体验差 | 增加热词、换供应商、优化麦克风 | Open |
| R-005 | TTS 延迟高 | 播报慢 | V0.5 已新增 `/api/chat/stream` 和分段 TTS; V0.6 已新增进入处理后的等待提示音, AI 结果音频就绪后会打断等待提示并优先播报最终回答, 且已通过人工验收; 当前仍不是供应商音频字节级真流式, 更低延迟留作后续优化 | Mitigated |
| R-006 | Dora 输出格式不稳定 | 前端解析失败 | Gateway 做 JSON 修复和容错; 已修复 Dora SSE 中 MCP ToolMessage 原始 JSON chunks 被误解析为最终回答的问题 | Open |
| R-007 | RAGFlow 检索质量一般或返回量过大 | 知识问答效果差 / Dora post-tool 变慢 | V0.5 已在本地 RAGFlow MCP server 固定 `keyword=false` 并瘦身返回字段、`page_size`、`top_k`、相似度阈值和 chunk 长度; 后续仍需结合真实文档调切片和召回 | Open |
| R-008 | 问数口径不清 | 回答不准 | V0.7 已采用 Gateway 本地只读 Excel Adapter 承接脱敏样例问数, 并验证 11 个固定问题; 正式客户真实数据源和指标口径仍需确认 | Mitigated |
| R-009 | 大模型误触发控屏 | 页面误切换 | action 白名单 + 二次校验 | Open |
| R-010 | 证券客户合规要求高 | 云模型受限 | POC 前确认云模型、数据范围、脱敏策略 | Open |
| R-011 | 本机未安装 pnpm / uv, 且 PATH 上 Python 为 3.14 | 非 Docker 本地开发会受阻 | V0.1 已通过 Docker 内 pnpm / uv 和 Python 3.12 构建验证; 本机非 Docker 开发前仍需补装工具 | Open |
| R-012 | 当前真实 Dora Agent 尚未按党建大屏 JSON Prompt 固化 | 真实 `screen_control` 可能无法稳定输出项目动作 JSON | 已发布专用 Agent `中天证券党建大屏语音助手`, 真实控屏端到端验证通过 | Closed |
| R-013 | 浏览器自动播放策略阻止 TTS 主动播报 | 数字人回答后不能自动发声, 等待提示音也可能被拦截 | V0.3 改为后台合成音频, 展示手动播报按钮和原生音频控件; V0.6 等待提示优先预热后端 TTS, 并用浏览器 `speechSynthesis` 兜底, 当前环境已通过人工验收; 正式客户环境仍需演示前检查播放权限 | Mitigated |
| R-014 | 百炼 API Key 已出现在对话上下文中 | 密钥泄露风险升高 | `.env` 不入 Git, 前端不暴露 Key; 客户移交或正式演示前建议在百炼控制台轮换 Key | Open |
| R-015 | 真实 ASR 麦克风链路验收风险 | 语音输入可能受浏览器权限、麦克风或音频格式影响 | 前端已改为 16k 单声道 WAV; 用户已完成人工验收 | Closed |
| R-016 | 浏览器后台监听受权限、焦点、现场噪声和自动播放策略限制 | 免点击体验可能无法在所有演示环境稳定运行 | V0.4 已实现用户显式启用开关 + 本地 VAD 截段 + 唤醒词 ASR 判断 + 手动按钮回退, 且真实唤醒已人工验收; V0.4.1 连续对话窗口和 V0.6 FVS 悬浮语音层均已人工验收 | Mitigated |
| R-017 | RAGFlow 默认 Chat 模型未配置 | `keyword=true`、TOC enhance、KG retrieval 或 RAGFlow 自己生成回答不可用 | V0.5 已明确 Dora 负责最终回答、RAGFlow 只做 `keyword=false` 向量检索; Dora MCP 问答已通过, 默认 Chat 模型不再是当前阻断项 | Open |
| R-018 | Dora 通用问数结果不稳定或无法说明口径 | 客户可能质疑问数准确性 | V0.8 计划新增 `ASK_METRICS_MODE=excel|dora|auto`, 保留 Excel fallback; Dora 问数必须带来源、口径、时间范围或无法确认说明 | Open |
| R-019 | TTS 字节级真流式在浏览器播放或供应商协议上不稳定 | 播报卡顿、打断失败或无法播放 | V0.8 真流式必须保留 `TTS_STREAMING_FALLBACK=segment`; 前端需验证 Web Audio / MediaSource 兼容性 | Open |
| R-020 | 运维监控 / 日志看板暴露敏感信息 | 泄露 API Key、供应商响应或客户数据 | Ops 接口不得返回 API Key、完整密钥、供应商敏感原始响应或未脱敏客户数据; 错误消息只给排障摘要 | Open |
| R-021 | 客户私有配置覆盖顺序不清或配置漂移 | 同一套代码在不同客户环境表现不一致 | V0.8 先实现明确的默认配置 + 客户覆盖层规则, 并补配置检查和文档 | Open |

## 当前遗留事项

- V0.1 Mock 闭环已完成。
- V0.2 Dora Adapter 已接入 OpenClaw `agents` 和 `sse/chat`, Mock 回退保留。
- 真实 Dora Agent `中天证券党建大屏语音助手` 已验证可返回 `answer` / `screen_control` / `fallback`。
- V0.3 已完成 ASR / TTS Provider 接口、Mock ASR、Mock TTS、最小前端语音输入和播报控件。
- 阿里云百炼真实 TTS 已验证通过; 浏览器麦克风真实 ASR 已通过人工验收。
- V0.4 语义唤醒 / 后台监听已完成真实麦克风人工验收, 已覆盖显式启用开关、本地 VAD、唤醒词 ASR 判断、状态机和手动按钮回退。
- V0.4.1 连续对话窗口已完成人工验收, 已覆盖播报后直接追问、超时退出和轮数退出。
- V0.5 已完成本地 RAGFlow Docker Desktop 基础部署和 MCP self-host 启动: Web `http://127.0.0.1:18089`, MCP `/mcp` `http://127.0.0.1:19382/mcp`, MCP `/sse` `http://127.0.0.1:19382/sse`。
- V0.5 已验证临时公网 MCP `http://liuchenxiang.uk:19382/mcp`: `initialize` 成功, `tools/list` 返回 `ragflow_retrieval`, `tools/call` 可返回 `zt_party_building_demo` 检索 chunk。
- V0.5 已验证 Dora Agent 通过公网 MCP 调用 RAGFlow, 并由 Dora 生成最终 `/api/chat` 的知识库 `answer`。
- V0.5 已对本地 RAGFlow MCP server 做 POC 返回量瘦身: 固定 `keyword=false`, 限制 `page_size<=3`、`top_k<=16`、`similarity_threshold>=0.35`, 精简 chunk 字段和 content 长度。
- V0.5 已新增 `/api/chat/stream`, 前端优先使用 Dora SSE + 分段 TTS; 本轮抽样验证“入党流程是什么?”首个 `dora_delta` 约 8.5s 到 17.6s、首个分段 `tts_ready` 约 11.6s 到 19.8s、最终 `answer` 约 12.0s 到 21.3s、全部分段 TTS 约 15.1s 到 27.1s 就绪。
- 已准备 3 份党建问数测试 Excel: 党员学习、组织生活与党建活动、党员发展流程。
- V0.7 已实现 Gateway 本地只读 Excel 问数 Adapter, `/api/chat` 和 `/api/chat/stream` 会在调用 Dora 前优先匹配问数意图; 11 个脱敏样例问数问题已通过接口 smoke。
- 用户已确认后续不立即输出验收报告, 而是先进入 V0.8 功能增强: Dora 通用问数 + Excel fallback、TTS 字节级真流式、运维监控 / 日志看板、客户私有配置目录。
- V0.5 已完成人工验收, 用户确认真实 Dora + RAGFlow MCP + 分段 TTS 链路通过。
- 已创建 `docs/demo_knowledge/` 最小党建知识库测试资料。
- 已在 RAGFlow 创建 `zt_party_building_demo` dataset, 上传 8 份测试资料并等待解析完成, 全部为 `DONE`。
- V0.6 FVS 真实集成已完成人工验收: 以数字人前端为主体 iframe 嵌入 FVS 看板, 并先将 `action_id` 白名单映射到 FVS `page_number` 分页切换能力。
- 已确认本机 FVS URL 可通过数字人前端同源代理渲染; 客户正式环境仍需在 V0.7 演示准备中确认是否采用同源代理、网关转发或调整 FVS 侧嵌入策略。
- V0.6 已实现 FVS 主画布悬浮语音层: 未唤醒时只显示角落麦克风入口, 唤醒 / 连续追问 / 思考 / 播报时展开语音状态、动画和文字记录。
- V0.6 已新增等待提示音策略: 正式指令或连续追问进入处理后立即播报“收到, 正在为您查找信息。”, AI 结果音频开始时打断等待提示并优先播报最终回答。
- V0.6 已完成人工验收, 用户确认“0.6验收完成”。
- 尚未创建 RAGFlow chat / assistant; 当前 V0.5 不需要该能力。
- 尚未配置 RAGFlow 默认 Chat 模型; `keyword=true` 检索会要求 Chat 模型, 当前固定使用 `keyword=false`。
- 尚未确认客户演示环境的麦克风 / 播放权限。
- PowerShell 直接发送中文 JSON 时可能受本地终端编码影响; API 和浏览器 UTF-8 链路已验证正常。
- 当前 TTS 优化为分段文件播放, 不是音频字节级边合成边播放; 若后续要求更低首响, 需评估供应商 TTS 真流式接口和前端 MediaSource / WebAudio 播放方案。
- 尚未实现 `ASK_METRICS_MODE=dora|excel|auto`。
- 尚未实现客户私有配置覆盖层。
- 尚未实现 TTS 字节级真流式。
- 尚未实现运维监控和日志看板。

## 待确认问题

- V0.7 / 正式演示环境是否沿用 `/webroot/` 同源代理, 还是由 FVS 侧调整 iframe 允许策略?
- FVS `page_number=1/2/3/4` 在正式演示环境刷新和切页后是否能稳定保持目标页面?
- 当前临时公网 MCP 映射是否满足客户演示网络和安全要求?
- 是否需要为后续增强检索或 RAGFlow 自答配置默认 Chat 模型?
- Dora Agent 通过公网 `/mcp` 调用 `ragflow_retrieval` 时能否长期稳定保持 `keyword=false`?
- RAGFlow MCP POC patch 在后续升级 RAGFlow 版本时如何维护?
- FVS 是否已有页面 / Tab 切换 JS API 或组件状态控制方式?
- FVS iframe 动作通信需要使用标准 `window.addEventListener("message")` 还是 FVS 自身 Adapter?
- 客户 POC 是否允许使用云 ASR / TTS?
- 客户 POC 演示环境是否允许长时间开启浏览器麦克风监听?
- 客户 POC 演示环境的现场噪声和麦克风增益是否需要单独调 VAD 阈值?
- POC 环境网络是否允许内网穿透?
- 正式客户党建问数执行链路是否继续沿用 Gateway Excel Adapter, 还是切换为 Dora、FineBI / FVS 数据源或数据库 Provider?
- 正式客户党建问数指标口径、数据刷新频率和授权范围是什么?
- Dora 通用问数是否已有可稳定调用的数据源、工具或客户侧数据集?
- TTS 供应商当前 WebSocket 协议是否支持边合成边返回可播放音频 chunk?
- 运维看板是否需要登录鉴权, 还是仅限本地 POC 内网访问?
- 客户私有配置目录最终是否需要支持多客户并存, 还是只保留 `zt-securities` 一个客户目录?

## 风险处理规则

- 发现新风险必须新增编号。
- 风险关闭时保留记录, 状态改为 Closed, 并说明关闭原因。
- 影响阶段计划的风险必须同步更新 `NEXT_ACTIONS.md`。
