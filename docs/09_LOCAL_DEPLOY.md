# 本地部署说明

本文档记录本地开发部署方式。V0.1 已创建可运行代码工程, 当前可通过 Docker Compose 启动前端和后端 Mock 闭环。

## 前置准备

- Windows 10 / 11。
- Docker Desktop。
- WSL2。
- Node.js 和 Python 可由 Docker 镜像提供, 本机不强依赖。
- 如需非 Docker 本地开发, 前端使用 pnpm, 后端使用 uv + Python 3.11/3.12。
- Dora API Key。
- 国产 ASR / TTS API Key。
- FVS 主模板网页框可访问数字人前端地址。
- 测试知识库文档。
- 测试问数数据。

## 推荐端口

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| digital-human-web | 18000 | 前端 |
| digital-human-api | 18080 | 后端 |
| reverse-proxy HTTP | 18081 | 代理 |
| reverse-proxy HTTPS | 18443 | HTTPS 入口 |
| RAGFlow Web | 18089 | 知识库页面, 独立 RAGFlow compose |
| RAGFlow API | 19380 | RAGFlow API, 独立 RAGFlow compose |
| RAGFlow MCP | 19382 | MCP Server, `/mcp` 和 `/sse` |

## 启动流程

V0.9 起推荐使用脚本启动:

```powershell
Copy-Item .env.example .env
# 修改 .env

scripts\check-poc.ps1
scripts\start-poc.ps1 -Build
```

演示稳态启动:

```powershell
scripts\start-poc.ps1 -Build -DemoStable
```

如果需要同时启动当前本机 `D:\Project\ragflow\docker` 下的 RAGFlow:

```powershell
scripts\start-poc.ps1 -Build -WithRagflow
```

停止:

```powershell
scripts\stop-poc.ps1
```

原始 Docker Compose 命令仍可使用:

```powershell
git clone <repo> configurable-digital-human
cd configurable-digital-human

Copy-Item .env.example .env
# 修改 .env

docker compose up -d --build
```

访问:

```text
http://localhost:18000
http://localhost:18000/ops
http://localhost:18080/api/health
```

V0.9 常用脚本:

```powershell
scripts\check-poc.ps1 -RequireServices
scripts\smoke-demo.ps1
scripts\export-logs.ps1 -Zip
```

`export-logs.ps1` 默认只导出脱敏 Ops Markdown / JSON 和 Compose 状态。若现场明确需要 Docker 原生日志, 再使用:

```powershell
scripts\export-logs.ps1 -IncludeDockerLogs -Zip
```

V0.7 本地问数 Adapter 需要读取仓库内脱敏 Excel, Docker Compose 已默认只读挂载:

```text
./docs/demo_data:/app/docs/demo_data:ro
```

V0.8 起 Docker Compose 可按客户 profile 传入:

```env
CUSTOMER_ID=default
CUSTOMER_CONFIG_DIR=
ASK_METRICS_MODE=excel
```

使用中天证券客户实例时设置:

```env
CUSTOMER_ID=zt-securities
CUSTOMER_CONFIG_DIR=/app/config/customers/zt-securities
```

后端会加载 `config/customers/<customer-id>/ask-metrics.yaml`, 其中 `data_dir` 可指向 `/app/docs/demo_data/ask_metrics` 或客户自己的只读问数数据目录。如需强制使用其他路径, 再显式设置 `ASK_METRICS_DATA_DIR` 或 `ASK_METRICS_CONFIG_PATH`。

## RAGFlow 启动策略

主项目不建议直接内嵌 RAGFlow 官方完整 compose。建议:

- 主项目 compose 只放数字人前端、后端和反向代理。
- RAGFlow 使用官方 Docker Compose 独立部署。
- 当前本地 RAGFlow 位于 `D:\Project\ragflow`, 启动命令为 `docker compose -f docker-compose.yml --profile cpu --profile elasticsearch up -d`。
- 当前本地 RAGFlow MCP server 已做 POC 返回量瘦身, 相关配置见 `docs/integrations/RAGFLOW_INTEGRATION.md`。
- Dora 需要访问 RAGFlow MCP 时, 根据网络情况选择内网 IP、隧道或部署到 Dora 可访问服务器。

## 本地麦克风注意事项

浏览器麦克风权限通常要求 HTTPS 或 localhost。开发阶段优先使用 `localhost`; POC 演示时再配置 HTTPS 入口。

## FVS iframe 联调

V0.6 已验收的推荐方式是让数字人前端作为主页面 iframe 加载 FVS 看板。拿到 FVS URL 后, 可先用 URL 参数临时验证:

```text
http://localhost:18000/?fvs_url=<url-encoded-fvs-url>
```

如果 FVS URL 为 `https://example.com/fvs`, 编码后类似:

```text
http://localhost:18000/?fvs_url=https%3A%2F%2Fexample.com%2Ffvs
```

当前本机 FVS 服务位于 `http://localhost:8075/webroot/...`, 且响应 `X-Frame-Options: SAMEORIGIN`。本地 Docker Web 已配置同源代理, 因此推荐正式配置写入 `.env` 时使用相对路径:

```env
VITE_FVS_INTEGRATION_MODE=iframe
VITE_FVS_URL=/webroot/decision/view/duchamp?viewlet=your-dashboard.fvs&page_number=1
VITE_FVS_TARGET_ORIGIN=
```

Web 容器会将 `/webroot/` 转发到 Docker Desktop 主机的 `http://host.docker.internal:8075/webroot/`。如果 iframe 区域无法显示 FVS, 优先检查 FVS 是否禁止 iframe 嵌入, 以及 `localhost:8075` 是否可访问。

## 常用验证

```powershell
docker compose ps
curl http://localhost:18080/api/health
```

问数 smoke:

```powershell
curl -Method POST http://localhost:18080/api/chat `
  -ContentType 'application/json' `
  -Body '{"session_id":"deploy-smoke","text":"当前党员学习完成率是多少?","context":{"mode":"text"}}'
```

期望返回 `type=answer`, 且 `speak_text` 包含 `87.5%`、`128人` 和 `112人`。

## 问数模式切换

V0.8 支持三种模式:

```env
ASK_METRICS_MODE=excel
ASK_METRICS_MODE=dora
ASK_METRICS_MODE=auto
```

- `excel`: 保持 V0.7 稳定演示, Excel Adapter 先匹配问数。
- `dora`: Excel Adapter 不抢答, 问数进入 Dora / Mock Dora。
- `auto`: 优先 Dora / Mock Dora, 请求失败或返回 `fallback` 时回退 Excel。

临时切换示例:

```powershell
$env:ASK_METRICS_MODE = 'auto'
docker compose up -d --force-recreate api
Remove-Item Env:\ASK_METRICS_MODE
```

## Dora 模式切换

默认保持 Mock:

```env
ENABLE_MOCK_DORA=true
```

临时验证真实 Dora:

```powershell
$env:ENABLE_MOCK_DORA = 'false'
docker compose up -d --force-recreate api
Remove-Item Env:\ENABLE_MOCK_DORA
```

验证完成后恢复 Mock:

```powershell
$env:ENABLE_MOCK_DORA = 'true'
docker compose up -d --force-recreate api
Remove-Item Env:\ENABLE_MOCK_DORA
```

真实 Dora 验证不需要前端持有 API Key; 所有 Dora 配置都只进入后端容器环境。

## 停止服务

```powershell
docker compose down
```

## 日志位置

目标路径:

```text
logs/
data/sessions.db
```
