from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import sqlite3
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from cryptography.exceptions import InvalidTag

from app.control_plane.errors import ControlPlaneError
from app.control_plane.p2_1 import (
    CAPABILITY_KEYS,
    PRESETS,
    PROFILE_SCHEMA_VERSION,
    PROFILE_STATES,
    PROVIDER_REGISTRY_HASH,
    PROVIDER_REGISTRY_VERSION,
    P21ControlPlane,
)
from app.control_plane.security import Ciphertext, PurposeKeyring, canonical_json
from app.control_plane.store import LOGICAL_SCHEMA_VERSION, MIGRATIONS, ControlPlaneStore

BACKUP_MANIFEST_SCHEMA = "p1_backup_manifest_v1"
BACKUP_AAD_SCHEMA = "p1_backup_aad_v1"
BACKUP_PURPOSE = "BACKUP_RECOVERY_ENCRYPTION"
BACKUP_ENTRIES = {
    "manifest.json",
    "payload.aes256gcm",
    "checksums.sha256",
    "verification.json",
}
PAYLOAD_ENTRIES = {"control-plane.logical.ndjson", "embedded-native.snapshot"}
P1_CONFIG_SCHEMA_VERSION = "p1_screen_config_v1"
P1_CONFIG_FIELDS = {"welcome_text", "fvs_binding_ref"}


class BackupIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class VerifiedSnapshot:
    manifest: dict[str, Any]
    manifest_hash: str
    ciphertext_hash: str
    native_snapshot: bytes
    logical_export: bytes
    safe_row_counts: dict[str, int]


class BackupManager:
    def __init__(
        self,
        store: ControlPlaneStore,
        keys: PurposeKeyring,
        backup_root: str | Path,
    ) -> None:
        self.store = store
        self.keys = keys
        self.backup_root = Path(backup_root).resolve()

    def storage_profile(self) -> dict[str, Any]:
        live_path = self.store.path.resolve()
        root = self.backup_root
        return {
            "engine": "SQLITE",
            "logical_schema_version": LOGICAL_SCHEMA_VERSION,
            "migration_version": MIGRATIONS[-1][0],
            "journal_mode": "WAL",
            "synchronous": "FULL",
            "backup_backend": "ENCRYPTED_HASHED_FILESYSTEM_BUNDLE",
            "backup_root_configured": True,
            "backup_root_distinct_from_live_database": root != live_path,
            "same_device_development_warning": True,
            "production_recovery_topology_verified": False,
            "default_schedule": "HOURLY_TARGET_NOT_SCHEDULED_IN_P1_3_PREVIEW",
            "retention": {"hourly": 24, "daily": 7, "weekly": 4},
            "runtime_detail_days_default": 3,
            "rpo_target": "UNVERIFIED",
            "rto_target": "UNVERIFIED",
        }

    def create_bundle(
        self,
        *,
        backup_id: str,
        tenant_id: str,
        deployment_id: str,
        created_at: float,
    ) -> dict[str, Any]:
        started = perf_counter()
        self._ensure_safe_root()
        bundle_name = f"backup-{backup_id}"
        final_dir = self.backup_root / bundle_name
        if final_dir.exists():
            raise BackupIntegrityError("Backup destination already exists")
        stage_dir = self.backup_root / f".{bundle_name}.tmp-{os.urandom(8).hex()}"
        stage_dir.mkdir(parents=False, exist_ok=False)
        try:
            snapshot_bytes = self._online_snapshot_bytes(stage_dir)
            verified_row_counts = self._validate_snapshot(snapshot_bytes)
            logical_export, row_counts, audit_head = self._logical_export(snapshot_bytes)
            if row_counts != verified_row_counts:
                raise BackupIntegrityError("Backup verification row counts changed")
            native_hash = hashlib.sha256(snapshot_bytes).hexdigest()
            logical_hash = hashlib.sha256(logical_export).hexdigest()
            migrations = [
                {"version": version, "checksum_sha256": checksum} for version, checksum, _ in MIGRATIONS
            ]
            authenticated_header = {
                "aad_schema": BACKUP_AAD_SCHEMA,
                "backup_id": backup_id,
                "tenant_id": tenant_id,
                "deployment_id": deployment_id,
                "logical_schema_version": LOGICAL_SCHEMA_VERSION,
                "migration_versions": migrations,
                "created_at": created_at,
                "audit_head_hash": audit_head,
                "native_snapshot_sha256": native_hash,
                "logical_export_sha256": logical_hash,
                "recovery_encryption_key_id": self.keys.key_id(BACKUP_PURPOSE),
            }
            aad = canonical_json(authenticated_header).encode("utf-8")
            payload = self._payload_zip(snapshot_bytes, logical_export)
            encrypted = self.keys.encrypt_for(BACKUP_PURPOSE, payload, aad)
            ciphertext_hash = hashlib.sha256(encrypted.value).hexdigest()
            manifest = {
                "schema_version": BACKUP_MANIFEST_SCHEMA,
                "authenticated_header": authenticated_header,
                "authenticated_header_sha256": hashlib.sha256(aad).hexdigest(),
                "encryption": {
                    "algorithm": "AES-256-GCM",
                    "nonce_base64": base64.b64encode(encrypted.nonce).decode("ascii"),
                    "ciphertext_sha256": ciphertext_hash,
                    "ciphertext_size": len(encrypted.value),
                },
                "safe_row_counts": row_counts,
            }
            manifest_bytes = (canonical_json(manifest) + "\n").encode("utf-8")
            manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
            verification = {
                "schema_version": "p1_backup_verification_v1",
                "outcome": "VERIFIED",
                "backup_id": backup_id,
                "manifest_sha256": manifest_hash,
                "ciphertext_sha256": ciphertext_hash,
                "logical_schema_version": LOGICAL_SCHEMA_VERSION,
                "migration_count": len(migrations),
                "foreign_key_violations": 0,
                "release_hash_mismatches": 0,
                "runtime_binding_complete_count": row_counts.get("runtime_bindings_complete", 0),
                "plaintext_sensitive_fields_exposed": False,
                "verified_at": created_at,
            }
            verification_bytes = (canonical_json(verification) + "\n").encode("utf-8")
            checksums = self._checksums_text(
                {
                    "manifest.json": manifest_bytes,
                    "payload.aes256gcm": encrypted.value,
                    "verification.json": verification_bytes,
                }
            )
            (stage_dir / "manifest.json").write_bytes(manifest_bytes)
            (stage_dir / "payload.aes256gcm").write_bytes(encrypted.value)
            (stage_dir / "verification.json").write_bytes(verification_bytes)
            (stage_dir / "checksums.sha256").write_text(checksums, encoding="utf-8")
            os.replace(stage_dir, final_dir)
            duration_ms = max(0, int((perf_counter() - started) * 1000))
            return {
                "backup_id": backup_id,
                "bundle_name": bundle_name,
                "manifest_hash": manifest_hash,
                "ciphertext_hash": ciphertext_hash,
                "recovery_encryption_key_id": self.keys.key_id(BACKUP_PURPOSE),
                "logical_schema_version": LOGICAL_SCHEMA_VERSION,
                "migration_versions": [item["version"] for item in migrations],
                "safe_row_counts": row_counts,
                "audit_head_hash": audit_head,
                "ciphertext_size": len(encrypted.value),
                "duration_ms": duration_ms,
            }
        except Exception:
            self._remove_stage(stage_dir)
            raise

    def verify_bundle(self, bundle_name: str) -> dict[str, Any]:
        started = perf_counter()
        snapshot = self.load_verified_snapshot(bundle_name)
        return {
            "outcome": "VERIFIED",
            "manifest": snapshot.manifest,
            "manifest_hash": snapshot.manifest_hash,
            "ciphertext_hash": snapshot.ciphertext_hash,
            "safe_row_counts": snapshot.safe_row_counts,
            "duration_ms": max(0, int((perf_counter() - started) * 1000)),
        }

    def load_verified_snapshot(self, bundle_name: str) -> VerifiedSnapshot:
        bundle_dir = self._bundle_dir(bundle_name)
        if not bundle_dir.is_dir():
            raise BackupIntegrityError("Backup bundle is unavailable")
        names = {item.name for item in bundle_dir.iterdir() if item.is_file()}
        if names != BACKUP_ENTRIES:
            raise BackupIntegrityError("Backup bundle file set is invalid")
        manifest_bytes = (bundle_dir / "manifest.json").read_bytes()
        payload = (bundle_dir / "payload.aes256gcm").read_bytes()
        verification_bytes = (bundle_dir / "verification.json").read_bytes()
        checksums = self._parse_checksums((bundle_dir / "checksums.sha256").read_text("utf-8"))
        expected_checksums = {
            "manifest.json": hashlib.sha256(manifest_bytes).hexdigest(),
            "payload.aes256gcm": hashlib.sha256(payload).hexdigest(),
            "verification.json": hashlib.sha256(verification_bytes).hexdigest(),
        }
        if checksums != expected_checksums:
            raise BackupIntegrityError("Backup bundle checksum verification failed")
        try:
            manifest = json.loads(manifest_bytes)
            verification = json.loads(verification_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackupIntegrityError("Backup metadata is invalid") from exc
        if (
            manifest.get("schema_version") != BACKUP_MANIFEST_SCHEMA
            or verification.get("outcome") != "VERIFIED"
        ):
            raise BackupIntegrityError("Backup metadata state is invalid")
        header = manifest.get("authenticated_header")
        encryption = manifest.get("encryption")
        if not isinstance(header, dict) or not isinstance(encryption, dict):
            raise BackupIntegrityError("Backup authenticated metadata is missing")
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        ciphertext_hash = hashlib.sha256(payload).hexdigest()
        if header.get("recovery_encryption_key_id") != self.keys.key_id(BACKUP_PURPOSE):
            raise BackupIntegrityError("Backup recovery key is unavailable")
        aad = canonical_json(header).encode("utf-8")
        if hashlib.sha256(aad).hexdigest() != manifest.get("authenticated_header_sha256"):
            raise BackupIntegrityError("Backup authenticated metadata changed")
        if ciphertext_hash != encryption.get("ciphertext_sha256"):
            raise BackupIntegrityError("Backup ciphertext changed")
        try:
            nonce = base64.b64decode(encryption["nonce_base64"], validate=True)
            plaintext = self.keys.decrypt_for(
                BACKUP_PURPOSE,
                Ciphertext(nonce=nonce, value=payload),
                aad,
            )
        except (InvalidTag, KeyError, TypeError, ValueError) as exc:
            raise BackupIntegrityError("Backup authentication failed") from exc
        native_snapshot, logical_export = self._read_payload(plaintext)
        if hashlib.sha256(native_snapshot).hexdigest() != header.get("native_snapshot_sha256"):
            raise BackupIntegrityError("Backup native snapshot hash changed")
        if hashlib.sha256(logical_export).hexdigest() != header.get("logical_export_sha256"):
            raise BackupIntegrityError("Backup logical export hash changed")
        safe_row_counts = self._validate_snapshot(native_snapshot)
        if safe_row_counts != manifest.get("safe_row_counts"):
            raise BackupIntegrityError("Backup row-count evidence changed")
        if verification.get("manifest_sha256") != manifest_hash:
            raise BackupIntegrityError("Backup verification does not bind the manifest")
        if (
            verification.get("backup_id") != header.get("backup_id")
            or verification.get("ciphertext_sha256") != ciphertext_hash
            or verification.get("logical_schema_version") != header.get("logical_schema_version")
        ):
            raise BackupIntegrityError("Backup verification identity is inconsistent")
        return VerifiedSnapshot(
            manifest=manifest,
            manifest_hash=manifest_hash,
            ciphertext_hash=ciphertext_hash,
            native_snapshot=native_snapshot,
            logical_export=logical_export,
            safe_row_counts=safe_row_counts,
        )

    @contextmanager
    def staged_snapshot(self, bundle_name: str) -> Iterator[tuple[Path, VerifiedSnapshot]]:
        snapshot = self.load_verified_snapshot(bundle_name)
        with tempfile.TemporaryDirectory(prefix="shuziren-p1-3-restore-") as directory:
            path = Path(directory) / "staged-control-plane.db"
            path.write_bytes(snapshot.native_snapshot)
            yield path, snapshot

    def _ensure_safe_root(self) -> None:
        self.backup_root.mkdir(parents=True, exist_ok=True)
        if self.backup_root == self.store.path.resolve():
            raise BackupIntegrityError("Backup root cannot be the live database")
        probe = self.backup_root / f".write-probe-{os.urandom(8).hex()}"
        try:
            probe.write_bytes(b"p1.3")
        finally:
            probe.unlink(missing_ok=True)

    def _bundle_dir(self, bundle_name: str) -> Path:
        if (
            not bundle_name
            or "/" in bundle_name
            or "\\" in bundle_name
            or not bundle_name.startswith("backup-")
        ):
            raise BackupIntegrityError("Backup bundle name is invalid")
        candidate = (self.backup_root / bundle_name).resolve()
        if candidate.parent != self.backup_root:
            raise BackupIntegrityError("Backup bundle path is invalid")
        return candidate

    def _online_snapshot_bytes(self, stage_dir: Path) -> bytes:
        snapshot_path = stage_dir / ".embedded-native.snapshot.tmp"
        source = self.store.connect()
        target = sqlite3.connect(snapshot_path)
        try:
            source.execute("PRAGMA wal_checkpoint(PASSIVE)")
            source.backup(target)
            target.commit()
        finally:
            target.close()
            source.close()
        value = snapshot_path.read_bytes()
        snapshot_path.unlink(missing_ok=True)
        return value

    @staticmethod
    def _logical_export(snapshot_bytes: bytes) -> tuple[bytes, dict[str, int], str | None]:
        with tempfile.TemporaryDirectory(prefix="shuziren-p1-3-export-") as directory:
            path = Path(directory) / "snapshot.db"
            path.write_bytes(snapshot_bytes)
            connection = sqlite3.connect(path)
            connection.row_factory = sqlite3.Row
            try:
                tables = [
                    row["name"]
                    for row in connection.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                        ORDER BY name
                        """
                    ).fetchall()
                ]
                lines: list[str] = []
                counts: dict[str, int] = {}
                for table in tables:
                    quoted = table.replace('"', '""')
                    rows = connection.execute(f'SELECT * FROM "{quoted}" ORDER BY rowid').fetchall()
                    counts[table] = len(rows)
                    for row in rows:
                        record = {
                            "table": table,
                            "row": {
                                key: BackupManager._logical_value(value) for key, value in dict(row).items()
                            },
                        }
                        lines.append(canonical_json(record))
                complete = connection.execute(
                    """
                    SELECT COUNT(*) AS count FROM runtime_bindings
                    WHERE digital_human_instance_id IS NOT NULL
                    """
                ).fetchone()["count"]
                counts["runtime_bindings_complete"] = int(complete)
                audit = connection.execute(
                    """
                    SELECT event_hash FROM security_audit_events
                    ORDER BY sequence DESC LIMIT 1
                    """
                ).fetchone()
            finally:
                connection.close()
        return (
            (("\n".join(lines) + "\n") if lines else "").encode("utf-8"),
            counts,
            audit["event_hash"] if audit else None,
        )

    @staticmethod
    def _logical_value(value: Any) -> Any:
        if isinstance(value, bytes):
            return {"encoding": "base64", "value": base64.b64encode(value).decode("ascii")}
        return value

    @staticmethod
    def _payload_zip(snapshot: bytes, logical_export: bytes) -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("embedded-native.snapshot", snapshot)
            archive.writestr("control-plane.logical.ndjson", logical_export)
        return output.getvalue()

    @staticmethod
    def _read_payload(payload: bytes) -> tuple[bytes, bytes]:
        try:
            with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
                names = set(archive.namelist())
                if names != PAYLOAD_ENTRIES:
                    raise BackupIntegrityError("Backup encrypted payload file set is invalid")
                if any(name.startswith(("/", "\\")) or ".." in Path(name).parts for name in names):
                    raise BackupIntegrityError("Backup encrypted payload path is invalid")
                native = archive.read("embedded-native.snapshot")
                logical = archive.read("control-plane.logical.ndjson")
        except (zipfile.BadZipFile, KeyError) as exc:
            raise BackupIntegrityError("Backup encrypted payload is invalid") from exc
        return native, logical

    @staticmethod
    def _validate_snapshot(snapshot_bytes: bytes) -> dict[str, int]:
        with tempfile.TemporaryDirectory(prefix="shuziren-p1-3-verify-") as directory:
            path = Path(directory) / "verify.db"
            path.write_bytes(snapshot_bytes)
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            connection.row_factory = sqlite3.Row
            try:
                foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
                if foreign_keys:
                    raise BackupIntegrityError("Backup foreign-key verification failed")
                applied = [
                    (row["version"], row["checksum_sha256"])
                    for row in connection.execute(
                        "SELECT version, checksum_sha256 FROM schema_migrations ORDER BY rowid"
                    ).fetchall()
                ]
                expected = [(version, checksum) for version, checksum, _ in MIGRATIONS]
                if applied != expected:
                    raise BackupIntegrityError("Backup migration registry is invalid")
                try:
                    ControlPlaneStore.validate_p21_schema_integrity(connection)
                except RuntimeError as exc:
                    raise BackupIntegrityError("Backup P2.1 schema object verification failed") from exc
                releases = connection.execute(
                    """
                    SELECT release_target_id, canonical_effective_config_json, content_hash
                    FROM release_targets
                    """
                ).fetchall()
                for row in releases:
                    actual = hashlib.sha256(
                        row["canonical_effective_config_json"].encode("utf-8")
                    ).hexdigest()
                    if actual != row["content_hash"]:
                        raise BackupIntegrityError("Backup release hash verification failed")
                BackupManager._validate_p21_capability_data(connection)
                BackupManager._validate_audit_chain(connection)
                tables = [
                    row["name"]
                    for row in connection.execute(
                        """
                        SELECT name FROM sqlite_master
                        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                        ORDER BY name
                        """
                    ).fetchall()
                ]
                counts = {
                    table: int(
                        connection.execute(
                            f'SELECT COUNT(*) AS count FROM "{table.replace(chr(34), chr(34) * 2)}"'
                        ).fetchone()["count"]
                    )
                    for table in tables
                }
                counts["runtime_bindings_complete"] = int(
                    connection.execute(
                        """
                        SELECT COUNT(*) AS count FROM runtime_bindings
                        WHERE digital_human_instance_id IS NOT NULL
                        """
                    ).fetchone()["count"]
                )
                if counts["runtime_bindings_complete"] < 3:
                    raise BackupIntegrityError("Backup lacks the three-screen binding baseline")
                return counts
            except sqlite3.Error as exc:
                raise BackupIntegrityError("Backup database verification failed") from exc
            finally:
                connection.close()

    @staticmethod
    def _validate_p21_capability_data(connection: sqlite3.Connection) -> None:
        try:
            ControlPlaneStore.validate_p21_schema_integrity(connection)
        except RuntimeError as exc:
            raise BackupIntegrityError("Capability profile schema object verification failed") from exc
        required_tables = {
            "capability_profiles",
            "capability_profile_versions",
            "config_draft_capability_assignments",
            "release_target_capability_snapshots",
        }
        present = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name IN (
                    'capability_profiles',
                    'capability_profile_versions',
                    'config_draft_capability_assignments',
                    'release_target_capability_snapshots'
                )
                """
            ).fetchall()
        }
        if not present:
            return
        if present != required_tables:
            raise BackupIntegrityError("Capability profile table set is incomplete")

        validator = object.__new__(P21ControlPlane)
        versions = connection.execute(
            "SELECT * FROM capability_profile_versions ORDER BY profile_id, version_number"
        ).fetchall()
        version_by_id = {row["profile_version_id"]: row for row in versions}
        version_data_by_id: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        for row in versions:
            try:
                spec = json.loads(row["canonical_spec_json"])
                canonical_spec, derived = validator._validate_and_derive_spec(spec)
            except (ControlPlaneError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise BackupIntegrityError("Capability profile version content is invalid") from exc
            if (
                row["schema_version"] != PROFILE_SCHEMA_VERSION
                or canonical_spec != row["canonical_spec_json"]
                or hashlib.sha256(canonical_spec.encode("utf-8")).hexdigest() != row["content_hash"]
                or row["provider_registry_version"] != PROVIDER_REGISTRY_VERSION
                or row["provider_registry_hash"] != PROVIDER_REGISTRY_HASH
                or canonical_json(derived["state_summary"]) != row["state_summary_json"]
                or canonical_json(derived["dependency_findings"]) != row["dependency_findings_json"]
                or int(derived["activation_eligible"]) != row["activation_eligible"]
            ):
                raise BackupIntegrityError("Capability profile version hash or registry binding changed")
            state_summary = derived["state_summary"]
            if set(state_summary) != set(CAPABILITY_KEYS) or any(
                state not in PROFILE_STATES for state in state_summary.values()
            ):
                raise BackupIntegrityError("Capability profile state summary is invalid")
            version_data_by_id[row["profile_version_id"]] = (spec, derived)

        profiles = connection.execute("SELECT * FROM capability_profiles ORDER BY profile_id").fetchall()
        profile_by_id = {row["profile_id"]: row for row in profiles}
        versions_by_profile: dict[str, list[sqlite3.Row]] = {}
        for version in versions:
            versions_by_profile.setdefault(version["profile_id"], []).append(version)
        if set(versions_by_profile) != set(profile_by_id):
            raise BackupIntegrityError("Capability profile version lineage is incomplete")
        for profile in profiles:
            try:
                canonical_name = validator._public_text(
                    profile["name"],
                    "Capability profile name",
                    minimum=1,
                    maximum=128,
                )
                canonical_description = validator._public_text(
                    profile["description"],
                    "Capability profile description",
                    minimum=0,
                    maximum=500,
                )
            except ControlPlaneError as exc:
                raise BackupIntegrityError("Capability profile public metadata is invalid") from exc
            if (
                canonical_name != profile["name"]
                or canonical_description != profile["description"]
                or profile["source_preset_id"] not in PRESETS
            ):
                raise BackupIntegrityError("Capability profile public metadata is invalid")
            lineage = versions_by_profile.get(profile["profile_id"], [])
            expected_numbers = list(range(1, profile["head_version_number"] + 1))
            actual_numbers = [row["version_number"] for row in lineage]
            head = version_by_id.get(profile["head_version_id"])
            if (
                actual_numbers != expected_numbers
                or head is None
                or head["profile_id"] != profile["profile_id"]
                or head["tenant_id"] != profile["tenant_id"]
                or head["deployment_id"] != profile["deployment_id"]
                or head["site_id"] != profile["site_id"]
                or head["version_number"] != profile["head_version_number"]
            ):
                raise BackupIntegrityError("Capability profile head reference is invalid")

        assignments = connection.execute(
            """
            SELECT a.*, d.tenant_id AS draft_tenant_id,
                   d.deployment_id AS draft_deployment_id,
                   d.target_type, d.screen_id AS draft_screen_id,
                   d.screen_group_id AS draft_group_id,
                   s.site_id AS screen_site_id, g.site_id AS group_site_id
            FROM config_draft_capability_assignments a
            JOIN config_drafts d ON d.draft_id = a.draft_id
            LEFT JOIN screen_instances s
              ON d.target_type = 'SCREEN'
             AND s.screen_id = d.screen_id
             AND s.tenant_id = d.tenant_id
             AND s.deployment_id = d.deployment_id
            LEFT JOIN screen_groups g
              ON d.target_type = 'SCREEN_GROUP'
             AND g.screen_group_id = d.screen_group_id
             AND g.tenant_id = d.tenant_id
             AND g.deployment_id = d.deployment_id
            ORDER BY a.draft_id, a.draft_revision
            """
        ).fetchall()
        assignment_by_revision = {(row["draft_id"], row["draft_revision"]): row for row in assignments}
        for assignment in assignments:
            version = version_by_id.get(assignment["profile_version_id"])
            target_site_id = (
                assignment["screen_site_id"]
                if assignment["target_type"] == "SCREEN"
                else assignment["group_site_id"]
            )
            if (
                version is None
                or assignment["tenant_id"] != assignment["draft_tenant_id"]
                or assignment["deployment_id"] != assignment["draft_deployment_id"]
                or target_site_id != assignment["site_id"]
                or assignment["tenant_id"] != version["tenant_id"]
                or assignment["deployment_id"] != version["deployment_id"]
                or assignment["site_id"] != version["site_id"]
                or assignment["profile_id"] != version["profile_id"]
                or assignment["version_number"] != version["version_number"]
                or assignment["profile_content_hash"] != version["content_hash"]
                or assignment["provider_registry_version"] != version["provider_registry_version"]
                or assignment["provider_registry_hash"] != version["provider_registry_hash"]
                or assignment["state_summary_json"] != version["state_summary_json"]
                or assignment["dependency_findings_json"] != version["dependency_findings_json"]
                or assignment["activation_eligible"] != version["activation_eligible"]
            ):
                raise BackupIntegrityError("Draft capability assignment reference changed")

        capability_event_types = {
            "CAPABILITY_PROFILE_CREATED",
            "CAPABILITY_PROFILE_VERSION_CREATED",
            "CONFIG_DRAFT_CAPABILITY_PROFILE_ASSIGNED",
        }
        fingerprint_event_types = capability_event_types | {"CONFIG_DRAFT_VALIDATED"}
        audit_rows = connection.execute("SELECT * FROM security_audit_events ORDER BY sequence").fetchall()
        active_integrity_tail: int | None = None
        previous_integrity_sequence: dict[int, int | None] = {}
        tail_by_event_hash: dict[str, int | None] = {}
        epoch_by_event_hash: dict[str, int] = {}
        current_epoch = 1
        for event in audit_rows:
            if event["event_type"] in fingerprint_event_types:
                previous_integrity_sequence[event["sequence"]] = active_integrity_tail
                active_integrity_tail = event["sequence"]
            elif event["event_type"] == "RESTORE_COMPLETED":
                try:
                    restore_details = json.loads(event["details_json"])
                    source_head = restore_details["source_manifest_audit_head"]
                    active_integrity_tail = tail_by_event_hash[source_head]
                    current_epoch = epoch_by_event_hash[source_head] + 1
                except (json.JSONDecodeError, KeyError, TypeError) as exc:
                    raise BackupIntegrityError("Capability restore audit anchor is invalid") from exc
            tail_by_event_hash[event["event_hash"]] = active_integrity_tail
            epoch_by_event_hash[event["event_hash"]] = current_epoch
        active_integrity_sequences: set[int] = set()
        while active_integrity_tail is not None:
            if active_integrity_tail in active_integrity_sequences:
                raise BackupIntegrityError("Capability audit anchor lineage contains a cycle")
            active_integrity_sequences.add(active_integrity_tail)
            active_integrity_tail = previous_integrity_sequence[active_integrity_tail]
        metadata_epoch = connection.execute(
            "SELECT revision FROM control_plane_metadata WHERE singleton = 1"
        ).fetchone()
        if metadata_epoch is None or metadata_epoch["revision"] != current_epoch:
            raise BackupIntegrityError("Control-plane epoch audit lineage is invalid")
        capability_audit_events = [
            event
            for event in audit_rows
            if event["sequence"] in active_integrity_sequences
            and event["event_type"] in capability_event_types
        ]
        for event in capability_audit_events:
            try:
                details = json.loads(event["details_json"])
            except (json.JSONDecodeError, TypeError) as exc:
                raise BackupIntegrityError("Capability audit anchor is invalid") from exc
            if (
                event["outcome"] != "SUCCESS"
                or not isinstance(details, dict)
                or (
                    event["event_type"].startswith("CAPABILITY_PROFILE_")
                    and event["target_type"] != "CAPABILITY_PROFILE"
                )
                or (
                    event["event_type"] == "CONFIG_DRAFT_CAPABILITY_PROFILE_ASSIGNED"
                    and event["target_type"] != "CONFIG_DRAFT"
                )
            ):
                raise BackupIntegrityError("Capability audit anchor is invalid")
            if event["event_type"] == "CAPABILITY_PROFILE_CREATED":
                profile = profile_by_id.get(event["target_id"])
                version = (
                    version_by_id.get(details.get("profile_version_id"))
                    if set(details)
                    == {
                        "site_id",
                        "source_preset_id",
                        "profile_version_id",
                        "content_hash",
                        "activation_eligible",
                    }
                    else None
                )
                if (
                    profile is None
                    or version is None
                    or version["profile_id"] != profile["profile_id"]
                    or version["version_number"] != 1
                    or details["site_id"] != profile["site_id"]
                    or details["source_preset_id"] != profile["source_preset_id"]
                    or details["content_hash"] != version["content_hash"]
                    or details["activation_eligible"] != bool(version["activation_eligible"])
                    or event["actor_id"] != profile["created_by_user_id"]
                    or event["actor_id"] != version["created_by_user_id"]
                    or event["created_at"] != profile["created_at"]
                    or event["created_at"] != version["created_at"]
                ):
                    raise BackupIntegrityError("Capability profile creation anchor changed")
            elif event["event_type"] == "CAPABILITY_PROFILE_VERSION_CREATED":
                profile = profile_by_id.get(event["target_id"])
                version = (
                    version_by_id.get(details.get("profile_version_id"))
                    if set(details)
                    == {
                        "profile_version_id",
                        "version_number",
                        "content_hash",
                        "activation_eligible",
                    }
                    else None
                )
                if (
                    profile is None
                    or version is None
                    or version["profile_id"] != profile["profile_id"]
                    or details["version_number"] != version["version_number"]
                    or details["content_hash"] != version["content_hash"]
                    or details["activation_eligible"] != bool(version["activation_eligible"])
                    or event["actor_id"] != version["created_by_user_id"]
                    or event["created_at"] != version["created_at"]
                ):
                    raise BackupIntegrityError("Capability profile version anchor changed")
            else:
                assignment = (
                    assignment_by_revision.get((event["target_id"], details.get("draft_revision")))
                    if set(details)
                    == {
                        "draft_revision",
                        "profile_id",
                        "profile_version_id",
                        "profile_content_hash",
                        "provider_registry_version",
                        "activation_eligible",
                    }
                    else None
                )
                if (
                    assignment is None
                    or details["profile_id"] != assignment["profile_id"]
                    or details["profile_version_id"] != assignment["profile_version_id"]
                    or details["profile_content_hash"] != assignment["profile_content_hash"]
                    or details["provider_registry_version"] != assignment["provider_registry_version"]
                    or details["activation_eligible"] != bool(assignment["activation_eligible"])
                    or event["actor_id"] != assignment["assigned_by_user_id"]
                    or event["created_at"] != assignment["assigned_at"]
                ):
                    raise BackupIntegrityError("Capability assignment audit anchor changed")

        validation_audit_by_revision: dict[tuple[str, int], tuple[dict[str, Any], int]] = {}
        for event in audit_rows:
            if (
                event["sequence"] not in active_integrity_sequences
                or event["event_type"] != "CONFIG_DRAFT_VALIDATED"
            ):
                continue
            try:
                details = json.loads(event["details_json"])
            except (json.JSONDecodeError, TypeError) as exc:
                raise BackupIntegrityError("Validation audit anchor is invalid") from exc
            if (
                event["outcome"] != "SUCCESS"
                or event["target_type"] != "CONFIG_DRAFT"
                or not isinstance(details, dict)
                or set(details)
                != {
                    "draft_revision",
                    "fingerprint_hash",
                    "target_set_hash",
                    "outcome",
                }
                or not BackupManager._is_int(details["draft_revision"])
                or not BackupManager._is_sha256(details["fingerprint_hash"])
                or not BackupManager._is_sha256(details["target_set_hash"])
                or details["outcome"] != "VALID"
            ):
                raise BackupIntegrityError("Validation audit anchor is invalid")
            key = (event["target_id"], details["draft_revision"])
            if key in validation_audit_by_revision:
                raise BackupIntegrityError("Validation audit anchor is ambiguous")
            validation_audit_by_revision[key] = (
                details,
                epoch_by_event_hash[event["event_hash"]],
            )

        approval_epochs_by_fingerprint: dict[str, set[int]] = {}
        for row in connection.execute(
            """
            SELECT v.fingerprint_id, a.control_plane_epoch
            FROM config_approval_records a
            JOIN preview_records p
              ON p.preview_record_id = a.preview_record_id
             AND p.draft_id = a.draft_id
             AND p.draft_revision = a.draft_revision
            JOIN validation_records v
              ON v.validation_record_id = p.validation_record_id
             AND v.draft_id = p.draft_id
             AND v.draft_revision = p.draft_revision
            WHERE v.outcome = 'VALID'
            """
        ).fetchall():
            approval_epochs_by_fingerprint.setdefault(row["fingerprint_id"], set()).add(
                row["control_plane_epoch"]
            )

        fingerprint_capability_marker: dict[str, bool] = {}
        fingerprint_target_sets: dict[str, list[str]] = {}
        fingerprint_target_set_hashes: dict[str, str] = {}
        fingerprint_effective_hashes: dict[str, dict[str, str]] = {}
        fingerprints = connection.execute(
            """
            SELECT rf.*, dr.schema_version AS draft_schema_version,
                   dr.canonical_spec_json AS draft_canonical_spec_json,
                   dr.content_hash AS draft_content_hash
            FROM resolution_fingerprints rf
            JOIN config_draft_revisions dr
              ON dr.draft_id = rf.draft_id
             AND dr.draft_revision = rf.draft_revision
            ORDER BY rf.fingerprint_id
            """
        ).fetchall()
        fingerprint_revision_keys = [(row["draft_id"], row["draft_revision"]) for row in fingerprints]
        if len(fingerprint_revision_keys) != len(set(fingerprint_revision_keys)) or set(
            fingerprint_revision_keys
        ) != set(validation_audit_by_revision):
            raise BackupIntegrityError("Resolution fingerprint audit lineage is incomplete")
        fingerprint_by_id = {row["fingerprint_id"]: row for row in fingerprints}
        for fingerprint in fingerprints:
            try:
                target_set = json.loads(fingerprint["target_set_json"])
                inputs = json.loads(fingerprint["resolution_inputs_json"])
                effective_hashes = json.loads(fingerprint["effective_hashes_json"])
                draft_spec = json.loads(fingerprint["draft_canonical_spec_json"])
            except (json.JSONDecodeError, TypeError) as exc:
                raise BackupIntegrityError("Resolution fingerprint JSON is invalid") from exc
            if (
                not isinstance(target_set, list)
                or not target_set
                or any(not isinstance(screen_id, str) or not screen_id for screen_id in target_set)
                or target_set != sorted(set(target_set))
                or canonical_json(target_set) != fingerprint["target_set_json"]
                or hashlib.sha256(fingerprint["target_set_json"].encode("utf-8")).hexdigest()
                != fingerprint["target_set_hash"]
                or not isinstance(inputs, list)
                or len(inputs) != len(target_set)
                or not isinstance(effective_hashes, dict)
                or set(effective_hashes) != set(target_set)
                or canonical_json(effective_hashes) != fingerprint["effective_hashes_json"]
                or any(not BackupManager._is_sha256(value) for value in effective_hashes.values())
                or fingerprint["draft_schema_version"] != P1_CONFIG_SCHEMA_VERSION
                or not isinstance(draft_spec, dict)
                or set(draft_spec) != P1_CONFIG_FIELDS
                or canonical_json(draft_spec) != fingerprint["draft_canonical_spec_json"]
                or hashlib.sha256(fingerprint["draft_canonical_spec_json"].encode("utf-8")).hexdigest()
                != fingerprint["draft_content_hash"]
            ):
                raise BackupIntegrityError("Resolution fingerprint structure is invalid")

            base_input_keys = {
                "screen_id",
                "screen_revision",
                "runtime_binding_revision",
                "binding_generation",
                "digital_human_instance_id",
                "digital_human_revision",
            }
            marker_keys = {
                "profile_id",
                "profile_version_id",
                "version_number",
                "profile_content_hash",
                "provider_registry_version",
                "provider_registry_hash",
                "capability_envelope_hash",
            }
            input_screen_ids: list[str] = []
            marker_presence: list[bool] = []
            capability_envelope_hashes: dict[str, str] = {}
            assignment = assignment_by_revision.get((fingerprint["draft_id"], fingerprint["draft_revision"]))
            for item in inputs:
                if not isinstance(item, dict):
                    raise BackupIntegrityError("Resolution fingerprint input is invalid")
                has_marker = "capability_profile" in item
                expected_input_keys = base_input_keys | ({"capability_profile"} if has_marker else set())
                if (
                    set(item) != expected_input_keys
                    or not isinstance(item["screen_id"], str)
                    or not item["screen_id"]
                    or not isinstance(item["digital_human_instance_id"], str)
                    or not item["digital_human_instance_id"]
                    or any(
                        not BackupManager._is_int(item[name])
                        for name in (
                            "screen_revision",
                            "runtime_binding_revision",
                            "binding_generation",
                            "digital_human_revision",
                        )
                    )
                ):
                    raise BackupIntegrityError("Resolution fingerprint input is invalid")
                expected_effective = {
                    "schema_version": P1_CONFIG_SCHEMA_VERSION,
                    "screen_id": item["screen_id"],
                    "digital_human_instance_id": item["digital_human_instance_id"],
                    "welcome_text": draft_spec["welcome_text"],
                    "fvs_binding_ref": draft_spec["fvs_binding_ref"],
                    "fvs_status": "UNVERIFIED",
                    "preview_provider": "MOCK_FVS",
                }
                expected_effective_hash = hashlib.sha256(
                    canonical_json(expected_effective).encode("utf-8")
                ).hexdigest()
                if effective_hashes.get(item["screen_id"]) != expected_effective_hash:
                    raise BackupIntegrityError("Resolution effective hash changed")
                input_screen_ids.append(item["screen_id"])
                marker_presence.append(has_marker)
                if not has_marker:
                    continue
                marker = item["capability_profile"]
                if (
                    not isinstance(marker, dict)
                    or set(marker) != marker_keys
                    or not isinstance(marker["profile_id"], str)
                    or not isinstance(marker["profile_version_id"], str)
                    or not BackupManager._is_int(marker["version_number"])
                    or not BackupManager._is_sha256(marker["profile_content_hash"])
                    or not isinstance(marker["provider_registry_version"], str)
                    or not BackupManager._is_sha256(marker["provider_registry_hash"])
                    or not BackupManager._is_sha256(marker["capability_envelope_hash"])
                    or assignment is None
                ):
                    raise BackupIntegrityError("Resolution capability marker is invalid")
                version = version_by_id.get(marker["profile_version_id"])
                if (
                    version is None
                    or marker["profile_id"] != assignment["profile_id"]
                    or marker["profile_version_id"] != assignment["profile_version_id"]
                    or marker["version_number"] != assignment["version_number"]
                    or marker["profile_content_hash"] != assignment["profile_content_hash"]
                    or marker["provider_registry_version"] != assignment["provider_registry_version"]
                    or marker["provider_registry_hash"] != assignment["provider_registry_hash"]
                ):
                    raise BackupIntegrityError("Resolution capability marker reference changed")
                spec, derived = version_data_by_id[version["profile_version_id"]]
                envelope = {
                    "schema_version": version["schema_version"],
                    "screen_id": item["screen_id"],
                    "digital_human_instance_id": item["digital_human_instance_id"],
                    "profile_id": version["profile_id"],
                    "profile_version_id": version["profile_version_id"],
                    "version_number": version["version_number"],
                    "content_hash": version["content_hash"],
                    "provider_registry_version": version["provider_registry_version"],
                    "provider_registry_hash": version["provider_registry_hash"],
                    "spec": spec,
                    "state_summary": derived["state_summary"],
                    "dependency_findings": derived["dependency_findings"],
                    "activation_eligible": bool(version["activation_eligible"]),
                }
                expected_envelope_hash = hashlib.sha256(canonical_json(envelope).encode("utf-8")).hexdigest()
                if marker["capability_envelope_hash"] != expected_envelope_hash:
                    raise BackupIntegrityError("Resolution capability envelope hash changed")
                capability_envelope_hashes[item["screen_id"]] = expected_envelope_hash
            if input_screen_ids != target_set or (any(marker_presence) and not all(marker_presence)):
                raise BackupIntegrityError("Resolution capability target set is incomplete")
            has_capability_marker = bool(marker_presence and marker_presence[0])
            if (assignment is not None) != has_capability_marker:
                raise BackupIntegrityError("Resolution capability assignment is incomplete")
            validation_anchor_with_epoch = validation_audit_by_revision.get(
                (fingerprint["draft_id"], fingerprint["draft_revision"])
            )
            if validation_anchor_with_epoch is None:
                raise BackupIntegrityError("Resolution fingerprint audit anchor changed")
            validation_anchor, validation_epoch = validation_anchor_with_epoch
            if (
                validation_anchor["fingerprint_hash"] != fingerprint["fingerprint_hash"]
                or validation_anchor["target_set_hash"] != fingerprint["target_set_hash"]
            ):
                raise BackupIntegrityError("Resolution fingerprint audit anchor changed")
            fingerprint_payload = {
                "draft_id": fingerprint["draft_id"],
                "draft_revision": fingerprint["draft_revision"],
                "schema_version": fingerprint["draft_schema_version"],
                "content_hash": fingerprint["draft_content_hash"],
                "target_set_hash": fingerprint["target_set_hash"],
                "group_revision": fingerprint["group_revision"],
                "inputs": inputs,
                "effective_hashes": effective_hashes,
                "capability_envelope_hashes": (capability_envelope_hashes if has_capability_marker else {}),
                "control_plane_epoch": validation_epoch,
            }
            approval_epochs = approval_epochs_by_fingerprint.get(fingerprint["fingerprint_id"], set())
            if len(approval_epochs) > 1 or any(
                not BackupManager._is_int(epoch) or epoch < 1 for epoch in approval_epochs
            ):
                raise BackupIntegrityError("Resolution fingerprint epoch evidence is invalid")
            if approval_epochs and approval_epochs != {validation_epoch}:
                raise BackupIntegrityError("Resolution fingerprint epoch evidence changed")
            expected_fingerprint_hashes = {
                hashlib.sha256(canonical_json(fingerprint_payload).encode("utf-8")).hexdigest()
            }
            if not has_capability_marker:
                legacy_payload = dict(fingerprint_payload)
                del legacy_payload["capability_envelope_hashes"]
                expected_fingerprint_hashes.add(
                    hashlib.sha256(canonical_json(legacy_payload).encode("utf-8")).hexdigest()
                )
            if fingerprint["fingerprint_hash"] not in expected_fingerprint_hashes:
                raise BackupIntegrityError("Resolution fingerprint hash changed")
            fingerprint_capability_marker[fingerprint["fingerprint_id"]] = has_capability_marker
            fingerprint_target_sets[fingerprint["fingerprint_id"]] = target_set
            fingerprint_target_set_hashes[fingerprint["fingerprint_id"]] = fingerprint["target_set_hash"]
            fingerprint_effective_hashes[fingerprint["fingerprint_id"]] = effective_hashes

        validations = connection.execute(
            "SELECT * FROM validation_records ORDER BY validation_record_id"
        ).fetchall()
        validation_by_id = {row["validation_record_id"]: row for row in validations}
        p21_validation_fingerprint_ids: set[str] = set()
        for validation in validations:
            if validation["outcome"] != "VALID":
                continue
            fingerprint = fingerprint_by_id.get(validation["fingerprint_id"])
            if (
                fingerprint is None
                or validation["draft_id"] != fingerprint["draft_id"]
                or validation["draft_revision"] != fingerprint["draft_revision"]
                or validation["fingerprint_hash"] != fingerprint["fingerprint_hash"]
            ):
                raise BackupIntegrityError("Validation fingerprint reference changed")
            if validation["validator_version"] == "p2_1_capability_profile_validator_v1":
                p21_validation_fingerprint_ids.add(validation["fingerprint_id"])

        previews = connection.execute("SELECT * FROM preview_records ORDER BY preview_record_id").fetchall()
        preview_by_id = {row["preview_record_id"]: row for row in previews}
        for preview in previews:
            validation = validation_by_id.get(preview["validation_record_id"])
            if (
                validation is None
                or validation["outcome"] != "VALID"
                or preview["draft_id"] != validation["draft_id"]
                or preview["draft_revision"] != validation["draft_revision"]
                or preview["fingerprint_hash"] != validation["fingerprint_hash"]
            ):
                raise BackupIntegrityError("Preview fingerprint reference changed")

        approvals = connection.execute(
            "SELECT * FROM config_approval_records ORDER BY approval_record_id"
        ).fetchall()
        approval_by_id = {row["approval_record_id"]: row for row in approvals}
        for approval in approvals:
            preview = preview_by_id.get(approval["preview_record_id"])
            if (
                preview is None
                or approval["draft_id"] != preview["draft_id"]
                or approval["draft_revision"] != preview["draft_revision"]
                or approval["fingerprint_hash"] != preview["fingerprint_hash"]
            ):
                raise BackupIntegrityError("Approval fingerprint reference changed")

        marked_fingerprint_ids = {
            fingerprint_id for fingerprint_id, marked in fingerprint_capability_marker.items() if marked
        }
        if p21_validation_fingerprint_ids != marked_fingerprint_ids:
            raise BackupIntegrityError("P2.1 validation marker lineage is incomplete")

        snapshots = connection.execute(
            """
            SELECT cs.*, rt.release_id, rt.rollback_source_target_id,
                   rt.canonical_effective_config_json AS base_effective_json,
                   rt.content_hash AS base_content_hash
            FROM release_target_capability_snapshots cs
            JOIN release_targets rt
              ON rt.release_target_id = cs.release_target_id
             AND rt.tenant_id = cs.tenant_id
             AND rt.deployment_id = cs.deployment_id
             AND rt.screen_id = cs.screen_id
            ORDER BY cs.release_target_id
            """
        ).fetchall()
        snapshot_by_target = {row["release_target_id"]: row for row in snapshots}
        expected_snapshot_keys = {
            "schema_version",
            "screen_id",
            "digital_human_instance_id",
            "profile_id",
            "profile_version_id",
            "version_number",
            "content_hash",
            "provider_registry_version",
            "provider_registry_hash",
            "spec",
            "state_summary",
            "dependency_findings",
            "activation_eligible",
        }
        for snapshot in snapshots:
            version = version_by_id.get(snapshot["profile_version_id"])
            try:
                envelope = json.loads(snapshot["canonical_capability_snapshot_json"])
                base_effective = json.loads(snapshot["base_effective_json"])
            except (json.JSONDecodeError, TypeError) as exc:
                raise BackupIntegrityError("Release capability snapshot JSON is invalid") from exc
            if not isinstance(envelope, dict) or not isinstance(
                base_effective,
                dict,
            ):
                raise BackupIntegrityError("Release capability snapshot JSON is invalid")
            canonical_envelope = canonical_json(envelope)
            if (
                set(envelope) != expected_snapshot_keys
                or version is None
                or canonical_envelope != snapshot["canonical_capability_snapshot_json"]
                or hashlib.sha256(canonical_envelope.encode("utf-8")).hexdigest()
                != snapshot["capability_envelope_hash"]
                or canonical_json(base_effective) != snapshot["base_effective_json"]
                or hashlib.sha256(snapshot["base_effective_json"].encode("utf-8")).hexdigest()
                != snapshot["base_content_hash"]
                or snapshot["tenant_id"] != version["tenant_id"]
                or snapshot["deployment_id"] != version["deployment_id"]
                or snapshot["site_id"] != version["site_id"]
                or snapshot["profile_id"] != version["profile_id"]
                or snapshot["version_number"] != version["version_number"]
                or snapshot["profile_content_hash"] != version["content_hash"]
                or snapshot["provider_registry_version"] != version["provider_registry_version"]
                or snapshot["provider_registry_hash"] != version["provider_registry_hash"]
                or envelope["schema_version"] != version["schema_version"]
                or envelope["screen_id"] != snapshot["screen_id"]
                or envelope["digital_human_instance_id"] != snapshot["digital_human_instance_id"]
                or base_effective.get("screen_id") != snapshot["screen_id"]
                or base_effective.get("digital_human_instance_id") != snapshot["digital_human_instance_id"]
                or envelope["profile_id"] != snapshot["profile_id"]
                or envelope["profile_version_id"] != snapshot["profile_version_id"]
                or envelope["version_number"] != snapshot["version_number"]
                or envelope["content_hash"] != snapshot["profile_content_hash"]
                or envelope["provider_registry_version"] != snapshot["provider_registry_version"]
                or envelope["provider_registry_hash"] != snapshot["provider_registry_hash"]
                or canonical_json(envelope["spec"]) != version["canonical_spec_json"]
                or canonical_json(envelope["state_summary"]) != version["state_summary_json"]
                or canonical_json(envelope["dependency_findings"]) != version["dependency_findings_json"]
                or not isinstance(envelope["activation_eligible"], bool)
                or bool(envelope["activation_eligible"]) != bool(version["activation_eligible"])
            ):
                raise BackupIntegrityError("Release capability snapshot hash or reference changed")

        assigned_releases = connection.execute(
            """
            SELECT r.release_id, a.profile_id, a.profile_version_id,
                   rt.release_target_id
            FROM config_releases r
            JOIN config_draft_capability_assignments a
              ON a.draft_id = r.normal_draft_id
             AND a.draft_revision = r.normal_draft_revision
            JOIN release_targets rt ON rt.release_id = r.release_id
            WHERE r.creation_kind = 'NORMAL'
            """
        ).fetchall()
        for row in assigned_releases:
            snapshot = snapshot_by_target.get(row["release_target_id"])
            if (
                snapshot is None
                or snapshot["profile_id"] != row["profile_id"]
                or snapshot["profile_version_id"] != row["profile_version_id"]
            ):
                raise BackupIntegrityError("Assigned release capability snapshot is unavailable")

        rollback_targets = connection.execute(
            """
            SELECT release_target_id, rollback_source_target_id
            FROM release_targets
            WHERE rollback_source_target_id IS NOT NULL
            """
        ).fetchall()
        for target in rollback_targets:
            source = snapshot_by_target.get(target["rollback_source_target_id"])
            copied = snapshot_by_target.get(target["release_target_id"])
            if (source is None) != (copied is None) or (
                source is not None
                and (
                    source["canonical_capability_snapshot_json"]
                    != copied["canonical_capability_snapshot_json"]
                    or source["capability_envelope_hash"] != copied["capability_envelope_hash"]
                )
            ):
                raise BackupIntegrityError("Rollback capability snapshot copy changed")

        releases = {
            row["release_id"]: row for row in connection.execute("SELECT * FROM config_releases").fetchall()
        }
        release_targets = connection.execute(
            "SELECT * FROM release_targets ORDER BY release_id, screen_id"
        ).fetchall()
        target_by_id = {row["release_target_id"]: row for row in release_targets}
        targets_by_release: dict[str, list[sqlite3.Row]] = {}
        for target in release_targets:
            targets_by_release.setdefault(target["release_id"], []).append(target)
        for release in releases.values():
            if release["creation_kind"] != "NORMAL":
                continue
            assignment = assignment_by_revision.get(
                (release["normal_draft_id"], release["normal_draft_revision"])
            )
            has_marker = fingerprint_capability_marker.get(release["normal_fingerprint_id"])
            effective_hashes = fingerprint_effective_hashes.get(release["normal_fingerprint_id"])
            approval = approval_by_id.get(release["normal_approval_record_id"])
            preview = preview_by_id.get(approval["preview_record_id"]) if approval is not None else None
            validation = (
                validation_by_id.get(preview["validation_record_id"]) if preview is not None else None
            )
            if (
                has_marker is None
                or effective_hashes is None
                or (assignment is not None) != has_marker
                or approval is None
                or approval["decision"] != "APPROVED"
                or validation is None
                or validation["fingerprint_id"] != release["normal_fingerprint_id"]
            ):
                raise BackupIntegrityError("Normal release capability lineage is incomplete")
            targets = targets_by_release.get(release["release_id"], [])
            if (
                sorted(target["screen_id"] for target in targets)
                != fingerprint_target_sets[release["normal_fingerprint_id"]]
                or release["target_set_hash"]
                != fingerprint_target_set_hashes[release["normal_fingerprint_id"]]
            ):
                raise BackupIntegrityError("Normal release target set is incomplete")
            for target in targets:
                if effective_hashes.get(target["screen_id"]) != target["content_hash"]:
                    raise BackupIntegrityError("Normal release effective hash changed")
                snapshot = snapshot_by_target.get(target["release_target_id"])
                if not has_marker:
                    if snapshot is not None:
                        raise BackupIntegrityError(
                            "Legacy normal release has an ungrounded capability snapshot"
                        )
                    continue
                if (
                    snapshot is None
                    or snapshot["profile_id"] != assignment["profile_id"]
                    or snapshot["profile_version_id"] != assignment["profile_version_id"]
                ):
                    raise BackupIntegrityError("Assigned release capability snapshot is unavailable")

        for snapshot_target_id in snapshot_by_target:
            target = target_by_id.get(snapshot_target_id)
            visited: set[str] = set()
            while target is not None and target["rollback_source_target_id"] is not None:
                if target["release_target_id"] in visited:
                    raise BackupIntegrityError("Rollback capability lineage contains a cycle")
                visited.add(target["release_target_id"])
                source = target_by_id.get(target["rollback_source_target_id"])
                if (
                    source is None
                    or source["release_id"] != target["rollback_source_release_id"]
                    or source["screen_id"] != target["screen_id"]
                ):
                    raise BackupIntegrityError("Rollback capability source reference changed")
                target = source
            if target is None:
                raise BackupIntegrityError("Capability snapshot release target is unavailable")
            release = releases.get(target["release_id"])
            if (
                release is None
                or release["creation_kind"] != "NORMAL"
                or not fingerprint_capability_marker.get(release["normal_fingerprint_id"], False)
                or assignment_by_revision.get((release["normal_draft_id"], release["normal_draft_revision"]))
                is None
                or target["release_target_id"] not in snapshot_by_target
            ):
                raise BackupIntegrityError("Capability snapshot has no assigned release lineage")

    @staticmethod
    def _is_sha256(value: Any) -> bool:
        if not isinstance(value, str) or len(value) != 64:
            return False
        try:
            int(value, 16)
        except ValueError:
            return False
        return value == value.lower()

    @staticmethod
    def _is_int(value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool)

    @staticmethod
    def _validate_audit_chain(connection: sqlite3.Connection) -> None:
        previous_hash: str | None = None
        rows = connection.execute("SELECT * FROM security_audit_events ORDER BY sequence").fetchall()
        for row in rows:
            if row["previous_event_hash"] != previous_hash:
                raise BackupIntegrityError("Backup audit chain predecessor changed")
            try:
                details = json.loads(row["details_json"])
            except json.JSONDecodeError as exc:
                raise BackupIntegrityError("Backup audit details are invalid") from exc
            payload = canonical_json(
                {
                    "event_id": row["event_id"],
                    "event_type": row["event_type"],
                    "actor_type": row["actor_type"],
                    "actor_id": row["actor_id"],
                    "target_type": row["target_type"],
                    "target_id": row["target_id"],
                    "outcome": row["outcome"],
                    "reason": row["reason"],
                    "details": details,
                    "previous_event_hash": row["previous_event_hash"],
                    "created_at": row["created_at"],
                }
            )
            expected = hashlib.sha256(
                b"shuziren:p1:security-audit-event:v1\0" + payload.encode("utf-8")
            ).hexdigest()
            if expected != row["event_hash"]:
                raise BackupIntegrityError("Backup audit chain hash changed")
            previous_hash = expected

    @staticmethod
    def _checksums_text(files: dict[str, bytes]) -> str:
        return "".join(
            f"{hashlib.sha256(value).hexdigest()}  {name}\n" for name, value in sorted(files.items())
        )

    @staticmethod
    def _parse_checksums(value: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for line in value.splitlines():
            parts = line.split("  ", 1)
            if len(parts) != 2 or len(parts[0]) != 64 or parts[1] in result:
                raise BackupIntegrityError("Backup checksum manifest is invalid")
            result[parts[1]] = parts[0]
        return result

    @staticmethod
    def _remove_stage(stage_dir: Path) -> None:
        if not stage_dir.exists():
            return
        for child in stage_dir.iterdir():
            if child.is_file():
                child.unlink(missing_ok=True)
        stage_dir.rmdir()
