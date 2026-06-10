# 风险与遗留事项

本文档记录项目风险、限制和待确认事项。风险状态应随着开发和联调持续更新。

## 风险清单

| 编号 | 风险 | 影响 | 控制措施 | 状态 |
| --- | --- | --- | --- | --- |
| R-001 | Dora 无法访问本地 RAGFlow MCP | 知识库链路不通 | 使用内网穿透或将 RAGFlow 部署到 Dora 可访问服务器 | Open |
| R-002 | FVS 禁止 iframe 嵌入 | 数字人外壳方案失败 | 改为 FVS 内嵌数字人全局浮层 | Open |
| R-003 | FVS 跨域无法直接调用 JS | 大屏控制失败 | 使用 postMessage 或 FVS 侧预埋 Adapter | Open |
| R-004 | 云 ASR 识别不准 | 语音体验差 | 增加热词、换供应商、优化麦克风 | Open |
| R-005 | TTS 延迟高 | 播报慢 | 先展示文字, 后续流式 TTS | Open |
| R-006 | Dora 输出格式不稳定 | 前端解析失败 | Gateway 做 JSON 修复和容错 | Open |
| R-007 | RAGFlow 检索质量一般 | 知识问答效果差 | POC 后调切片、召回、Prompt | Open |
| R-008 | 问数口径不清 | 回答不准 | 先限定测试指标和标准问法 | Open |
| R-009 | 大模型误触发控屏 | 页面误切换 | action 白名单 + 二次校验 | Open |
| R-010 | 证券客户合规要求高 | 云模型受限 | POC 前确认云模型、数据范围、脱敏策略 | Open |
| R-011 | 本机未安装 pnpm / uv, 且 PATH 上 Python 为 3.14 | 非 Docker 本地开发会受阻 | 项目标准仍固定 pnpm + uv; Docker 使用 Python 3.12; 本机开发前补装工具 | Open |

## 当前遗留事项

- 尚未创建前后端工程。
- 尚未创建前端工程。
- 尚未创建后端工程。
- 尚未创建 Docker Compose。
- 尚未确认 Dora API 形态。
- 尚未确认 FVS iframe 和控制接口。
- 尚未准备真实测试知识库文档。
- 尚未确认 ASR / TTS 供应商账号。

## 待确认问题

- Dora 当前版本的 SSE 返回格式是什么?
- Dora 外接 MCP 对 HTTP `/mcp` 和 SSE `/sse` 的兼容性如何?
- FVS 是否允许 iframe 嵌入?
- FVS 是否已有页面 / Tab 切换 JS API?
- 客户 POC 是否允许使用云 ASR / TTS?
- POC 环境网络是否允许内网穿透?
- 党建问数数据源由 Dora、FineBI 还是 Mock API 提供?

## 风险处理规则

- 发现新风险必须新增编号。
- 风险关闭时保留记录, 状态改为 Closed, 并说明关闭原因。
- 影响阶段计划的风险必须同步更新 `NEXT_ACTIONS.md`。
