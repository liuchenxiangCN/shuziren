# RAGFlow 集成说明

> Lifecycle: `AS_BUILT_POC`。本文描述当前 POC RAGFlow / MCP 接入和历史环境证据，不是多屏产品目标契约。

## 目标

RAGFlow 负责测试知识库文档的解析、向量检索和 MCP 服务暴露。Dora 通过外接 MCP 调用 RAGFlow, 取得知识库 chunks 后由 Dora 自己生成最终回答。

V0.5 明确边界:

- Dora 负责意图判断、工具调用和最终 `answer` / `screen_control` / `fallback` 输出。
- RAGFlow 只负责知识库检索, 不负责生成最终自然语言回答。
- MCP 调用 `ragflow_retrieval` 时固定使用 `keyword=false`。
- 当前 V0.5 不要求配置 RAGFlow 默认 Chat 模型, 也不要求创建 RAGFlow chat / assistant。

## 本地知识库内容

已准备 V0.5 最小脱敏测试资料:

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

已在 RAGFlow 中创建 dataset:

```text
name: zt_party_building_demo
description: 中天证券党建大屏 POC 演示知识库
id: d7481bc0649311f18b616324ad8eb1c0
```

最小验证问题:

- 我是张书记, 请给我欢迎语。
- 张书记最近调研了什么?
- 入党流程是什么?
- 党员学习制度有哪些要求?
- 党支部组织建设规范是什么?

## 本地部署状态

2026-06-10 已按用户要求改为本地 Docker Desktop 部署, 不再使用远端服务器。

部署目录:

```text
D:\Project\ragflow
```

版本:

```text
RAGFlow v0.25.6
```

本地端口:

| 服务 | 本地地址 | 说明 |
| --- | --- | --- |
| RAGFlow Web | `http://127.0.0.1:18089` | UI 登录、dataset、assistant、API Key |
| RAGFlow API | `http://127.0.0.1:19380` | 容器内 9380 映射 |
| RAGFlow MCP Streamable HTTP | `http://127.0.0.1:19382/mcp` | Dora 优先尝试 |
| RAGFlow MCP SSE | `http://127.0.0.1:19382/sse` | `/mcp` 不兼容时尝试 |
| Elasticsearch | `http://127.0.0.1:11200` | 需鉴权, 以容器健康为准 |
| MySQL | `127.0.0.1:13306` | 仅本地调试 |
| Redis | `127.0.0.1:16379` | 仅本地调试 |
| MinIO | `http://127.0.0.1:19000` | 仅本地调试 |

本地启动命令:

```powershell
Set-Location D:\Project\ragflow\docker
docker compose -f docker-compose.yml --profile cpu --profile elasticsearch up -d
```

本地停止命令:

```powershell
Set-Location D:\Project\ragflow\docker
docker compose -f docker-compose.yml --profile cpu --profile elasticsearch down
```

当前本地 `docker-compose.yml` 已在 `ragflow-cpu` 的 `command` 中启用:

```text
--enable-adminserver
--enable-mcpserver
--mcp-host=0.0.0.0
--mcp-port=9382
--mcp-base-url=http://127.0.0.1:9380
--mcp-script-path=/ragflow/mcp/server/server.py
--mcp-mode=self-host
--mcp-host-api-key=${RAGFLOW_MCP_HOST_API_KEY}
```

当前本地 `docker-compose.yml` 还将本地 MCP server 脚本挂载进 `ragflow-cpu`:

```text
../mcp/server/server.py:/ragflow/mcp/server/server.py:ro
```

## V0.5 MCP 返回量瘦身

为降低 Dora 接收 MCP 工具结果后的二次推理耗时, 当前本地 RAGFlow MCP server 做了 POC 级瘦身:

- 强制 `keyword=false`, 避免触发未配置 Chat 模型的 keyword search。
- `page_size` 最大 3。
- `top_k` 最大 16。
- `similarity_threshold` 最低 0.35。
- 单个 chunk `content` 最长 1200 字符。
- MCP chunk 只返回 `content`、`document_name`、`document_id`、`dataset_id`、`similarity`。
- 去掉每次检索前额外拉取 document / dataset metadata cache 的步骤。

上述默认值写在 `D:\Project\ragflow\mcp\server\server.py`, 也可通过 RAGFlow `docker/.env` 覆盖:

```env
RAGFLOW_MCP_MAX_PAGE_SIZE=3
RAGFLOW_MCP_MAX_TOP_K=16
RAGFLOW_MCP_MIN_SIMILARITY=0.35
RAGFLOW_MCP_MAX_CONTENT_CHARS=1200
```

注意: 这是本地 POC 为 Dora 工具输出做的瘦身 patch, 后续若升级 RAGFlow 版本, 需要重新核对 `mcp/server/server.py` 的上游变更。

`RAGFLOW_MCP_HOST_API_KEY` 已写入 `D:\Project\ragflow\docker\.env`, 不写入本项目 Git 文档。该 Key 仅用于本地 RAGFlow MCP self-host 模式认证。

本地验证结果:

```text
GET http://127.0.0.1:18089/ -> 200, title=RAGFlow
GET http://127.0.0.1:18089/api/v1/system/healthz -> 200, db/doc_engine/redis/storage/status 均为 ok
GET http://127.0.0.1:19382/sse -> 200 text/event-stream
GET http://127.0.0.1:19382/mcp -> 406 Not Acceptable, 提示客户端需要 Accept: text/event-stream, 说明 Streamable HTTP 端点已监听
```

公网映射验证结果:

```text
URL: http://liuchenxiang.uk:19382/mcp
GET /mcp with Accept: application/json, text/event-stream -> 200 text/event-stream
POST /mcp initialize -> 200, server=ragflow-mcp-server, protocolVersion=2025-03-26
POST /mcp tools/list -> 200, 暴露工具 ragflow_retrieval
POST /mcp tools/call ragflow_retrieval -> 200, 可返回 dataset 检索 chunk
```

当前公网 MCP 链路已通, RAGFlow dataset 已可通过 `ragflow_retrieval` 返回知识库片段。

## Dataset 导入状态

2026-06-10 已完成:

- 配置默认 Embedding: `text-embedding-v3@Tongyi-Qianwen`。
- 创建 dataset: `zt_party_building_demo`。
- 上传 `docs/demo_knowledge/` 下 8 份测试 Markdown, 不包含目录说明 `README.md`。
- 为最小 Markdown 解析关闭 RAPTOR / GraphRAG, 避免额外依赖默认 Chat 模型。
- 8 份文档均解析完成, 状态为 `DONE`, 每份生成 1 个 chunk。

文档解析结果:

| 文档 | 状态 | Chunks | Tokens |
| --- | --- | ---: | ---: |
| `leader_zhang.md` | DONE | 1 | 233 |
| `leader_li.md` | DONE | 1 | 165 |
| `leader_wang.md` | DONE | 1 | 149 |
| `news_2026_party_research.md` | DONE | 1 | 189 |
| `news_2026_org_building.md` | DONE | 1 | 171 |
| `party_study_policy.md` | DONE | 1 | 221 |
| `join_party_process.md` | DONE | 1 | 229 |
| `branch_org_building_standard.md` | DONE | 1 | 229 |

MCP 检索验证:

```text
Local MCP:  http://127.0.0.1:19382/mcp
Public MCP: http://liuchenxiang.uk:19382/mcp
Tool: ragflow_retrieval
Query: 张书记最近调研了什么?
Result: 返回 leader_zhang.md / news_2026_party_research.md 相关 chunk
Query: 入党流程是什么?
Result: 返回 join_party_process.md 相关 chunk
```

注意: 当前未设置默认 Chat 模型。`ragflow_retrieval` 使用 `keyword=false` 可正常向量检索; 若启用 `keyword=true`、TOC enhance 或 KG retrieval, RAGFlow 会要求默认 Chat 模型。V0.5 已决定不启用这些增强开关。

## Dora MCP 问答验证

2026-06-10 已将本地 POC 后端切换为真实 Dora:

```text
ENABLE_MOCK_DORA=false
DORA_AGENT_NAME=中天证券党建大屏语音助手
```

用户已在 Dora Agent 侧接入公网 MCP:

```text
http://liuchenxiang.uk:19382/mcp
```

验证路径:

```text
POC /api/chat
-> Dora OpenClaw SSE
-> Dora Agent 调用 RAGFlow MCP ragflow_retrieval
-> RAGFlow /api/v1/retrieval
-> Dora 基于 chunks 生成 answer
-> Gateway 归一为 /api/chat answer
```

通过问题:

| 问题 | 结果 |
| --- | --- |
| `张书记最近调研了什么?` | 返回基层营业部党建调研、党员学习、组织生活、党建引领业务发展等要点 |
| `入党流程是什么?` | 返回递交申请、谈话、积极分子、培养考察、发展对象、政治审查、预备党员、转正等流程 |
| `党员学习制度有哪些要求?` | 返回按月集中学习、学习计划 / 签到 / 台账、学习内容、补学整改和综合评价要求 |
| `党支部组织建设规范是什么?` | 返回组织设置、职责分工、三会一课、主题党日、党员发展、党费收缴和整改闭环要求 |

RAGFlow 日志在 Dora 测试期间出现公网 MCP 触发的成功检索:

```text
POST /mcp -> 200 / 202
POST /api/v1/retrieval -> 200
```

性能观察:

- RAGFlow 检索自身通常约 0.2s 到 1.3s。
- Dora 工具调用前决策和工具结果后的最终回答生成通常各占数秒, 是当前主要延迟来源。
- MCP 返回量瘦身后, 工具结果更短, 有利于降低 Dora post-tool 阶段负担, 但不能消除 Dora 两阶段推理耗时。

补充观察:

- 普通知识库问法稳定通过。
- “请严格依据知识库回答: 党支部组织建设规范是什么?” 触发了 RAGFlow retrieval, 但 Dora 最终返回 `fallback`; 判断为 Dora Agent 工具结果转回答的 Prompt 稳定性边角问题, 不影响正常演示问法。
- 领导欢迎语 `我是张书记, 请给我欢迎语。` 返回了可播报欢迎语, 但未明显引用领导资料中的近期关注方向, 后续可单独调 Dora Prompt。
- 前端真实提问曾出现 `DORA_OUTPUT_INVALID` fallback, 根因是 Dora SSE 中 MCP ToolMessage 原始 JSON chunks 被 Gateway 拼入最终文本。已在 `apps/api/app/services/dora_client.py` 忽略工具消息, 修复后同一 session 复测 `入党流程是什么?` 和 `张书记最近调研了什么?` 均返回 `answer`。

## 本地接入流程

```text
RAGFlow Web 可访问
-> 创建 dataset
-> 上传测试文档
-> 等待解析完成
-> 启用 MCP Server
-> Dora 外接 MCP
-> Dora 调用 ragflow_retrieval(keyword=false)
-> Dora 根据检索 chunks 生成最终回答
```

## Dora 外接 MCP 配置

本地验证时:

```text
名称: ragflow_party_knowledge
传输方式: HTTP, 优先 /mcp; 如不兼容则试 SSE /sse
URL: http://127.0.0.1:19382/mcp
```

Dora 真实联调时, `127.0.0.1` 对远程 Dora 不可见, 必须替换为 Dora 可访问地址:

```text
名称: ragflow_party_knowledge
传输方式: HTTP, 优先 /mcp; 如不兼容则试 SSE /sse
URL: http://可访问地址:19382/mcp
请求头:
{
  "Accept": "application/json, text/event-stream",
  "Content-Type": "application/json"
}
```

当前临时公网映射地址:

```text
URL: http://liuchenxiang.uk:19382/mcp
```

当前 RAGFlow MCP 使用 self-host 模式, Key 在 MCP 服务启动时提供给 RAGFlow, Dora 作为 MCP client 通常不再额外传 RAGFlow API Key。若后续切换为 host 模式, Dora client 请求需要携带 RAGFlow API Key, 且 RAGFlow 官方说明 host 模式暂不支持 Streamable HTTP, 需使用 SSE。

## 网络注意事项

- MCP 地址必须是 Dora 服务器能访问的地址。
- 本地 `localhost` 对 Dora 不可见。
- 若 Dora 在远程服务器, 需要 Windows 局域网 IP、内网穿透, 或将 RAGFlow 部署到 Dora 可访问服务器。
- 不建议公网裸露 MCP 服务。
- POC 前必须确认网络与鉴权方案。
- RAGFlow 官方建议 x86 CPU >= 4 核、内存 >= 16GB、磁盘 >= 50GB、Docker >= 24.0.0、Compose >= v2.26.1。
- 当前本地 Docker Desktop 分配约 16GB 内存, 能启动 V0.5 最小服务。

## 待确认

- Dora 侧 MCP 配置界面对 `/mcp` Streamable HTTP 的兼容性; 当前公网 `/mcp` 已通过 MCP initialize 和 tools/list 协议验证。
- Dora 侧能否访问本机 RAGFlow MCP 地址; 如不能, 选择局域网 IP 或临时隧道方案。
- Dora 调用 RAGFlow MCP 后是否能长期稳定按项目 `answer` JSON 格式返回。
- Dora 对 MCP 的兼容性。
- 后续真实客户资料是否可脱敏导入。
