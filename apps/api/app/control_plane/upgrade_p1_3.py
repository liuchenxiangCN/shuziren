from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

from app.control_plane.service import ControlPlaneService
from app.control_plane.store import MIGRATION_003_VERSION, MIGRATIONS
from app.control_plane.upgrade_preview import copy_sqlite_database


def _verify_accepted_p1_2_source(path: Path) -> None:
    source_uri = f"{path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as connection:
        rows = connection.execute(
            "SELECT version, checksum_sha256 FROM schema_migrations ORDER BY rowid"
        ).fetchall()
        if rows != [(version, checksum) for version, checksum, _ in MIGRATIONS[:2]]:
            raise SystemExit("Source is not an exact accepted P1.2 migration registry")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise SystemExit("Source P1.2 database has foreign-key violations")


def main() -> int:
    parser = argparse.ArgumentParser(description="Upgrade a copied accepted-P1.2 preview database to P1.3.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--backup-root", required=True)
    args = parser.parse_args()
    root_key_b64 = os.environ.get("CONTROL_PLANE_ROOT_KEY_B64", "")
    if not root_key_b64:
        raise SystemExit("CONTROL_PLANE_ROOT_KEY_B64 is required through the process environment")
    source_path = Path(args.source).resolve()
    target_path = Path(args.database).resolve()
    backup_root = Path(args.backup_root).resolve()
    if not source_path.is_file():
        raise SystemExit(f"Accepted P1.2 source is missing: {source_path}")
    if backup_root.exists():
        raise SystemExit(f"Refusing to reuse an existing backup root: {backup_root}")
    _verify_accepted_p1_2_source(source_path)
    copy_sqlite_database(str(source_path), str(target_path))
    service = ControlPlaneService(
        str(target_path),
        root_key_b64,
        preview_mode=True,
        backup_root=backup_root,
    )
    status = service.status()
    if status["migration_version"] != MIGRATION_003_VERSION:
        raise SystemExit("Copied preview did not reach 003_publish_rollback_recovery")
    with service.store.connect() as connection:
        screens = connection.execute(
            "SELECT screen_id FROM screen_instances ORDER BY slug, screen_id"
        ).fetchall()
        metadata = connection.execute(
            "SELECT fixture_screen_id FROM control_plane_metadata WHERE singleton = 1"
        ).fetchone()
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        existing_bindings = connection.execute(
            """
            SELECT desired_release_target_id, applied_release_target_id,
                binding_generation
            FROM runtime_bindings ORDER BY screen_id
            """
        ).fetchall()
    if (
        metadata is None
        or len(screens) != 3
        or screens[0]["screen_id"] != metadata["fixture_screen_id"]
        or violations
        or any(tuple(row) != (None, None, 0) for row in existing_bindings)
    ):
        raise SystemExit("P1.3 copied-preview verification failed")
    print("Copied preview upgraded to 003_publish_rollback_recovery.")
    print(f"Preserved Screen 1 ID: {metadata['fixture_screen_id']}")
    print(f"Inventory screen count: {len(screens)}")
    print("Existing P1.2 runtime bindings remained null-release generation zero.")
    print("Root key and credential material were not written to stdout.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
