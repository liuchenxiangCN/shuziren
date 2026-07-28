from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool
from test_control_plane import control_plane as _shared_control_plane
from test_control_plane import login, mutation_headers
from test_p2_1_capability_profiles import _enroll_device, _publish_and_ack
from test_p2_2_controlled_querying import (
    _create_controlled_query_profile,
    _create_query_release,
    _poll_execution,
)

from app.control_plane.service import ControlPlaneService


@pytest.fixture()
def p22_database_control_plane(
    tmp_path: Path,
) -> tuple[FastAPI, ControlPlaneService, Path]:
    return _shared_control_plane.__wrapped__(tmp_path)


DATABASE_CASES = (
    (
        "POSTGRESQL",
        "postgresql+psycopg",
        "P22_POSTGRES",
        5432,
    ),
    (
        "MYSQL",
        "mysql+pymysql",
        "P22_MYSQL",
        3306,
    ),
    (
        "ORACLE",
        "oracle+oracledb",
        "P22_ORACLE",
        1521,
    ),
)


def _connection_case(
    engine: str,
    driver: str,
    prefix: str,
    default_port: int,
) -> dict[str, Any]:
    required = ("HOST", "DATABASE", "USERNAME", "PASSWORD")
    values = {name: os.environ.get(f"{prefix}_{name}", "") for name in required}
    if any(not values[name] for name in required):
        pytest.skip(f"{prefix} exact reference database is not configured")
    port = int(os.environ.get(f"{prefix}_PORT", str(default_port)))
    relation = os.environ.get(f"{prefix}_RELATION", "approved_metrics")
    return {
        "engine": engine,
        "driver": driver,
        "host": values["HOST"],
        "port": port,
        "database": values["DATABASE"],
        "username": values["USERNAME"],
        "password": values["PASSWORD"],
        "relation": relation,
    }


@pytest.mark.parametrize(
    ("engine", "driver", "prefix", "default_port"),
    DATABASE_CASES,
)
def test_exact_read_only_database_adapter_executes_bound_dataset(
    p22_database_control_plane: tuple[FastAPI, ControlPlaneService, Path],
    engine: str,
    driver: str,
    prefix: str,
    default_port: int,
) -> None:
    case = _connection_case(engine, driver, prefix, default_port)
    app, _, _ = p22_database_control_plane
    implementation, csrf_impl = login(app, "implementation")
    administrator, csrf_admin = login(app, "admin-a")
    admin_b, csrf_b = login(app, "admin-b")
    screen = implementation.get("/api/v1/control-plane/screen-instances").json()["items"][0]

    url = URL.create(
        driver,
        username=case["username"],
        password=case["password"],
        host=case["host"],
        port=case["port"],
        database=case["database"] if engine != "ORACLE" else None,
        query={"service_name": case["database"]} if engine == "ORACLE" else {},
    )
    direct = create_engine(url, poolclass=NullPool, hide_parameters=True)
    try:
        with direct.begin() as connection, pytest.raises(DBAPIError):
            connection.execute(
                text(
                    f"INSERT INTO {case['relation']}"
                    "(business_date, shift, output) "
                    "VALUES ('2026-07-28', 'DENIED', 1)"
                )
            )
        with direct.connect() as connection:
            before_count = connection.execute(
                text(f"SELECT COUNT(*) AS row_count FROM {case['relation']}")
            ).scalar_one()
            before_fields = list(
                connection.execute(text(f"SELECT * FROM {case['relation']} WHERE 1 = 0")).keys()
            )
    finally:
        direct.dispose()

    created_source = administrator.post(
        "/api/v1/control-plane/query-sources",
        headers=mutation_headers(
            csrf_admin,
            **{"Idempotency-Key": f"p22-real-source-{engine.lower()}"},
        ),
        json={
            "site_id": screen["site_id"],
            "display_name": f"{engine} exact read-only reference",
            "engine": engine,
            "read_only_account_confirmed": True,
            "connection": {
                "host": case["host"],
                "port": case["port"],
                "database": case["database"],
                "username": case["username"],
                "password": case["password"],
            },
        },
    )
    assert created_source.status_code == 201, created_source.text
    source = created_source.json()
    assert case["password"] not in created_source.text
    tested_source = administrator.post(
        f"/api/v1/control-plane/query-sources/{source['source_id']}:test",
        headers=mutation_headers(
            csrf_admin,
            **{
                "If-Match": source["etag"],
                "Idempotency-Key": f"p22-real-test-{engine.lower()}",
            },
        ),
    )
    assert tested_source.status_code == 200, tested_source.text
    assert tested_source.json()["qualification_state"] == "AVAILABLE"
    refreshed_source = administrator.get(f"/api/v1/control-plane/query-sources/{source['source_id']}").json()

    created_dataset = administrator.post(
        "/api/v1/control-plane/query-datasets",
        headers=mutation_headers(
            csrf_admin,
            **{"Idempotency-Key": f"p22-real-dataset-{engine.lower()}"},
        ),
        json={
            "source_id": source["source_id"],
            "display_name": f"{engine} shift output",
            "metric_definition": "Finished units by shift",
            "time_scope_description": "Approved reference fixture",
            "freshness_label": "Exact ephemeral database fixture",
            "parameters": [{"name": "shift", "type": "string", "required": True}],
            "output_fields": ["business_date", "shift", "output"],
            "definition": {
                "query_template": (
                    f"SELECT business_date, shift, output FROM {case['relation']} WHERE shift = :shift"
                ),
                "allowed_relations": [case["relation"]],
            },
            "row_limit": 20,
            "timeout_ms": 5_000,
        },
    )
    assert created_dataset.status_code == 201, created_dataset.text
    assert "SELECT business_date" not in created_dataset.text
    dataset = created_dataset.json()
    profile = _create_controlled_query_profile(
        implementation,
        csrf_impl,
        site_id=screen["site_id"],
        suffix=f"real-{engine.lower()}",
    )
    release = _create_query_release(
        implementation,
        csrf_impl,
        administrator,
        csrf_admin,
        screen_id=screen["screen_id"],
        profile_version_id=profile["head_version_id"],
        dataset_version_ids=[dataset["dataset_version_id"]],
        suffix=f"real-{engine.lower()}",
    )
    device, device_headers = _enroll_device(
        app,
        implementation,
        csrf_impl,
        admin_b,
        csrf_b,
        screen_id=screen["screen_id"],
        suffix=f"p22-real-{engine.lower()}",
    )
    _publish_and_ack(
        implementation,
        csrf_impl,
        admin_b,
        csrf_b,
        device,
        device_headers,
        screen_id=screen["screen_id"],
        release=release,
        suffix=f"p22-real-{engine.lower()}",
    )
    started = device.post(
        f"/api/v1/device/query-datasets/{dataset['dataset_id']}:execute",
        headers={
            **device_headers,
            "Idempotency-Key": f"p22-real-query-{engine.lower()}",
        },
        json={"parameters": {"shift": "A"}},
    )
    assert started.status_code == 202, started.text
    result = _poll_execution(
        device,
        f"/api/v1/device/query-executions/{started.json()['execution_id']}",
        headers=device_headers,
    )
    assert result["state"] == "SUCCEEDED", result
    assert result["row_count"] == 2
    assert {row["output"] for row in result["rows"]} == {110, 120}
    assert result["source"]["engine"] == engine
    assert result["source"]["qualification"] == "DEPLOYMENT_LOCAL_AVAILABLE"
    assert refreshed_source["qualification"]["product_certification"] == "UNVERIFIED"

    injection = device.post(
        f"/api/v1/device/query-datasets/{dataset['dataset_id']}:execute",
        headers={
            **device_headers,
            "Idempotency-Key": f"p22-real-injection-{engine.lower()}",
        },
        json={"parameters": {"shift": "A' OR '1'='1"}},
    )
    assert injection.status_code == 202, injection.text
    injection_result = _poll_execution(
        device,
        f"/api/v1/device/query-executions/{injection.json()['execution_id']}",
        headers=device_headers,
    )
    assert injection_result["state"] == "SUCCEEDED"
    assert injection_result["row_count"] == 0
    invariant_check = create_engine(url, poolclass=NullPool, hide_parameters=True)
    try:
        with invariant_check.connect() as connection:
            after_count = connection.execute(
                text(f"SELECT COUNT(*) AS row_count FROM {case['relation']}")
            ).scalar_one()
            after_fields = list(
                connection.execute(text(f"SELECT * FROM {case['relation']} WHERE 1 = 0")).keys()
            )
        assert after_count == before_count
        assert after_fields == before_fields
    finally:
        invariant_check.dispose()

    for _ in range(100):
        status = device.get(
            f"/api/v1/device/query-executions/{started.json()['execution_id']}",
            headers=device_headers,
        )
        assert status.status_code == 200
        if status.json()["state"] == "SUCCEEDED":
            break
        time.sleep(0.01)
