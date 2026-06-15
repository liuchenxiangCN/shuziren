from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from app.services.ask_metrics_provider import AskMetricsProviderStatus, MetricResult
from app.services.yaml_loader import load_yaml_file


NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_PACKAGE_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


class ExcelAskMetricsProvider:
    name = "excel"

    def __init__(self, data_dir: str | Path, config_path: str | Path | None = None) -> None:
        self.data_dir = Path(data_dir)
        self.config_path = Path(config_path) if config_path else None
        self.config = self._load_config()
        self.metrics = _metric_definitions(self.config)
        self._sheet_cache: dict[tuple[str, str, str], Any] = {}
        self._workbook_cache: dict[str, dict[str, list[list[object | None]]]] = {}

    def status(self) -> AskMetricsProviderStatus:
        return AskMetricsProviderStatus(
            name=self.name,
            status="implemented",
            source="customer_config" if self.config_path and self.config_path.exists() else "root_config",
            notes=f"{len(self.metrics)} configured metric definitions",
        )

    def query(self, text: str) -> MetricResult | None:
        normalized = _normalize_text(text)
        for metric in self.metrics:
            if _matches(normalized, metric.get("match")):
                return self._evaluate_metric(metric)
        return None

    def _evaluate_metric(self, metric: dict[str, Any]) -> MetricResult:
        context = self._build_context(metric)
        for transform in _as_list(metric.get("transforms")):
            self._apply_transform(context, transform)

        result = _as_dict(metric.get("result"))
        source = self._source_from_config(result.get("source"), context)
        return MetricResult(
            title=_render_template(str(result.get("title") or metric.get("id") or ""), context),
            speak_text=_render_template(str(result.get("speak_text") or ""), context),
            summary=_render_template(str(result.get("summary") or ""), context),
            bullets=self._render_bullets(result.get("bullets"), context),
            source=source,
            provider=self.name,
            metric_id=str(metric.get("id") or ""),
        )

    def _build_context(self, metric: dict[str, Any]) -> dict[str, Any]:
        context: dict[str, Any] = {}
        for alias, spec in _as_dict(metric.get("context")).items():
            if not isinstance(spec, dict):
                continue
            workbook_key = str(spec.get("workbook") or "")
            sheet_key = str(spec.get("sheet") or "")
            parser = str(spec.get("type") or "dashboard")
            context[alias] = self._load_source(workbook_key, sheet_key, parser)
        return context

    def _load_source(self, workbook_key: str, sheet_key: str, parser: str) -> Any:
        cache_key = (workbook_key, sheet_key, parser)
        if cache_key in self._sheet_cache:
            return self._sheet_cache[cache_key]

        workbook_config = self._workbook_config(workbook_key)
        sheets = _as_dict(workbook_config.get("sheets"))
        file_name = str(workbook_config.get("file") or "")
        sheet_name = str(sheets.get(sheet_key) or "")
        workbook = self._load_workbook(workbook_key, file_name)
        rows = workbook[sheet_name]
        if parser == "table":
            value = _table_dicts(rows)
        elif parser == "dashboard":
            value = _dashboard_metrics(rows)
        else:
            raise ValueError(f"Unsupported ask metrics source type: {parser}")
        self._sheet_cache[cache_key] = value
        return value

    def _load_workbook(self, workbook_key: str, file_name: str) -> dict[str, list[list[object | None]]]:
        if workbook_key not in self._workbook_cache:
            self._workbook_cache[workbook_key] = _read_xlsx(self.data_dir / file_name)
        return self._workbook_cache[workbook_key]

    def _apply_transform(self, context: dict[str, Any], transform: dict[str, Any]) -> None:
        transform_type = str(transform.get("type") or "")
        if transform_type == "min_row":
            rows = _as_list(context.get(str(transform.get("source") or "")))
            by = str(transform.get("by") or "")
            context[str(transform.get("as") or "row")] = min(rows, key=lambda row: _to_float(row[by]))
            return
        if transform_type == "filter_rows":
            rows = _as_list(context.get(str(transform.get("source") or "")))
            where = _as_dict(transform.get("where"))
            context[str(transform.get("as") or "rows")] = [
                row for row in rows if _row_matches(row, where)
            ]
            return
        if transform_type == "distribution":
            rows = _as_list(context.get(str(transform.get("source") or "")))
            label_field = str(transform.get("label_field") or "")
            value_field = str(transform.get("value_field") or "")
            context[str(transform.get("as") or "distribution")] = [
                {"label": row.get(label_field), "value": row.get(value_field)}
                for row in rows
                if _truthy_metric_value(row.get(value_field))
            ]
            return
        if transform_type == "join_items":
            items = _as_list(context.get(str(transform.get("source") or "")))
            template = str(transform.get("template") or "{value}")
            separator = str(transform.get("separator") or "")
            context[str(transform.get("as") or "joined")] = separator.join(
                _render_template(template, context, item=_as_dict(item)) for item in items
            )
            return
        if transform_type == "render_items":
            items = _as_list(context.get(str(transform.get("source") or "")))
            template = str(transform.get("template") or "{value}")
            context[str(transform.get("as") or "items")] = [
                _render_template(template, context, item=_as_dict(item)) for item in items
            ]
            return
        raise ValueError(f"Unsupported ask metrics transform: {transform_type}")

    def _render_bullets(self, bullets_config: Any, context: dict[str, Any]) -> list[str]:
        bullets: list[str] = []
        for bullet in _as_list(bullets_config):
            if isinstance(bullet, str):
                bullets.append(_render_template(bullet, context))
                continue
            if isinstance(bullet, dict) and bullet.get("extend"):
                bullets.extend(str(item) for item in _as_list(context.get(str(bullet["extend"]))))
                continue
            if isinstance(bullet, dict) and bullet.get("template"):
                bullets.append(_render_template(str(bullet["template"]), context))
        return bullets

    def _source_from_config(self, source_config: Any, context: dict[str, Any]) -> str:
        if isinstance(source_config, str):
            return _render_template(source_config, context)
        if isinstance(source_config, list):
            return ", ".join(self._source_label(item) for item in source_config)
        if isinstance(source_config, dict):
            if source_config.get("text") is not None:
                return _render_template(str(source_config["text"]), context)
            refs = _as_list(source_config.get("refs"))
            return ", ".join(self._source_label(item) for item in refs)
        return ""

    def _source_label(self, source_ref: Any) -> str:
        ref = _as_dict(source_ref)
        workbook = self._workbook_config(str(ref.get("workbook") or ""))
        sheets = _as_dict(workbook.get("sheets"))
        sheet_key = str(ref.get("sheet") or "")
        return f"{workbook.get('file')} / {sheets.get(sheet_key)}"

    def _load_config(self) -> dict[str, Any]:
        if self.config_path and self.config_path.exists():
            data = load_yaml_file(self.config_path)
            return data if isinstance(data, dict) else {}
        return {"workbooks": {}, "metrics": []}

    def _workbook_config(self, key: str) -> dict[str, Any]:
        workbooks = _as_dict(self.config.get("workbooks"))
        workbook = workbooks.get(key)
        if not isinstance(workbook, dict):
            raise KeyError(f"Ask metrics workbook config is missing: {key}")
        return workbook


def _metric_definitions(config: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = [item for item in _as_list(config.get("metrics")) if isinstance(item, dict)]
    return sorted(metrics, key=lambda item: int(item.get("priority") or 1000))


def _matches(text: str, match_config: Any) -> bool:
    match = _as_dict(match_config)
    all_terms = [_normalize_text(str(term)) for term in _as_list(match.get("all"))]
    if any(term and term not in text for term in all_terms):
        return False
    any_terms = [_normalize_text(str(term)) for term in _as_list(match.get("any"))]
    if any_terms and not any(term in text for term in any_terms):
        return False
    for group in _as_list(match.get("any_groups")):
        group_terms = [_normalize_text(str(term)) for term in _as_list(group)]
        if group_terms and not any(term in text for term in group_terms):
            return False
    none_terms = [_normalize_text(str(term)) for term in _as_list(match.get("none"))]
    if any(term and term in text for term in none_terms):
        return False
    return bool(all_terms or any_terms or match.get("any_groups"))


def _row_matches(row: Any, where: dict[str, Any]) -> bool:
    if not isinstance(row, dict):
        return False
    field = str(where.get("field") or "")
    value = row.get(field)
    if "equals" in where and str(value or "") != str(where["equals"]):
        return False
    if "contains" in where and str(where["contains"]) not in str(value or ""):
        return False
    return True


def _render_template(template: str, context: dict[str, Any], *, item: dict[str, Any] | None = None) -> str:
    def replace(match: re.Match[str]) -> str:
        return str(_format_value(_resolve_expr(match.group(1), context, item=item)))

    return re.sub(r"\{([^{}]+)\}", replace, template)


def _resolve_expr(expr: str, context: dict[str, Any], *, item: dict[str, Any] | None = None) -> Any:
    parts = [part.strip() for part in expr.split("|")]
    value = _resolve_path(parts[0], context, item=item)
    for filter_name in parts[1:]:
        if filter_name == "number":
            value = _format_number(value)
        elif filter_name == "percent":
            value = _format_percent(value)
        elif filter_name == "count":
            value = len(_as_list(value))
    return value


def _resolve_path(path: str, context: dict[str, Any], *, item: dict[str, Any] | None = None) -> Any:
    if item is not None and path in item:
        return item[path]
    if path in context:
        return context[path]
    if "." not in path:
        return ""
    first, rest = path.split(".", 1)
    value: Any = context.get(first)
    for part in rest.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return ""
    return value


def _format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "、".join(str(item) for item in value)
    return str(value)


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


def _truthy_metric_value(value: object) -> bool:
    try:
        return _to_float(value) > 0
    except (TypeError, ValueError):
        return bool(value)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
