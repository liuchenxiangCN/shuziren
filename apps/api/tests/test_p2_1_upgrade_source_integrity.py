from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.control_plane import store as store_module
from app.control_plane.security import PurposeKeyring
from app.control_plane.service import ControlPlaneService
from app.control_plane.store import MIGRATION_004_VERSION
from app.control_plane.upgrade_p2_1 import _verify_accepted_p1_3_source

PREVIEW_IDENTITIES = [
    {
        "username": username,
        "display_name": username,
        "role_id": role_id,
        "password": "P13-Upgrade-Integrity!42",
    }
    for username, role_id in (
        ("admin-a", "platform_admin"),
        ("admin-b", "platform_admin"),
        ("implementation", "implementation_engineer"),
        ("auditor", "auditor"),
    )
]


def _create_exact_p1_3_source(
    path: Path,
    root_key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    full_migrations = store_module.MIGRATIONS
    with monkeypatch.context() as patch:
        patch.setattr(store_module, "MIGRATIONS", full_migrations[:3])
        service = ControlPlaneService(
            str(path),
            root_key,
            preview_mode=True,
        )
        service.initialize_preview(
            tenant_id="tenant-p21-upgrade-integrity",
            deployment_id="deployment-p21-upgrade-integrity",
            screen_id="screen-p21-upgrade-integrity",
            identities=PREVIEW_IDENTITIES,
        )


def _online_copy(source_path: Path, target_path: Path) -> None:
    source = sqlite3.connect(source_path)
    target = sqlite3.connect(target_path)
    try:
        source.backup(target)
        target.commit()
    finally:
        target.close()
        source.close()


def test_exact_p1_3_upgrade_and_repeated_004_initialization_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_path = tmp_path / "accepted-p1-3.db"
    root_key = PurposeKeyring.generate_root_base64()
    _create_exact_p1_3_source(source_path, root_key, monkeypatch)

    _verify_accepted_p1_3_source(source_path)
    with monkeypatch.context() as patch:
        patch.setattr(store_module, "MIGRATIONS", store_module.MIGRATIONS[:4])
        upgraded = ControlPlaneService(
            str(source_path),
            root_key,
            preview_mode=True,
        )
        assert upgraded.status()["migration_version"] == MIGRATION_004_VERSION

        repeated = ControlPlaneService(
            str(source_path),
            root_key,
            preview_mode=True,
        )
        assert repeated.status()["migration_version"] == MIGRATION_004_VERSION

        fresh = ControlPlaneService(
            str(tmp_path / "fresh-p2-1.db"),
            root_key,
            preview_mode=True,
        )
        assert fresh.status()["migration_version"] == MIGRATION_004_VERSION


@pytest.mark.parametrize(
    "mutation",
    (
        "weaken_immutable_trigger",
        "remove_security_index",
        "add_unknown_schema_object",
    ),
)
def test_p1_3_source_schema_integrity_fails_closed_before_004(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    accepted_path = tmp_path / "accepted-p1-3.db"
    tampered_path = tmp_path / f"{mutation}.db"
    root_key = PurposeKeyring.generate_root_base64()
    _create_exact_p1_3_source(accepted_path, root_key, monkeypatch)
    _online_copy(accepted_path, tampered_path)

    connection = sqlite3.connect(tampered_path)
    try:
        if mutation == "weaken_immutable_trigger":
            connection.execute("DROP TRIGGER security_audit_events_no_update")
            connection.execute(
                """
                CREATE TRIGGER security_audit_events_no_update
                BEFORE UPDATE ON security_audit_events
                BEGIN
                    SELECT 1;
                END
                """
            )
        elif mutation == "remove_security_index":
            connection.execute("DROP INDEX idx_high_risk_state")
        else:
            connection.execute(
                """
                CREATE TABLE unexpected_security_shadow (
                    record_id TEXT PRIMARY KEY
                )
                """
            )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(SystemExit, match="schema object integrity"):
        _verify_accepted_p1_3_source(tampered_path)
    with pytest.raises(RuntimeError, match="schema object integrity"):
        ControlPlaneService(
            str(tampered_path),
            root_key,
            preview_mode=True,
        )

    with sqlite3.connect(tampered_path) as connection:
        applied_versions = connection.execute(
            "SELECT version FROM schema_migrations ORDER BY rowid"
        ).fetchall()
    assert applied_versions == [(version,) for version, _, _ in store_module.MIGRATIONS[:3]]
