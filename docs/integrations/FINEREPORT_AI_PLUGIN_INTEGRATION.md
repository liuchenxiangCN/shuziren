# FineReport 官方智能问数插件集成设计

## 文档状态

- Lifecycle: `TARGET_NOT_IMPLEMENTED` / `EXTERNAL_GATE`
- 状态: 目标集成设计；API/认证/权限行为已有 2026-07-29 本地实测证据（deployment-local），升级稳定性与厂商确认仍未关闭
- 日期: 2026-07-26；本地实测: 2026-07-29
- 本地样本: `docs/fine-plugin-com.fr.plugin.decision.ai.v11-1.2.5-202606151853.zip`
- SHA-256: `D1F1F6BFA70C44652231293318ED4124B97B8A227209C0A35156F7EB1E4D68AB`
- 原始实测证据（gitignored，仅本机）: `data/plugin-probe/`（SUMMARY.md、Arthas jad dump、SSE 抓帧、UI 截图）

本文档基于插件包静态检查、2026-07-29 本地运行环境实测和当前产品边界编写。实测证据是 deployment-local 的：它证明插件 1.2.5 在 FineReport 11.0（jar 11.5.11）本地的真实行为，不等于厂商接口承诺，不关闭升级稳定性与生产兼容性门禁。

## 1. 已确认的包信息

插件 `plugin.xml` 声明:

| 字段 | 值 |
| --- | --- |
| 插件 ID | `com.fr.plugin.decision.ai.v11` |
| 名称 | `FR智能检索问答` |
| 版本 | `1.2.5` |
| FineReport 环境范围 | `11.0~11.0`（实测在 jar 11.5.11 上正常加载运行，该字段按 11.0 大版本线匹配） |
| Vendor | `FineReport AI Group` |
| 主包 | `com.fr.ai` |

产品面向 FineReport / FVS 11.0 大版本及之后版本，但该样本 manifest 只自报 `11.0~11.0`。因此“产品目标版本范围”和“插件 1.2.5 已验证范围”必须分开记录；11.0 之后版本需使用客户实际安装的对应插件版本重新执行兼容性探针。

描述能力包括:

- FineReport / FVS 模板智能检索。
- 自然语言定位模板。
- 参数化数据查询。
- 多轮问答。
- 推荐问题。
- 数据解读。

包内还声明或包含 Controller 注册、全局请求过滤器、平台配置和 DBAccessProvider 等扩展点。主 JAR 全部 437 个 class 被帆软商业加密（无 CAFEBABE 魔数），静态反编译不可行；路由级信息来自随包明文前端 JS 和运行时 Arthas jad dump（见 §2）。

## 2. 本地实测证据（2026-07-29，deployment-local）

实测环境：FineReport 设计器 11.0（jar 11.5.11，内嵌 Tomcat `:8075`），插件经“插件管理→从本地安装”正式安装。LLM 为 DeepSeek `deepseek-v4-flash`（OpenAI 兼容，非流式/流式/工具调用全部通过插件测试连接），Embedding 为 SiliconFlow `Qwen/Qwen3-VL-Embedding-8B`。

安装注意：手动把插件文件拷贝到 `WEB-INF/plugins` **不会**被运行时注册（日志零痕迹、端点 404）；必须走平台“插件管理→从本地安装”。安装后配置与索引跨重启持久化。

### 2.1 认证机制（实测 + jad 源码证实）

- 平台登录: `POST /webroot/decision/login`（JSON `{username,password}`，明文可用）→ `accessToken`（JWT，iss=fanruan）。
- 平台内端点: `Authorization: Bearer <token>`；建会话另带 `sessionid` 头。
- OpenAPI token 提取顺序（`AuthContextHelper.extractToken`）: query `fine_auth_token` → `Authorization: Bearer` → cookie `fine_auth_token`。**OpenAPI token 就是 FR 平台 token**，无独立签名体系；`POST /ai/api/auth/refresh` 用现有 token 换发新平台 token（TTL 取平台登录超时配置，缺省 30 分钟）。
- 无效/缺失 token（三种传法均实测）→ 平台过滤器先行 **302 跳登录页 HTML**，不是插件 JSON 错误。机器客户端必须按 302 判定鉴权失败。
- 统一响应包装 `{"code","message","data"}`；错误码枚举 `BAD_REQUEST(400)/UNAUTHORIZED(401)/FORBIDDEN(403)/NOT_FOUND(404)/UNPROCESSABLE(422)/INTERNAL(500)/UPSTREAM_FAIL(502)`。

### 2.2 OpenAPI 端点表（第三方嵌入面，逐条实测）

base = `/webroot/decision`

| 端点 | 方法 | 请求体 | 响应 data | 实测 |
| --- | --- | --- | --- | --- |
| `/ai/api/health` | GET | — | `"openapi-1.0.0"` | ✅ |
| `/ai/api/auth/refresh` | POST | `{}` | `{token, expiresAt}` | ✅ |
| `/ai/api/search/templates` | POST | `{query, keywords?, type?}` | `{items:[{id,name,path,type,aiSummary}]}` | ✅ 按用户权限过滤 |
| `/ai/api/templates/list` | GET | — | 同上 | ✅ 只列授权模板 |
| `/ai/api/templates/{id}/meta` | GET | — | `{params, metrics, dimensions}`（内置参数已过滤） | ✅ 未授权拒绝 |
| `/ai/api/params/range` | POST | `{templateId, paramName, generatedParams?}` | `{options:[{text,value}], supportsMultiple}` | ✅ 读活模板控件取值 |
| `/ai/api/params/validate` | POST | 同 range + `value` | `{valid, error}` | ✅ |
| `/ai/api/sessions` | POST | `{entryId, parameters?}` | `{sessionId, frSessionId, resourceType}` | ✅ 但见 §2.5 F-01 |
| `/ai/api/sessions/{sessionId}/data` | GET | `pageIndex, pageSize(≤10000)` | `{columns,rows,meta.total}` | ✅ 但见 §2.5 F-01 |
| `/ai/api/chart/validate` | POST | `{chartJson}` | `{valid, normalized, error}` | ✅ |
| `/ai/api/summary/template` | POST | `{templateId}` | `{summary}`（索引时存储的 AI 摘要） | ✅ |
| `/ai/api/embed` | GET | `fine_auth_token, redirect, sessionID?` | 种 cookie 后 302 到模板预览页 | jad 证实：redirect 白名单仅 `/view/report`、`/view/form`；token 失效回 auth-required HTML（postMessage `fr-auth-expired`） |

- `entryId` = 模板相对路径（如 `寿险经营管理驾驶舱/寿险经营管理驾驶舱.fvs`），`resourceType` 按后缀识别 cpt/frm/fvs；meta/params/summary 的 `{id}` = 目录条目 UUID。
- entryId 指向不存在的模板也返回 OK（`frSessionId:null`），客户端须自行判空。

### 2.3 平台内端点与 SSE（实测）

- 对话: `POST /ai/assets/chat/new` → `{chatId}`；`POST /ai/assets/chat?query=&chatId=`（SSE）；`POST /ai/assets/chat/cancel`；`POST /ai/assets/feedback` `{chatId,operation,type,message}`。
- SSE 帧: `id:N` + `data:{"type","content"}`；type ∈ `chatId / reasoning / msg / tool_call / complete / error`；`complete` 帧含 `tokenUsage{inputTokenCount,outputTokenCount,totalTokenCount}`。实测一次真实问数: 435 msg + 285 reasoning + 4 tool_call + complete（输入 18219 / 输出 1202 tokens）。
- 模型测试连接（SSE 分步帧 `event:progress/complete`，自动探测流式/工具调用能力）: `POST /ai/assets/config/model/test/llm`、`/test/vector`，body `{url,model,apiKey,llmMaxContext?}`。
- 配置: `GET/POST /ai/assets/config/model`（字段 `url/model/key/llmMaxContext/supportsTools/supportsStreaming/supportsStreamingTools/embedUrl/embedModel/embedKey`；**读取时 key/embedKey 已掩码 `********`**）；`GET/POST /ai/assets/config/template`（全局开关 `templateQuestionEnabled/autoDetectNewTemplate/dataSourceCitationEnabled/conversationMode`）；`GET/POST /ai/assets/config/template/entries`（POST body `{data:[{id,enabled}]}`，diff 语义）；`POST .../template/reindex`、`/reindexFailed`；`GET /ai/assets/config/index/status`（另有 SSE `/index/status/stream`）。
- 模板内数据解读: `/ai/template/analysis/chat(/new/cancel)`、`/feedback`、`/recommendation`；`/ai/profile/create|list|uploadAttachment`；推荐配置 `/ai/recommendation/config/(analysis|retrieval)(/save|/delete)`。
- 聊天页面: `GET /assets/ai/web/chat(/before)`。

### 2.4 模板索引（实测）

链路: 模板配置页勾选模板（API: POST entries `{data:[{id,enabled:true}]}`）→ reindex → LLM 提取元数据与摘要 → Lucene + 向量（embedding 持久化到文件）。实测 4 个 FVS 中 2 个成功（约 11s/21s 每个），2 个失败——失败原因是目录条目指向的模板文件在 `reportlets/` 不存在（错误码 11300005 模板文件流读取失败），属环境数据问题。检索召回偏保守：精确词（如“寿险”）有命中，泛词（“财务/驾驶舱/项目”）可能召回为空，集成时需按此调优提问引导。

### 2.5 权限继承实测矩阵（零权限用户 probe_u1 vs 管理员）

| 能力 | 零权限用户实测 | 结论 |
| --- | --- | --- |
| `templates/list`、`search/templates` | items:[] | ✅ 继承 FR 目录权限（源码: `TemplateAuthorityContext.getAuthorizedTemplateIds(userId)`） |
| `templates/{id}/meta`、`params/*`、`summary/template` | 拒绝（`UPSTREAM_FAIL`，语义非 `FORBIDDEN`） | ✅ 拒绝，但错误码不精确 |
| 平台内 chat 检索问数 | 多次检索后明确回答“未找到相关资产数据” | ✅ 检索链路受权限过滤 |
| 配置端点 `/ai/assets/config/*` | 平台 HTML 错误页 | ✅ 非管理员被拒（非 JSON 403） |
| `POST /ai/api/sessions` + `GET .../data` | 拿到两张模板真实组件数据（与管理员相同数值） | ❌ F-01，见下 |

**F-01（仅记录，不阻塞本项目）**: 插件 1.2.5 的 OpenAPI sessions 链路（`POST /ai/api/sessions`、`GET /ai/api/sessions/{id}/data`）不校验 entryId 的模板权限；任何持有有效平台 token 的用户可按模板路径读取任意模板计算数据（零权限用户两张模板复现，jad 源码确认无权限检查调用）。按 2026-07-29 用户决定：仅作记录，不影响本次项目开发。产品连接器设计仍应在自身层面对每屏绑定身份做模板权限校验（与本产品“权限拒绝不得回退到更高权限源”边界一致）。

### 2.6 其他实测观察

- 日志出现一次 `Decrypt failed: Message is larger than modulus`（ai-asset-fast-executor 线程），未阻断索引；疑似与较长密钥的 RSA 加解密有关，待厂商确认。
- 嵌入场景全局过滤器 `EmbedAuthFilter` 只挂 `/view/*`：仅当 `Sec-Fetch-Dest: iframe` 且带 `dora_embed` cookie 时校验 token，失效则回 auth-required HTML。
- LLM 依赖链：langchain4j 0.36.6（OpenAI 兼容）+ okhttp-sse；检索为本地 Lucene 8.11 + IK 分词 + embedding；模板“数据解读”由前端 inject.js 采集页面快照随对话上报，非服务端读模板。

## 3. 当前仍不能视为已确认的内容

- 厂商对接口稳定性的正式承诺、插件升级后的兼容保证（单版本本地实测无法证明）。
- FineReport 11.0 之后各小版本和客户实际环境的兼容性。
- 客户实际安装的合法授权和厂商支持、厂商与本产品之间的支持责任边界。
- 多轮升级路径下配置、索引和会话数据的迁移行为。

不得根据内部 Web 资源路径或类名直接承诺生产 API。本文 §2 的实测契约可作为连接器开发的工作基线，但冻结生产契约仍需官方文档或厂商确认。

## 4. 产品连接器定位

产品新增复合连接器 `FineReportAiConnector`，负责认证、健康、模板发现、会话和能力探测；它在目标问数 SPI `AskDataProvider` 下提供一等实现:

```text
FineReportAiPluginAskProvider
```

当前 POC 的 `AskMetricsProvider` 在 P2 演进或适配到目标 `AskDataProvider`，不能把现有 Excel 指标接口直接当作官方插件完整契约。核心业务不直接依赖插件内部类或路径。连接器负责:

- 插件存在性、版本和授权探测。
- FineReport 实例认证或用户身份透传。
- 模板 / FVS 资源发现。
- 会话创建与维护。
- 自然语言查询。
- 参数生成、校验和补充。
- 结果、图表、推荐问题与错误归一化。
- 权限失败、会话失效和插件不可用的安全处理。
- 统一监控、审计和 fallback。

按 FineReport 插件机制，该包预期由 FineReport 侧加载，但实际进程、类加载和资源拓扑仍需在运行环境确认。产品把它视为 FineReport 侧黑盒，只通过厂商确认的外部边界调用；HTTP / OpenAPI 是当前候选方式，不在拿到正式契约前固化。不得把插件 JAR 或其第三方依赖并入本产品服务进程。交付前需评估 FineReport JVM heap、索引磁盘和插件供应链清单。

## 5. 安装后能力探测

每个 FineReport ConnectorInstance 首次保存和每次升级后执行:

1. 检查 FineReport 版本、插件 ID、插件版本和启用状态。
2. 调用只读健康能力，确认连接和基础响应。
3. 校验认证方式和当前服务身份。
4. 校验测试用户能访问指定 FVS 模板。
5. 探测模板搜索、元数据、会话、参数、查询、图表和推荐问题能力。
6. 对客户指定测试模板执行一条无敏感数据的合成问数。
7. 记录能力矩阵、响应时间、权限范围和不支持项。
8. 生成兼容性报告，只有通过的能力才能在 CapabilityProfile 中启用。

能力探测必须是只读或可安全撤销的，不能修改客户模板、数据集或权限。§2 的实测端点表即该探测的实现基线：健康用 `/ai/api/health`，模板发现用 `/ai/api/templates/list`，元数据用 `/ai/api/templates/{id}/meta`，会话用 `/ai/api/sessions`，鉴权失败按 302 判定。

## 6. 运行链路

```text
大屏请求
-> 设备身份解析 ScreenInstance
-> 解析当前 CapabilityProfile
-> 解析 FineReport 用户 / 服务身份策略
-> FineReportAiPluginAskProvider
-> 插件会话与模板 / 参数问数
-> 标准化结果
-> 权限与来源校验
-> 文本 / 图表 / 跳转建议
-> TTS 与前端展示
```

建议的标准结果字段:

- `provider`
- `query_id`
- `session_ref`
- `answer`
- `speak_text`
- `metrics`
- `template_ref`
- `parameters`
- `filters`
- `time_range`
- `data_updated_at`
- `sources`
- `permission_context`
- `chart`
- `suggested_questions`
- `duration_ms`
- `fallback_reason`

字段最终形态应在拿到官方接口文档和真实响应样例后同步到 `06_API_CONTRACT.md` 与 `07_DATA_CONTRACT.md`。当前不修改运行时 API / 数据契约。实测可映射关系：插件 SSE `msg/reasoning` 流 → `answer/speak_text`，`tool_call` → 过程展示，`complete.tokenUsage` → `duration_ms`/计量，`/ai/api/templates/{id}/meta` 的 `params` → `parameters`，`chart/validate` 的 `normalized` → `chart`。

## 7. 权限与安全

- 大屏访客不登录产品后台，默认不存在可透传的访客个人 FineReport 身份。
- 每个 ScreenInstance 绑定一个最小权限的 FineReport 展示 / 服务身份或受控会话策略，使问数结果不超出该大屏原有模板和数据范围。
- 如果后续场景确实存在已登录用户，个人身份透传只能作为经契约验证的可选模式，不能成为产品默认假设。
- 禁止使用超级管理员账号为所有大屏问数。
- 产品后台用户、DeviceEnrollment 设备凭据和 FineReport 展示 / 服务身份分别管理，不得复用同一 Token。
- 插件返回内容进入 LLM 前执行字段最小化和脱敏。
- 日志只记录模板标识、参数摘要、权限结果、耗时和请求 ID，不记录明文凭据或完整敏感结果。
- 所有跳转和控屏建议仍需转换为 `action_id`，由后端白名单再次校验。
- 连接器不得通过页面 DOM 抓取或注入脚本模拟问数。
- 连接器调用插件 OpenAPI 前，必须在产品侧按 §2.5 F-01 自行校验目标模板在该大屏身份的授权集合内。

## 8. Fallback

推荐默认策略:

```text
官方插件可用且权限通过
-> 使用官方插件

插件不支持当前模板 / 暂时不可用
-> 按大屏 CapabilityProfile 选择受控数据库或 Excel

仍不可用
-> 返回清晰的安全 fallback
```

权限拒绝不得自动回退到权限更高的数据源，否则会造成越权。只有连接故障或明确的能力不支持，且备用 Provider 权限等价时，才允许自动 fallback。

## 9. 交付与授权

标准交付固定采用:

- 客户自行获得合法授权，并把官方插件安装到自己的 FineReport 工程。
- 产品安装程序不内置、不复制该插件包。
- 产品仓库、安装包和连接器包均不分发该插件。
- 产品提供版本检测、连接配置、能力探测和兼容性报告。
- 交付记录 FineReport、FVS、插件和本产品版本组合。

上线支持前仍必须取得或验证:

- 官方接口文档与稳定性承诺。
- 精确版本兼容矩阵。
- 认证与权限继承方案（本地实测已覆盖 1.2.5 行为，见 §2，仍需厂商确认）。
- 升级、故障和技术支持责任。

## 10. 阶段门禁

### P2 进入门禁

- 获取官方接口文档或厂商技术确认。（仍未关闭）
- 先在隔离的 FineReport 11.0 测试环境安装客户提供的合法插件，再逐步覆盖 11.0 之后的认证组合。（11.0 本地环境已完成，见 §2；11.0 之后版本组合未覆盖）
- 完成兼容、认证、权限和最小问数链路验证。（本地已完成：认证 §2.1、权限 §2.5、问数链路 §2.3；兼容性矩阵未覆盖）
- 冻结第一版连接器能力矩阵。（可待厂商确认后冻结）

### 门禁通过后才允许实现

- 编写 Provider Adapter。
- 增加配置 schema、健康检查和兼容性探测。
- 增加请求 / 响应契约和回归样例。
- 增加权限一致性、安全负测和 fallback 测试。

在 P2 进入门禁通过前，不应把静态检查得到的内部路径写入产品配置或实现中。§2 的实测路径同样不得直接写入产品实现；连接器实现时必须经配置化封装并在能力探测中动态验证。
