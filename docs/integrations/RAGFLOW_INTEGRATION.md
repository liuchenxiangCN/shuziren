# RAGFlow 集成说明

## 目标

RAGFlow 负责测试知识库文档的解析、检索和 MCP 服务暴露。Dora 通过外接 MCP 调用 RAGFlow。

## 本地知识库内容

建议准备:

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

## 本地接入流程

```text
RAGFlow Web 可访问
-> 创建 dataset
-> 上传测试文档
-> 等待解析完成
-> 创建 chat / assistant
-> 启用 MCP Server
-> Dora 外接 MCP
-> Dora Agent 可调用知识库
```

## Dora 外接 MCP 配置

```text
名称: ragflow_party_knowledge
传输方式: HTTP, 优先 /mcp; 如不兼容则试 SSE /sse
URL: http://可访问地址:9382/mcp
请求头:
{
  "Authorization": "Bearer <RAGFLOW_API_KEY>"
}
```

## 网络注意事项

- MCP 地址必须是 Dora 服务器能访问的地址。
- 本地 `localhost` 对 Dora 不可见。
- 若 Dora 在远程服务器, 需要内网穿透或将 RAGFlow 部署到 Dora 可访问服务器。
- 不建议公网裸露 MCP 服务。
- POC 前必须确认网络与鉴权方案。

## 待确认

- RAGFlow 版本。
- MCP Server 端口。
- MCP 传输方式。
- Dora 对 MCP 的兼容性。
- 测试文档是否可脱敏。

