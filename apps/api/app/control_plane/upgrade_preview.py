from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

from app.control_plane.service import ControlPlaneService
from app.control_plane.store import MIGRATION_002_VERSION


def copy_sqlite_database(source: str, target: str) -> None:
    source_path = Path(source).resolve()
    target_path = Path(target).resolve()
    if target_path.exists():
        raise FileExistsError(f"Refusing to overwrite copied preview database: {target_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"{source_path.as_uri()}?mode=ro"
    with (
        sqlite3.connect(source_uri, uri=True) as source_connection,
        sqlite3.connect(target_path) as target_connection,
    ):
        source_connection.backup(target_connection)


def main() -> int:
    parser = argparse.ArgumentParser(description="Upgrade a copied accepted-P1.1 preview database to P1.2.")
    parser.add_argument("--database", required=True)
    parser.add_argument("--source")
    args = parser.parse_args()
    root_key_b64 = os.environ.get("CONTROL_PLANE_ROOT_KEY_B64", "")
    if not root_key_b64:
        raise SystemExit("CONTROL_PLANE_ROOT_KEY_B64 is required through the process environment")
    if args.source:
        copy_sqlite_database(args.source, args.database)
    service = ControlPlaneService(
        args.database,
        root_key_b64,
        preview_mode=True,
    )
    status = service.status()
    if status["migration_version"] != MIGRATION_002_VERSION:
        raise SystemExit("Copied preview did not reach 002_three_screen_inventory")
    with service.store.connect() as connection:
        screens = connection.execute(
            "SELECT screen_id FROM screen_instances ORDER BY slug, screen_id"
        ).fetchall()
        metadata = connection.execute(
            "SELECT fixture_screen_id FROM control_plane_metadata WHERE singleton = 1"
        ).fetchone()
    if metadata is None or len(screens) < 3 or screens[0]["screen_id"] != metadata["fixture_screen_id"]:
        raise SystemExit("P1.2 copied-preview verification failed")
    print("Copied preview upgraded to 002_three_screen_inventory.")
    print(f"Preserved Screen 1 ID: {metadata['fixture_screen_id']}")
    print(f"Inventory screen count: {len(screens)}")
    print("Root key and credential material were not written to stdout.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
