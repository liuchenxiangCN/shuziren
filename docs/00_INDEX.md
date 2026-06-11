# 文档总入口

本目录是项目的长期上下文和交付知识库。任何开发、联调、移交、复盘都应优先更新这里, 避免关键信息只停留在聊天记录中。

## 先读文档

| 文档 | 用途 |
| --- | --- |
| [../AGENTS.md](../AGENTS.md) | Agent 执行入口、阅读顺序和维护规则 |
| [CODEX_CONTEXT.md](CODEX_CONTEXT.md) | Codex 跨对话恢复上下文 |
| [NEXT_ACTIONS.md](NEXT_ACTIONS.md) | 当前阶段、下一步任务、验收点 |
| [DEV_LOG.md](DEV_LOG.md) | 每轮开发事实记录 |
| [13_RISKS_AND_TODO.md](13_RISKS_AND_TODO.md) | 风险、限制、遗留事项 |

## 项目蓝图

| 文档 | 用途 |
| --- | --- |
| [01_PROJECT_BRIEF.md](01_PROJECT_BRIEF.md) | 项目背景、建设目标、非目标 |
| [02_PRODUCT_BLUEPRINT.md](02_PRODUCT_BLUEPRINT.md) | 业务场景、用户流程、产品形态 |
| [03_ARCHITECTURE.md](03_ARCHITECTURE.md) | 总体架构、服务边界、数据流 |
| [04_TECH_STACK.md](04_TECH_STACK.md) | 技术选型、供应商策略 |

## 工程执行

| 文档 | 用途 |
| --- | --- |
| [05_DEVELOPMENT_PLAN.md](05_DEVELOPMENT_PLAN.md) | 阶段计划、任务拆解、验收标准 |
| [06_API_CONTRACT.md](06_API_CONTRACT.md) | HTTP / SSE / WebSocket 接口契约 |
| [07_DATA_CONTRACT.md](07_DATA_CONTRACT.md) | Dora 输出、ScreenAction、日志结构 |
| [08_CONFIG_GUIDE.md](08_CONFIG_GUIDE.md) | .env、YAML、客户配置说明 |
| [09_LOCAL_DEPLOY.md](09_LOCAL_DEPLOY.md) | 本地部署、端口、Docker 启动 |
| [10_TEST_PLAN.md](10_TEST_PLAN.md) | 测试用例和验收清单 |

## POC 与移交

| 文档 | 用途 |
| --- | --- |
| [11_POC_DEMO_SCRIPT.md](11_POC_DEMO_SCRIPT.md) | 演示脚本和演示话术 |
| [12_CUSTOMER_HANDOFF.md](12_CUSTOMER_HANDOFF.md) | 客户移交、运维、常见问题 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更记录 |
| [14_ENHANCEMENT_ROADMAP.md](14_ENHANCEMENT_ROADMAP.md) | V0.8 功能增强、V0.9 交付优化、V1.0 验收交付路线 |

## V1.0 验收交付包

| 文档 | 用途 |
| --- | --- |
| [delivery/v1.0/README.md](delivery/v1.0/README.md) | V1.0 验收交付包索引 |
| [delivery/v1.0/01_ACCEPTANCE_REPORT.md](delivery/v1.0/01_ACCEPTANCE_REPORT.md) | 验收报告 |
| [delivery/v1.0/02_DEPLOYMENT_PLAN.md](delivery/v1.0/02_DEPLOYMENT_PLAN.md) | 部署方案 |
| [delivery/v1.0/03_USER_MANUAL.md](delivery/v1.0/03_USER_MANUAL.md) | 用户手册 |
| [delivery/v1.0/04_OPERATIONS_MANUAL.md](delivery/v1.0/04_OPERATIONS_MANUAL.md) | 运维手册 |
| [delivery/v1.0/05_CONFIGURATION_MANUAL.md](delivery/v1.0/05_CONFIGURATION_MANUAL.md) | 配置手册 |
| [delivery/v1.0/06_TEST_REPORT.md](delivery/v1.0/06_TEST_REPORT.md) | 测试报告 |
| [delivery/v1.0/07_CUSTOMER_HANDOFF_CHECKLIST.md](delivery/v1.0/07_CUSTOMER_HANDOFF_CHECKLIST.md) | 客户移交清单 |

## 决策记录

ADR 位于 [decisions](decisions)。

- [ADR-0001-project-scope.md](decisions/ADR-0001-project-scope.md)
- [ADR-0002-mock-first-strategy.md](decisions/ADR-0002-mock-first-strategy.md)
- [ADR-0003-screen-action-whitelist.md](decisions/ADR-0003-screen-action-whitelist.md)
- [ADR-0004-adapter-provider-strategy.md](decisions/ADR-0004-adapter-provider-strategy.md)
- [ADR-0005-package-management.md](decisions/ADR-0005-package-management.md)
- [ADR-0006-fvs-web-frame-communication.md](decisions/ADR-0006-fvs-web-frame-communication.md)
- [ADR-0007-fvs-iframe-host.md](decisions/ADR-0007-fvs-iframe-host.md)
- [ADR-0008-fvs-same-origin-proxy.md](decisions/ADR-0008-fvs-same-origin-proxy.md)
- [ADR-0009-fvs-floating-voice-overlay.md](decisions/ADR-0009-fvs-floating-voice-overlay.md)
- [ADR-0010-local-excel-ask-metrics-adapter.md](decisions/ADR-0010-local-excel-ask-metrics-adapter.md)
- [ADR-0011-enhancement-before-handoff.md](decisions/ADR-0011-enhancement-before-handoff.md)
- [ADR-0012-customer-config-overlay-and-ask-metrics-mode.md](decisions/ADR-0012-customer-config-overlay-and-ask-metrics-mode.md)
- [ADR-0013-tts-byte-streaming-with-pcm-web-audio.md](decisions/ADR-0013-tts-byte-streaming-with-pcm-web-audio.md)
- [ADR-0014-readonly-sanitized-ops-dashboard.md](decisions/ADR-0014-readonly-sanitized-ops-dashboard.md)
- [ADR-0015-v09-delivery-scripts-and-demo-stable-mode.md](decisions/ADR-0015-v09-delivery-scripts-and-demo-stable-mode.md)
- [ADR-0016-fvs-minimal-overlay-and-ops-route.md](decisions/ADR-0016-fvs-minimal-overlay-and-ops-route.md)

## 外部集成

| 文档 | 用途 |
| --- | --- |
| [integrations/DORA_AGENT_PROMPT.md](integrations/DORA_AGENT_PROMPT.md) | Dora Agent 系统提示词 |
| [integrations/DORA_INTEGRATION.md](integrations/DORA_INTEGRATION.md) | Dora API / SSE 接入 |
| [integrations/RAGFLOW_INTEGRATION.md](integrations/RAGFLOW_INTEGRATION.md) | RAGFlow / MCP 接入 |
| [integrations/FVS_INTEGRATION.md](integrations/FVS_INTEGRATION.md) | FVS 看板集成 |
| [integrations/ASR_TTS_INTEGRATION.md](integrations/ASR_TTS_INTEGRATION.md) | ASR / TTS 接入 |

## 客户资料

当前客户目录:

- [customers/zt-securities](customers/zt-securities)

客户化内容应放入 `docs/customers/<customer-id>/` 和未来的 `config/customers/<customer-id>/`, 不应写死在核心代码中。
