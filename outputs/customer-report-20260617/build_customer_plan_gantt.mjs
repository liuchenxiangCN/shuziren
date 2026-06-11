import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const outputDir = "D:/Project/shuziren/outputs/customer-report-20260617";
const outputPath = path.join(outputDir, "zt_project_plan_gantt_20260610_0630.xlsx");

const reportDate = new Date(2026, 5, 17);
const projectStart = new Date(2026, 5, 10);
const projectEnd = new Date(2026, 5, 30);
const holidaySet = new Set([
  "2026-06-13",
  "2026-06-14",
  "2026-06-19",
  "2026-06-20",
  "2026-06-21",
  "2026-06-27",
  "2026-06-28",
]);

const colors = {
  navy: "#17324D",
  blue: "#2F75B5",
  paleBlue: "#D9EAF7",
  teal: "#0F766E",
  green: "#D9EAD3",
  greenDark: "#6AA84F",
  amber: "#F9CB9C",
  amberDark: "#E69138",
  red: "#C00000",
  redSoft: "#F4CCCC",
  gray: "#D9D9D9",
  grayDark: "#666666",
  graySoft: "#F3F6F8",
  white: "#FFFFFF",
  text: "#1F2933",
  border: "#B7C9D6",
  holiday: "#E7E6E6",
  milestone: "#7030A0",
};

function iso(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function cnDate(d) {
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function addDays(d, days) {
  const next = new Date(d);
  next.setDate(next.getDate() + days);
  return next;
}

function dateRange(start, end) {
  const out = [];
  for (let d = new Date(start); d <= end; d = addDays(d, 1)) {
    out.push(new Date(d));
  }
  return out;
}

function isHoliday(d) {
  return holidaySet.has(iso(d));
}

function workdaysBetween(start, end) {
  return dateRange(start, end).filter((d) => !isHoliday(d)).length;
}

function overlapsDay(task, day) {
  const dayIso = iso(day);
  return task.startIso <= dayIso && dayIso <= task.endIso;
}

function dayOfWeekCn(d) {
  return ["日", "一", "二", "三", "四", "五", "六"][d.getDay()];
}

function colName(indexOneBased) {
  let n = indexOneBased;
  let name = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    name = String.fromCharCode(65 + rem) + name;
    n = Math.floor((n - 1) / 26);
  }
  return name;
}

function dateFromIso(value) {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
}

const tasks = [
  {
    wbs: "1.1",
    phase: "启动与方案",
    task: "项目启动、范围确认与客户汇报口径梳理",
    type: "管理",
    desc: "明确党建大屏数字人 POC 目标、边界、演示路径和阶段汇报口径。",
    deliverable: "项目启动记录、范围边界、汇报口径",
    startIso: "2026-06-10",
    endIso: "2026-06-10",
    status: "已完成",
    progress: 1,
    acceptance: "核心链路范围、阶段目标和汇报口径确认完成。",
    note: "作为 6/10 启动基线。",
  },
  {
    wbs: "1.2",
    phase: "启动与方案",
    task: "总体技术方案与系统架构设计",
    type: "设计",
    desc: "梳理前端、Gateway、Dora、ASR/TTS、FVS、RAGFlow 的 Adapter 化架构。",
    deliverable: "技术方案、架构边界、安全约束",
    startIso: "2026-06-10",
    endIso: "2026-06-11",
    status: "已完成",
    progress: 1,
    acceptance: "形成可复用本地 POC 架构, 明确 Mock 开关和白名单控制。",
    note: "不在前端暴露密钥, 控屏只走 action_id。",
  },
  {
    wbs: "2.1",
    phase: "核心链路",
    task: "前后端基础链路与会话日志联调",
    type: "开发/联调",
    desc: "完成前端交互、后端 Gateway、会话日志、演示状态和基础问答链路联调。",
    deliverable: "可访问前端、后端 API、会话日志",
    startIso: "2026-06-10",
    endIso: "2026-06-12",
    status: "已完成",
    progress: 1,
    acceptance: "文本问题可进入后端, 返回标准 answer / screen_control / fallback。",
    note: "覆盖本地 POC 主入口。",
  },
  {
    wbs: "2.2",
    phase: "核心链路",
    task: "Mock Dora / ASR / TTS / FVS 链路联调",
    type: "开发/联调",
    desc: "保留外部系统 Mock 开关, 跑通语音识别、对话、播报和大屏动作模拟链路。",
    deliverable: "Mock 全链路联调结果",
    startIso: "2026-06-11",
    endIso: "2026-06-15",
    status: "已完成",
    progress: 1,
    acceptance: "Mock 链路可完成端到端流程验证, 外部依赖异常不影响演示底座。",
    note: "6/13、6/14 仅保留风险响应。",
  },
  {
    wbs: "2.3",
    phase: "核心链路",
    task: "本地知识库样例与 RAGFlow MCP 基础验证",
    type: "联调",
    desc: "准备样例知识资料, 验证 RAGFlow dataset、MCP 检索和 Dora 调用边界。",
    deliverable: "样例知识库、MCP 检索验证记录",
    startIso: "2026-06-12",
    endIso: "2026-06-16",
    status: "已完成",
    progress: 1,
    acceptance: "样例资料可检索, Dora 可基于知识库片段生成回答。",
    note: "为后续真实知识库专项预留接口经验。",
  },
  {
    wbs: "2.4",
    phase: "核心链路",
    task: "大屏控制白名单与 FVS 页面联动验证",
    type: "联调",
    desc: "通过 action_id 白名单校验后触发 FVS iframe 页面切换, 验证控屏安全路径。",
    deliverable: "控屏动作白名单、FVS 联动验证",
    startIso: "2026-06-15",
    endIso: "2026-06-17",
    status: "已完成",
    progress: 1,
    acceptance: "语音/文本指令可触发白名单动作, 非法动作被拒绝。",
    note: "不执行模型生成 JavaScript。",
  },
  {
    wbs: "2.5",
    phase: "阶段汇报",
    task: "端到端演示脚本、日志和阶段性材料整理",
    type: "交付",
    desc: "整理截至 6/17 的阶段汇报材料、验收口径、演示脚本和待完成专项。",
    deliverable: "客户阶段汇报材料",
    startIso: "2026-06-16",
    endIso: "2026-06-17",
    status: "已完成",
    progress: 1,
    acceptance: "明确已完成 Mock 链路联调与端到端流程验证, 真实外部系统接入进入专项实施阶段。",
    note: "本工作簿即为阶段汇报附件。",
  },
  {
    wbs: "3.1",
    phase: "新增专项",
    task: "自定义新闻爬虫需求细化与新闻源白名单确认",
    type: "需求/设计",
    desc: "确认人员检索字段、新闻源范围、采集频率、合规边界和本地存储格式。",
    deliverable: "新闻源白名单、爬虫字段和验收标准",
    startIso: "2026-06-18",
    endIso: "2026-06-18",
    status: "计划中",
    progress: 0,
    acceptance: "前端可选择/输入人员, 后端只访问客户确认的新闻源白名单。",
    note: "指定新闻网站暂未确定, 先按可配置白名单设计。",
  },
  {
    wbs: "3.2",
    phase: "新增专项",
    task: "人员新闻采集模块开发",
    type: "开发",
    desc: "后端按人员名称和新闻源检索相关新闻, 支持抓取、去重、来源 URL、发布时间和失败重试。",
    deliverable: "自定义爬虫服务、采集结果结构",
    startIso: "2026-06-18",
    endIso: "2026-06-22",
    status: "计划中",
    progress: 0,
    acceptance: "输入指定人员后可从白名单新闻源采集相关公开新闻。",
    note: "6/19-6/21 仅风险响应/问题跟进。",
  },
  {
    wbs: "3.3",
    phase: "新增专项",
    task: "人员信息整理、摘要与结构化",
    type: "开发",
    desc: "对采集内容进行清洗、去重、摘要、人物关联判定和来源保留, 形成可入库文档。",
    deliverable: "结构化人员资料、Markdown/JSON 入库文档",
    startIso: "2026-06-22",
    endIso: "2026-06-23",
    status: "计划中",
    progress: 0,
    acceptance: "每条信息保留标题、来源、URL、发布时间、摘要和可信度说明。",
    note: "避免无来源摘要直接入库。",
  },
  {
    wbs: "3.4",
    phase: "新增专项",
    task: "本地 RAGFlow 知识库导入适配",
    type: "开发/联调",
    desc: "将整理后资料保存到本地 RAGFlow dataset, 支持上传、解析状态检查、失败重试和导入日志。",
    deliverable: "RAGFlow 导入 Adapter、导入日志",
    startIso: "2026-06-23",
    endIso: "2026-06-24",
    status: "计划中",
    progress: 0,
    acceptance: "指定人员资料可写入本地 RAGFlow 知识库并完成解析。",
    note: "为后续 RAGFlow MCP 调用做数据准备。",
  },
  {
    wbs: "3.5",
    phase: "新增专项",
    task: "新闻爬虫到知识库导入闭环联调",
    type: "联调",
    desc: "串联前端指定人员、后端采集、资料整理、RAGFlow 导入和状态反馈。",
    deliverable: "爬虫->整理->入库闭环演示",
    startIso: "2026-06-24",
    endIso: "2026-06-25",
    status: "计划中",
    progress: 0,
    acceptance: "完成至少 1 名指定人员的新闻采集、整理、入库和可追溯验证。",
    note: "完成后进入知识库调用专项。",
  },
  {
    wbs: "4.1",
    phase: "RAGFlow 调用",
    task: "RAGFlow 知识库 MCP 调用专项联调",
    type: "开发/联调",
    desc: "打通 Dora / Gateway 调用本地 RAGFlow 知识库, 验证新增人员资料可被检索和回答。",
    deliverable: "MCP 调用联调记录、知识库问答样例",
    startIso: "2026-06-24",
    endIso: "2026-06-26",
    status: "计划中",
    progress: 0,
    acceptance: "围绕指定人员提问时, 回答能引用新增新闻资料和来源。",
    note: "对应客户关心的 RAGFlow 知识库调用能力。",
  },
  {
    wbs: "4.2",
    phase: "RAGFlow 调用",
    task: "前端知识库导入和查询状态展示",
    type: "开发",
    desc: "前端展示采集进度、导入状态、解析结果和可查询状态, 支持失败提示和重试入口。",
    deliverable: "前端状态页/面板",
    startIso: "2026-06-25",
    endIso: "2026-06-26",
    status: "计划中",
    progress: 0,
    acceptance: "用户可看到指定人员资料从采集到可问答的状态闭环。",
    note: "不在前端暴露 RAGFlow API Key。",
  },
  {
    wbs: "5.1",
    phase: "优化专项",
    task: "性能优化专项",
    type: "优化",
    desc: "优化爬虫并发、RAGFlow 导入轮询、检索返回量、Dora 等待时间、TTS 首响和缓存策略。",
    deliverable: "性能优化清单、耗时对比",
    startIso: "2026-06-25",
    endIso: "2026-06-29",
    status: "计划中",
    progress: 0,
    acceptance: "关键链路耗时有记录, 演示等待体验可控, 超时有兜底提示。",
    note: "6/27-6/28 仅风险响应/问题跟进。",
  },
  {
    wbs: "5.2",
    phase: "优化专项",
    task: "安全优化专项",
    type: "优化",
    desc: "补充新闻源白名单、URL 校验、频控、脱敏、密钥边界、日志清洗和导入内容安全检查。",
    deliverable: "安全优化清单、安全验证记录",
    startIso: "2026-06-25",
    endIso: "2026-06-29",
    status: "计划中",
    progress: 0,
    acceptance: "不访问非白名单站点, 不暴露密钥, 日志和导出内容完成脱敏。",
    note: "覆盖爬虫、知识库、运维日志和前端展示。",
  },
  {
    wbs: "6.1",
    phase: "测试验收",
    task: "系统联调、回归测试和验收问题修复",
    type: "测试",
    desc: "围绕语音唤醒、人员新闻采集、知识库导入、RAGFlow 调用、控屏、播报做回归。",
    deliverable: "测试记录、问题修复清单",
    startIso: "2026-06-29",
    endIso: "2026-06-30",
    status: "计划中",
    progress: 0,
    acceptance: "核心演示路径、异常兜底和日志记录通过验收测试。",
    note: "作为上线前验收依据。",
  },
  {
    wbs: "6.2",
    phase: "上线",
    task: "完成测试验收并上线",
    type: "里程碑",
    desc: "完成客户验收、上线确认、交付物归档和后续运维交接。",
    deliverable: "验收确认、上线记录",
    startIso: "2026-06-30",
    endIso: "2026-06-30",
    status: "计划中",
    progress: 0,
    acceptance: "2026-06-30 完成测试验收并上线。",
    note: "目标完成节点。",
  },
].map((task) => ({
  ...task,
  start: dateFromIso(task.startIso),
  end: dateFromIso(task.endIso),
  workdays: workdaysBetween(dateFromIso(task.startIso), dateFromIso(task.endIso)),
}));

const riskRows = [
  ["R-新增-001", "指定新闻网站暂未确定", "爬虫范围和解析策略可能变化", "6/18 先确认客户新闻源白名单; 支持配置化新闻源; 未确认前保留人工导入兜底", "Open"],
  ["R-新增-002", "公开新闻采集合规和版权边界", "未经授权采集或过度抓取可能带来合规风险", "只采集公开页面; 遵守网站规则; 限频; 记录 URL 和来源; 不抓取登录态/付费/敏感内容", "Open"],
  ["R-新增-003", "人员同名导致资料混淆", "知识库回答可能引用错误人员信息", "增加职务、单位、关键词约束; 低置信度资料进入待确认状态; 回答保留来源", "Open"],
  ["R-新增-004", "RAGFlow 导入解析失败或耗时不稳定", "新增资料无法及时用于问答", "导入后轮询解析状态; 失败重试; 保留导入日志; 支持小批量导入", "Open"],
  ["R-新增-005", "知识库调用延迟和答案质量波动", "影响现场演示体验", "控制检索返回量; 设置超时和兜底; 记录耗时; 优化 chunk 与相似度阈值", "Open"],
  ["R-新增-006", "爬虫入口被滥用或 SSRF", "安全风险", "后端校验 URL; 只允许新闻源白名单; 禁止访问内网地址; 增加频控和日志审计", "Open"],
];

const milestones = [
  ["M1", "项目启动", new Date(2026, 5, 10), "完成项目范围和阶段汇报口径确认"],
  ["M2", "阶段性进展汇报", new Date(2026, 5, 17), "已完成 Mock 链路联调与端到端流程验证"],
  ["M3", "自定义新闻爬虫方案确认", new Date(2026, 5, 18), "确认新闻源白名单、采集字段、合规边界"],
  ["M4", "爬虫到 RAGFlow 入库闭环", new Date(2026, 5, 25), "完成指定人员新闻采集、整理、导入验证"],
  ["M5", "RAGFlow 知识库调用联调完成", new Date(2026, 5, 26), "新增人员资料可通过知识库问答检索"],
  ["M6", "上线验收", new Date(2026, 5, 30), "完成测试验收并上线"],
];

const calendarDays = dateRange(projectStart, projectEnd);
const workingDays = calendarDays.filter((d) => !isHoliday(d));
const completedWorkdays = workingDays.filter((d) => d <= reportDate);
const futureWorkdays = workingDays.filter((d) => d > reportDate);
const completedTasks = tasks.filter((t) => t.status === "已完成").length;
const projectProgress = completedWorkdays.length / workingDays.length;

const workbook = Workbook.create();

function setupSheet(sheet) {
  sheet.showGridLines = false;
}

function setColWidths(sheet, widths) {
  widths.forEach((width, idx) => {
    sheet.getRange(`${colName(idx + 1)}:${colName(idx + 1)}`).format.columnWidthPx = width;
  });
}

function styleTitle(sheet, range, title) {
  const r = sheet.getRange(range);
  r.merge();
  r.values = [[title]];
  r.format = {
    fill: colors.navy,
    font: { bold: true, color: colors.white, size: 16 },
    horizontalAlignment: "center",
    verticalAlignment: "center",
  };
  r.format.rowHeightPx = 36;
}

function styleSection(sheet, range, title) {
  const r = sheet.getRange(range);
  r.merge();
  r.values = [[title]];
  r.format = {
    fill: colors.paleBlue,
    font: { bold: true, color: colors.navy, size: 12 },
    horizontalAlignment: "left",
    verticalAlignment: "center",
    borders: { preset: "outside", style: "thin", color: colors.border },
  };
  r.format.rowHeightPx = 24;
}

function styleHeader(range, fill = colors.blue) {
  range.format = {
    fill,
    font: { bold: true, color: colors.white },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: colors.border },
  };
}

function styleBody(range) {
  range.format = {
    fill: colors.white,
    font: { color: colors.text },
    verticalAlignment: "top",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#DDE6ED" },
  };
}

function writeRows(sheet, startCell, rows) {
  sheet.getRange(startCell).write(rows);
}

const summary = workbook.worksheets.add("客户汇报摘要");
setupSheet(summary);
setColWidths(summary, [145, 105, 70, 210, 28, 180, 120, 160, 160, 160, 160, 160]);
styleTitle(summary, "A1:L1", "中天证券党建大屏数字人 POC 项目进度计划与实施甘特图");
summary.getRange("A2:L2").merge();
summary.getRange("A2:L2").values = [["汇报口径日期：2026-06-17｜计划周期：2026-06-10 至 2026-06-30｜目标：完成测试验收并上线"]];
summary.getRange("A2:L2").format = {
  fill: colors.graySoft,
  font: { color: colors.text, bold: true },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};

styleSection(summary, "A4:L4", "一、客户汇报摘要");
const summaryText = [
  ["阶段结论", "截至 2026-06-17, 项目按计划完成 Mock 链路联调与端到端流程验证, 真实外部系统接入进入专项实施阶段。"],
  ["已完成重点", "完成项目启动、总体方案、前后端基础链路、Mock Dora/ASR/TTS/FVS 联调、本地知识库样例验证、大屏白名单控制与 FVS 联动验证、阶段材料整理。"],
  ["后续关键专项", "1. 自定义新闻爬虫及导入知识库; 2. RAGFlow 知识库调用; 3. 性能优化; 4. 安全优化。"],
  ["新增需求范围", "前端根据用户指定人员发起请求, 后端按客户确认的新闻源白名单采集公开新闻, 清洗整理后保存到本地 RAGFlow 知识库, 并衔接后续 RAGFlow MCP 问答能力。"],
  ["非工作日安排", "6/13、6/14、6/19、6/20、6/21、6/27、6/28 不安排正式开发, 仅保留风险响应/问题跟进。"],
  ["上线目标", "2026-06-30 完成测试验收并上线。"],
];
summary.getRange("A5:A10").values = summaryText.map((r) => [r[0]]);
summary.getRange("A5:A10").format = {
  fill: colors.paleBlue,
  font: { bold: true, color: colors.navy },
  horizontalAlignment: "center",
  verticalAlignment: "top",
  borders: { preset: "all", style: "thin", color: colors.border },
};
summary.getRange("B5:L10").merge(true);
summary.getRange("B5:B10").values = summaryText.map((r) => [r[1]]);
summary.getRange("B5:L10").format = {
  fill: colors.white,
  font: { color: colors.text },
  verticalAlignment: "top",
  wrapText: true,
  borders: { preset: "all", style: "thin", color: "#DDE6ED" },
};
summary.getRange("A5:L10").format.rowHeightPx = 44;

styleSection(summary, "A12:L12", "二、关键进度指标");
const kpiRows = [
  ["计划工作日", workingDays.length, "天", "剔除指定非工作日"],
  ["截至 6/17 已投入工作日", completedWorkdays.length, "天", "6/10、6/11、6/12、6/15、6/16、6/17"],
  ["后续剩余工作日", futureWorkdays.length, "天", "6/18、6/22-6/26、6/29-6/30"],
  ["阶段性工作日进度", projectProgress, "", "按工作日口径计算"],
  ["任务总数", tasks.length, "项", "含管理、开发、联调、测试、上线"],
  ["截至 6/17 已完成任务", completedTasks, "项", "已完成项均集中在核心链路和阶段汇报"],
];
summary.getRange("A13:D19").values = [["指标", "数值", "单位", "说明"], ...kpiRows];
styleHeader(summary.getRange("A13:D13"), colors.teal);
styleBody(summary.getRange("A14:D19"));
summary.getRange("B17:B17").format.numberFormat = "0.0%";
summary.getRange("B14:B19").format = {
  font: { bold: true, color: colors.navy },
  horizontalAlignment: "center",
  borders: { preset: "all", style: "thin", color: "#DDE6ED" },
};

summary.getRange("F13:L13").merge();
summary.getRange("F13:L13").values = [["待完成专项及验收目标"]];
styleHeader(summary.getRange("F13:L13"), colors.teal);
const remainingRows = [
  ["自定义爬虫及导入知识库", "6/18-6/25", "按指定人员和新闻源白名单采集公开新闻, 整理后导入本地 RAGFlow。"],
  ["RAGFlow 知识库调用", "6/24-6/26", "新增人员资料可被 MCP 检索并在回答中保留来源。"],
  ["性能优化", "6/25-6/29", "优化采集、导入、检索、首响和超时兜底。"],
  ["安全优化", "6/25-6/29", "新闻源白名单、URL 校验、限频、脱敏、密钥和日志安全。"],
  ["测试验收上线", "6/29-6/30", "完成回归、问题修复、验收确认和上线。"],
];
summary.getRange("F14:G14").values = [["专项", "计划时间"]];
summary.getRange("H14:L14").merge();
summary.getRange("H14:H14").values = [["验收目标"]];
styleHeader(summary.getRange("F14:L14"), colors.blue);
summary.getRange("F15:G19").values = remainingRows.map((r) => [r[0], r[1]]);
summary.getRange("H15:L19").merge(true);
summary.getRange("H15:H19").values = remainingRows.map((r) => [r[2]]);
styleBody(summary.getRange("F15:L19"));
summary.getRange("F15:F19").format = {
  fill: colors.paleBlue,
  font: { bold: true, color: colors.navy },
  wrapText: true,
  borders: { preset: "all", style: "thin", color: "#DDE6ED" },
};

styleSection(summary, "A20:L20", "三、每日计划投入强度");
const dailyCounts = calendarDays.map((d) => {
  const count = tasks.filter((t) => overlapsDay(t, d) && !isHoliday(d)).length;
  return [cnDate(d), isHoliday(d) ? 0 : count];
});
summary.getRange("A21:B42").values = [["日期", "并行任务数"], ...dailyCounts];
styleHeader(summary.getRange("A21:B21"), colors.blue);
styleBody(summary.getRange("A22:B42"));
const chart = summary.charts.add("bar", summary.getRange("A21:B42"));
chart.title = "6/10-6/30 每日计划投入强度";
chart.hasLegend = false;
chart.xAxis = { axisType: "textAxis" };
chart.yAxis = { numberFormatCode: "0" };
chart.setPosition("D21", "L42");

const plan = workbook.worksheets.add("实施计划");
setupSheet(plan);
setColWidths(plan, [58, 105, 250, 86, 260, 190, 92, 92, 80, 95, 80, 260, 210]);
styleTitle(plan, "A1:M1", "项目实施计划表");
plan.getRange("A2:M2").merge();
plan.getRange("A2:M2").values = [["说明：本表为客户汇报用计划口径, 不设置负责人列; 日期从 2026-06-10 至 2026-06-30, 指定非工作日仅保留风险响应/问题跟进。"]];
plan.getRange("A2:M2").format = {
  fill: colors.graySoft,
  font: { color: colors.text, bold: true },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
const planHeaders = ["WBS", "阶段", "任务名称", "任务类型", "工作内容", "交付物", "开始日期", "结束日期", "工作日", "状态", "进度", "验收/完成标准", "备注"];
plan.getRange("A4:M4").values = [planHeaders];
styleHeader(plan.getRange("A4:M4"));
const planRows = tasks.map((t) => [
  t.wbs,
  t.phase,
  t.task,
  t.type,
  t.desc,
  t.deliverable,
  t.start,
  t.end,
  t.workdays,
  t.status,
  t.progress,
  t.acceptance,
  t.note,
]);
plan.getRange(`A5:M${4 + planRows.length}`).values = planRows;
styleBody(plan.getRange(`A5:M${4 + planRows.length}`));
plan.getRange(`G5:H${4 + planRows.length}`).setNumberFormat("yyyy-mm-dd");
plan.getRange(`I5:I${4 + planRows.length}`).format.numberFormat = "0";
plan.getRange(`K5:K${4 + planRows.length}`).format.numberFormat = "0%";
plan.getRange(`A5:A${4 + planRows.length}`).format.horizontalAlignment = "center";
plan.getRange(`G5:K${4 + planRows.length}`).format.horizontalAlignment = "center";
for (let i = 0; i < tasks.length; i++) {
  const row = 5 + i;
  const task = tasks[i];
  const rowRange = plan.getRange(`A${row}:M${row}`);
  rowRange.format.rowHeightPx = 52;
  if (task.status === "已完成") {
    plan.getRange(`J${row}:K${row}`).format = {
      fill: colors.green,
      font: { bold: true, color: "#274E13" },
      horizontalAlignment: "center",
      borders: { preset: "all", style: "thin", color: "#DDE6ED" },
    };
  } else if (task.type === "里程碑") {
    plan.getRange(`J${row}:K${row}`).format = {
      fill: "#EADCF8",
      font: { bold: true, color: colors.milestone },
      horizontalAlignment: "center",
      borders: { preset: "all", style: "thin", color: "#DDE6ED" },
    };
  } else {
    plan.getRange(`J${row}:K${row}`).format = {
      fill: colors.amber,
      font: { bold: true, color: "#7F3F00" },
      horizontalAlignment: "center",
      borders: { preset: "all", style: "thin", color: "#DDE6ED" },
    };
  }
}
plan.freezePanes.freezeRows(4);
plan.getRange(`K5:K${4 + planRows.length}`).format.numberFormat = "0%";

const gantt = workbook.worksheets.add("甘特图");
setupSheet(gantt);
setColWidths(gantt, [58, 95, 230, 84, 84, ...calendarDays.map(() => 36), 90, 80, 180]);
styleTitle(gantt, "A1:AC1", "实施甘特图（2026-06-10 至 2026-06-30）");
gantt.getRange("A2:AC2").merge();
gantt.getRange("A2:AC2").values = [["绿色=截至 6/17 已完成；橙色=后续计划；紫色=上线里程碑；灰色=指定非工作日，仅保留风险响应/问题跟进。"]];
gantt.getRange("A2:AC2").format = {
  fill: colors.graySoft,
  font: { color: colors.text, bold: true },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
const ganttBaseHeaders = ["WBS", "阶段", "任务名称", "开始", "结束"];
const dateHeaders = calendarDays.map((d) => cnDate(d));
const tailHeaders = ["状态", "进度", "关键交付"];
gantt.getRange(`A4:AC4`).values = [[...ganttBaseHeaders, ...dateHeaders, ...tailHeaders]];
styleHeader(gantt.getRange("A4:AC4"));
gantt.getRange(`A5:AC5`).values = [["", "", "星期/非工作日", "", "", ...calendarDays.map((d) => (isHoliday(d) ? "休" : `周${dayOfWeekCn(d)}`)), "", "", ""]];
gantt.getRange("A5:AC5").format = {
  fill: "#EDF2F7",
  font: { bold: true, color: colors.grayDark },
  horizontalAlignment: "center",
  borders: { preset: "all", style: "thin", color: colors.border },
};
for (let i = 0; i < calendarDays.length; i++) {
  const col = colName(6 + i);
  if (isHoliday(calendarDays[i])) {
    gantt.getRange(`${col}4:${col}${5 + tasks.length}`).format.fill = colors.holiday;
  }
}
const ganttRows = tasks.map((t) => [
  t.wbs,
  t.phase,
  t.task,
  t.start,
  t.end,
  ...calendarDays.map(() => ""),
  t.status,
  t.progress,
  t.deliverable,
]);
gantt.getRange(`A6:AC${5 + ganttRows.length}`).values = ganttRows;
styleBody(gantt.getRange(`A6:AC${5 + ganttRows.length}`));
gantt.getRange(`D6:E${5 + ganttRows.length}`).setNumberFormat("yyyy-mm-dd");
gantt.getRange(`AB6:AB${5 + ganttRows.length}`).format.numberFormat = "0%";
gantt.getRange(`A6:B${5 + ganttRows.length}`).format.horizontalAlignment = "center";
gantt.getRange(`D6:AC${5 + ganttRows.length}`).format.horizontalAlignment = "center";
for (let i = 0; i < tasks.length; i++) {
  const row = 6 + i;
  const task = tasks[i];
  gantt.getRange(`A${row}:AC${row}`).format.rowHeightPx = 34;
  for (let j = 0; j < calendarDays.length; j++) {
    const day = calendarDays[j];
    const col = colName(6 + j);
    const cell = gantt.getRange(`${col}${row}`);
    if (overlapsDay(task, day)) {
      if (isHoliday(day)) {
        cell.values = [["·"]];
        cell.format = {
          fill: colors.holiday,
          font: { color: colors.grayDark },
          horizontalAlignment: "center",
          borders: { preset: "all", style: "thin", color: colors.border },
        };
      } else if (task.type === "里程碑") {
        cell.values = [["◆"]];
        cell.format = {
          fill: colors.milestone,
          font: { bold: true, color: colors.white },
          horizontalAlignment: "center",
          borders: { preset: "all", style: "thin", color: colors.border },
        };
      } else if (task.status === "已完成") {
        cell.values = [[""]];
        cell.format = {
          fill: colors.greenDark,
          borders: { preset: "all", style: "thin", color: colors.border },
        };
      } else {
        cell.values = [[""]];
        cell.format = {
          fill: colors.amberDark,
          borders: { preset: "all", style: "thin", color: colors.border },
        };
      }
    }
  }
  if (task.status === "已完成") {
    gantt.getRange(`AA${row}:AB${row}`).format = {
      fill: colors.green,
      font: { bold: true, color: "#274E13" },
      horizontalAlignment: "center",
      borders: { preset: "all", style: "thin", color: "#DDE6ED" },
    };
  } else if (task.type === "里程碑") {
    gantt.getRange(`AA${row}:AB${row}`).format = {
      fill: "#EADCF8",
      font: { bold: true, color: colors.milestone },
      horizontalAlignment: "center",
      borders: { preset: "all", style: "thin", color: "#DDE6ED" },
    };
  } else {
    gantt.getRange(`AA${row}:AB${row}`).format = {
      fill: colors.amber,
      font: { bold: true, color: "#7F3F00" },
      horizontalAlignment: "center",
      borders: { preset: "all", style: "thin", color: "#DDE6ED" },
    };
  }
}
gantt.freezePanes.freezeRows(5);
gantt.freezePanes.freezeColumns(5);
gantt.getRange(`AB6:AB${5 + ganttRows.length}`).format.numberFormat = "0%";

const risk = workbook.worksheets.add("里程碑与风险");
setupSheet(risk);
setColWidths(risk, [70, 200, 120, 560, 110, 220]);
styleTitle(risk, "A1:F1", "里程碑、待完成专项与风险控制");
styleSection(risk, "A3:F3", "一、关键里程碑");
risk.getRange("A4:D4").values = [["编号", "里程碑", "日期", "完成标准"]];
styleHeader(risk.getRange("A4:D4"), colors.blue);
risk.getRange(`A5:D${4 + milestones.length}`).values = milestones;
styleBody(risk.getRange(`A5:D${4 + milestones.length}`));
risk.getRange(`C5:C${4 + milestones.length}`).setNumberFormat("yyyy-mm-dd");
risk.getRange(`A5:A${4 + milestones.length}`).format.horizontalAlignment = "center";

styleSection(risk, "A13:F13", "二、未完成专项说明");
const pendingSpecials = [
  ["自定义爬虫及导入知识库", "尚未完成", "6/18-6/25", "新闻源待客户确认, 当前按可配置白名单和公开页面采集设计。"],
  ["RAGFlow 知识库调用", "尚未完成", "6/24-6/26", "需要在新增人员资料导入后验证 MCP 检索和 Dora/Gateway 调用。"],
  ["性能优化", "尚未完成", "6/25-6/29", "针对采集、导入、检索、Dora 和 TTS 首响进行优化。"],
  ["安全优化", "尚未完成", "6/25-6/29", "覆盖新闻源白名单、SSRF 防护、限频、日志脱敏和密钥边界。"],
];
risk.getRange("A14:D14").values = [["专项", "状态", "计划时间", "说明"]];
styleHeader(risk.getRange("A14:D14"), colors.teal);
risk.getRange("A15:D18").values = pendingSpecials;
styleBody(risk.getRange("A15:D18"));
risk.getRange("B15:B18").format = {
  fill: colors.amber,
  font: { bold: true, color: "#7F3F00" },
  horizontalAlignment: "center",
  borders: { preset: "all", style: "thin", color: "#DDE6ED" },
};

styleSection(risk, "A20:F20", "三、主要风险与控制措施");
risk.getRange("A21:E21").values = [["编号", "风险", "影响", "控制措施", "状态"]];
styleHeader(risk.getRange("A21:E21"), colors.red);
risk.getRange(`A22:E${21 + riskRows.length}`).values = riskRows;
styleBody(risk.getRange(`A22:E${21 + riskRows.length}`));
risk.getRange(`E22:E${21 + riskRows.length}`).format = {
  fill: colors.redSoft,
  font: { bold: true, color: colors.red },
  horizontalAlignment: "center",
  borders: { preset: "all", style: "thin", color: "#DDE6ED" },
};
risk.getRange(`A22:E${21 + riskRows.length}`).format.rowHeightPx = 50;

const cal = workbook.worksheets.add("工作日历");
setupSheet(cal);
setColWidths(cal, [100, 100, 120, 180, 300]);
styleTitle(cal, "A1:E1", "项目工作日历");
cal.getRange("A3:E3").values = [["日期", "星期", "是否工作日", "安排", "说明"]];
styleHeader(cal.getRange("A3:E3"), colors.blue);
const calRows = calendarDays.map((d) => [
  d,
  `周${dayOfWeekCn(d)}`,
  isHoliday(d) ? "非工作日" : "工作日",
  isHoliday(d) ? "风险响应/问题跟进" : "正式开发/联调/测试",
  isHoliday(d) ? "不安排正式开发任务" : "按实施计划推进",
]);
cal.getRange("A4:E24").values = calRows;
styleBody(cal.getRange("A4:E24"));
cal.getRange("A4:A24").setNumberFormat("yyyy-mm-dd");
for (let i = 0; i < calRows.length; i++) {
  const row = 4 + i;
  if (calRows[i][2] === "非工作日") {
    cal.getRange(`A${row}:E${row}`).format = {
      fill: colors.holiday,
      font: { color: colors.grayDark },
      borders: { preset: "all", style: "thin", color: colors.border },
    };
  }
}

const hidden = workbook.worksheets.add("数据源");
setupSheet(hidden);
hidden.getRange("A1:D1").values = [["字段", "值", "说明", "备注"]];
styleHeader(hidden.getRange("A1:D1"), colors.grayDark);
hidden.getRange("A2:D10").values = [
  ["汇报口径日期", reportDate, "计划进展统计截至日期", ""],
  ["项目开始", projectStart, "计划开始日期", ""],
  ["项目结束", projectEnd, "计划结束日期", ""],
  ["指定非工作日", [...holidaySet].join(", "), "客户指定日期", "仅保留风险响应/问题跟进"],
  ["计划工作日", workingDays.length, "剔除指定非工作日", ""],
  ["截至 6/17 已投入工作日", completedWorkdays.length, "剔除指定非工作日", ""],
  ["阶段性工作日进度", projectProgress, "已投入工作日 / 总工作日", ""],
  ["已完成任务数", completedTasks, "截至 6/17", ""],
  ["任务总数", tasks.length, "计划任务总数", ""],
];
styleBody(hidden.getRange("A2:D10"));
hidden.getRange("B2:B4").setNumberFormat("yyyy-mm-dd");
hidden.getRange("B8:B8").format.numberFormat = "0.0%";

// Final compact verification previews.
await fs.mkdir(outputDir, { recursive: true });
const summaryPreview = await workbook.render({ sheetName: "客户汇报摘要", range: "A1:L42", scale: 1, format: "png" });
await fs.writeFile(path.join(outputDir, "preview_summary.png"), new Uint8Array(await summaryPreview.arrayBuffer()));
const ganttPreview = await workbook.render({ sheetName: "甘特图", range: "A1:AD24", scale: 1, format: "png" });
await fs.writeFile(path.join(outputDir, "preview_gantt.png"), new Uint8Array(await ganttPreview.arrayBuffer()));

const inspect = await workbook.inspect({
  kind: "table",
  range: "客户汇报摘要!A1:L18",
  include: "values,formulas",
  tableMaxRows: 20,
  tableMaxCols: 12,
  maxChars: 4000,
});
console.log(inspect.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 200 },
  summary: "final formula error scan",
  maxChars: 2000,
});
console.log(errors.ndjson);

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);
console.log(`saved:${outputPath}`);
