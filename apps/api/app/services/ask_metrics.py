from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree as ET

from app.models import ChatRequest, ChatResponse
from app.services.yaml_loader import load_yaml_file


NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_PACKAGE_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


@dataclass(frozen=True)
class MetricResult:
    title: str
    speak_text: str
    summary: str
    bullets: list[str]
    source: str


class AskMetricsService:
    """Read-only local Excel query adapter for V0.7 POC metric questions."""

    def __init__(self, data_dir: str | Path, config_path: str | Path | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.config_path = Path(config_path) if config_path else None
        self.config = self._load_config()
        self._cache: dict[str, object] | None = None

    def respond(self, request: ChatRequest, *, message_id: str | None = None) -> ChatResponse | None:
        result = self.query(request.text)
        if result is None:
            return None
        return ChatResponse(
            session_id=request.session_id,
            message_id=message_id or f"msg-{uuid4().hex[:12]}",
            type="answer",
            title=result.title,
            speak_text=result.speak_text,
            display={
                "mode": "text",
                "summary": result.summary,
                "bullets": [*result.bullets, f"数据来源：{result.source}"],
                "source": result.source,
            },
        )

    def query(self, text: str) -> MetricResult | None:
        normalized = _normalize_text(text)
        if not self._looks_like_metric_question(normalized):
            return None

        data = self._load()

        if "总结" in normalized and ("党建" in normalized or "整体" in normalized):
            return self._overall_summary(data)
        if "支部" in normalized and "学习" in normalized and ("最低" in normalized or "倒数" in normalized):
            return self._study_lowest_branch(data)
        if "学习" in normalized and "完成率" in normalized:
            return self._study_completion_rate(data)
        if "党员总数" in normalized or ("学习" in normalized and "总人数" in normalized):
            return self._study_total_members(data)
        if "学习" in normalized and ("完成学习" in normalized or "已完成学习" in normalized):
            return self._study_completed_count(data)
        if "学习" in normalized and "未完成" in normalized:
            return self._study_uncompleted_count(data)
        if "主题党日" in normalized:
            return self._org_theme_day_count(data)
        if "参会率" in normalized or "平均参会" in normalized:
            return self._org_attendance_rate(data)
        if "整改" in normalized and "闭环" in normalized:
            return self._org_rectification_rate(data)
        if ("组织生活" in normalized or "活动" in normalized) and "完成率" in normalized:
            return self._org_activity_completion_rate(data)
        if "积极分子" in normalized:
            return self._development_stage_count(data, "入党积极分子")
        if "发展对象" in normalized:
            return self._development_stage_count(data, "发展对象", include_distribution=True)
        if "转正" in normalized:
            return self._development_regularized_count(data)
        if "材料" in normalized and ("待补充" in normalized or "补充" in normalized):
            return self._development_material_pending(data)
        if "政审" in normalized and ("待" in normalized or "未完成" in normalized or "多少" in normalized):
            return self._development_political_pending(data)
        return None

    @staticmethod
    def _looks_like_metric_question(text: str) -> bool:
        metric_terms = (
            "完成率",
            "多少",
            "几次",
            "几人",
            "人数",
            "平均",
            "最低",
            "排名",
            "闭环",
            "参会率",
            "主题党日",
            "积极分子",
            "发展对象",
            "转正",
            "待补充",
            "政审",
            "指标",
            "数据",
            "整体情况",
        )
        domain_terms = (
            "党员",
            "学习",
            "组织生活",
            "党建",
            "活动",
            "主题党日",
            "整改",
            "入党",
            "党员发展",
            "政审",
            "材料",
            "支部",
        )
        return any(term in text for term in metric_terms) and any(term in text for term in domain_terms)

    def _load(self) -> dict[str, object]:
        if self._cache is not None:
            return self._cache

        study_config = self._workbook_config("study")
        org_config = self._workbook_config("org_life")
        development_config = self._workbook_config("development")

        study = _read_xlsx(self.data_dir / study_config["file"])
        org = _read_xlsx(self.data_dir / org_config["file"])
        development = _read_xlsx(self.data_dir / development_config["file"])
        self._cache = {
            "study_dashboard": _dashboard_metrics(study[study_config["sheets"]["dashboard"]]),
            "study_branch": _table_dicts(study[study_config["sheets"]["branch_summary"]]),
            "org_dashboard": _dashboard_metrics(org[org_config["sheets"]["dashboard"]]),
            "development_dashboard": _dashboard_metrics(
                development[development_config["sheets"]["dashboard"]]
            ),
            "development_detail": _table_dicts(development[development_config["sheets"]["detail"]]),
            "development_branch": _table_dicts(
                development[development_config["sheets"]["branch_summary"]]
            ),
        }
        return self._cache

    def _load_config(self) -> dict[str, object]:
        if self.config_path and self.config_path.exists():
            return load_yaml_file(self.config_path)
        return {
            "workbooks": {
                "study": {
                    "file": "zt_party_study_metrics_2026.xlsx",
                    "sheets": {"dashboard": "Dashboard", "branch_summary": "支部汇总"},
                },
                "org_life": {
                    "file": "zt_party_org_life_metrics_2026.xlsx",
                    "sheets": {"dashboard": "Dashboard"},
                },
                "development": {
                    "file": "zt_party_development_metrics_2026.xlsx",
                    "sheets": {
                        "dashboard": "Dashboard",
                        "detail": "发展对象明细",
                        "branch_summary": "支部汇总",
                    },
                },
            }
        }

    def _workbook_config(self, key: str) -> dict[str, object]:
        workbooks = self.config.get("workbooks")
        if not isinstance(workbooks, dict) or key not in workbooks:
            raise KeyError(f"Ask metrics workbook config is missing: {key}")
        workbook = workbooks[key]
        if not isinstance(workbook, dict):
            raise TypeError(f"Ask metrics workbook config is invalid: {key}")
        return workbook

    def _source(self, workbook_key: str, sheet_key: str) -> str:
        workbook = self._workbook_config(workbook_key)
        sheets = workbook["sheets"]
        return f"{workbook['file']} / {sheets[sheet_key]}"

    def _study_completion_rate(self, data: dict[str, object]) -> MetricResult:
        metrics = data["study_dashboard"]
        return MetricResult(
            title="党员学习完成率",
            speak_text=f"当前党员学习完成率为{_format_percent(metrics['学习完成率'])}，党员总数{_format_number(metrics['党员总数'])}人，已完成学习{_format_number(metrics['已完成学习人数'])}人。",
            summary=f"当前党员学习完成率为 {_format_percent(metrics['学习完成率'])}。",
            bullets=[
                f"党员总数：{_format_number(metrics['党员总数'])} 人",
                f"已完成学习：{_format_number(metrics['已完成学习人数'])} 人",
                f"未完成：{_format_number(metrics['未完成人数'])} 人",
            ],
            source=self._source("study", "dashboard"),
        )

    def _study_total_members(self, data: dict[str, object]) -> MetricResult:
        metrics = data["study_dashboard"]
        return MetricResult(
            title="党员学习人数",
            speak_text=f"按2026年6月学习口径，党员总数为{_format_number(metrics['党员总数'])}人。",
            summary=f"党员总数 {_format_number(metrics['党员总数'])} 人。",
            bullets=[
                f"已完成学习：{_format_number(metrics['已完成学习人数'])} 人",
                f"学习完成率：{_format_percent(metrics['学习完成率'])}",
            ],
            source=self._source("study", "dashboard"),
        )

    def _study_completed_count(self, data: dict[str, object]) -> MetricResult:
        metrics = data["study_dashboard"]
        return MetricResult(
            title="本月学习完成人数",
            speak_text=f"本月已完成学习人数为{_format_number(metrics['已完成学习人数'])}人，完成率为{_format_percent(metrics['学习完成率'])}。",
            summary=f"本月已完成学习 {_format_number(metrics['已完成学习人数'])} 人。",
            bullets=[
                f"党员总数：{_format_number(metrics['党员总数'])} 人",
                f"未完成：{_format_number(metrics['未完成人数'])} 人",
            ],
            source=self._source("study", "dashboard"),
        )

    def _study_uncompleted_count(self, data: dict[str, object]) -> MetricResult:
        metrics = data["study_dashboard"]
        return MetricResult(
            title="本月学习未完成人数",
            speak_text=f"本月未完成学习人数为{_format_number(metrics['未完成人数'])}人。",
            summary=f"未完成学习 {_format_number(metrics['未完成人数'])} 人。",
            bullets=[
                f"已完成学习：{_format_number(metrics['已完成学习人数'])} 人",
                f"学习完成率：{_format_percent(metrics['学习完成率'])}",
            ],
            source=self._source("study", "dashboard"),
        )

    def _study_lowest_branch(self, data: dict[str, object]) -> MetricResult:
        branches = data["study_branch"]
        lowest = min(branches, key=lambda row: _to_float(row["完成率"]))
        return MetricResult(
            title="学习完成率最低支部",
            speak_text=f"当前学习完成率最低的是{lowest['支部名称']}，完成率为{_format_percent(lowest['完成率'])}，已完成{_format_number(lowest['已完成人数'])}人，党员数{_format_number(lowest['党员数'])}人。",
            summary=f"{lowest['支部名称']}完成率最低，为 {_format_percent(lowest['完成率'])}。",
            bullets=[
                f"已完成人数：{_format_number(lowest['已完成人数'])} 人",
                f"党员数：{_format_number(lowest['党员数'])} 人",
                f"心得未提交：{_format_number(lowest['心得未提交'])} 人",
            ],
            source=self._source("study", "branch_summary"),
        )

    def _org_theme_day_count(self, data: dict[str, object]) -> MetricResult:
        metrics = data["org_dashboard"]
        return MetricResult(
            title="主题党日开展次数",
            speak_text=f"2026年1到6月主题党日完成次数为{_format_number(metrics['主题党日完成次数'])}次。",
            summary=f"主题党日完成 {_format_number(metrics['主题党日完成次数'])} 次。",
            bullets=[
                f"已完成活动：{_format_number(metrics['已完成活动数'])} 次",
                f"活动完成率：{_format_percent(metrics['活动完成率'])}",
            ],
            source=self._source("org_life", "dashboard"),
        )

    def _org_attendance_rate(self, data: dict[str, object]) -> MetricResult:
        metrics = data["org_dashboard"]
        return MetricResult(
            title="组织生活平均参会率",
            speak_text=f"2026年1到6月组织生活平均参会率为{_format_percent(metrics['平均参会率'])}。",
            summary=f"平均参会率 {_format_percent(metrics['平均参会率'])}。",
            bullets=[
                f"已完成活动：{_format_number(metrics['已完成活动数'])} 次",
                f"活动完成率：{_format_percent(metrics['活动完成率'])}",
            ],
            source=self._source("org_life", "dashboard"),
        )

    def _org_rectification_rate(self, data: dict[str, object]) -> MetricResult:
        metrics = data["org_dashboard"]
        return MetricResult(
            title="整改事项闭环率",
            speak_text=f"当前整改事项数为{_format_number(metrics['整改事项数'])}项，整改闭环率为{_format_percent(metrics['整改闭环率'])}。",
            summary=f"整改闭环率 {_format_percent(metrics['整改闭环率'])}。",
            bullets=[
                f"整改事项数：{_format_number(metrics['整改事项数'])} 项",
                f"活动完成率：{_format_percent(metrics['活动完成率'])}",
            ],
            source=self._source("org_life", "dashboard"),
        )

    def _org_activity_completion_rate(self, data: dict[str, object]) -> MetricResult:
        metrics = data["org_dashboard"]
        return MetricResult(
            title="组织生活活动完成率",
            speak_text=f"2026年1到6月活动计划总数为{_format_number(metrics['活动计划总数'])}次，已完成{_format_number(metrics['已完成活动数'])}次，活动完成率为{_format_percent(metrics['活动完成率'])}。",
            summary=f"组织生活活动完成率 {_format_percent(metrics['活动完成率'])}。",
            bullets=[
                f"计划活动：{_format_number(metrics['活动计划总数'])} 次",
                f"已完成活动：{_format_number(metrics['已完成活动数'])} 次",
                f"未完成活动：{_format_number(metrics['未完成活动数'])} 次",
            ],
            source=self._source("org_life", "dashboard"),
        )

    def _development_stage_count(
        self,
        data: dict[str, object],
        stage: str,
        *,
        include_distribution: bool = False,
    ) -> MetricResult:
        metrics = data["development_dashboard"]
        key = f"{stage}人数"
        if stage == "入党积极分子":
            key = "入党积极分子人数"
        count = metrics[key]
        bullets = [f"{stage}：{_format_number(count)} 人"]
        if include_distribution:
            distribution = _stage_distribution(data["development_branch"], stage)
            bullets.extend(f"{name}：{_format_number(value)} 人" for name, value in distribution)
            distribution_text = "，".join(f"{name}{_format_number(value)}人" for name, value in distribution)
            speak_text = f"当前{stage}共有{_format_number(count)}人，分布为{distribution_text}。"
        else:
            speak_text = f"当前{stage}共有{_format_number(count)}人。"
        return MetricResult(
            title=f"{stage}人数",
            speak_text=speak_text,
            summary=f"{stage} {_format_number(count)} 人。",
            bullets=bullets,
            source=f"{self._source('development', 'dashboard')}, {self._source('development', 'branch_summary')}",
        )

    def _development_regularized_count(self, data: dict[str, object]) -> MetricResult:
        metrics = data["development_dashboard"]
        return MetricResult(
            title="本年转正党员人数",
            speak_text=f"2026年党员发展台账中，本年转正党员为{_format_number(metrics['本年转正人数'])}人。",
            summary=f"本年转正党员 {_format_number(metrics['本年转正人数'])} 人。",
            bullets=[
                f"发展台账总人数：{_format_number(metrics['发展台账总人数'])} 人",
                f"预备党员：{_format_number(metrics['预备党员人数'])} 人",
            ],
            source=self._source("development", "dashboard"),
        )

    def _development_material_pending(self, data: dict[str, object]) -> MetricResult:
        rows = [
            row
            for row in data["development_detail"]
            if str(row.get("材料状态") or "") == "待补充"
        ]
        names = "、".join(
            f"{row['姓名']}（{row['支部名称']}，{row['人员ID']}）" for row in rows
        )
        return MetricResult(
            title="党员发展材料待补充",
            speak_text=f"当前党员发展材料待补充人数为{len(rows)}人，分别是{names}。",
            summary=f"材料待补充 {len(rows)} 人。",
            bullets=[f"{row['姓名']}：{row['支部名称']}，当前阶段{row['当前阶段']}" for row in rows],
            source=self._source("development", "detail"),
        )

    def _development_political_pending(self, data: dict[str, object]) -> MetricResult:
        rows = [
            row
            for row in data["development_detail"]
            if "待完成" in str(row.get("政审状态") or "")
        ]
        names = "、".join(
            f"{row['姓名']}（{row['支部名称']}，{row['人员ID']}）" for row in rows
        )
        return MetricResult(
            title="政审待完成人数",
            speak_text=f"当前政审待完成人数为{len(rows)}人，分别是{names}。",
            summary=f"政审待完成 {len(rows)} 人。",
            bullets=[f"{row['姓名']}：{row['支部名称']}，当前阶段{row['当前阶段']}" for row in rows],
            source=self._source("development", "detail"),
        )

    def _overall_summary(self, data: dict[str, object]) -> MetricResult:
        study = data["study_dashboard"]
        org = data["org_dashboard"]
        dev = data["development_dashboard"]
        return MetricResult(
            title="党建工作整体情况",
            speak_text=(
                f"当前党建数据整体平稳。党员学习完成率为{_format_percent(study['学习完成率'])}，"
                f"组织生活活动完成率为{_format_percent(org['活动完成率'])}，"
                f"入党积极分子{_format_number(dev['入党积极分子人数'])}人，发展对象{_format_number(dev['发展对象人数'])}人。"
            ),
            summary="学习、组织生活和党员发展三类测试指标已汇总。",
            bullets=[
                f"学习完成率：{_format_percent(study['学习完成率'])}",
                f"组织生活活动完成率：{_format_percent(org['活动完成率'])}",
                f"平均参会率：{_format_percent(org['平均参会率'])}",
                f"入党积极分子：{_format_number(dev['入党积极分子人数'])} 人",
                f"发展对象：{_format_number(dev['发展对象人数'])} 人",
            ],
            source="docs/demo_data/ask_metrics/*.xlsx",
        )


def _read_xlsx(path: Path) -> dict[str, list[list[object | None]]]:
    if not path.exists():
        raise FileNotFoundError(f"Ask metrics workbook not found: {path}")

    with zipfile.ZipFile(path) as archive:
        shared_strings = _read_shared_strings(archive)
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_targets = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall(f"{NS_PACKAGE_REL}Relationship")
        }
        sheets: dict[str, list[list[object | None]]] = {}
        for sheet in workbook.findall(f"{NS_MAIN}sheets/{NS_MAIN}sheet"):
            name = sheet.attrib["name"]
            rel_id = sheet.attrib[f"{NS_REL}id"]
            target = rel_targets[rel_id].lstrip("/")
            if not target.startswith("xl/"):
                target = f"xl/{target}"
            sheets[name] = _read_worksheet(archive, target, shared_strings)
    return sheets


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall(f"{NS_MAIN}si"):
        parts = [node.text or "" for node in item.iter(f"{NS_MAIN}t")]
        strings.append("".join(parts))
    return strings


def _read_worksheet(
    archive: zipfile.ZipFile,
    target: str,
    shared_strings: list[str],
) -> list[list[object | None]]:
    root = ET.fromstring(archive.read(target))
    rows: list[list[object | None]] = []
    for row in root.findall(f"{NS_MAIN}sheetData/{NS_MAIN}row"):
        row_values: list[object | None] = []
        for cell in row.findall(f"{NS_MAIN}c"):
            column_index = _column_index(cell.attrib.get("r", "A1"))
            while len(row_values) < column_index:
                row_values.append(None)
            row_values.append(_cell_value(cell, shared_strings))
        rows.append(row_values)
    return rows


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> object | None:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{NS_MAIN}t")) or None

    value_node = cell.find(f"{NS_MAIN}v")
    if value_node is None or value_node.text is None:
        return None

    raw_value = value_node.text
    if cell_type == "s":
        index = int(raw_value)
        return shared_strings[index] if index < len(shared_strings) else ""
    if cell_type == "b":
        return raw_value == "1"
    if cell_type in {"str", "e"}:
        return raw_value
    return _parse_number(raw_value)


def _parse_number(value: str) -> int | float | str:
    try:
        parsed = float(value)
    except ValueError:
        return value
    if parsed.is_integer():
        return int(parsed)
    return parsed


def _column_index(cell_ref: str) -> int:
    letters = re.match(r"([A-Z]+)", cell_ref.upper())
    if not letters:
        return 0
    index = 0
    for char in letters.group(1):
        index = index * 26 + ord(char) - ord("A") + 1
    return index - 1


def _dashboard_metrics(rows: list[list[object | None]]) -> dict[str, object]:
    metrics: dict[str, object] = {}
    for row in rows:
        if len(row) >= 2 and isinstance(row[0], str) and row[1] is not None:
            metrics[row[0]] = row[1]
    return metrics


def _table_dicts(rows: list[list[object | None]]) -> list[dict[str, object]]:
    if not rows:
        return []
    headers = [str(value) if value is not None else "" for value in rows[0]]
    table: list[dict[str, object]] = []
    for row in rows[1:]:
        if not any(value is not None for value in row):
            continue
        item = {
            header: row[index] if index < len(row) else None
            for index, header in enumerate(headers)
            if header
        }
        table.append(item)
    return table


def _stage_distribution(rows: object, stage: str) -> list[tuple[str, object]]:
    distribution: list[tuple[str, object]] = []
    for row in rows:
        value = row.get(stage)
        if value:
            distribution.append((str(row["支部名称"]), value))
    return distribution


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).strip()


def _format_number(value: object) -> str:
    number = _to_float(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.1f}".rstrip("0").rstrip(".")


def _format_percent(value: object) -> str:
    return f"{_to_float(value) * 100:.1f}%"


def _to_float(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().rstrip("%")
        number = float(cleaned)
        return number / 100 if value.strip().endswith("%") else number
    raise TypeError(f"Value cannot be converted to float: {value!r}")
