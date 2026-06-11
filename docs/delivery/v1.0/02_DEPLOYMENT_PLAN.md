# V1.0 部署方案

## 部署目标

在客户 Windows 本地演示机上部署党建大屏对话数字人 POC, 通过 Docker Desktop 启动数字人前端、后端和运维看板, 通过独立 RAGFlow Docker Compose 提供知识库检索, 并对接 Dora、ASR / TTS 和 FVS 看板。

## 拓扑

```text
浏览器
  -> http://localhost:18000
  -> 数字人前端 / FVS iframe host / /ops 运维看板
  -> http://localhost:18080/api
  -> FastAPI Gateway
  -> Dora / ASR / TTS / RAGFlow / SQLite / Screen Action Whitelist

RAGFlow 独立 Docker Compose
  -> Web: http://127.0.0.1:18089
  -> MCP: http://127.0.0.1:19382/mcp

FVS
  -> 推荐由数字人前端 iframe 嵌入
  -> 本机 SAMEORIGIN 场景可通过 /webroot/ 同源代理
```

## 主机要求

| 项目 | 建议 |
| --- | --- |
| 操作系统 | Windows 10 / 11 |
| 容器运行时 | Docker Desktop + WSL2 |
| CPU | 4 核及以上 |
| 内存 | 主项目建议 8GB 可用; RAGFlow 建议 Docker Desktop 分配 16GB |
| 磁盘 | 主项目 10GB 以上; RAGFlow 官方建议 50GB 以上 |
| 浏览器 | Chrome / Edge 最新稳定版 |
| 网络 | 可访问 Dora、ASR / TTS、FVS; Dora 需能访问 RAGFlow MCP 地址 |

## 端口规划

| 服务 | 地址 | 说明 |
| --- | --- | --- |
| Web | `http://localhost:18000` | 主演示页面和 `/ops` 运维看板 |
| API | `http://localhost:18080` | Gateway API |
| RAGFlow Web | `http://127.0.0.1:18089` | RAGFlow 管理页面 |
| RAGFlow API | `http://127.0.0.1:19380` | RAGFlow API |
| RAGFlow MCP | `http://127.0.0.1:19382/mcp` | MCP Streamable HTTP |
| FVS 本机测试服务 | `http://localhost:8075/webroot/...` | 当前测试环境示例 |

## 部署目录

```text
D:\Project\shuziren
D:\Project\ragflow
```

主项目目录:

```text
apps/api
apps/web
config
config/customers/zt-securities
docs/demo_data
scripts
data
logs
```

RAGFlow 目录:

```text
D:\Project\ragflow\docker
```

## 部署步骤

### 1. 准备主项目配置

```powershell
Set-Location D:\Project\shuziren
Copy-Item .env.example .env
```

按客户环境修改 `.env`:

- Dora 地址、Agent、Key。
- ASR / TTS Key 和模型。
- FVS URL 和集成模式。
- Mock 开关。
- `ASK_METRICS_MODE`。
- `DEMO_STABLE_MODE`。

密钥只写入 `.env`, 不写入 YAML、前端代码或文档。

### 2. 启动 RAGFlow

如客户现场需要真实知识库链路:

```powershell
Set-Location D:\Project\ragflow\docker
docker compose -f docker-compose.yml --profile cpu --profile elasticsearch up -d
```

验证:

```powershell
curl http://127.0.0.1:18089/api/v1/system/healthz
```

注意:

- Dora 远端无法访问本机 `127.0.0.1`。
- 真实 Dora MCP 地址需使用 Dora 可访问的内网 IP、隧道或服务器地址。
- 不建议公网裸露 MCP 服务。

### 3. 预检

```powershell
Set-Location D:\Project\shuziren
scripts\check-poc.ps1
```

如果只希望先检查本地配置, 可跳过外部探测:

```powershell
scripts\check-poc.ps1 -SkipExternal
```

### 4. 启动 POC

常规启动:

```powershell
scripts\start-poc.ps1 -Build
```

演示稳态启动:

```powershell
scripts\start-poc.ps1 -Build -DemoStable
```

同时尝试启动本机 RAGFlow:

```powershell
scripts\start-poc.ps1 -Build -WithRagflow
```

访问:

```text
http://localhost:18000
http://localhost:18000/ops
http://localhost:18080/api/health
```

### 5. 运行 Smoke

```powershell
scripts\smoke-demo.ps1 -ExecuteScreenActions
```

通过标准:

- 领导欢迎返回 `answer`。
- 入党流程返回 `answer`。
- 学习完成率返回 `87.5%`。
- 成品库存和总览返回 `screen_control` 并通过 `/api/screen/execute`。

### 6. 导出日志包

```powershell
scripts\export-logs.ps1 -Zip
```

默认日志包只包含脱敏 Ops Markdown / JSON 和 Compose 状态。

如现场明确需要 Docker 原生日志:

```powershell
scripts\export-logs.ps1 -IncludeDockerLogs -Zip
```

## FVS 部署策略

推荐模式:

```env
VITE_FVS_INTEGRATION_MODE=iframe
VITE_FVS_URL=/webroot/decision/view/duchamp?viewlet=your-dashboard.fvs&page_number=1
VITE_FVS_TARGET_ORIGIN=
```

如果 FVS 返回 `X-Frame-Options: SAMEORIGIN`, 使用同源代理:

```text
http://localhost:18000/webroot/... -> http://host.docker.internal:8075/webroot/...
```

大屏切换仍必须走:

```text
用户指令 -> Dora / Mock Dora -> action_id -> Gateway 白名单校验 -> 前端控制 FVS iframe
```

## 停止和恢复

停止主项目:

```powershell
scripts\stop-poc.ps1
```

停止 RAGFlow:

```powershell
Set-Location D:\Project\ragflow\docker
docker compose -f docker-compose.yml --profile cpu --profile elasticsearch down
```

重启主项目:

```powershell
scripts\start-poc.ps1
```

## 备份和保留

建议保留:

- `.env` 的客户现场版本, 仅限受控运维人员访问。
- `config/customers/zt-securities/` 非敏感客户配置。
- `logs/exports/*.zip` 验收日志包。
- `data/sessions.db` 如需追溯会话日志。
- RAGFlow dataset 导入记录和 MCP 配置截图。

## 部署验收清单

| 项目 | 标准 | 结果 |
| --- | --- | --- |
| Docker Desktop 启动 | `docker info` 成功 | 待现场填写 |
| 主项目预检 | `scripts/check-poc.ps1 -SkipExternal` 无 error | 待现场填写 |
| API 健康 | `/api/health` 返回 `ok` | 待现场填写 |
| Web 页面 | `http://localhost:18000` 可访问 | 待现场填写 |
| Ops 看板 | `http://localhost:18000/ops` 可访问 | 待现场填写 |
| RAGFlow | healthz 返回全部 ok | 待现场填写 |
| Dora | Agent 可调用 | 待现场填写 |
| ASR / TTS | 麦克风和播报可用 | 待现场填写 |
| FVS | iframe 可显示并切页 | 待现场填写 |
| 日志包 | `export-logs.ps1 -Zip` 成功 | 待现场填写 |
