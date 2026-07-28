from __future__ import annotations

import argparse
import os

from app.control_plane.service import ControlPlaneService


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an isolated control-plane browser fixture.")
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    root_key = os.environ.get("CONTROL_PLANE_ROOT_KEY_B64", "")
    password = (
        os.environ.get("P2_2_BROWSER_GATE_PASSWORD", "")
        or os.environ.get("P2_1_BROWSER_GATE_PASSWORD", "")
        or os.environ.get("P1_3_BROWSER_GATE_PASSWORD", "")
        or os.environ.get("P1_2_BROWSER_GATE_PASSWORD", "")
    )
    if not root_key or not password:
        raise SystemExit("Browser-gate key and password must be supplied through the process environment")
    service = ControlPlaneService(args.database, root_key, preview_mode=True)
    result = service.initialize_preview(
        tenant_id="tenant-browser-gate",
        deployment_id="deployment-browser-gate",
        screen_id="screen-trust-fixture",
        identities=[
            {
                "username": "admin-a",
                "display_name": "预览管理员 A",
                "role_id": "platform_admin",
                "password": password,
            },
            {
                "username": "admin-b",
                "display_name": "预览管理员 B",
                "role_id": "platform_admin",
                "password": password,
            },
            {
                "username": "implementation",
                "display_name": "预览实施工程师",
                "role_id": "implementation_engineer",
                "password": password,
            },
            {
                "username": "auditor",
                "display_name": "预览审计员",
                "role_id": "auditor",
                "password": password,
            },
        ],
    )
    print(f"BROWSER_FIXTURE_OK screens={len(result['inventory']['screen_ids'])}")
    print("Credential material was not written to stdout.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
