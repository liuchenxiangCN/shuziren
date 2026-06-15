# ADR-0023: 通用可配置数字人项目定位

## Status

Accepted

## Date

2026-06-15

## Context

项目早期以中天证券党建大屏数字人 POC 为主要叙述对象, 代码和文档中也存在 `zt-securities`、党建大屏、专用 Dora Agent、党建知识库和党建问数数据等表述。

用户已明确新的主线定位: 本项目应是通用可配置数字人项目。中天证券党建大屏只应作为一个可通过配置实现的客户需求实例。

当前代码已经具备客户配置覆盖层:

- 默认配置: `config/*.yaml`
- 客户配置: `config/customers/<customer-id>/*.yaml`
- 中天证券实例: `config/customers/zt-securities/`
- 客户文档: `docs/customers/zt-securities/`

## Decision

- 项目本体定位为通用可配置数字人 POC 模板。
- 核心代码、默认配置和主线方案文档不再以中天证券党建场景作为项目本体。
- 中天证券党建大屏需求通过客户 profile 实现, 包括:
  - 项目名称、产品名称、客户名称、场景名称、助手名称。
  - 唤醒词、欢迎语、演示问题和话术。
  - Dora Agent 名称和 Prompt profile。
  - RAGFlow dataset / 知识库配置。
  - 问数数据源和指标口径。
  - FVS 看板地址、页面参数和 `action_id` 白名单。
- 历史交付包、历史日志和 `docs/customers/zt-securities/` 继续保留中天证券事实记录, 不批量改写。
- 后续阶段 0 / 阶段 1 要优先完成主线通用化检查和只读 effective config, 让前端可看到当前生效的项目 / 客户 / 场景配置。

## Consequences

优点:

- 同一套代码可以复用到多个客户和多个业务场景。
- 中天证券需求仍可保留, 但不污染默认模板和后续架构判断。
- 配置中心的价值更清晰: 它负责把客户实例从代码和文档主线中剥离出来。

约束:

- 默认模板、前端标题、运维导出标题和 API 示例需要使用通用项目名。
- 新增客户时应新建 `config/customers/<customer-id>/` 和 `docs/customers/<customer-id>/`, 不应修改核心代码。
- 已交付给中天证券的 V1.0 材料是历史客户交付物, 不代表主线项目定位。
