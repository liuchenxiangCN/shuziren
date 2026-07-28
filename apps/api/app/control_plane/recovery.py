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
