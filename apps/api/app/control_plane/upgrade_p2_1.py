from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

from app.control_plane.service import ControlPlaneService
from app.control_plane.store import (
    MIGRATION_004_VERSION,
    MIGRATIONS,
    ControlPlaneStore,
)
from app.control_plane.upgrade_preview import copy_sqlite_database


def _verify_accepted_p1_3_source(path: Path) -> None:
    source_uri = f"{path.resolve().as_uri()}?mode=ro"
    try:
        with sqlite3.connect(source_uri, uri=True) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT version, checksum_sha256 FROM schema_migrations ORDER BY rowid"
            ).fetchall()
            if [(row["version"], row["checksum_sha256"]) for row in rows] != [
                (version, checksum) for version, checksum, _ in MIGRATIONS[:3]
            ]:
                raise SystemExit("Source is not an exact accepted P1.3 migration registry")
            ControlPlaneStore.validate_schema_object_integrity(
                connection,
                MIGRATIONS[:3],
            )
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise SystemExit("Source P1.3 database has foreign-key violations")
            if connection.execute("SELECT COUNT(*) FROM runtime_bindings").fetchone()[0] != 3:
                raise SystemExit("Source P1.3 database lacks the accepted three-screen binding baseline")
    except (RuntimeError, sqlite3.DatabaseError) as exc:
        raise SystemExit("Source P1.3 schema object integrity verification failed") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upgrade an online copy of the accepted P1.3 preview database to P2.1."
    )
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
        raise SystemExit(f"Accepted P1.3 source is missing: {source_path}")
    if backup_root.exists():
        raise SystemExit(f"Refusing to reuse an existing backup root: {backup_root}")
    _verify_accepted_p1_3_source(source_path)
    copy_sqlite_database(str(source_path), str(target_path))
    service = ControlPlaneService(
        str(target_path),
        root_key_b64,
        preview_mode=True,
        backup_root=backup_root,
    )
    status = service.status()
    if status["migration_version"] != MIGRATION_004_VERSION:
        raise SystemExit("Copied preview did not reach 004_capability_profiles")
    with service.store.connect() as connection:
        screens = connection.execute(
            "SELECT screen_id FROM screen_instances ORDER BY slug, screen_id"
        ).fetchall()
        metadata = connection.execute(
            "SELECT fixture_screen_id FROM control_plane_metadata WHERE singleton = 1"
        ).fetchone()
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        profile_count = connection.execute("SELECT COUNT(*) FROM capability_profiles").fetchone()[0]
        version_count = connection.execute("SELECT COUNT(*) FROM capability_profile_versions").fetchone()[0]
        snapshot_count = connection.execute(
            "SELECT COUNT(*) FROM release_target_capability_snapshots"
        ).fetchone()[0]
    if (
        metadata is None
        or len(screens) != 3
        or screens[0]["screen_id"] != metadata["fixture_screen_id"]
        or violations
        or profile_count
        or version_count
        or snapshot_count
    ):
        raise SystemExit("P2.1 copied-preview verification failed")
    print("Copied preview upgraded to 004_capability_profiles.")
    print(f"Preserved Screen 1 ID: {metadata['fixture_screen_id']}")
    print(f"Inventory screen count: {len(screens)}")
    print("Capability profile, version and release-snapshot tables begin empty.")
    print("Root key and credential material were not written to stdout.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
