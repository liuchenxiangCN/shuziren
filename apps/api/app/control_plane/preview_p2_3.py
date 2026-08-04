from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import io
import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.control_plane.errors import ControlPlaneError
from app.control_plane.preview import IDENTITIES
from app.control_plane.router import (
    control_plane_error_handler,
    router,
    sanitized_validation_errors,
)
from app.control_plane.security import PurposeKeyring
from app.control_plane.service import ControlPlaneService
from app.control_plane.store import MIGRATION_005_VERSION

ORIGIN = "https://manage.test"
DEVICE_ORIGIN = "https://device.test"

# Three screens on one site with distinct capability profiles. The third
# profile carries the permission-equivalent tts fallback pair
# mock_tts -> browser_text_fallback so the FALLBACK_RESOLVED drill outcome is
# demonstrable in the preview.
SCREEN_PLANS = (
    {
        "suffix": "text",
        "name": "P2.3 text-only query screen",
        "preset": "text_only",
        "tts_fallback": False,
    },
    {
        "suffix": "voice",
        "name": "P2.3 mock-voice query screen",
        "preset": "mock_voice",
        "tts_fallback": False,
    },
    {
        "suffix": "fallback",
        "name": "P2.3 mock-presenter fallback screen",
        "preset": "mock_presenter",
        "tts_fallback": True,
    },
)
DATASET_PLANS = (
    {"suffix": "normal", "display_name": "Shift output normal", "timeout_ms": 5_000},
    {"suffix": "slow", "display_name": "Shift output slow long-timeout", "timeout_ms": 120_000},
)


def _workbook_base64() -> str:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Metrics"
    worksheet.append(["business_date", "shift", "output", "quality_rate"])
    worksheet.append(["2026-07-28", "A", 120, 0.98])
    worksheet.append(["2026-07-28", "B", 95, 0.96])
    worksheet.append(["2026-07-27", "A", 110, 0.97])
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return base64.b64encode(output.getvalue()).decode("ascii")


def _login(app: FastAPI, username: str, password: str) -> tuple[TestClient, str]:
    client = TestClient(app, base_url=ORIGIN)
    response = client.post(
        "/api/v1/control-plane/auth/sessions",
        headers={"Origin": ORIGIN},
        json={"username": username, "password": password},
    )
    if response.status_code != 200:
        raise SystemExit(f"Preview fixture login failed for {username}: {response.text}")
    return client, response.headers["x-csrf-token"]


def _mutation_headers(csrf: str, **extra: str) -> dict[str, str]:
    return {"Origin": ORIGIN, "X-CSRF-Token": csrf, **extra}


def _test_avatar_payload(
    site_id: str, version: str, label: str, background: str, accent: str
) -> dict[str, Any]:
    preview = {
        "schema_version": "p3_test_avatar_preview_v1",
        "label": label,
        "background": background,
        "accent": accent,
    }
    content = json.dumps(preview, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    digest = hashlib.sha256(content).hexdigest()
    return {
        "site_id": site_id,
        "manifest": {
            "schema_version": "p3_avatar_package_v1",
            "avatar_id": "test-guide",
            "version": version,
            "display_name": "P3 test guide",
            "avatar_type": "test",
            "renderer_type": "test_card",
            "renderer_version_range": "^1.0.0",
            "entry_asset": "avatar.json",
            "resources": [
                {
                    "path": "avatar.json",
                    "media_type": "application/vnd.shuziren.test-avatar+json",
                    "size_bytes": len(content),
                    "sha256": digest,
                }
            ],
            "states": {
                "idle": "avatar.json",
                "listening": "avatar.json",
                "thinking": "avatar.json",
                "speaking": "avatar.json",
                "error": "avatar.json",
            },
            "lip_sync_mode": "volume",
            "requirements": {
                "browser": "test-contract",
                "gpu": "not-required",
                "vram_mb": 0,
                "memory_mb": 64,
            },
            "canvas": {
                "aspect_ratio": "1:1",
                "transparent_background": False,
                "safe_area_percent": 8,
            },
            "license": {
                "kind": "TEST_ONLY",
                "rights_holder": "Generated P3 preview fixture",
                "expires_at": None,
                "usage_scope": "DEVELOPMENT_PREVIEW",
            },
        },
        "files": [
            {
                "path": "avatar.json",
                "content_base64": base64.b64encode(content).decode("ascii"),
            }
        ],
    }


def _seed_p3_avatar_assets(
    implementation: TestClient,
    csrf: str,
    screens: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    plans = (
        ("1.0.0", "P3 teal test guide", "#E8F5F0", "#147D64"),
        ("2.0.0", "P3 gold test guide", "#FFF5D8", "#A56A00"),
    )
    versions = []
    for index, (version, label, background, accent) in enumerate(plans, start=1):
        created = implementation.post(
            "/api/v1/control-plane/avatar-packages",
            headers=_mutation_headers(
                csrf,
                **{"Idempotency-Key": f"p3-preview-avatar-create-{index}"},
            ),
            json=_test_avatar_payload(screens[0]["site_id"], version, label, background, accent),
        )
        if created.status_code != 201:
            raise SystemExit(f"P3 preview avatar creation failed: {created.text}")
        versions.append(created.json())

    def prefetch_and_publish(screen: dict[str, Any], version: dict[str, Any], suffix: str) -> None:
        screen_id = screen["screen_id"]
        prefetched = implementation.post(
            f"/api/v1/control-plane/screen-instances/{screen_id}/"
            f"avatar-package-versions/{version['package_version_id']}:prefetch",
            headers=_mutation_headers(
                csrf,
                **{"Idempotency-Key": f"p3-preview-avatar-prefetch-{suffix}"},
            ),
            json={"expected_content_hash": version["content_hash"]},
        )
        if prefetched.status_code != 200 or prefetched.json()["outcome"] != "READY":
            raise SystemExit(f"P3 preview avatar prefetch failed: {prefetched.text}")
        binding = implementation.get(f"/api/v1/control-plane/screen-instances/{screen_id}/avatar-binding")
        if binding.status_code != 200:
            raise SystemExit(f"P3 preview avatar binding fetch failed: {binding.text}")
        current = binding.json()
        published = implementation.post(
            f"/api/v1/control-plane/screen-instances/{screen_id}/avatar-publications",
            headers=_mutation_headers(
                csrf,
                **{
                    "Idempotency-Key": f"p3-preview-avatar-publish-{suffix}",
                    "If-Match": current["etag"],
                },
            ),
            json={
                "package_version_id": version["package_version_id"],
                "expected_binding_generation": current["binding_generation"],
                "reason": f"publish P3 preview avatar {suffix}",
            },
        )
        if published.status_code != 200:
            raise SystemExit(f"P3 preview avatar publication failed: {published.text}")

    prefetch_and_publish(screens[0], versions[0], "screen-one-v1")
    prefetch_and_publish(screens[1], versions[0], "screen-two-v1")
    prefetch_and_publish(screens[1], versions[1], "screen-two-v2")
    return versions


def _request_action(
    client: TestClient,
    csrf: str,
    path: str,
    payload: dict[str, Any],
    key: str,
    *,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    headers = _mutation_headers(csrf, **{"Idempotency-Key": key})
    headers.update(extra_headers or {})
    response = client.post(path, headers=headers, json=payload)
    if response.status_code != 202:
        raise SystemExit(f"Preview fixture high-risk request failed: {response.text}")
    return response.json()


def _approve_action(client: TestClient, csrf: str, action: dict[str, Any], *, key: str) -> None:
    response = client.post(
        f"/api/v1/control-plane/high-risk-actions/{action['high_risk_action_id']}:approve",
        headers=_mutation_headers(
            csrf,
            **{
                "Idempotency-Key": key,
                "If-Match": action["etag"],
            },
        ),
        json={
            "expected_request_digest": action["request_digest"],
            "reason": "independent preview approval",
        },
    )
    if response.status_code != 200:
        raise SystemExit(f"Preview fixture high-risk approval failed: {response.text}")


def _create_excel_source(client: TestClient, csrf: str, *, site_id: str) -> dict[str, Any]:
    created = client.post(
        "/api/v1/control-plane/query-sources",
        headers=_mutation_headers(csrf, **{"Idempotency-Key": "p23-preview-source-create"}),
        json={
            "site_id": site_id,
            "display_name": "P2.3 reference workbook",
            "engine": "EXCEL",
            "read_only_account_confirmed": True,
            "excel_file_name": "reference.xlsx",
            "excel_workbook_base64": _workbook_base64(),
        },
    )
    if created.status_code != 201:
        raise SystemExit(f"Preview fixture source creation failed: {created.text}")
    source = created.json()
    tested = client.post(
        f"/api/v1/control-plane/query-sources/{source['source_id']}:test",
        headers=_mutation_headers(
            csrf,
            **{
                "If-Match": source["etag"],
                "Idempotency-Key": "p23-preview-source-test",
            },
        ),
    )
    if tested.status_code != 200 or tested.json()["qualification_state"] != "AVAILABLE":
        raise SystemExit(f"Preview fixture source qualification failed: {tested.text}")
    fetched = client.get(f"/api/v1/control-plane/query-sources/{source['source_id']}")
    if fetched.status_code != 200:
        raise SystemExit(f"Preview fixture source fetch failed: {fetched.text}")
    return fetched.json()


def _create_dataset(
    client: TestClient,
    csrf: str,
    *,
    source_id: str,
    suffix: str,
    display_name: str,
    timeout_ms: int,
) -> dict[str, Any]:
    created = client.post(
        "/api/v1/control-plane/query-datasets",
        headers=_mutation_headers(csrf, **{"Idempotency-Key": f"p23-preview-dataset-create-{suffix}"}),
        json={
            "source_id": source_id,
            "display_name": display_name,
            "metric_definition": "Finished units by business date and shift",
            "time_scope_description": "Rows in the approved reference workbook",
            "freshness_label": "Reference fixture generated for P2.3",
            "parameters": [
                {"name": "shift", "type": "string", "required": True},
            ],
            "output_fields": [
                "business_date",
                "shift",
                "output",
                "quality_rate",
            ],
            "definition": {
                "worksheet": "Metrics",
                "parameter_columns": {"shift": "shift"},
            },
            "row_limit": 20,
            "timeout_ms": timeout_ms,
        },
    )
    if created.status_code != 201:
        raise SystemExit(f"Preview fixture dataset creation failed: {created.text}")
    return created.json()


def _create_profile(
    client: TestClient,
    csrf: str,
    *,
    site_id: str,
    suffix: str,
    name: str,
    preset: str,
    tts_fallback: bool,
) -> dict[str, Any]:
    created = client.post(
        "/api/v1/control-plane/capability-profiles",
        headers=_mutation_headers(csrf, **{"Idempotency-Key": f"p23-preview-profile-create-{suffix}"}),
        json={
            "site_id": site_id,
            "name": name,
            "description": "P2.3 preview capability profile",
            "source_preset_id": preset,
        },
    )
    if created.status_code != 201:
        raise SystemExit(f"Preview fixture profile creation failed: {created.text}")
    profile = created.json()
    spec = profile["head_version"]["spec"]
    spec["querying"] = {
        "enabled": True,
        "primary_provider_id": "controlled_query",
        "fallback_provider_ids": [],
        "timeout_ms": 5_000,
    }
    if tts_fallback:
        spec["tts"] = {
            "enabled": True,
            "primary_provider_id": "mock_tts",
            "fallback_provider_ids": ["browser_text_fallback"],
            "timeout_ms": 5_000,
        }
    versioned = client.post(
        f"/api/v1/control-plane/capability-profiles/{profile['profile_id']}/versions",
        headers=_mutation_headers(
            csrf,
            **{
                "If-Match": profile["etag"],
                "Idempotency-Key": f"p23-preview-profile-version-{suffix}",
            },
        ),
        json={"spec": spec},
    )
    if versioned.status_code != 201:
        raise SystemExit(f"Preview fixture profile version failed: {versioned.text}")
    return versioned.json()


def _create_release(
    implementation: TestClient,
    csrf_impl: str,
    approver: TestClient,
    csrf_approver: str,
    *,
    screen_id: str,
    profile_version_id: str,
    dataset_version_ids: list[str],
    suffix: str,
) -> dict[str, Any]:
    created = implementation.post(
        "/api/v1/control-plane/config-drafts",
        headers=_mutation_headers(csrf_impl, **{"Idempotency-Key": f"p23-preview-draft-create-{suffix}"}),
        json={
            "target_type": "SCREEN",
            "target_id": screen_id,
            "schema_version": "p1_screen_config_v1",
        },
    )
    if created.status_code != 201:
        raise SystemExit(f"Preview fixture draft creation failed: {created.text}")
    draft = created.json()
    replaced = implementation.put(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}/spec",
        headers=_mutation_headers(csrf_impl, **{"If-Match": draft["etag"]}),
        json={
            "welcome_text": f"P2.3 preview screen {suffix}",
            "fvs_binding_ref": f"https://fvs.example.test/p2-3/{suffix}",
        },
    )
    if replaced.status_code != 200:
        raise SystemExit(f"Preview fixture draft spec failed: {replaced.text}")
    draft = replaced.json()
    assigned_profile = implementation.put(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}/capability-profile",
        headers=_mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p23-preview-profile-assign-{suffix}",
            },
        ),
        json={"profile_version_id": profile_version_id},
    )
    if assigned_profile.status_code != 200:
        raise SystemExit(f"Preview fixture profile assignment failed: {assigned_profile.text}")
    draft = assigned_profile.json()
    assigned_query = implementation.put(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}/query-datasets",
        headers=_mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p23-preview-query-assign-{suffix}",
            },
        ),
        json={"dataset_version_ids": dataset_version_ids},
    )
    if assigned_query.status_code != 200:
        raise SystemExit(f"Preview fixture query assignment failed: {assigned_query.text}")
    draft = assigned_query.json()
    validated = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:validate",
        headers=_mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p23-preview-validate-{suffix}",
            },
        ),
    )
    if validated.status_code != 200 or validated.json()["validation"]["outcome"] != "VALID":
        raise SystemExit(f"Preview fixture draft validation failed: {validated.text}")
    draft = validated.json()
    previewed = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:preview",
        headers=_mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p23-preview-preview-{suffix}",
            },
        ),
    )
    if previewed.status_code != 200:
        raise SystemExit(f"Preview fixture draft preview failed: {previewed.text}")
    draft = previewed.json()
    submitted = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:submit-for-approval",
        headers=_mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p23-preview-submit-{suffix}",
            },
        ),
    )
    if submitted.status_code != 200:
        raise SystemExit(f"Preview fixture draft submission failed: {submitted.text}")
    draft = submitted.json()
    approved = approver.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:approve",
        headers=_mutation_headers(
            csrf_approver,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p23-preview-approve-{suffix}",
            },
        ),
        json={"reason": "independent P2.3 preview approval"},
    )
    if approved.status_code != 200:
        raise SystemExit(f"Preview fixture draft approval failed: {approved.text}")
    draft = approved.json()
    released = implementation.post(
        f"/api/v1/control-plane/config-drafts/{draft['draft_id']}:release",
        headers=_mutation_headers(
            csrf_impl,
            **{
                "If-Match": draft["etag"],
                "Idempotency-Key": f"p23-preview-release-{suffix}",
            },
        ),
        json={"reason": "create immutable P2.3 preview release"},
    )
    if released.status_code != 201:
        raise SystemExit(f"Preview fixture release failed: {released.text}")
    return released.json()


def _publish_and_ack(
    app: FastAPI,
    implementation: TestClient,
    csrf_impl: str,
    approver: TestClient,
    csrf_approver: str,
    *,
    screen_id: str,
    release: dict[str, Any],
    suffix: str,
) -> None:
    payload = {"reason": f"enroll P2.3 preview device {suffix}"}
    action = _request_action(
        implementation,
        csrf_impl,
        f"/api/v1/control-plane/screen-instances/{screen_id}/device-enrollments",
        payload,
        f"p23-preview-enroll-request-{suffix}",
    )
    _approve_action(approver, csrf_approver, action, key=f"p23-preview-enroll-approve-{suffix}")
    issued = implementation.post(
        f"/api/v1/control-plane/screen-instances/{screen_id}/device-enrollments",
        headers=_mutation_headers(
            csrf_impl,
            **{
                "Idempotency-Key": f"p23-preview-enroll-execute-{suffix}",
                "High-Risk-Action-ID": action["high_risk_action_id"],
            },
        ),
        json=payload,
    )
    if issued.status_code != 201:
        raise SystemExit(f"Preview fixture device enrollment failed: {issued.text}")
    device = TestClient(app, base_url=DEVICE_ORIGIN)
    claimed = device.post(
        "/api/v1/device/enrollments:claim",
        headers={"Idempotency-Key": f"p23-preview-device-claim-{suffix}"},
        json={"enrollment_token": issued.json()["enrollment_token"]},
    )
    if claimed.status_code != 200:
        raise SystemExit(f"Preview fixture device claim failed: {claimed.text}")
    device_headers = {"Authorization": f"DeviceCredential {claimed.json()['credential']}"}
    binding = implementation.get(f"/api/v1/control-plane/screen-instances/{screen_id}/runtime-binding")
    if binding.status_code != 200:
        raise SystemExit(f"Preview fixture runtime binding fetch failed: {binding.text}")
    binding = binding.json()
    target = release["targets"][0]
    publish_payload = {
        "release_id": release["release_id"],
        "release_target_id": target["release_target_id"],
        "expected_binding_generation": binding["binding_generation"],
        "reason": f"publish P2.3 preview release {suffix}",
    }
    publish_action = _request_action(
        implementation,
        csrf_impl,
        f"/api/v1/control-plane/screen-instances/{screen_id}/publications",
        publish_payload,
        f"p23-preview-publish-request-{suffix}",
        extra_headers={"If-Match": binding["etag"]},
    )
    _approve_action(approver, csrf_approver, publish_action, key=f"p23-preview-publish-approve-{suffix}")
    published = implementation.post(
        f"/api/v1/control-plane/screen-instances/{screen_id}/publications",
        headers=_mutation_headers(
            csrf_impl,
            **{
                "If-Match": binding["etag"],
                "Idempotency-Key": f"p23-preview-publish-execute-{suffix}",
                "High-Risk-Action-ID": publish_action["high_risk_action_id"],
            },
        ),
        json=publish_payload,
    )
    if published.status_code != 201:
        raise SystemExit(f"Preview fixture publication failed: {published.text}")
    current = device.get("/api/v1/device/config-releases/current", headers=device_headers)
    if current.status_code != 200:
        raise SystemExit(f"Preview fixture current release fetch failed: {current.text}")
    acknowledged = device.post(
        f"/api/v1/device/config-releases/{target['release_target_id']}:ack",
        headers={
            **device_headers,
            "Idempotency-Key": f"p23-preview-ack-{suffix}",
        },
        json={
            "binding_generation": current.json()["binding_generation"],
            "content_hash": target["content_hash"],
        },
    )
    if acknowledged.status_code != 200:
        raise SystemExit(f"Preview fixture release acknowledgement failed: {acknowledged.text}")


def _collect_identities() -> list[dict[str, str]]:
    shared_password = os.environ.get("P2_3_PREVIEW_PASSWORD", "")
    identities = []
    for username, display_name, role_id in IDENTITIES:
        if shared_password:
            password = shared_password
        else:
            password = getpass.getpass(
                f"Password for {username} ({display_name}, 15-128 Unicode code points): "
            )
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
    return identities


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize the P2.3 concurrent-and-failure-isolation development preview. "
        "Never use for production."
    )
    parser.add_argument("--database", required=True)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--backup-root", required=True)
    parser.add_argument("--tenant-id", default="tenant-preview")
    parser.add_argument("--deployment-id", default="deployment-preview")
    parser.add_argument("--screen-id", default="screen-trust-fixture")
    parser.add_argument("--container-database", default="/app/data/control-plane-p2-3.db")
    parser.add_argument(
        "--container-backup-root",
        default="/app/data/control-plane-p2-3-backups",
    )
    parser.add_argument(
        "--seed-p3",
        action="store_true",
        help="Also seed the test-only P3 AvatarPackage switching fixture.",
    )
    args = parser.parse_args()

    env_path = Path(args.env_file).resolve()
    database_path = Path(args.database).resolve()
    backup_root = Path(args.backup_root).resolve()
    if env_path.exists() or database_path.exists() or backup_root.exists():
        raise SystemExit("Refusing to overwrite an existing P2.3 env, database or backup root")

    root_key_b64 = os.environ.get("CONTROL_PLANE_ROOT_KEY_B64", "") or PurposeKeyring.generate_root_base64()
    identities = _collect_identities()

    service = ControlPlaneService(
        str(database_path),
        root_key_b64,
        preview_mode=True,
        backup_root=backup_root,
    )
    service.initialize_preview(
        tenant_id=args.tenant_id,
        deployment_id=args.deployment_id,
        screen_id=args.screen_id,
        identities=identities,
    )
    with service.store.connect() as connection:
        migration_005 = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (MIGRATION_005_VERSION,),
        ).fetchone()
    if migration_005 is None:
        raise SystemExit("P2.3 preview did not preserve migration 005")

    app = FastAPI()
    app.state.control_plane_service = service
    app.state.control_plane_allowed_origins = (ORIGIN,)
    app.include_router(router)
    app.add_exception_handler(ControlPlaneError, control_plane_error_handler)

    async def validation_handler(_, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "details": sanitized_validation_errors(exc)}},
        )

    app.add_exception_handler(RequestValidationError, validation_handler)

    passwords = {identity["username"]: identity["password"] for identity in identities}
    implementation, csrf_impl = _login(app, "implementation", passwords["implementation"])
    admin_a, csrf_a = _login(app, "admin-a", passwords["admin-a"])
    admin_b, csrf_b = _login(app, "admin-b", passwords["admin-b"])

    screens_response = implementation.get("/api/v1/control-plane/screen-instances")
    if screens_response.status_code != 200:
        raise SystemExit(f"Preview fixture screen listing failed: {screens_response.text}")
    screens = screens_response.json()["items"]
    if len(screens) < len(SCREEN_PLANS):
        raise SystemExit("P2.3 preview inventory did not provide three screens")
    site_id = screens[0]["site_id"]

    source = _create_excel_source(implementation, csrf_impl, site_id=site_id)
    datasets = [
        _create_dataset(
            implementation,
            csrf_impl,
            source_id=source["source_id"],
            suffix=plan["suffix"],
            display_name=plan["display_name"],
            timeout_ms=plan["timeout_ms"],
        )
        for plan in DATASET_PLANS
    ]
    dataset_version_ids = [dataset["dataset_version_id"] for dataset in datasets]

    published = []
    for plan, screen in zip(SCREEN_PLANS, screens, strict=True):
        profile = _create_profile(
            implementation,
            csrf_impl,
            site_id=site_id,
            suffix=plan["suffix"],
            name=plan["name"],
            preset=plan["preset"],
            tts_fallback=plan["tts_fallback"],
        )
        release = _create_release(
            implementation,
            csrf_impl,
            admin_a,
            csrf_a,
            screen_id=screen["screen_id"],
            profile_version_id=profile["head_version_id"],
            dataset_version_ids=dataset_version_ids,
            suffix=plan["suffix"],
        )
        _publish_and_ack(
            app,
            implementation,
            csrf_impl,
            admin_b,
            csrf_b,
            screen_id=screen["screen_id"],
            release=release,
            suffix=plan["suffix"],
        )
        published.append(
            {
                "screen_id": screen["screen_id"],
                "profile_name": plan["name"],
                "preset": plan["preset"],
            }
        )

    avatar_versions = _seed_p3_avatar_assets(implementation, csrf_impl, screens) if args.seed_p3 else []

    env_path.write_text(
        "\n".join(
            (
                "# Generated P2.3 development preview settings. Never commit this file.",
                "CONTROL_PLANE_PREVIEW_MODE=true",
                f"CONTROL_PLANE_ROOT_KEY_B64={root_key_b64}",
                f"CONTROL_PLANE_DB_PATH={args.container_database}",
                f"CONTROL_PLANE_BACKUP_ROOT={args.container_backup_root}",
                "SESSION_LOG_RETENTION_DAYS=3",
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
    print("P2.3 concurrent-and-failure-isolation development preview initialized.")
    print(f"Database: {database_path}")
    print(f"Backup root: {backup_root}")
    print(f"Environment file: {env_path}")
    print(f"Site ID: {site_id}")
    print(f"QuerySource ID: {source['source_id']}")
    for dataset, plan in zip(datasets, DATASET_PLANS, strict=True):
        print(
            f"Dataset ID: {dataset['dataset_id']} ({plan['display_name']}, timeout_ms={plan['timeout_ms']})"
        )
    for item in published:
        print(f"Screen ID: {item['screen_id']} ({item['profile_name']}, preset={item['preset']})")
    if avatar_versions:
        print(
            "P3 test-only AvatarPackage versions seeded: "
            + ", ".join(version["version"] for version in avatar_versions)
        )
    print("All three screens are published and acknowledged; the fallback screen resolves")
    print("tts drills through mock_tts -> browser_text_fallback (permission-equivalent).")
    print("Passwords and root key were not written to stdout.")
    print("Local API: scripts\\start-p2-3-local-api.ps1")
    print("Local web: cd apps\\web; pnpm dev")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
