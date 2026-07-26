# FineReport 官方智能问数插件集成设计

## 文档状态

- Lifecycle: `TARGET_NOT_IMPLEMENTED` / `EXTERNAL_GATE`
- 状态: 目标集成设计，待外部契约和运行环境验证
- 日期: 2026-07-26
- 本地样本: `docs/fine-plugin-com.fr.plugin.decision.ai.v11-1.2.5-202606151853.zip`
- SHA-256: `D1F1F6BFA70C44652231293318ED4124B97B8A227209C0A35156F7EB1E4D68AB`

本文档基于插件包静态检查和当前产品边界编写。静态检查只能证明包内声明和类存在，不能证明具体 HTTP 路由、请求方法、认证协议或生产兼容性。

## 1. 已确认的包信息

插件 `plugin.xml` 声明:

| 字段 | 值 |
| --- | --- |
| 插件 ID | `com.fr.plugin.decision.ai.v11` |
| 名称 | `FR智能检索问答` |
| 版本 | `1.2.5` |
| FineReport 环境范围 | `11.0~11.0` |
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

包内还声明或包含 Controller 注册、全局请求过滤器、平台配置和 DBAccessProvider 等扩展点。类清单中可见与认证、健康、元数据、检索、会话、参数、图表和嵌入相关的 Controller / DTO 名称。

静态类名支持的候选能力链为:

```text
auth / refresh
-> health
-> authorized template search
-> template metadata
-> parameter range / generate / validate
-> create session
-> fetch session data
-> optional chart validate / summary
```

这只是连接器探针的验证顺序，不是已确认的官方 URL 或请求契约。

## 2. 当前不能视为已确认的内容

- 对外稳定的 API Base Path。
- 每个接口的 HTTP 方法、请求体和响应体。
- 登录态、Token、Cookie、签名或嵌入鉴权方式。
- 是否能继承当前 FineReport 用户、组织和模板权限。
- FVS 模板问数的完整会话流程。
- FineReport 11 各小版本和补丁版本兼容性。
- 插件升级后的接口稳定承诺。
- 客户实际安装是否具备合法授权和厂商支持。
- 厂商与本产品之间的支持责任边界。

不得根据内部 Web 资源路径或类名直接承诺生产 API。插件类可能经过保护，只有在受支持 FineReport 运行环境安装后，结合官方文档或厂商确认才能冻结契约。

## 3. 产品连接器定位

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

## 4. 安装后能力探测

每个 FineReport ConnectorInstance 首次保存和每次升级后执行:

1. 检查 FineReport 版本、插件 ID、插件版本和启用状态。
2. 调用只读健康能力，确认连接和基础响应。
3. 校验认证方式和当前服务身份。
4. 校验测试用户能访问指定 FVS 模板。
5. 探测模板搜索、元数据、会话、参数、查询、图表和推荐问题能力。
6. 对客户指定测试模板执行一条无敏感数据的合成问数。
7. 记录能力矩阵、响应时间、权限范围和不支持项。
8. 生成兼容性报告，只有通过的能力才能在 CapabilityProfile 中启用。

能力探测必须是只读或可安全撤销的，不能修改客户模板、数据集或权限。

## 5. 运行链路

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

字段最终形态应在拿到官方接口文档和真实响应样例后同步到 `06_API_CONTRACT.md` 与 `07_DATA_CONTRACT.md`。当前不修改运行时 API / 数据契约。

## 6. 权限与安全

- 大屏访客不登录产品后台，默认不存在可透传的访客个人 FineReport 身份。
- 每个 ScreenInstance 绑定一个最小权限的 FineReport 展示 / 服务身份或受控会话策略，使问数结果不超出该大屏原有模板和数据范围。
- 如果后续场景确实存在已登录用户，个人身份透传只能作为经契约验证的可选模式，不能成为产品默认假设。
- 禁止使用超级管理员账号为所有大屏问数。
- 产品后台用户、DeviceEnrollment 设备凭据和 FineReport 展示 / 服务身份分别管理，不得复用同一 Token。
- 插件返回内容进入 LLM 前执行字段最小化和脱敏。
- 日志只记录模板标识、参数摘要、权限结果、耗时和请求 ID，不记录明文凭据或完整敏感结果。
- 所有跳转和控屏建议仍需转换为 `action_id`，由后端白名单再次校验。
- 连接器不得通过页面 DOM 抓取或注入脚本模拟问数。

## 7. Fallback

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

## 8. 交付与授权

标准交付固定采用:

- 客户自行获得合法授权，并把官方插件安装到自己的 FineReport 工程。
- 产品安装程序不内置、不复制该插件包。
- 产品仓库、安装包和连接器包均不分发该插件。
- 产品提供版本检测、连接配置、能力探测和兼容性报告。
- 交付记录 FineReport、FVS、插件和本产品版本组合。

上线支持前仍必须取得或验证:

- 官方接口文档与稳定性承诺。
- 精确版本兼容矩阵。
- 认证与权限继承方案。
- 升级、故障和技术支持责任。

## 9. 阶段门禁

### P2 进入门禁

- 获取官方接口文档或厂商技术确认。
- 先在隔离的 FineReport 11.0 测试环境安装客户提供的合法插件，再逐步覆盖 11.0 之后的认证组合。
- 完成兼容、认证、权限和最小问数链路验证。
- 冻结第一版连接器能力矩阵。

### 门禁通过后才允许实现

- 编写 Provider Adapter。
- 增加配置 schema、健康检查和兼容性探测。
- 增加请求 / 响应契约和回归样例。
- 增加权限一致性、安全负测和 fallback 测试。

在 P2 进入门禁通过前，不应把静态检查得到的内部路径写入产品配置或实现中。
