from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

from app.control_plane.security import PurposeKeyring
from app.control_plane.service import ControlPlaneService

IDENTITIES = (
    ("admin-a", "预览管理员 A", "platform_admin"),
    ("admin-b", "预览管理员 B", "platform_admin"),
    ("implementation", "预览实施工程师", "implementation_engineer"),
    ("auditor", "预览审计员", "auditor"),
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Explicitly initialize the P1.1 development preview. Never use for production."
    )
    parser.add_argument("--database", required=True)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--tenant-id", default="tenant-preview")
    parser.add_argument("--deployment-id", default="deployment-preview")
    parser.add_argument("--screen-id", default="screen-trust-fixture")
    args = parser.parse_args()

    env_path = Path(args.env_file).resolve()
    database_path = Path(args.database).resolve()
    if env_path.exists():
        raise SystemExit(f"Refusing to overwrite existing preview env file: {env_path}")
    root_key_b64 = PurposeKeyring.generate_root_base64()
    identities = []
    for username, display_name, role_id in IDENTITIES:
        password = getpass.getpass(f"Password for {username} ({display_name}, 15-128 Unicode code points): ")
        confirmation = getpass.getpass(f"Confirm password for {username}: ")
        if password != confirmation:
            raise SystemExit(f"Password confirmation did not match for {username}")
        identities.append(
            {
                "username": username,
                "display_name": display_name,
                "role_id": role_id,
                "password": password,
            }
        )

    service = ControlPlaneService(
        str(database_path),
        root_key_b64,
        preview_mode=True,
    )
    result = service.initialize_preview(
        tenant_id=args.tenant_id,
        deployment_id=args.deployment_id,
        screen_id=args.screen_id,
        identities=identities,
    )
    env_path.write_text(
        "\n".join(
            (
                "# Generated P1.1 development preview settings. Never commit this file.",
                "CONTROL_PLANE_PREVIEW_MODE=true",
                f"CONTROL_PLANE_ROOT_KEY_B64={root_key_b64}",
                "CONTROL_PLANE_DB_PATH=/app/data/control-plane.db",
                'CONTROL_PLANE_ALLOWED_ORIGINS=["http://localhost:18000","http://127.0.0.1:18000"]',
                "",
            )
        ),
        encoding="utf-8",
    )
    try:
        os.chmod(env_path, 0o600)
    except OSError:
        pass
    print("P1.1 development preview initialized.")
    print(f"Database: {database_path}")
    print(f"Environment file: {env_path}")
    print(f"Trust-only screen fixture: {result['fixture_screen_id']}")
    print("Passwords and root key were not written to stdout.")
    print(f"Start with: docker compose --env-file {env_path.name} up --build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
