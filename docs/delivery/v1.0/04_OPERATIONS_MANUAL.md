# V1.0 运维手册

## 运维入口

Web:

```text
http://localhost:18000
```

Ops:

```text
http://localhost:18000/ops
```

API Health:

```text
http://localhost:18080/api/health
```

## 常用脚本

所有脚本从仓库根目录执行:

```powershell
Set-Location D:\Project\shuziren
```

| 脚本 | 用途 |
| --- | --- |
| `scripts\check-poc.ps1` | 预检 Docker、端口、配置、API、Web、Ops 依赖和 RAGFlow |
| `scripts\start-poc.ps1` | 启动 API / Web |
| `scripts\stop-poc.ps1` | 停止 API / Web |
| `scripts\smoke-demo.ps1` | 固定演示问题集 smoke |
| `scripts\export-logs.ps1` | 导出脱敏日志包 |

## 启动

首次启动:

```powershell
Copy-Item .env.example .env
scripts\check-poc.ps1
scripts\start-poc.ps1 -Build
```

演示稳态启动:

```powershell
scripts\start-poc.ps1 -Build -DemoStable
```

启动并尝试拉起本机 RAGFlow:

```powershell
scripts\start-poc.ps1 -Build -WithRagflow
```

## 停止

```powershell
scripts\stop-poc.ps1
```

如需停止独立 RAGFlow:

```powershell
Set-Location D:\Project\ragflow\docker
docker compose -f docker-compose.yml --profile cpu --profile elasticsearch down
```

## 预检

基础预检:

```powershell
scripts\check-poc.ps1
```

要求 API / Web 已启动:

```powershell
scripts\check-poc.ps1 -RequireServices
```

跳过外部依赖探测:

```powershell
scripts\check-poc.ps1 -SkipExternal
```

输出 JSON:

```powershell
scripts\check-poc.ps1 -RequireServices -SkipExternal -Json
```

预检结果说明:

| 状态 | 含义 |
| --- | --- |
| `ok` | 检查通过 |
| `warning` | 可继续演示, 但存在需关注项 |
| `error` | 需修复后再验收 |
| `skipped` | 本次检查跳过 |

## Smoke

```powershell
scripts\smoke-demo.ps1 -ExecuteScreenActions
```

脚本会验证:

- 张书记欢迎语。
- 入党流程知识库问答。
- 学习完成率问数。
- 成品库存控屏。
- 返回总览控屏。

输出目录:

```text
logs/smoke/
```

## 日志导出

```powershell
scripts\export-logs.ps1 -Zip
```

输出目录:

```text
logs/exports/
```

默认内容:

- Ops Markdown 摘要。
- Ops Health / Dependencies / Sessions / Errors / Metrics JSON。
- Demo Config JSON。
- Docker Compose 状态。

默认不包含 Docker 原生日志。如现场明确需要:

```powershell
scripts\export-logs.ps1 -IncludeDockerLogs -Zip
```

注意: Docker 原生日志可能包含第三方库输出, 导出前应确认客户数据和合规要求。

## Ops 看板

访问:

```text
http://localhost:18000/ops
```

可查看:

- 系统状态。
- 依赖状态。
- 最近会话。
- 错误列表。
- 耗时指标。
- 日志导出入口。

依赖项:

| 依赖 | 说明 |
| --- | --- |
| SQLite 会话日志 | `data/sessions.db` 是否可读写 |
| Screen Actions | 动作白名单是否加载 |
| Dora | Agent 配置和连通性 |
| RAGFlow | RAGFlow API / MCP 配置和连通性 |
| ASR | Mock 或真实 ASR 配置就绪 |
| TTS | Mock 或真实 TTS 配置就绪 |
| FVS | Mock 或 iframe URL 配置状态 |

Ops 接口和导出内容会截断摘要并脱敏常见 Key / Token / Bearer / `sk-*` / `ak-*` 模式。

## 故障排查

| 现象 | 检查 | 处理 |
| --- | --- | --- |
| Web 打不开 | `docker compose ps`, 18000 端口 | 重启 `scripts\start-poc.ps1`; 检查端口占用 |
| API 不健康 | `/api/health`, 容器日志 | 检查 `.env`, 重启 API |
| Dora 超时 | Ops 依赖、网络、`DORA_BASE_URL`、Key | 确认 Dora 地址和权限; 演示可临时启用 `DEMO_STABLE_MODE` |
| RAGFlow 探测失败 | `http://127.0.0.1:18089/api/v1/system/healthz` | 启动 RAGFlow; 确认 Dora 可访问 MCP 地址 |
| 问数无结果 | `ASK_METRICS_MODE`, Excel 文件目录 | 检查 `docs/demo_data/ask_metrics` 和客户 `ask-metrics.yaml` |
| ASR 无法识别 | 浏览器麦克风权限、ASR Key、网络 | 允许麦克风; 临时启用 `ENABLE_MOCK_ASR=true` |
| TTS 不播报 | 浏览器自动播放、TTS Key、音量 | 手动播放; 检查 `TTS_STREAMING_ENABLED` 和音箱 |
| FVS 空白 | FVS URL、X-Frame-Options、同源代理 | 使用 `/webroot/` 相对路径或调整 FVS iframe 策略 |
| 控屏失败 | `action_id` 是否在白名单 | 修改 `screen-actions.yaml`, 重新启动服务 |
| Ops 暴露范围 | `/ops` 未鉴权 | 本地内网使用; 正式交付需增加反向代理鉴权或访问控制 |

## 变更流程

1. 修改 `.env` 或 `config/customers/zt-securities/*.yaml`。
2. 运行 `scripts\check-poc.ps1 -SkipExternal`。
3. 重启服务。
4. 运行 `scripts\smoke-demo.ps1`。
5. 导出日志包。
6. 在 `docs/DEV_LOG.md` 和 `docs/CHANGELOG.md` 记录变更。

## 安全规则

- 不在前端配置 API Key。
- 不把 `.env` 提交到 Git。
- 不执行模型生成的 SQL、Python、JavaScript 或 shell。
- 控屏只执行后端白名单允许的 `action_id`。
- 日志包默认使用脱敏 Ops 导出。
