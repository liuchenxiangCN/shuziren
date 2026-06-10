# 本地部署说明

本文档记录本地开发部署方式。当前尚未创建代码工程, 以下为目标形态。

## 前置准备

- Windows 10 / 11。
- Docker Desktop。
- WSL2。
- Node.js 和 Python 可由 Docker 镜像提供, 本机不强依赖。
- 如需非 Docker 本地开发, 前端使用 pnpm, 后端使用 uv + Python 3.11/3.12。
- Dora API Key。
- 国产 ASR / TTS API Key。
- FVS 看板访问地址。
- 测试知识库文档。
- 测试问数数据。

## 推荐端口

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| digital-human-web | 18000 | 前端 |
| digital-human-api | 18080 | 后端 |
| reverse-proxy HTTP | 18081 | 代理 |
| reverse-proxy HTTPS | 18443 | HTTPS 入口 |
| RAGFlow Web | 9380 | 知识库页面 |
| RAGFlow MCP | 9382 | MCP Server |

## 目标启动流程

```powershell
git clone <repo> zt-digital-human
cd zt-digital-human

Copy-Item .env.example .env
# 修改 .env

docker compose up -d --build
```

访问:

```text
http://localhost:18000
http://localhost:18080/api/health
```

## RAGFlow 启动策略

主项目不建议直接内嵌 RAGFlow 官方完整 compose。建议:

- 主项目 compose 只放数字人前端、后端和反向代理。
- RAGFlow 使用官方 Docker Compose 独立部署。
- Dora 需要访问 RAGFlow MCP 时, 根据网络情况选择内网 IP、隧道或部署到 Dora 可访问服务器。

## 本地麦克风注意事项

浏览器麦克风权限通常要求 HTTPS 或 localhost。开发阶段优先使用 `localhost`; POC 演示时再配置 HTTPS 入口。

## 常用验证

```powershell
docker compose ps
curl http://localhost:18080/api/health
```

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
