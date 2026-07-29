from __future__ import annotations

import json
from pathlib import Path

from app.control_plane.capacity_p2_3 import (
    DISCLAIMER,
    MAX_GLOBAL_INFLIGHT,
    MAX_PER_SCREEN_INFLIGHT,
    SCHEMA_VERSION,
    main,
    run_measurement,
)
from app.control_plane.p2_2 import EXECUTOR_WORKERS, MAX_RETAINED_JOBS


def test_capacity_measurement_produces_sanitized_reports(tmp_path: Path) -> None:
    output_dir = tmp_path / "capacity"
    report = run_measurement(output_dir, rounds=1, warmup=0)

    json_path = output_dir / "capacity-measurement.json"
    md_path = output_dir / "capacity-measurement.md"
    assert json_path.exists()
    assert md_path.exists()
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded == report

    assert loaded["schema_version"] == SCHEMA_VERSION
    environment = loaded["environment"]
    assert environment["cpu_count"] >= 1
    assert environment["python_version"]
    assert environment["timestamp_utc"]
    limits = loaded["config_limits"]
    assert limits["max_global_inflight"] == MAX_GLOBAL_INFLIGHT
    assert limits["max_per_screen_inflight"] == MAX_PER_SCREEN_INFLIGHT
    assert limits["executor_workers"] == EXECUTOR_WORKERS
    assert limits["max_retained_jobs"] == MAX_RETAINED_JOBS

    phases = loaded["phases"]
    assert set(phases) == {"sequential_baseline", "three_screen_concurrent", "saturation"}
    sequential = phases["sequential_baseline"]
    assert len(sequential["screens"]) == 3
    for screen in sequential["screens"]:
        assert len(screen["latency_ms"]) == 1
        assert screen["stats"]["count"] == 1
        assert screen["all_succeeded"] is True
    concurrent = phases["three_screen_concurrent"]
    assert concurrent["rounds"] == 1
    assert concurrent["completed"] == 3
    assert concurrent["all_succeeded"] is True

    saturation = phases["saturation"]
    assert saturation["rejected_backpressure"] > 0
    assert saturation["rejected_backpressure"] + saturation["completed"] == saturation["submitted"]
    assert saturation["all_terminal"] is True
    assert saturation["all_rejections_retryable"] is True
    assert saturation["recovery"]["verdict"] is True
    for observed in saturation["observed_queue_status"]:
        assert observed["inflight"] <= MAX_PER_SCREEN_INFLIGHT

    verdicts = loaded["verdicts"]
    assert all(verdicts.values())

    markdown = md_path.read_text(encoding="utf-8")
    assert "deployment-local" in markdown.casefold()
    assert "not an SLA" in markdown
    assert "not a customer-environment certification" in markdown
    assert DISCLAIMER in markdown
    # No absolute host paths or home directories leak into either artifact.
    serialized = json_path.read_text(encoding="utf-8") + markdown
    assert str(tmp_path) not in serialized
    assert str(Path.home()) not in serialized


def test_capacity_measurement_cli_writes_reports(tmp_path: Path) -> None:
    output_dir = tmp_path / "cli-capacity"
    assert main(["--output-dir", str(output_dir), "--rounds", "1", "--warmup", "0"]) == 0
    loaded = json.loads((output_dir / "capacity-measurement.json").read_text(encoding="utf-8"))
    assert loaded["schema_version"] == SCHEMA_VERSION
    assert loaded["parameters"] == {
        "rounds": 1,
        "warmup": 0,
        "warmup_completed": 0,
        "screens": 3,
    }
    assert (output_dir / "capacity-measurement.md").exists()
