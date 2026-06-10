# 客户移交说明

本文档面向客户或后续交付团队, 用于解释系统能力、部署方式、当前限制和后续建议。

## 系统能力

本系统提供党建大屏语音交互能力:

- 语音唤醒。
- 中文 ASR 识别。
- Dora Agent 问答和问数。
- RAGFlow 知识库问答。
- 大屏动作白名单控制。
- TTS 语音播报。
- 字幕、状态动效、回复窗口。
- 会话日志和耗时记录。

## 部署方式

目标部署方式:

- 本地 Windows + Docker Desktop + WSL2。
- 数字人前端和后端由本项目 Docker Compose 启动。
- RAGFlow 建议使用官方 Docker Compose 独立部署。
- Dora、ASR、TTS 使用客户确认的外部服务。
- FVS 使用客户现有大屏地址或现场集成方式。

## 启动命令

```powershell
Copy-Item .env.example .env
docker compose up -d --build
```

访问:

```text
http://localhost:18000
http://localhost:18080/api/health
```

## 停止命令

```powershell
docker compose down
```

## 日志位置

目标路径:

```text
logs/
data/sessions.db
```

## 外部依赖

- Dora 平台。
- RAGFlow。
- FVS 看板。
- 国产 ASR。
- 国产 TTS。
- 网络连通和 API Key。

## 安全边界

- 大模型不得直接输出并执行 JavaScript。
- 大屏控制只允许使用白名单 `action_id`。
- 后端负责校验动作合法性。
- 前端不保存或暴露 API Key。
- 生产或正式 POC 前需确认云模型、数据范围、脱敏策略和合规边界。

## 当前限制

- 当前阶段尚未实现代码工程。
- 第一版将优先使用 Mock 模式。
- 语义唤醒不是严格本地 KWS。
- RAGFlow 检索质量需要结合真实文档调优。
- FVS 真实控制方式需等待现场接口确认。
- 问数口径需要客户确认数据源和指标定义。

## 常见问题

### Dora 无法访问本地 RAGFlow MCP

本地 `localhost` 对 Dora 服务器不可见。可选方案:

- 使用 Windows 局域网 IP。
- 使用 FRP / Cloudflare Tunnel / ngrok。
- 将 RAGFlow 部署到 Dora 可访问的服务器。

### FVS 不能 iframe 嵌入

需要改为 FVS 内嵌数字人全局浮层, 或调整 FVS 的嵌入策略。

### 大屏控制失败

优先检查:

- `action_id` 是否在白名单中。
- FVS Adapter 是否已预埋。
- 是否存在跨域或 iframe 通信限制。

## 后续建议

- 先完成 V0.1 Mock 闭环。
- 再逐个接入 Dora、TTS、ASR、RAGFlow、FVS。
- POC 前准备稳定演示脚本和测试报告。
- 正式上线前进行合规、安全、网络和运维评审。

