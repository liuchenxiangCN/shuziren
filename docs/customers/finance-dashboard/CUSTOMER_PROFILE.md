# 企业财务综合驾驶舱 - 客户 Profile

## 场景概述

面向集团企业财务综合驾驶舱大屏的数字人交互场景。通过语音唤醒数字人"小财", 可以：
- 查询核心财务指标（收入、利润、成本、资产、现金流）
- 通过语音指令切换大屏页面（总览、财务指标、成本分析、预算执行）
- 进行连续追问和对话

## 快速启动

### 1. 配置 .env

将 `config/customers/finance-dashboard/customer.env.example` 中的配置合并到项目根目录 `.env`：

```bash
CUSTOMER_ID=finance-dashboard
CUSTOMER_NAME=XX集团
CUSTOMER_CONFIG_DIR=/app/config/customers/finance-dashboard
ASK_METRICS_MODE=excel

VITE_FVS_INTEGRATION_MODE=iframe
VITE_FVS_URL=/webroot/decision/view/duchamp?viewlet=%E9%9B%86%E5%9B%A2%E8%B4%A2%E5%8A%A1%E7%BB%BC%E5%90%88%E9%A9%BE%E9%A9%B6%E8%88%B1%2F%E9%9B%86%E5%9B%A2%E8%B4%A2%E5%8A%A1%E7%BB%BC%E5%90%88%E9%A9%BE%E9%A9%B6%E8%88%B1.fvs&page_number=1

# 真实 ASR/TTS（需要填入真实 API Key）
ENABLE_MOCK_ASR=false
ENABLE_MOCK_TTS=false
ASR_API_KEY=your_aliyun_asr_api_key
TTS_API_KEY=your_aliyun_tts_api_key

# Mock Dora 和 FVS（不需要真实后端）
ENABLE_MOCK_DORA=true
ENABLE_MOCK_FVS=true
```

### 2. 启动服务

```powershell
# 构建并启动
scripts/start-poc.ps1 -Build

# 或手动
docker compose up -d --build api web
```

### 3. 访问

- 数字人前端：http://localhost:18000
- 运维看板：http://localhost:18000/ops
- 后端 API：http://localhost:18080/api/health

### 4. 运行 Smoke 测试

```powershell
scripts/smoke-demo.ps1
```

## 演示话术

| 场景 | 话术 | 预期效果 |
|---|---|---|
| 唤醒 | "小财小财" | 进入 listening 状态，播报"您好。" |
| 领导欢迎 | "我是王总" | 返回财务欢迎语 |
| 收入查询 | "当前营业收入是多少？" | 返回营业收入数据 |
| 利润查询 | "净利润怎么样？" | 返回利润指标 |
| 成本查询 | "成本费用情况如何？" | 返回成本分析 |
| 资产查询 | "总资产和负债情况？" | 返回资产负债表 |
| 预算查询 | "预算执行进度？" | 返回预算执行情况 |
| 切换页面 | "切换到财务指标页面" | 大屏切换到财务指标页 |
| 返回首页 | "返回总览" | 大屏切换回总览 |

## 问数 Excel 数据

问数数据位于 `docs/demo_data/ask_metrics/finance/`，包含：

| 文件 | 内容 |
|---|---|
| `finance_overview_metrics_2026.xlsx` | Dashboard: 营收、利润、资产、现金流；板块明细: 各业务板块数据 |
| `finance_cost_metrics_2026.xlsx` | Dashboard: 成本费用；费用类别: 分类明细 |
| `finance_budget_metrics_2026.xlsx` | Dashboard: 预算执行；预算明细: 各项目预算明细 |

所有数据均为脱敏演示数据，可按实际需要替换。

## FVS 大屏

- FVS 地址：`http://localhost:8075/webroot/decision/view/duchamp?viewlet=集团财务综合驾驶舱/集团财务综合驾驶舱.fvs`
- 通过 nginx 同源代理 `/webroot/` → `http://host.docker.internal:8075/webroot/` 解决 iframe 跨域
- 页面映射：page_number=1(总览)、2(财务指标)、3(成本分析)、4(预算执行)
- 大屏切换通过 `action_id` 白名单 + URL 参数 `page_number` 实现

## Mock 说明

| 组件 | 模式 | 说明 |
|---|---|---|
| Dora Agent | Mock | 通过 `demo-cases.yaml` 关键词匹配返回预设回答 |
| 知识库/RAGFlow | Mock | 不启用真实 RAGFlow，知识问答走 Mock Dora |
| 问数 | Mock (Excel) | 通过 `excel` 模式读取本地 Excel 文件 |
| 大屏控制 | Mock | 通过 `action_id` + URL 参数切换 FVS 页面 |
| ASR | 真实 | 使用阿里云百炼 Paraformer 实时语音识别 |
| TTS | 真实 | 使用阿里云百炼 CosyVoice 语音合成 |
