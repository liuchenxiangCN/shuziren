from __future__ import annotations

import hashlib
import logging
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_control_plane import control_plane as _shared_control_plane


@pytest.fixture()
def p21_error_control_plane(tmp_path: Path) -> tuple[FastAPI, Path]:
    app, _, database_path = _shared_control_plane.__wrapped__(tmp_path)
    return app, database_path


def test_validation_error_does_not_reflect_attacker_controlled_locator(
    p21_error_control_plane: tuple[FastAPI, Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    app, database_path = p21_error_control_plane
    marker_hash = hashlib.sha256(b"p2.1-validation-locator-regression").hexdigest()
    unknown_field = f"unknown_{marker_hash}"
    selection = {
        "enabled": False,
        "primary_provider_id": None,
        "fallback_provider_ids": [],
        "timeout_ms": 1000,
    }
    spec = {
        capability: dict(selection)
        for capability in (
            "dora",
            "knowledge",
            "direct_llm",
            "asr",
            "tts",
            "querying",
            "fvs_control",
        )
    }
    spec["dora"][unknown_field] = "ignored"

    caplog.set_level(logging.DEBUG)
    with TestClient(app, base_url="https://manage.test") as client:
        response = client.post(
            "/api/v1/control-plane/capability-profiles/profile-test/versions",
            headers={
                "If-Match": '"profile-etag"',
                "Idempotency-Key": "validation-locator-test",
            },
            json={"spec": spec},
        )

    assert response.status_code == 422
    assert response.json()["error"]["details"] == [
        {
            "type": "unexpected_field",
            "loc": ["body", "field", "field", "field"],
            "msg": "Unexpected request field",
        }
    ]
    assert marker_hash not in response.text
    assert marker_hash not in "\n".join(record.getMessage() for record in caplog.records)

    with sqlite3.connect(database_path) as connection:
        audit_text = "\n".join(
            str(value)
            for row in connection.execute(
                """
                SELECT event_type, actor_type, actor_id, target_type, target_id,
                    outcome, reason, details_json
                FROM security_audit_events
                ORDER BY sequence
                """
            ).fetchall()
            for value in row
        )
    assert marker_hash not in audit_text
