# 中天证券知识库计划

## 知识库范围

第一阶段准备三类测试资料:

- 领导资料。
- 新闻资料。
- 党建制度和流程文档。

## 建议目录

```text
docs/demo_knowledge/
├─ leaders/
│  ├─ leader_zhang.md
│  ├─ leader_li.md
│  └─ leader_wang.md
├─ news/
│  ├─ news_2026_party_research.md
│  └─ news_2026_org_building.md
└─ party_docs/
   ├─ party_study_policy.md
   ├─ join_party_process.md
   └─ branch_org_building_standard.md
```

## 领导资料样例

```md
# 张某某书记资料

## 基本信息
- 姓名：张某某
- 职务：中天证券党委书记
- 关注方向：基层党建、党员学习、组织建设

## 近期动态
- 2026 年 5 月，调研基层营业部党建工作。
- 2026 年 6 月，参加党建引领业务发展专题会议。

## 适合欢迎语
张书记您好，欢迎莅临中天证券党建大屏。了解到您近期重点关注基层党建和党员学习工作，当前大屏已准备好相关数据和资料。
```

## RAGFlow 导入步骤

1. 登录 RAGFlow。
2. 创建 dataset。
3. 上传测试资料。
4. 等待解析完成。
5. 启用 MCP Server。
6. 在 Dora 配置外接 MCP。
7. Dora 调用 `ragflow_retrieval(keyword=false)` 获取知识库片段。
8. Dora 根据片段生成最终回答, 并使用测试问题验证。

## 当前资料状态

- 已在 `docs/demo_knowledge/` 准备 8 份 V0.5 最小测试资料。
- 已覆盖 3 位测试领导、2 篇新闻资料、3 份党建制度 / 流程文档。
- 内容均为脱敏演示样例, 不包含真实敏感或未授权信息。
- 已在 RAGFlow 中创建 `zt_party_building_demo` dataset。
- 已上传 8 份测试 Markdown 并解析完成, 全部为 `DONE`。
- 已通过公网 MCP `ragflow_retrieval` 验证可检索 `join_party_process.md` 等知识库片段。
- 已通过 Dora Agent + 公网 MCP 验证知识库问答, 覆盖张书记近期调研、入党流程、党员学习制度、党支部组织建设规范。

## 待验证问题

- 我是张书记, 请给我欢迎语。
- 张书记最近调研了什么?
- 入党流程是什么?
- 党员学习制度有哪些要求?
- 党支部组织建设规范是什么?
