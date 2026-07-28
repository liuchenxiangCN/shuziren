from __future__ import annotations

import base64
import binascii
import hashlib
import io
import json
import math
import re
import sqlite3
import threading
import zipfile
from collections.abc import Callable, Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any
from xml.etree import ElementTree

import sqlglot
from cryptography.exceptions import InvalidTag
from openpyxl import load_workbook
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.pool import NullPool
from sqlglot import exp

from app.control_plane.errors import ControlPlaneError
from app.control_plane.security import Ciphertext, canonical_json, opaque_id

DATASET_SCHEMA_VERSION = "p2_controlled_dataset_v1"
QUERY_VALIDATOR_VERSION = "p2_2_controlled_query_validator_v2"
QUERY_SNAPSHOT_SCHEMA_VERSION = "p2_query_snapshot_v1"
QUERY_ENGINES = ("EXCEL", "MYSQL", "ORACLE", "POSTGRESQL")
DATABASE_ENGINES = {"MYSQL", "ORACLE", "POSTGRESQL"}
PARAMETER_TYPES = {"string", "integer", "number", "boolean", "date"}
MAX_WORKBOOK_BYTES = 10 * 1024 * 1024
MAX_WORKBOOK_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_WORKBOOK_ENTRIES = 512
MAX_WORKBOOK_ROWS = 50_000
MAX_WORKBOOK_COLUMNS = 100
MAX_WORKBOOK_CELLS = 500_000
MAX_GLOBAL_INFLIGHT = 6
MAX_PER_SCREEN_INFLIGHT = 2
EXECUTOR_WORKERS = 3
MAX_RETAINED_JOBS = 256

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_RELATION = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_$#]*(?:\.[a-zA-Z_][a-zA-Z0-9_$#]*){0,2}$")
_FORBIDDEN_SQL_TEXT = re.compile(
    r"""(?isx)(
        ;|--|/\*|\*/|\x00|
        \b(?:insert|update|delete|merge|replace|upsert|truncate)\b|
        \b(?:create|alter|drop|rename|comment|grant|revoke)\b|
        \b(?:call|execute|exec|prepare|deallocate|copy|load|outfile|dumpfile)\b|
        \b(?:attach|detach|pragma|vacuum|analyze|begin|commit|rollback|savepoint)\b|
        \b(?:for\s+(?:update|share)|lock\s+in\s+share\s+mode)\b
    )"""
)
_FORBIDDEN_MYSQL_SQL_TEXT = re.compile(r"(?m)\#")
_ALLOWED_SQL_FUNCTIONS = {
    "ABS",
    "AVG",
    "CAST",
    "CEIL",
    "CEILING",
    "COALESCE",
    "CONCAT",
    "COUNT",
    "DATE_TRUNC",
    "EXTRACT",
    "FLOOR",
    "LOWER",
    "MAX",
    "MIN",
    "NULLIF",
    "ROUND",
    "SUM",
    "UPPER",
}
_FORBIDDEN_ARCHIVE_PART = re.compile(
    r"""(?ix)
    (?:^|/)(?:
        activex(?:/|$)|
        ctrlprops(?:/|$)|
        dialogsheets(?:/|$)|
        embeddings(?:/|$)|
        externallinks(?:/|$)|
        macrosheets(?:/|$)|
        model(?:/|$)|
        oleobjects?(?:/|$)|
        querytables(?:/|$)|
        webextensions(?:/|$)|
        connections\.xml$|
        vbaproject\.bin$
    )|
    \.bin$
    """
)
_FORBIDDEN_CONTENT_TYPE = re.compile(
    r"(?i)(?:macroenabled|vba|activex|oleobject|externallink|connections|querytable)"
)
_URI_TARGET = re.compile(r"(?i)^(?:[a-z][a-z0-9+.-]*:|//)")


@dataclass
class QueryJob:
    execution_id: str
    request_id: str
    screen_id: str
    source_id: str
    dataset_id: str
    dataset_version_id: str
    cancel_event: threading.Event = field(default_factory=threading.Event)
    future: Future[None] | None = None
    cancel_adapter: Callable[[], None] | None = None
    result: dict[str, Any] | None = None
    authority_error_code: str | None = None
    timed_out: bool = False
    slot_released: bool = False
    terminal: bool = False
    lock: threading.RLock = field(default_factory=threading.RLock)


class QueryExecutionFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.public_message = message


class P22ControlPlane:
    def __init__(self, owner: Any, source_root: str | Path) -> None:
        self.owner = owner
        self.source_root = Path(source_root)
        self.source_root.mkdir(parents=True, exist_ok=True)
        self._executor = ThreadPoolExecutor(
            max_workers=EXECUTOR_WORKERS,
            thread_name_prefix="controlled-query",
        )
        self._jobs: dict[str, QueryJob] = {}
        self._jobs_lock = threading.RLock()
        self._global_slots = threading.BoundedSemaphore(MAX_GLOBAL_INFLIGHT)
        self._screen_inflight: dict[str, int] = {}
        self._authority_locks_guard = threading.RLock()
        self._authority_locks: dict[tuple[str, str], threading.RLock] = {}
        self._execution_gate = threading.RLock()
        self._reconcile_orphaned_executions()

    @contextmanager
    def restore_quiescence(self) -> Iterator[None]:
        with self._execution_gate:
            with self.owner.store.connect() as connection:
                active = connection.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM query_executions
                    WHERE state IN ('QUEUED', 'RUNNING')
                    """
                ).fetchone()["count"]
            with self._jobs_lock:
                active_workers = any(
                    job.future is not None and not job.future.done() for job in self._jobs.values()
                )
            if active or active_workers:
                raise ControlPlaneError(
                    409,
                    "ACTIVE_QUERY_RESTORE_FORBIDDEN",
                    "Cancel or complete controlled queries before restoring",
                )
            yield

    def on_restore_cutover(self) -> None:
        with self._jobs_lock:
            if any(job.future is not None and not job.future.done() for job in self._jobs.values()):
                raise RuntimeError("Controlled-query workers crossed a restore cutover")
            self._jobs.clear()
            self._screen_inflight.clear()
            self._global_slots = threading.BoundedSemaphore(MAX_GLOBAL_INFLIGHT)

    def _reconcile_orphaned_executions(self) -> None:
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            if not self._table_exists(connection, "query_executions"):
                return
            rows = connection.execute(
                """
                SELECT * FROM query_executions
                WHERE state IN ('QUEUED', 'RUNNING')
                ORDER BY created_at, execution_id
                """
            ).fetchall()
            for row in rows:
                connection.execute(
                    """
                    UPDATE query_executions
                    SET state = 'FAILED',
                        error_code = 'QUERY_PROCESS_RESTARTED',
                        completed_at = ?, revision = revision + 1
                    WHERE execution_id = ? AND state IN ('QUEUED', 'RUNNING')
                    """,
                    (now, row["execution_id"]),
                )
                self.owner._append_audit(
                    connection,
                    event_type="CONTROLLED_QUERY_RECOVERED",
                    actor_type="SYSTEM",
                    actor_id="control-plane-startup",
                    target_type="QUERY_EXECUTION",
                    target_id=row["execution_id"],
                    outcome="DENIED",
                    reason=None,
                    details={
                        "request_id": row["request_id"],
                        "screen_id": row["screen_id"],
                        "dataset_id": row["dataset_id"],
                        "previous_state": row["state"],
                        "state": "FAILED",
                        "error_code": "QUERY_PROCESS_RESTARTED",
                    },
                    now=now,
                )

    # QuerySource registration and qualification.

    def list_sources(self, principal: Any) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.read")
        with self.owner.store.connect() as connection:
            rows = connection.execute(
                """
                SELECT s.*, v.source_version_id, v.config_hash, v.secret_id,
                       v.workbook_sha256, sv.fingerprint_suffix
                FROM query_sources s
                JOIN query_source_versions v
                  ON v.source_version_id = s.head_version_id
                 AND v.source_id = s.source_id
                LEFT JOIN query_secret_versions sv
                  ON sv.secret_version_id = v.secret_version_id
                WHERE s.tenant_id = ? AND s.deployment_id = ?
                ORDER BY s.site_id, s.display_name, s.source_id
                """,
                (principal.tenant_id, principal.deployment_id),
            ).fetchall()
            return {
                "api_version": "v1",
                "items": [
                    self._source_response(row)
                    for row in rows
                    if self.owner._can_access_site(
                        principal,
                        row["site_id"],
                        "config.read",
                    )
                ],
            }

    def get_source(self, principal: Any, source_id: str) -> dict[str, Any]:
        with self.owner.store.connect() as connection:
            source = self._load_source(
                connection,
                principal,
                source_id,
                "config.read",
            )
            return self._source_response(source)

    def create_source(
        self,
        principal: Any,
        *,
        site_id: str,
        display_name: str,
        engine: str,
        read_only_account_confirmed: bool,
        connection_input: dict[str, Any] | None,
        excel_file_name: str | None,
        excel_workbook_base64: str | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.edit_technical")
        display_name = self._public_text(display_name, "QuerySource name", 1, 128)
        engine = engine.strip().upper()
        if engine not in QUERY_ENGINES:
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "Unsupported QuerySource engine")
        if engine in DATABASE_ENGINES:
            self.owner.require_permission(principal, "secret.write")
            if not read_only_account_confirmed:
                raise ControlPlaneError(
                    422,
                    "READ_ONLY_ACCOUNT_REQUIRED",
                    "A dedicated read-only database account must be confirmed",
                )
            connection_payload = self._validate_connection_input(engine, connection_input)
            if excel_file_name is not None or excel_workbook_base64 is not None:
                raise ControlPlaneError(
                    422,
                    "SCHEMA_VALIDATION_FAILED",
                    "Database QuerySources cannot contain workbook input",
                )
            workbook: bytes | None = None
            workbook_metadata: dict[str, Any] | None = None
            secret_fingerprint = self.owner.keys.digest(
                "SENSITIVE_REQUEST_DIGEST_HMAC",
                canonical_json(connection_payload),
            )
        else:
            if connection_input is not None:
                raise ControlPlaneError(
                    422,
                    "SCHEMA_VALIDATION_FAILED",
                    "Excel QuerySources cannot contain database connection input",
                )
            workbook, workbook_metadata = self._decode_and_validate_workbook(
                excel_file_name,
                excel_workbook_base64,
            )
            secret_fingerprint = None
            read_only_account_confirmed = True

        operation_id = "createQuerySource"
        command = {
            "site_id": site_id,
            "display_name": display_name,
            "engine": engine,
            "read_only_account_confirmed": bool(read_only_account_confirmed),
            "connection_fingerprint": secret_fingerprint,
            "workbook_sha256": (hashlib.sha256(workbook).hexdigest() if workbook is not None else None),
        }
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        source_id = opaque_id("qsrc")
        source_version_id = opaque_id("qsv")
        workbook_path: Path | None = None
        if workbook is not None:
            workbook_path = self.source_root / f"{source_version_id}.xlsx"
            workbook_path.write_bytes(workbook)

        try:
            with self.owner.store.transaction() as db:
                self.owner._site_row(
                    db,
                    principal,
                    site_id,
                    "config.edit_technical",
                )
                replay = self.owner._idempotency_lookup(
                    db,
                    phase=operation_id,
                    principal_key=principal.user_id,
                    idempotency_key=idempotency_key,
                    request_digest=request_digest,
                )
                if replay is not None:
                    if workbook_path is not None:
                        workbook_path.unlink(missing_ok=True)
                    return json.loads(replay["result_json"])

                secret_id: str | None = None
                secret_version_id: str | None = None
                fingerprint_suffix: str | None = None
                config: dict[str, Any]
                if engine == "EXCEL":
                    if workbook is None or workbook_metadata is None or workbook_path is None:
                        raise RuntimeError("Validated workbook is unavailable")
                    config = {
                        "storage_key": workbook_path.name,
                        "workbook_sha256": hashlib.sha256(workbook).hexdigest(),
                        "worksheet_names": workbook_metadata["worksheet_names"],
                    }
                else:
                    if connection_payload is None:
                        raise RuntimeError("Validated database connection is unavailable")
                    secret_id = opaque_id("qsec")
                    secret_version_id = opaque_id("qscv")
                    key_id = self.owner.keys.key_id("SECRET_ENVELOPE_ENCRYPTION")
                    aad_payload = {
                        "schema_version": "p2_query_secret_aad_v1",
                        "tenant_id": principal.tenant_id,
                        "deployment_id": principal.deployment_id,
                        "site_id": site_id,
                        "source_id": source_id,
                        "source_version_id": source_version_id,
                        "secret_id": secret_id,
                        "secret_version_id": secret_version_id,
                        "engine": engine,
                        "envelope_key_id": key_id,
                    }
                    aad_json = canonical_json(aad_payload)
                    encrypted = self.owner.keys.encrypt_for(
                        "SECRET_ENVELOPE_ENCRYPTION",
                        canonical_json(connection_payload).encode("utf-8"),
                        aad_json.encode("utf-8"),
                    )
                    fingerprint_suffix = self.owner.keys.digest(
                        "SENSITIVE_REQUEST_DIGEST_HMAC",
                        canonical_json(connection_payload),
                    )[-12:]
                    db.execute(
                        """
                        INSERT INTO query_secret_records(
                            secret_id, tenant_id, deployment_id, site_id,
                            secret_type, current_version_id, state,
                            created_by_user_id, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, 'DATABASE_CONNECTION', ?, 'ACTIVE', ?, ?, ?)
                        """,
                        (
                            secret_id,
                            principal.tenant_id,
                            principal.deployment_id,
                            site_id,
                            secret_version_id,
                            principal.user_id,
                            now,
                            now,
                        ),
                    )
                    db.execute(
                        """
                        INSERT INTO query_secret_versions(
                            secret_version_id, secret_id, version_number,
                            envelope_key_id, envelope_nonce, envelope_ciphertext,
                            envelope_aad_json, envelope_aad_hash,
                            fingerprint_suffix, created_by_user_id, created_at
                        ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            secret_version_id,
                            secret_id,
                            key_id,
                            encrypted.nonce,
                            encrypted.value,
                            aad_json,
                            hashlib.sha256(aad_json.encode("utf-8")).hexdigest(),
                            fingerprint_suffix,
                            principal.user_id,
                            now,
                        ),
                    )
                    config = {
                        "connection_material": "ENCRYPTED_SECRET_VERSION",
                        "connection_fields": [
                            "database",
                            "host",
                            "password",
                            "port",
                            "username",
                        ],
                    }

                canonical_config = canonical_json(config)
                config_hash = hashlib.sha256(canonical_config.encode("utf-8")).hexdigest()
                db.execute(
                    """
                    INSERT INTO query_sources(
                        source_id, tenant_id, deployment_id, site_id,
                        display_name, engine, head_version_id, state,
                        qualification_state, read_only_account_confirmed,
                        created_by_user_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', 'UNVERIFIED', ?, ?, ?, ?)
                    """,
                    (
                        source_id,
                        principal.tenant_id,
                        principal.deployment_id,
                        site_id,
                        display_name,
                        engine,
                        source_version_id,
                        int(read_only_account_confirmed),
                        principal.user_id,
                        now,
                        now,
                    ),
                )
                db.execute(
                    """
                    INSERT INTO query_source_versions(
                        source_version_id, source_id, tenant_id, deployment_id,
                        site_id, version_number, engine, canonical_config_json,
                        config_hash, secret_id, secret_version_id,
                        workbook_sha256, workbook_content,
                        created_by_user_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        source_version_id,
                        source_id,
                        principal.tenant_id,
                        principal.deployment_id,
                        site_id,
                        engine,
                        canonical_config,
                        config_hash,
                        secret_id,
                        secret_version_id,
                        (hashlib.sha256(workbook).hexdigest() if workbook is not None else None),
                        workbook,
                        principal.user_id,
                        now,
                    ),
                )
                self.owner._append_audit(
                    db,
                    event_type="QUERY_SOURCE_CREATED",
                    actor_type="USER",
                    actor_id=principal.user_id,
                    target_type="QUERY_SOURCE",
                    target_id=source_id,
                    outcome="SUCCESS",
                    reason=None,
                    details={
                        "site_id": site_id,
                        "source_version_id": source_version_id,
                        "engine": engine,
                        "config_hash": config_hash,
                        "credential_configured": secret_id is not None,
                        "workbook_configured": workbook is not None,
                    },
                    now=now,
                )
                row = self._source_row(db, source_id)
                result = self._source_response(row)
                self.owner._idempotency_store(
                    db,
                    phase=operation_id,
                    principal_key=principal.user_id,
                    idempotency_key=idempotency_key,
                    request_digest=request_digest,
                    result=result,
                    now=now,
                )
                return result
        except Exception:
            if workbook_path is not None:
                workbook_path.unlink(missing_ok=True)
            raise

    def test_source(
        self,
        principal: Any,
        source_id: str,
        *,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.edit_technical")
        with self._authority_lock("query-source", source_id):
            result = self._test_source_serialized(
                principal,
                source_id,
                if_match=if_match,
                idempotency_key=idempotency_key,
            )
            if result["qualification_state"] != "AVAILABLE":
                self._cancel_jobs_for_authority(
                    resource_kind="query-source",
                    resource_id=source_id,
                    error_code="QUERY_SOURCE_NOT_AVAILABLE",
                )
        return result

    def _test_source_serialized(
        self,
        principal: Any,
        source_id: str,
        *,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        operation_id = "testQuerySource"
        command = {"source_id": source_id, "if_match": if_match}
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        started = perf_counter()
        with self.owner.store.connect() as connection:
            source = self._load_source(
                connection,
                principal,
                source_id,
                "config.edit_technical",
            )
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            self.owner._require_resource_etag(
                if_match,
                "query-source",
                source_id,
                source["revision"],
            )

        outcome = "AVAILABLE"
        code = "CONNECTION_TEST_PASSED"
        try:
            self._probe_source(source)
        except QueryExecutionFailure as exc:
            outcome = "FAILED"
            code = exc.code
        latency_ms = max(0, int((perf_counter() - started) * 1000))
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            current = self._load_source(
                connection,
                principal,
                source_id,
                "config.edit_technical",
            )
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            self.owner._require_resource_etag(
                if_match,
                "query-source",
                source_id,
                current["revision"],
            )
            connection.execute(
                """
                UPDATE query_sources
                SET qualification_state = ?, qualification_code = ?,
                    last_tested_at = ?, updated_at = ?, revision = revision + 1
                WHERE source_id = ? AND revision = ?
                """,
                (
                    outcome,
                    code,
                    now,
                    now,
                    source_id,
                    current["revision"],
                ),
            )
            self.owner._append_audit(
                connection,
                event_type="QUERY_SOURCE_CONNECTION_TESTED",
                actor_type="USER",
                actor_id=principal.user_id,
                target_type="QUERY_SOURCE",
                target_id=source_id,
                outcome="SUCCESS" if outcome == "AVAILABLE" else "DENIED",
                reason=None,
                details={
                    "engine": current["engine"],
                    "qualification_state": outcome,
                    "qualification_code": code,
                    "latency_ms": latency_ms,
                    "read_only_account_confirmed": bool(current["read_only_account_confirmed"]),
                },
                now=now,
            )
            result = {
                "api_version": "v1",
                "source_id": source_id,
                "source_version_id": current["source_version_id"],
                "engine": current["engine"],
                "qualification_state": outcome,
                "code": code,
                "message": self._qualification_message(code),
                "latency_ms": latency_ms,
                "deployment_local_evidence": True,
                "product_certification": "UNVERIFIED",
                "read_only_assurance": (
                    "WORKBOOK_READ_ONLY_ADAPTER"
                    if current["engine"] == "EXCEL"
                    else "ADMIN_ATTESTED_AND_TEMPLATE_ENFORCED"
                ),
            }
            self.owner._idempotency_store(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                now=now,
            )
            return result

    def disable_source(
        self,
        principal: Any,
        source_id: str,
        *,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.edit_technical")
        return self._disable_envelope(
            principal,
            resource_kind="query-source",
            table="query_sources",
            id_column="source_id",
            resource_id=source_id,
            if_match=if_match,
            idempotency_key=idempotency_key,
            operation_id="disableQuerySource",
            event_type="QUERY_SOURCE_DISABLED",
        )

    # Immutable approved datasets.

    def list_datasets(
        self,
        principal: Any,
        *,
        site_id: str | None = None,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.read")
        with self.owner.store.connect() as connection:
            rows = connection.execute(
                """
                SELECT d.*, v.*, s.engine, s.display_name AS source_display_name,
                       s.state AS source_state,
                       s.qualification_state AS source_qualification_state
                FROM query_datasets d
                JOIN query_dataset_versions v
                  ON v.dataset_version_id = d.head_version_id
                 AND v.dataset_id = d.dataset_id
                JOIN query_sources s ON s.source_id = d.source_id
                WHERE d.tenant_id = ? AND d.deployment_id = ?
                  AND (? IS NULL OR d.site_id = ?)
                ORDER BY d.site_id, d.display_name, d.dataset_id
                """,
                (
                    principal.tenant_id,
                    principal.deployment_id,
                    site_id,
                    site_id,
                ),
            ).fetchall()
            return {
                "api_version": "v1",
                "items": [
                    self._dataset_response(row)
                    for row in rows
                    if self.owner._can_access_site(
                        principal,
                        row["site_id"],
                        "config.read",
                    )
                ],
            }

    def get_dataset(self, principal: Any, dataset_id: str) -> dict[str, Any]:
        with self.owner.store.connect() as connection:
            row = self._load_dataset(
                connection,
                principal,
                dataset_id,
                "config.read",
            )
            return self._dataset_response(row)

    def create_dataset(
        self,
        principal: Any,
        *,
        source_id: str,
        display_name: str,
        metric_definition: str,
        time_scope_description: str,
        freshness_label: str,
        parameters: list[dict[str, Any]],
        output_fields: list[str],
        definition: dict[str, Any],
        row_limit: int,
        timeout_ms: int,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.edit_technical")
        display_name = self._public_text(display_name, "Dataset name", 1, 128)
        metric_definition = self._public_text(
            metric_definition,
            "Metric definition",
            1,
            500,
        )
        time_scope_description = self._public_text(
            time_scope_description,
            "Time-scope description",
            1,
            300,
        )
        freshness_label = self._public_text(
            freshness_label,
            "Freshness label",
            1,
            128,
        )
        if not isinstance(row_limit, int) or isinstance(row_limit, bool) or not 1 <= row_limit <= 500:
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "row_limit must be 1 through 500")
        if not isinstance(timeout_ms, int) or isinstance(timeout_ms, bool) or not 100 <= timeout_ms <= 120000:
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "timeout_ms must be 100 through 120000",
            )
        parameter_schema = self._validate_parameter_schema(parameters)
        normalized_fields = self._validate_output_fields(output_fields)
        with self.owner.store.connect() as connection:
            source = self._load_source(
                connection,
                principal,
                source_id,
                "config.edit_technical",
            )
        normalized_definition = self._validate_dataset_definition(
            source,
            parameter_schema,
            normalized_fields,
            definition,
        )
        parameter_json = canonical_json(parameter_schema)
        fields_json = canonical_json(normalized_fields)
        definition_json = canonical_json(normalized_definition)
        definition_hash = hashlib.sha256(
            canonical_json(
                {
                    "schema_version": DATASET_SCHEMA_VERSION,
                    "source_id": source_id,
                    "source_version_id": source["source_version_id"],
                    "metric_definition": metric_definition,
                    "time_scope_description": time_scope_description,
                    "freshness_label": freshness_label,
                    "parameters": parameter_schema,
                    "output_fields": normalized_fields,
                    "definition": normalized_definition,
                    "row_limit": row_limit,
                    "timeout_ms": timeout_ms,
                }
            ).encode("utf-8")
        ).hexdigest()
        operation_id = "createQueryDataset"
        command = {
            "source_id": source_id,
            "display_name": display_name,
            "definition_hash": definition_hash,
        }
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            source = self._load_source(
                connection,
                principal,
                source_id,
                "config.edit_technical",
            )
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            dataset_id = opaque_id("qds")
            dataset_version_id = opaque_id("qdsv")
            connection.execute(
                """
                INSERT INTO query_datasets(
                    dataset_id, tenant_id, deployment_id, site_id,
                    source_id, display_name, head_version_id, state,
                    created_by_user_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?, ?)
                """,
                (
                    dataset_id,
                    principal.tenant_id,
                    principal.deployment_id,
                    source["site_id"],
                    source_id,
                    display_name,
                    dataset_version_id,
                    principal.user_id,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO query_dataset_versions(
                    dataset_version_id, dataset_id, tenant_id, deployment_id,
                    site_id, source_id, source_version_id, version_number,
                    schema_version, metric_definition, time_scope_description,
                    freshness_label, canonical_parameter_schema_json,
                    canonical_output_fields_json, canonical_definition_json,
                    definition_hash, row_limit, timeout_ms,
                    created_by_user_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset_version_id,
                    dataset_id,
                    principal.tenant_id,
                    principal.deployment_id,
                    source["site_id"],
                    source_id,
                    source["source_version_id"],
                    DATASET_SCHEMA_VERSION,
                    metric_definition,
                    time_scope_description,
                    freshness_label,
                    parameter_json,
                    fields_json,
                    definition_json,
                    definition_hash,
                    row_limit,
                    timeout_ms,
                    principal.user_id,
                    now,
                ),
            )
            self.owner._append_audit(
                connection,
                event_type="QUERY_DATASET_CREATED",
                actor_type="USER",
                actor_id=principal.user_id,
                target_type="QUERY_DATASET",
                target_id=dataset_id,
                outcome="SUCCESS",
                reason=None,
                details={
                    "site_id": source["site_id"],
                    "source_id": source_id,
                    "source_version_id": source["source_version_id"],
                    "dataset_version_id": dataset_version_id,
                    "definition_hash": definition_hash,
                    "parameter_names": [parameter["name"] for parameter in parameter_schema],
                    "output_fields": normalized_fields,
                    "row_limit": row_limit,
                    "timeout_ms": timeout_ms,
                },
                now=now,
            )
            row = self._dataset_row(connection, dataset_id)
            result = self._dataset_response(row)
            self.owner._idempotency_store(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                now=now,
            )
            return result

    def disable_dataset(
        self,
        principal: Any,
        dataset_id: str,
        *,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.edit_technical")
        return self._disable_envelope(
            principal,
            resource_kind="query-dataset",
            table="query_datasets",
            id_column="dataset_id",
            resource_id=dataset_id,
            if_match=if_match,
            idempotency_key=idempotency_key,
            operation_id="disableQueryDataset",
            event_type="QUERY_DATASET_DISABLED",
        )

    # Draft/release sidecars preserve accepted P1.3 and P2.1 base schemas.

    def assign_draft_datasets(
        self,
        principal: Any,
        draft_id: str,
        *,
        dataset_version_ids: list[str],
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.owner.require_permission(principal, "config.edit_technical")
        if (
            not isinstance(dataset_version_ids, list)
            or len(dataset_version_ids) > 50
            or any(not isinstance(value, str) or not value for value in dataset_version_ids)
            or len(dataset_version_ids) != len(set(dataset_version_ids))
        ):
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "Dataset version IDs must be a unique list of at most 50 items",
            )
        ordered_ids = sorted(dataset_version_ids)
        operation_id = "assignDraftQueryDatasets"
        command = {
            "draft_id": draft_id,
            "dataset_version_ids": ordered_ids,
            "if_match": if_match,
        }
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            draft = self.owner.p1_3._load_draft(
                connection,
                principal,
                draft_id,
                "config.edit_technical",
            )
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            self.owner._require_resource_etag(
                if_match,
                "config-draft",
                draft_id,
                draft["revision"],
            )
            if draft["state"] != "DRAFT" or draft["current_revision"] < 1:
                raise ControlPlaneError(
                    409,
                    "INVALID_STATE_TRANSITION",
                    "Only a populated DRAFT can receive query datasets",
                )
            site_id = self.owner.p2_1._draft_site_id(connection, draft)
            refs = self._verified_dataset_refs(
                connection,
                principal,
                site_id,
                ordered_ids,
                require_available=False,
            )
            refs_json = canonical_json(refs)
            assignment_hash = hashlib.sha256(refs_json.encode("utf-8")).hexdigest()
            current = self._draft_assignment_row(
                connection,
                draft_id,
                draft["current_revision"],
            )
            if current is not None and current["assignment_hash"] == assignment_hash:
                result = self.owner.p1_3._draft_response(connection, draft)
            else:
                next_revision = draft["current_revision"] + 1
                connection.execute(
                    """
                    INSERT INTO config_draft_revisions(
                        draft_id, draft_revision, schema_version,
                        canonical_spec_json, content_hash,
                        created_by_user_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        draft_id,
                        next_revision,
                        draft["schema_version"],
                        draft["working_spec_json"],
                        draft["content_hash"],
                        principal.user_id,
                        now,
                    ),
                )
                self.owner.p2_1.copy_draft_assignment_forward(
                    connection,
                    draft_id=draft_id,
                    source_revision=draft["current_revision"],
                    target_revision=next_revision,
                )
                self._insert_draft_assignment(
                    connection,
                    draft_id=draft_id,
                    draft_revision=next_revision,
                    principal=principal,
                    site_id=site_id,
                    refs_json=refs_json,
                    assignment_hash=assignment_hash,
                    now=now,
                )
                metadata = self.owner._metadata(connection)
                connection.execute(
                    """
                    UPDATE config_drafts SET state = 'DRAFT',
                        current_revision = ?, last_editor_user_id = ?,
                        validation_record_id = NULL, preview_record_id = NULL,
                        approval_record_id = NULL, control_plane_epoch = ?,
                        updated_at = ?, revision = revision + 1
                    WHERE draft_id = ?
                    """,
                    (
                        next_revision,
                        principal.user_id,
                        metadata["revision"],
                        now,
                        draft_id,
                    ),
                )
                self.owner._append_audit(
                    connection,
                    event_type="CONFIG_DRAFT_QUERY_DATASETS_ASSIGNED",
                    actor_type="USER",
                    actor_id=principal.user_id,
                    target_type="CONFIG_DRAFT",
                    target_id=draft_id,
                    outcome="SUCCESS",
                    reason=None,
                    details={
                        "draft_revision": next_revision,
                        "assignment_hash": assignment_hash,
                        "dataset_version_ids": ordered_ids,
                    },
                    now=now,
                )
                updated = self.owner.p1_3._load_draft(
                    connection,
                    principal,
                    draft_id,
                    "config.read",
                )
                result = self.owner.p1_3._draft_response(connection, updated)
            self.owner._idempotency_store(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                now=now,
            )
            return result

    def draft_assignment_response(
        self,
        connection: sqlite3.Connection,
        draft_id: str,
        draft_revision: int,
    ) -> dict[str, Any] | None:
        row = self._draft_assignment_row(connection, draft_id, draft_revision)
        if row is None:
            return None
        refs = self._verified_assignment_refs(connection, row)
        return {
            "schema_version": QUERY_SNAPSHOT_SCHEMA_VERSION,
            "dataset_refs": refs,
            "assignment_hash": row["assignment_hash"],
            "assigned_by_user_id": row["assigned_by_user_id"],
            "assigned_at": row["assigned_at"],
            "immutable": True,
        }

    def copy_draft_assignment_forward(
        self,
        connection: sqlite3.Connection,
        *,
        draft_id: str,
        source_revision: int,
        target_revision: int,
    ) -> bool:
        if not self._table_exists(connection, "config_draft_query_assignments"):
            return
        source = self._draft_assignment_row(connection, draft_id, source_revision)
        if source is None:
            return
        connection.execute(
            """
            INSERT INTO config_draft_query_assignments(
                draft_id, draft_revision, tenant_id, deployment_id,
                site_id, canonical_dataset_refs_json, assignment_hash,
                assigned_by_user_id, assigned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                draft_id,
                target_revision,
                source["tenant_id"],
                source["deployment_id"],
                source["site_id"],
                source["canonical_dataset_refs_json"],
                source["assignment_hash"],
                source["assigned_by_user_id"],
                source["assigned_at"],
            ),
        )

    def resolve_draft_queries(
        self,
        connection: sqlite3.Connection,
        *,
        draft_id: str,
        draft_revision: int,
        targets: list[dict[str, Any]],
        capability_resolution: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        assignment = self._draft_assignment_row(connection, draft_id, draft_revision)
        querying = self._querying_selection(capability_resolution)
        if assignment is None:
            if querying["enabled"]:
                raise ControlPlaneError(
                    422,
                    "QUERY_DATASET_ASSIGNMENT_REQUIRED",
                    "Controlled querying requires an approved dataset assignment",
                )
            return None
        refs = self._verified_assignment_refs(connection, assignment)
        if not querying["enabled"]:
            if refs:
                raise ControlPlaneError(
                    422,
                    "QUERYING_CAPABILITY_DISABLED",
                    "Datasets cannot be assigned while querying is disabled",
                )
            return {
                "assignment": assignment,
                "dataset_refs": [],
                "querying_enabled": False,
                "activation_eligible": True,
                "findings": [],
                "snapshot_hashes": {},
            }
        if querying["primary_provider_id"] != "controlled_query" or querying["fallback_provider_ids"]:
            raise ControlPlaneError(
                422,
                "CONTROLLED_QUERY_PROVIDER_REQUIRED",
                "P2.2 datasets require controlled_query as the sole querying Provider",
            )
        if not refs:
            raise ControlPlaneError(
                422,
                "QUERY_DATASET_ASSIGNMENT_REQUIRED",
                "At least one approved dataset is required",
            )
        findings: list[dict[str, Any]] = []
        activation_eligible = True
        for ref in refs:
            source = connection.execute(
                """
                SELECT state, qualification_state FROM query_sources
                WHERE source_id = ? AND head_version_id = ?
                """,
                (ref["source_id"], ref["source_version_id"]),
            ).fetchone()
            dataset = connection.execute(
                """
                SELECT state FROM query_datasets
                WHERE dataset_id = ? AND head_version_id = ?
                """,
                (ref["dataset_id"], ref["dataset_version_id"]),
            ).fetchone()
            if (
                source is None
                or dataset is None
                or source["state"] != "ACTIVE"
                or dataset["state"] != "ACTIVE"
                or source["qualification_state"] != "AVAILABLE"
            ):
                activation_eligible = False
                findings.append(
                    {
                        "severity": "ERROR",
                        "code": "QUERY_SOURCE_NOT_AVAILABLE",
                        "dataset_id": ref["dataset_id"],
                        "source_id": ref["source_id"],
                        "message": "An assigned QuerySource is disabled, untested or unavailable.",
                    }
                )
        snapshot_hashes: dict[str, str] = {}
        for target in targets:
            snapshot = self._query_snapshot_payload(
                screen_id=target["screen_id"],
                digital_human_instance_id=target["effective_config"]["digital_human_instance_id"],
                assignment_hash=assignment["assignment_hash"],
                dataset_refs=refs,
                querying_enabled=True,
            )
            snapshot_hashes[target["screen_id"]] = hashlib.sha256(
                canonical_json(snapshot).encode("utf-8")
            ).hexdigest()
        return {
            "assignment": assignment,
            "dataset_refs": refs,
            "querying_enabled": True,
            "activation_eligible": activation_eligible,
            "findings": findings,
            "snapshot_hashes": snapshot_hashes,
        }

    def record_validation(
        self,
        connection: sqlite3.Connection,
        *,
        principal: Any,
        draft: sqlite3.Row,
        base_validation_record_id: str,
        query_resolution: dict[str, Any] | None,
        now: float,
    ) -> dict[str, Any] | None:
        if query_resolution is None:
            return None
        findings = query_resolution["findings"]
        outcome = "PASS" if query_resolution["activation_eligible"] else "FAIL"
        findings_json = canonical_json(findings)
        record_id = opaque_id("qval")
        connection.execute(
            """
            INSERT INTO query_validation_records(
                query_validation_record_id, draft_id, draft_revision,
                base_validation_record_id, assignment_hash, outcome,
                findings_json, findings_hash, validator_version,
                created_by_user_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                draft["draft_id"],
                draft["current_revision"],
                base_validation_record_id,
                query_resolution["assignment"]["assignment_hash"],
                outcome,
                findings_json,
                hashlib.sha256(findings_json.encode("utf-8")).hexdigest(),
                QUERY_VALIDATOR_VERSION,
                principal.user_id,
                now,
            ),
        )
        return {
            "query_validation_record_id": record_id,
            "outcome": outcome,
            "findings": findings,
        }

    def require_release_validation(
        self,
        connection: sqlite3.Connection,
        *,
        draft: sqlite3.Row,
        base_validation_record_id: str,
        query_resolution: dict[str, Any] | None,
    ) -> None:
        if query_resolution is None:
            return
        record = connection.execute(
            """
            SELECT * FROM query_validation_records
            WHERE draft_id = ? AND draft_revision = ?
              AND base_validation_record_id = ?
            """,
            (
                draft["draft_id"],
                draft["current_revision"],
                base_validation_record_id,
            ),
        ).fetchone()
        if (
            record is None
            or record["outcome"] != "PASS"
            or record["assignment_hash"] != query_resolution["assignment"]["assignment_hash"]
            or not query_resolution["activation_eligible"]
        ):
            raise ControlPlaneError(
                409,
                "QUERY_VALIDATION_STALE",
                "Controlled-query validation evidence is unavailable or stale",
            )

    def insert_release_snapshot(
        self,
        connection: sqlite3.Connection,
        *,
        release_target_id: str,
        target: dict[str, Any],
        query_resolution: dict[str, Any] | None,
        now: float,
    ) -> None:
        if query_resolution is None:
            return
        snapshot = self._query_snapshot_payload(
            screen_id=target["screen_id"],
            digital_human_instance_id=target["effective_config"]["digital_human_instance_id"],
            assignment_hash=query_resolution["assignment"]["assignment_hash"],
            dataset_refs=query_resolution["dataset_refs"],
            querying_enabled=query_resolution["querying_enabled"],
        )
        canonical_snapshot = canonical_json(snapshot)
        connection.execute(
            """
            INSERT INTO release_target_query_snapshots(
                release_target_id, tenant_id, deployment_id, site_id,
                screen_id, canonical_query_snapshot_json,
                query_snapshot_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                release_target_id,
                query_resolution["assignment"]["tenant_id"],
                query_resolution["assignment"]["deployment_id"],
                query_resolution["assignment"]["site_id"],
                target["screen_id"],
                canonical_snapshot,
                hashlib.sha256(canonical_snapshot.encode("utf-8")).hexdigest(),
                now,
            ),
        )

    def copy_release_snapshot_forward(
        self,
        connection: sqlite3.Connection,
        *,
        source_release_target_id: str,
        target_release_target_id: str,
        now: float,
    ) -> None:
        if not self._table_exists(connection, "release_target_query_snapshots"):
            return
        source = connection.execute(
            """
            SELECT * FROM release_target_query_snapshots
            WHERE release_target_id = ?
            """,
            (source_release_target_id,),
        ).fetchone()
        if source is None:
            return
        target = connection.execute(
            "SELECT * FROM release_targets WHERE release_target_id = ?",
            (target_release_target_id,),
        ).fetchone()
        if (
            target is None
            or target["tenant_id"] != source["tenant_id"]
            or target["deployment_id"] != source["deployment_id"]
            or target["screen_id"] != source["screen_id"]
        ):
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Query rollback snapshot ownership changed",
            )
        connection.execute(
            """
            INSERT INTO release_target_query_snapshots(
                release_target_id, tenant_id, deployment_id, site_id,
                screen_id, canonical_query_snapshot_json,
                query_snapshot_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target_release_target_id,
                source["tenant_id"],
                source["deployment_id"],
                source["site_id"],
                source["screen_id"],
                source["canonical_query_snapshot_json"],
                source["query_snapshot_hash"],
                now,
            ),
        )

    def release_snapshot_response(
        self,
        connection: sqlite3.Connection,
        release_target_id: str,
    ) -> dict[str, Any] | None:
        row = self._release_snapshot_row(connection, release_target_id)
        if row is None:
            return None
        snapshot = self._verified_release_snapshot(connection, row)
        return {
            **snapshot,
            "query_snapshot_hash": row["query_snapshot_hash"],
            "immutable": True,
        }

    # Screen-bound dataset discovery and bounded asynchronous execution.

    def list_screen_datasets(
        self,
        principal: Any,
        screen_id: str,
    ) -> dict[str, Any]:
        with self.owner.store.connect() as connection:
            screen = self.owner._screen_row(
                connection,
                principal,
                screen_id,
                "config.read",
            )
            binding, target, snapshot = self._applied_query_context(
                connection,
                screen["screen_id"],
                principal.tenant_id,
                principal.deployment_id,
            )
            return self._runtime_dataset_list(
                screen_id=screen["screen_id"],
                binding=binding,
                target=target,
                snapshot=snapshot,
            )

    def list_device_datasets(self, device: Any) -> dict[str, Any]:
        with self.owner.store.connect() as connection:
            binding, target, snapshot = self._applied_query_context(
                connection,
                device.screen_id,
                device.tenant_id,
                device.deployment_id,
            )
            return self._runtime_dataset_list(
                screen_id=device.screen_id,
                binding=binding,
                target=target,
                snapshot=snapshot,
            )

    def start_user_execution(
        self,
        principal: Any,
        screen_id: str,
        dataset_id: str,
        *,
        parameters: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        with self.owner.store.connect() as connection:
            screen = self.owner._screen_row(
                connection,
                principal,
                screen_id,
                "config.read",
            )
        return self._start_execution(
            tenant_id=principal.tenant_id,
            deployment_id=principal.deployment_id,
            site_id=screen["site_id"],
            screen_id=screen["screen_id"],
            dataset_id=dataset_id,
            parameters=parameters,
            actor_type="USER",
            actor_id=principal.user_id,
            principal_key=principal.user_id,
            idempotency_key=idempotency_key,
        )

    def start_device_execution(
        self,
        device: Any,
        dataset_id: str,
        *,
        parameters: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._start_execution(
            tenant_id=device.tenant_id,
            deployment_id=device.deployment_id,
            site_id=None,
            screen_id=device.screen_id,
            dataset_id=dataset_id,
            parameters=parameters,
            actor_type="DEVICE",
            actor_id=device.credential_id,
            principal_key=device.credential_id,
            idempotency_key=idempotency_key,
        )

    def get_user_execution(
        self,
        principal: Any,
        screen_id: str,
        execution_id: str,
    ) -> dict[str, Any]:
        with self.owner.store.connect() as connection:
            self.owner._screen_row(
                connection,
                principal,
                screen_id,
                "config.read",
            )
        return self._execution_response(
            execution_id,
            tenant_id=principal.tenant_id,
            deployment_id=principal.deployment_id,
            screen_id=screen_id,
        )

    def get_device_execution(
        self,
        device: Any,
        execution_id: str,
    ) -> dict[str, Any]:
        return self._execution_response(
            execution_id,
            tenant_id=device.tenant_id,
            deployment_id=device.deployment_id,
            screen_id=device.screen_id,
        )

    def cancel_user_execution(
        self,
        principal: Any,
        screen_id: str,
        execution_id: str,
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        with self.owner.store.connect() as connection:
            self.owner._screen_row(
                connection,
                principal,
                screen_id,
                "config.read",
            )
        return self._cancel_execution(
            execution_id,
            tenant_id=principal.tenant_id,
            deployment_id=principal.deployment_id,
            screen_id=screen_id,
            actor_type="USER",
            actor_id=principal.user_id,
            principal_key=principal.user_id,
            idempotency_key=idempotency_key,
        )

    def cancel_device_execution(
        self,
        device: Any,
        execution_id: str,
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._cancel_execution(
            execution_id,
            tenant_id=device.tenant_id,
            deployment_id=device.deployment_id,
            screen_id=device.screen_id,
            actor_type="DEVICE",
            actor_id=device.credential_id,
            principal_key=f"device:{device.credential_id}",
            idempotency_key=idempotency_key,
        )

    def _start_execution(
        self,
        *,
        tenant_id: str,
        deployment_id: str,
        site_id: str | None,
        screen_id: str,
        dataset_id: str,
        parameters: dict[str, Any],
        actor_type: str,
        actor_id: str,
        principal_key: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        with self._execution_gate:
            return self._start_execution_serialized(
                tenant_id=tenant_id,
                deployment_id=deployment_id,
                site_id=site_id,
                screen_id=screen_id,
                dataset_id=dataset_id,
                parameters=parameters,
                actor_type=actor_type,
                actor_id=actor_id,
                principal_key=principal_key,
                idempotency_key=idempotency_key,
            )

    def _start_execution_serialized(
        self,
        *,
        tenant_id: str,
        deployment_id: str,
        site_id: str | None,
        screen_id: str,
        dataset_id: str,
        parameters: dict[str, Any],
        actor_type: str,
        actor_id: str,
        principal_key: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        operation_phase = "startControlledQueryDevice" if actor_type == "DEVICE" else "startControlledQuery"
        if not isinstance(parameters, dict):
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "parameters must be an object",
            )
        with self.owner.store.connect() as connection:
            _binding, target, snapshot = self._applied_query_context(
                connection,
                screen_id,
                tenant_id,
                deployment_id,
            )
            if site_id is not None and site_id != snapshot["site_id"]:
                raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "Dataset was not found")
            ref = next(
                (item for item in snapshot["dataset_refs"] if item["dataset_id"] == dataset_id),
                None,
            )
            if ref is None:
                raise ControlPlaneError(
                    404,
                    "RESOURCE_NOT_FOUND",
                    "Dataset was not found",
                )
            dataset = self._runtime_dataset_row(connection, ref)
            normalized_parameters, time_scope = self._validate_runtime_parameters(
                dataset,
                parameters,
            )
            command = {
                "screen_id": screen_id,
                "release_target_id": target["release_target_id"],
                "dataset_id": dataset_id,
                "dataset_version_id": ref["dataset_version_id"],
                "parameter_digest": self.owner.keys.digest(
                    "SENSITIVE_REQUEST_DIGEST_HMAC",
                    canonical_json(normalized_parameters),
                ),
            }
            request_digest = self.owner._sensitive_request_digest(operation_phase, command)
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_phase,
                principal_key=principal_key,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])

        execution_id = opaque_id("qex")
        request_id = opaque_id("req")
        now = self.owner.clock()
        acquired, rejection = self._acquire_execution_slot(screen_id)
        if not acquired:
            with self.owner.store.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO query_executions(
                        execution_id, request_id, tenant_id, deployment_id,
                        site_id, screen_id, release_target_id, source_id,
                        source_version_id, dataset_id, dataset_version_id,
                        actor_type, actor_id, parameter_names_json,
                        parameter_digest, state, error_code, created_at,
                        completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'REJECTED_BACKPRESSURE', ?, ?, ?)
                    """,
                    (
                        execution_id,
                        request_id,
                        tenant_id,
                        deployment_id,
                        snapshot["site_id"],
                        screen_id,
                        target["release_target_id"],
                        ref["source_id"],
                        ref["source_version_id"],
                        dataset_id,
                        ref["dataset_version_id"],
                        actor_type,
                        actor_id,
                        canonical_json(sorted(normalized_parameters)),
                        command["parameter_digest"],
                        rejection,
                        now,
                        now,
                    ),
                )
                result = {
                    "api_version": "v1",
                    "execution_id": execution_id,
                    "request_id": request_id,
                    "state": "REJECTED_BACKPRESSURE",
                    "error": {
                        "code": rejection,
                        "message": "The controlled-query queue is full; retry later.",
                        "retryable": True,
                    },
                }
                self.owner._append_audit(
                    connection,
                    event_type="CONTROLLED_QUERY_COMPLETED",
                    actor_type=actor_type,
                    actor_id=actor_id,
                    target_type="QUERY_EXECUTION",
                    target_id=execution_id,
                    outcome="DENIED",
                    reason=None,
                    details={
                        "request_id": request_id,
                        "screen_id": screen_id,
                        "source_id": ref["source_id"],
                        "source_version_id": ref["source_version_id"],
                        "dataset_id": dataset_id,
                        "dataset_version_id": ref["dataset_version_id"],
                        "parameter_names": sorted(normalized_parameters),
                        "parameter_digest": command["parameter_digest"],
                        "state": "REJECTED_BACKPRESSURE",
                        "error_code": rejection,
                        "row_count": None,
                        "latency_ms": 0,
                    },
                    now=now,
                )
                self.owner._idempotency_store(
                    connection,
                    phase=operation_phase,
                    principal_key=principal_key,
                    idempotency_key=idempotency_key,
                    request_digest=request_digest,
                    result=result,
                    now=now,
                )
                return result

        job = QueryJob(
            execution_id=execution_id,
            request_id=request_id,
            screen_id=screen_id,
            source_id=ref["source_id"],
            dataset_id=dataset_id,
            dataset_version_id=ref["dataset_version_id"],
        )
        with self._jobs_lock:
            self._jobs[execution_id] = job
        try:
            with self.owner.store.transaction() as connection:
                connection.execute(
                    """
                    INSERT INTO query_executions(
                        execution_id, request_id, tenant_id, deployment_id,
                        site_id, screen_id, release_target_id, source_id,
                        source_version_id, dataset_id, dataset_version_id,
                        actor_type, actor_id, parameter_names_json,
                        parameter_digest, state, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'QUEUED', ?)
                    """,
                    (
                        execution_id,
                        request_id,
                        tenant_id,
                        deployment_id,
                        snapshot["site_id"],
                        screen_id,
                        target["release_target_id"],
                        ref["source_id"],
                        ref["source_version_id"],
                        dataset_id,
                        ref["dataset_version_id"],
                        actor_type,
                        actor_id,
                        canonical_json(sorted(normalized_parameters)),
                        command["parameter_digest"],
                        now,
                    ),
                )
                result = {
                    "api_version": "v1",
                    "execution_id": execution_id,
                    "request_id": request_id,
                    "state": "QUEUED",
                    "screen_id": screen_id,
                    "dataset_id": dataset_id,
                    "poll_after_ms": 50,
                }
                self.owner._idempotency_store(
                    connection,
                    phase=operation_phase,
                    principal_key=principal_key,
                    idempotency_key=idempotency_key,
                    request_digest=request_digest,
                    result=result,
                    now=now,
                )
            job.future = self._executor.submit(
                self._run_execution,
                job,
                dict(ref),
                normalized_parameters,
                time_scope,
                snapshot,
                target["release_target_id"],
            )
            return result
        except Exception:
            with self._jobs_lock:
                self._jobs.pop(execution_id, None)
            self._release_execution_slot(screen_id)
            raise

    def _run_execution(
        self,
        job: QueryJob,
        ref: dict[str, Any],
        parameters: dict[str, Any],
        time_scope: dict[str, Any],
        snapshot: dict[str, Any],
        release_target_id: str,
    ) -> None:
        started = perf_counter()
        started_at = self.owner.clock()
        timeout_timer: threading.Timer | None = None
        try:
            if job.cancel_event.is_set():
                raise self._cancellation_failure(job)
            with (
                self._authority_lock("query-source", job.source_id),
                self._authority_lock("query-dataset", job.dataset_id),
            ):
                if job.cancel_event.is_set():
                    raise self._cancellation_failure(job)
                with self.owner.store.transaction() as connection:
                    current = connection.execute(
                        "SELECT state FROM query_executions WHERE execution_id = ?",
                        (job.execution_id,),
                    ).fetchone()
                    if current is None or current["state"] != "QUEUED":
                        raise self._cancellation_failure(job)
                    try:
                        dataset = self._runtime_dataset_row(connection, ref)
                    except ControlPlaneError as exc:
                        if exc.code in {
                            "QUERY_SOURCE_NOT_AVAILABLE",
                            "QUERY_DATASET_NOT_AVAILABLE",
                        }:
                            raise QueryExecutionFailure(exc.code, exc.message) from exc
                        raise
                    updated = connection.execute(
                        """
                        UPDATE query_executions
                        SET state = 'RUNNING', started_at = ?, revision = revision + 1
                        WHERE execution_id = ? AND state = 'QUEUED'
                        """,
                        (started_at, job.execution_id),
                    )
                    if updated.rowcount != 1:
                        raise self._cancellation_failure(job)
            timeout_timer = threading.Timer(
                dataset["timeout_ms"] / 1000,
                self._expire_execution,
                args=(job, dataset["timeout_ms"]),
            )
            timeout_timer.daemon = True
            timeout_timer.start()
            if job.cancel_event.is_set():
                raise self._cancellation_failure(job)
            rows, fields = self._execute_dataset(job, dataset, parameters)
            if job.cancel_event.is_set():
                raise self._cancellation_failure(job)
            latency_ms = max(0, int((perf_counter() - started) * 1000))
            result = {
                "api_version": "v1",
                "execution_id": job.execution_id,
                "request_id": job.request_id,
                "state": "SUCCEEDED",
                "source": {
                    "source_id": dataset["source_id"],
                    "source_version_id": dataset["source_version_id"],
                    "label": dataset["source_display_name"],
                    "engine": dataset["engine"],
                    "qualification": "DEPLOYMENT_LOCAL_AVAILABLE",
                    "product_certification": "UNVERIFIED",
                },
                "dataset": {
                    "dataset_id": dataset["dataset_id"],
                    "dataset_version_id": dataset["dataset_version_id"],
                    "label": dataset["display_name"],
                    "metric_definition": dataset["metric_definition"],
                    "time_scope_description": dataset["time_scope_description"],
                    "freshness_label": dataset["freshness_label"],
                },
                "requested_time_scope": time_scope,
                "permission_subject": {
                    "type": "SCREEN_INSTANCE",
                    "screen_id": snapshot["screen_id"],
                    "release_target_id": release_target_id,
                },
                "provider": "controlled_query",
                "latency_ms": latency_ms,
                "cache": "MISS_NO_SHARED_CACHE",
                "fields": fields,
                "row_count": len(rows),
                "rows": rows,
            }
            with job.lock:
                job.result = result
            self._finish_execution(
                job,
                state="SUCCEEDED",
                error_code=None,
                row_count=len(rows),
                latency_ms=latency_ms,
            )
        except QueryExecutionFailure as exc:
            state = {
                "QUERY_CANCELLED": "CANCELLED",
                "QUERY_TIMED_OUT": "TIMED_OUT",
            }.get(exc.code, "FAILED")
            latency_ms = max(0, int((perf_counter() - started) * 1000))
            with job.lock:
                job.result = {
                    "api_version": "v1",
                    "execution_id": job.execution_id,
                    "request_id": job.request_id,
                    "state": state,
                    "error": {
                        "code": exc.code,
                        "message": exc.public_message,
                        "retryable": exc.code
                        in {
                            "QUERY_TIMED_OUT",
                            "QUERY_SOURCE_UNAVAILABLE",
                        },
                    },
                }
            self._finish_execution(
                job,
                state=state,
                error_code=exc.code,
                row_count=None,
                latency_ms=latency_ms,
            )
        except Exception:  # noqa: BLE001 - worker failures are deliberately sanitized
            latency_ms = max(0, int((perf_counter() - started) * 1000))
            with job.lock:
                job.result = {
                    "api_version": "v1",
                    "execution_id": job.execution_id,
                    "request_id": job.request_id,
                    "state": "FAILED",
                    "error": {
                        "code": "QUERY_EXECUTION_FAILED",
                        "message": "The controlled query failed safely.",
                        "retryable": False,
                    },
                }
            self._finish_execution(
                job,
                state="FAILED",
                error_code="QUERY_EXECUTION_FAILED",
                row_count=None,
                latency_ms=latency_ms,
            )
        finally:
            if timeout_timer is not None:
                timeout_timer.cancel()
            with job.lock:
                job.cancel_adapter = None
                job.terminal = True
            self._release_job_slot_once(job)
            self._prune_terminal_jobs()

    def _finish_execution(
        self,
        job: QueryJob,
        *,
        state: str,
        error_code: str | None,
        row_count: int | None,
        latency_ms: int,
    ) -> None:
        now = self.owner.clock()
        with job.lock:
            with self.owner.store.transaction() as connection:
                current = connection.execute(
                    "SELECT * FROM query_executions WHERE execution_id = ?",
                    (job.execution_id,),
                ).fetchone()
                if current is None:
                    job.terminal = True
                    return False
                if current["state"] in {
                    "SUCCEEDED",
                    "FAILED",
                    "TIMED_OUT",
                    "CANCELLED",
                    "REJECTED_BACKPRESSURE",
                }:
                    job.terminal = True
                    return False
                connection.execute(
                    """
                    UPDATE query_executions
                    SET state = ?, error_code = ?, row_count = ?, latency_ms = ?,
                        completed_at = ?, revision = revision + 1
                    WHERE execution_id = ?
                    """,
                    (
                        state,
                        error_code,
                        row_count,
                        latency_ms,
                        now,
                        job.execution_id,
                    ),
                )
                self.owner._append_audit(
                    connection,
                    event_type="CONTROLLED_QUERY_COMPLETED",
                    actor_type=current["actor_type"],
                    actor_id=current["actor_id"],
                    target_type="QUERY_EXECUTION",
                    target_id=job.execution_id,
                    outcome="SUCCESS" if state == "SUCCEEDED" else "DENIED",
                    reason=None,
                    details={
                        "request_id": job.request_id,
                        "screen_id": current["screen_id"],
                        "source_id": current["source_id"],
                        "source_version_id": current["source_version_id"],
                        "dataset_id": current["dataset_id"],
                        "dataset_version_id": current["dataset_version_id"],
                        "parameter_names": json.loads(current["parameter_names_json"]),
                        "parameter_digest": current["parameter_digest"],
                        "state": state,
                        "error_code": error_code,
                        "row_count": row_count,
                        "latency_ms": latency_ms,
                    },
                    now=now,
                )
            job.terminal = True
            return True

    def _execution_response(
        self,
        execution_id: str,
        *,
        tenant_id: str,
        deployment_id: str,
        screen_id: str,
    ) -> dict[str, Any]:
        with self.owner.store.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM query_executions
                WHERE execution_id = ? AND tenant_id = ?
                  AND deployment_id = ? AND screen_id = ?
                """,
                (execution_id, tenant_id, deployment_id, screen_id),
            ).fetchone()
        if row is None:
            raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "Query execution was not found")
        with self._jobs_lock:
            job = self._jobs.get(execution_id)
        if job is not None:
            with job.lock:
                if job.result is not None:
                    return dict(job.result)
        return self._execution_response_from_row(row)

    def _execution_response_from_row(
        self,
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        response = {
            "api_version": "v1",
            "execution_id": row["execution_id"],
            "request_id": row["request_id"],
            "state": row["state"],
            "screen_id": row["screen_id"],
            "dataset_id": row["dataset_id"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
        }
        if row["state"] in {"FAILED", "TIMED_OUT", "CANCELLED", "REJECTED_BACKPRESSURE"}:
            response["error"] = {
                "code": row["error_code"],
                "message": self._execution_error_message(row["error_code"]),
                "retryable": row["error_code"]
                in {
                    "QUERY_TIMED_OUT",
                    "QUERY_SOURCE_UNAVAILABLE",
                    "GLOBAL_QUERY_BACKPRESSURE",
                    "SCREEN_QUERY_BACKPRESSURE",
                },
            }
        elif row["state"] == "SUCCEEDED":
            response["result_retained"] = False
            response["message"] = "The in-memory result is no longer retained; run the dataset again."
        else:
            response["poll_after_ms"] = 50
        return response

    def _cancel_execution(
        self,
        execution_id: str,
        *,
        tenant_id: str,
        deployment_id: str,
        screen_id: str,
        actor_type: str,
        actor_id: str,
        principal_key: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        operation_phase = "cancelControlledQueryDevice" if actor_type == "DEVICE" else "cancelControlledQuery"
        request_digest = self.owner._sensitive_request_digest(
            operation_phase,
            {"execution_id": execution_id, "screen_id": screen_id},
        )
        with self.owner.store.transaction() as connection:
            row = connection.execute(
                """
                SELECT * FROM query_executions
                WHERE execution_id = ? AND tenant_id = ?
                  AND deployment_id = ? AND screen_id = ?
                """,
                (execution_id, tenant_id, deployment_id, screen_id),
            ).fetchone()
            if row is None:
                raise ControlPlaneError(
                    404,
                    "RESOURCE_NOT_FOUND",
                    "Query execution was not found",
                )
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_phase,
                principal_key=principal_key,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            now = self.owner.clock()
            if row["state"] in {
                "SUCCEEDED",
                "FAILED",
                "TIMED_OUT",
                "CANCELLED",
                "REJECTED_BACKPRESSURE",
            }:
                result = self._execution_response_from_row(row)
                self.owner._idempotency_store(
                    connection,
                    phase=operation_phase,
                    principal_key=principal_key,
                    idempotency_key=idempotency_key,
                    request_digest=request_digest,
                    result=result,
                    now=now,
                )
                return result
            connection.execute(
                """
                UPDATE query_executions
                SET state = 'CANCELLED', error_code = 'QUERY_CANCELLED',
                    completed_at = ?, revision = revision + 1
                WHERE execution_id = ?
                """,
                (now, execution_id),
            )
            self.owner._append_audit(
                connection,
                event_type="CONTROLLED_QUERY_CANCELLED",
                actor_type=actor_type,
                actor_id=actor_id,
                target_type="QUERY_EXECUTION",
                target_id=execution_id,
                outcome="SUCCESS",
                reason=None,
                details={
                    "request_id": row["request_id"],
                    "screen_id": screen_id,
                    "dataset_id": row["dataset_id"],
                },
                now=now,
            )
            updated = connection.execute(
                "SELECT * FROM query_executions WHERE execution_id = ?",
                (execution_id,),
            ).fetchone()
            result = self._execution_response_from_row(updated)
            self.owner._idempotency_store(
                connection,
                phase=operation_phase,
                principal_key=principal_key,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                now=now,
            )
        with self._jobs_lock:
            job = self._jobs.get(execution_id)
        if job is not None:
            job.cancel_event.set()
            with job.lock:
                cancel_adapter = job.cancel_adapter
                future = job.future
            if cancel_adapter is not None:
                with suppress(Exception):
                    cancel_adapter()
            cancelled_before_start = future.cancel() if future is not None else False
            with job.lock:
                job.result = dict(result)
                if cancelled_before_start:
                    job.terminal = True
            if cancelled_before_start:
                self._release_job_slot_once(job)
                self._prune_terminal_jobs()
        return result

    # Adapter implementations.

    def _probe_source(self, source: sqlite3.Row) -> None:
        if source["state"] != "ACTIVE":
            raise QueryExecutionFailure("QUERY_SOURCE_DISABLED", "The QuerySource is disabled")
        if source["engine"] == "EXCEL":
            self._verified_source_config(source)
            payload = bytes(source["workbook_content"] or b"")
            if hashlib.sha256(payload).hexdigest() != source["workbook_sha256"]:
                raise QueryExecutionFailure(
                    "WORKBOOK_INTEGRITY_FAILED",
                    "The workbook integrity check failed",
                )
            self._inspect_workbook(payload)
            return
        connection_payload = self._decrypt_source_connection(source)
        engine = self._database_engine(source["engine"], connection_payload, timeout_ms=5_000)
        try:
            with engine.connect() as connection:
                self._configure_database_connection(
                    source["engine"],
                    connection,
                    timeout_ms=5_000,
                    job=None,
                )
                connection.execute(text("SELECT 1"))
        except (DBAPIError, SQLAlchemyError, OSError) as exc:
            raise QueryExecutionFailure(
                "QUERY_SOURCE_UNAVAILABLE",
                "The database connection test failed safely",
            ) from exc
        finally:
            engine.dispose()

    def _execute_dataset(
        self,
        job: QueryJob,
        dataset: sqlite3.Row,
        parameters: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        if dataset["engine"] == "EXCEL":
            return self._execute_excel(job, dataset, parameters)
        return self._execute_database(job, dataset, parameters)

    def _execute_excel(
        self,
        job: QueryJob,
        dataset: sqlite3.Row,
        parameters: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        self._verified_source_config(dataset)
        payload = bytes(dataset["workbook_content"] or b"")
        if hashlib.sha256(payload).hexdigest() != dataset["workbook_sha256"]:
            raise QueryExecutionFailure(
                "WORKBOOK_INTEGRITY_FAILED",
                "The workbook integrity check failed",
            )
        definition = json.loads(dataset["canonical_definition_json"])
        output_fields = json.loads(dataset["canonical_output_fields_json"])
        deadline = perf_counter() + dataset["timeout_ms"] / 1000
        workbook = load_workbook(
            io.BytesIO(payload),
            read_only=True,
            data_only=False,
            keep_links=False,
        )
        try:
            if definition["worksheet"] not in workbook.sheetnames:
                raise QueryExecutionFailure(
                    "WORKSHEET_NOT_FOUND",
                    "The approved worksheet is unavailable",
                )
            worksheet = workbook[definition["worksheet"]]
            rows_iter = worksheet.iter_rows(values_only=False)
            try:
                header_cells = next(rows_iter)
            except StopIteration:
                return [], output_fields
            headers = [str(cell.value).strip() if cell.value is not None else "" for cell in header_cells]
            if len(headers) != len(set(headers)) or any(not header for header in headers):
                raise QueryExecutionFailure(
                    "WORKBOOK_SCHEMA_CHANGED",
                    "The workbook header is invalid or changed",
                )
            index_by_field = {field: index for index, field in enumerate(headers)}
            required_columns = set(output_fields) | set(definition["parameter_columns"].values())
            if not required_columns.issubset(index_by_field):
                raise QueryExecutionFailure(
                    "WORKBOOK_SCHEMA_CHANGED",
                    "The workbook columns no longer match the approved dataset",
                )
            result: list[dict[str, Any]] = []
            for row in rows_iter:
                if job.cancel_event.is_set():
                    raise self._cancellation_failure(job)
                if perf_counter() > deadline:
                    raise QueryExecutionFailure("QUERY_TIMED_OUT", "The query timed out")
                values = [cell.value for cell in row]
                matched = True
                for parameter_name, column in definition["parameter_columns"].items():
                    expected = parameters.get(parameter_name)
                    actual = values[index_by_field[column]] if index_by_field[column] < len(values) else None
                    if expected is not None and self._json_scalar(actual) != expected:
                        matched = False
                        break
                if not matched:
                    continue
                item = {
                    field: self._json_scalar(
                        values[index_by_field[field]] if index_by_field[field] < len(values) else None
                    )
                    for field in output_fields
                }
                result.append(item)
                if len(result) >= dataset["row_limit"]:
                    break
            return result, output_fields
        finally:
            workbook.close()

    def _execute_database(
        self,
        job: QueryJob,
        dataset: sqlite3.Row,
        parameters: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        if job.cancel_event.is_set():
            raise self._cancellation_failure(job)
        connection_payload = self._decrypt_source_connection(dataset)
        engine = self._database_engine(
            dataset["engine"],
            connection_payload,
            timeout_ms=dataset["timeout_ms"],
        )
        output_fields = json.loads(dataset["canonical_output_fields_json"])
        definition = json.loads(dataset["canonical_definition_json"])
        try:
            if job.cancel_event.is_set():
                raise self._cancellation_failure(job)
            with engine.connect() as connection:
                self._configure_database_connection(
                    dataset["engine"],
                    connection,
                    timeout_ms=dataset["timeout_ms"],
                    job=job,
                )
                if job.cancel_event.is_set():
                    raise self._cancellation_failure(job)
                result = connection.execute(
                    text(definition["query_template"]),
                    parameters,
                )
                fields = list(map(str, result.keys()))
                if (
                    len(fields) != len(set(fields))
                    or any(field not in output_fields for field in fields)
                    or set(fields) != set(output_fields)
                ):
                    raise QueryExecutionFailure(
                        "RESULT_FIELD_NOT_ALLOWLISTED",
                        "The result fields do not match the approved dataset",
                    )
                rows: list[dict[str, Any]] = []
                for row in result.fetchmany(dataset["row_limit"] + 1):
                    if job.cancel_event.is_set():
                        raise self._cancellation_failure(job)
                    rows.append({field: self._json_scalar(row._mapping[field]) for field in output_fields})
                return rows[: dataset["row_limit"]], output_fields
        except QueryExecutionFailure:
            raise
        except (DBAPIError, SQLAlchemyError, OSError) as exc:
            if job.cancel_event.is_set():
                raise self._cancellation_failure(job) from exc
            if self._looks_like_timeout(exc):
                raise QueryExecutionFailure(
                    "QUERY_TIMED_OUT",
                    "The query timed out",
                ) from exc
            raise QueryExecutionFailure(
                "QUERY_SOURCE_UNAVAILABLE",
                "The database query failed safely",
            ) from exc
        finally:
            with job.lock:
                job.cancel_adapter = None
            engine.dispose()

    def _configure_database_connection(
        self,
        engine_name: str,
        connection: Any,
        *,
        timeout_ms: int,
        job: QueryJob | None,
    ) -> None:
        raw = connection.connection.driver_connection
        if engine_name == "POSTGRESQL":
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            connection.exec_driver_sql(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
            cancel = getattr(raw, "cancel", None)
        elif engine_name == "MYSQL":
            connection.exec_driver_sql(f"SET SESSION MAX_EXECUTION_TIME={int(timeout_ms)}")
            cancel = getattr(raw, "close", None)
        else:
            raw.call_timeout = int(timeout_ms)
            cancel = getattr(raw, "cancel", None)
        if job is not None and callable(cancel):
            with job.lock:
                job.cancel_adapter = cancel

    @staticmethod
    def _database_engine(
        engine_name: str,
        payload: dict[str, Any],
        *,
        timeout_ms: int,
    ) -> Any:
        driver = {
            "MYSQL": "mysql+pymysql",
            "ORACLE": "oracle+oracledb",
            "POSTGRESQL": "postgresql+psycopg",
        }[engine_name]
        connect_args: dict[str, Any] = {}
        if engine_name == "MYSQL":
            connect_args = {
                "connect_timeout": max(1, min(30, (timeout_ms + 999) // 1000)),
                "read_timeout": max(1, min(120, (timeout_ms + 999) // 1000)),
                "write_timeout": max(1, min(120, (timeout_ms + 999) // 1000)),
            }
        elif engine_name == "POSTGRESQL":
            connect_args = {
                "connect_timeout": max(1, min(30, (timeout_ms + 999) // 1000)),
            }
        elif engine_name == "ORACLE":
            connect_args = {
                "tcp_connect_timeout": max(1.0, min(30.0, timeout_ms / 1000)),
            }
        url = URL.create(
            driver,
            username=payload["username"],
            password=payload["password"],
            host=payload["host"],
            port=payload["port"],
            database=(payload["database"] if engine_name != "ORACLE" else None),
            query=({"service_name": payload["database"]} if engine_name == "ORACLE" else {}),
        )
        return create_engine(
            url,
            poolclass=NullPool,
            connect_args=connect_args,
            hide_parameters=True,
        )

    # Validation and integrity helpers.

    def _validate_connection_input(
        self,
        engine: str,
        value: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not isinstance(value, dict) or set(value) != {
            "host",
            "port",
            "database",
            "username",
            "password",
        }:
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "Database connection input must contain exactly the closed fields",
            )
        host = self._private_connection_text(value["host"], "host", 1, 253)
        database = self._private_connection_text(value["database"], "database", 1, 128)
        username = self._private_connection_text(value["username"], "username", 1, 128)
        password = self._private_connection_text(value["password"], "password", 1, 1024)
        port = value["port"]
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise ControlPlaneError(422, "SCHEMA_VALIDATION_FAILED", "port must be 1 through 65535")
        if any(marker in host for marker in ("://", "/", "\\", "@", "?", "#")):
            raise ControlPlaneError(
                422,
                "DSN_FORBIDDEN",
                "Submit separate connection fields, never a DSN",
            )
        if engine == "ORACLE" and any(marker in database for marker in ("(", ")", "=")):
            raise ControlPlaneError(
                422,
                "DSN_FORBIDDEN",
                "Oracle database must be a service name, never a descriptor",
            )
        return {
            "host": host,
            "port": port,
            "database": database,
            "username": username,
            "password": password,
        }

    def _decode_and_validate_workbook(
        self,
        file_name: str | None,
        encoded: str | None,
    ) -> tuple[bytes, dict[str, Any]]:
        if (
            not isinstance(file_name, str)
            or not file_name
            or Path(file_name).name != file_name
            or not file_name.casefold().endswith(".xlsx")
        ):
            raise ControlPlaneError(
                422,
                "WORKBOOK_TYPE_FORBIDDEN",
                "Only a plain .xlsx filename is accepted",
            )
        if not isinstance(encoded, str) or not encoded:
            raise ControlPlaneError(
                422,
                "WORKBOOK_REQUIRED",
                "A base64-encoded .xlsx workbook is required",
            )
        try:
            payload = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ControlPlaneError(
                422,
                "WORKBOOK_INVALID",
                "Workbook base64 is invalid",
            ) from exc
        if not payload or len(payload) > MAX_WORKBOOK_BYTES:
            raise ControlPlaneError(
                422,
                "WORKBOOK_SIZE_EXCEEDED",
                "Workbook size is outside the accepted limit",
            )
        return payload, self._inspect_workbook(payload)

    def _inspect_workbook(self, payload: bytes) -> dict[str, Any]:
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                members = archive.infolist()
                if (
                    len(members) > MAX_WORKBOOK_ENTRIES
                    or sum(item.file_size for item in members) > MAX_WORKBOOK_UNCOMPRESSED_BYTES
                ):
                    raise ControlPlaneError(
                        422,
                        "WORKBOOK_SIZE_EXCEEDED",
                        "Workbook archive limits were exceeded",
                    )
                member_names: set[str] = set()
                for member in members:
                    normalized = member.filename.replace("\\", "/")
                    normalized_casefold = normalized.casefold()
                    parts = normalized.rstrip("/").split("/")
                    if (
                        not normalized
                        or normalized.startswith("/")
                        or re.match(r"(?i)^[a-z]:", normalized)
                        or any(part in {"", ".", ".."} for part in parts)
                        or normalized_casefold in member_names
                        or member.flag_bits & 0x1
                        or (member.external_attr >> 16) & 0o170000 == 0o120000
                        or _FORBIDDEN_ARCHIVE_PART.search(normalized)
                    ):
                        raise ControlPlaneError(
                            422,
                            "WORKBOOK_ACTIVE_CONTENT_FORBIDDEN",
                            "Workbook active or external content is forbidden",
                        )
                    member_names.add(normalized_casefold)
                    if normalized_casefold.endswith(".rels"):
                        self._inspect_relationship_part(archive.read(member))
                    elif normalized_casefold == "[content_types].xml":
                        self._inspect_content_types_part(archive.read(member))
        except zipfile.BadZipFile as exc:
            raise ControlPlaneError(
                422,
                "WORKBOOK_INVALID",
                "Workbook ZIP structure is invalid",
            ) from exc
        try:
            workbook = load_workbook(
                io.BytesIO(payload),
                read_only=True,
                data_only=False,
                keep_links=False,
            )
        except Exception as exc:
            raise ControlPlaneError(
                422,
                "WORKBOOK_INVALID",
                "Workbook could not be parsed safely",
            ) from exc
        try:
            if not workbook.sheetnames:
                raise ControlPlaneError(
                    422,
                    "WORKBOOK_INVALID",
                    "Workbook must contain a worksheet",
                )
            total_cells = 0
            for worksheet in workbook.worksheets:
                if worksheet.max_row > MAX_WORKBOOK_ROWS or worksheet.max_column > MAX_WORKBOOK_COLUMNS:
                    raise ControlPlaneError(
                        422,
                        "WORKBOOK_SIZE_EXCEEDED",
                        "Workbook dimensions exceed the accepted limit",
                    )
                for row in worksheet.iter_rows():
                    total_cells += len(row)
                    if total_cells > MAX_WORKBOOK_CELLS:
                        raise ControlPlaneError(
                            422,
                            "WORKBOOK_SIZE_EXCEEDED",
                            "Workbook cell count exceeds the accepted limit",
                        )
                    for cell in row:
                        if cell.data_type == "f":
                            raise ControlPlaneError(
                                422,
                                "WORKBOOK_FORMULA_FORBIDDEN",
                                "Workbook formulas are forbidden",
                            )
            return {"worksheet_names": list(workbook.sheetnames)}
        finally:
            workbook.close()

    @staticmethod
    def _inspect_relationship_part(payload: bytes) -> None:
        if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
            raise ControlPlaneError(
                422,
                "WORKBOOK_ACTIVE_CONTENT_FORBIDDEN",
                "Workbook active or external content is forbidden",
            )
        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError as exc:
            raise ControlPlaneError(
                422,
                "WORKBOOK_INVALID",
                "Workbook relationship metadata is invalid",
            ) from exc
        for relationship in root.iter():
            attributes = {key.casefold(): value for key, value in relationship.attrib.items()}
            target_mode = attributes.get("targetmode", "").casefold()
            relationship_type = attributes.get("type", "").casefold()
            target = attributes.get("target", "").strip()
            if (
                target_mode == "external"
                or relationship_type.endswith(("/hyperlink", "/externallink"))
                or _URI_TARGET.match(target)
                or target.startswith("\\\\")
            ):
                raise ControlPlaneError(
                    422,
                    "WORKBOOK_ACTIVE_CONTENT_FORBIDDEN",
                    "Workbook active or external content is forbidden",
                )

    @staticmethod
    def _inspect_content_types_part(payload: bytes) -> None:
        if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
            raise ControlPlaneError(
                422,
                "WORKBOOK_ACTIVE_CONTENT_FORBIDDEN",
                "Workbook active or external content is forbidden",
            )
        try:
            root = ElementTree.fromstring(payload)
        except ElementTree.ParseError as exc:
            raise ControlPlaneError(
                422,
                "WORKBOOK_INVALID",
                "Workbook content-type metadata is invalid",
            ) from exc
        for item in root.iter():
            if any(_FORBIDDEN_CONTENT_TYPE.search(value) for value in item.attrib.values()):
                raise ControlPlaneError(
                    422,
                    "WORKBOOK_ACTIVE_CONTENT_FORBIDDEN",
                    "Workbook active or external content is forbidden",
                )

    def _validate_parameter_schema(
        self,
        parameters: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not isinstance(parameters, list) or len(parameters) > 32:
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "parameters must contain at most 32 definitions",
            )
        normalized: list[dict[str, Any]] = []
        names: set[str] = set()
        for item in parameters:
            if not isinstance(item, dict) or set(item) != {"name", "type", "required"}:
                raise ControlPlaneError(
                    422,
                    "SCHEMA_VALIDATION_FAILED",
                    "Each parameter must contain name, type and required",
                )
            name = item["name"]
            kind = item["type"]
            required = item["required"]
            if not isinstance(name, str) or not _IDENTIFIER.fullmatch(name) or name in names:
                raise ControlPlaneError(
                    422,
                    "SCHEMA_VALIDATION_FAILED",
                    "Parameter names must be unique safe identifiers",
                )
            if kind not in PARAMETER_TYPES or not isinstance(required, bool):
                raise ControlPlaneError(
                    422,
                    "SCHEMA_VALIDATION_FAILED",
                    "Parameter type or required flag is invalid",
                )
            names.add(name)
            normalized.append({"name": name, "type": kind, "required": required})
        return sorted(normalized, key=lambda item: item["name"])

    def _validate_output_fields(self, fields: list[str]) -> list[str]:
        if (
            not isinstance(fields, list)
            or not fields
            or len(fields) > 64
            or any(not isinstance(field, str) or not _IDENTIFIER.fullmatch(field) for field in fields)
            or len(fields) != len(set(fields))
        ):
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "output_fields must be a unique list of safe identifiers",
            )
        return list(fields)

    def _validate_dataset_definition(
        self,
        source: sqlite3.Row,
        parameters: list[dict[str, Any]],
        output_fields: list[str],
        definition: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(definition, dict):
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "definition must be an object",
            )
        parameter_names = {item["name"] for item in parameters}
        if source["engine"] == "EXCEL":
            if set(definition) != {"worksheet", "parameter_columns"}:
                raise ControlPlaneError(
                    422,
                    "SCHEMA_VALIDATION_FAILED",
                    "Excel definition must contain worksheet and parameter_columns",
                )
            worksheet = self._public_text(definition["worksheet"], "Worksheet", 1, 128)
            columns = definition["parameter_columns"]
            if (
                not isinstance(columns, dict)
                or set(columns) != parameter_names
                or any(
                    not isinstance(column, str) or not _IDENTIFIER.fullmatch(column)
                    for column in columns.values()
                )
            ):
                raise ControlPlaneError(
                    422,
                    "SCHEMA_VALIDATION_FAILED",
                    "Excel parameter_columns must map every parameter to a safe column",
                )
            self._verify_excel_dataset_columns(source, worksheet, output_fields, columns)
            return {
                "kind": "EXCEL_FILTER",
                "worksheet": worksheet,
                "parameter_columns": {name: columns[name] for name in sorted(columns)},
            }
        if set(definition) != {"query_template", "allowed_relations"}:
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "Database definition must contain query_template and allowed_relations",
            )
        query_template = definition["query_template"]
        relations = definition["allowed_relations"]
        if (
            not isinstance(query_template, str)
            or not query_template.strip()
            or len(query_template) > 20_000
            or _FORBIDDEN_SQL_TEXT.search(query_template)
            or (source["engine"] == "MYSQL" and _FORBIDDEN_MYSQL_SQL_TEXT.search(query_template))
        ):
            raise ControlPlaneError(
                422,
                "READ_ONLY_TEMPLATE_REQUIRED",
                "Only one read-only parameterized SELECT template is accepted",
            )
        if (
            not isinstance(relations, list)
            or not relations
            or len(relations) > 32
            or any(
                not isinstance(relation, str) or not _RELATION.fullmatch(relation) for relation in relations
            )
            or len(relations) != len(set(relations))
        ):
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                "allowed_relations must be a unique closed relation list",
            )
        dialect = {
            "MYSQL": "mysql",
            "ORACLE": "oracle",
            "POSTGRESQL": "postgres",
        }[source["engine"]]
        try:
            statements = sqlglot.parse(query_template, read=dialect)
        except sqlglot.errors.ParseError as exc:
            raise ControlPlaneError(
                422,
                "SQL_TEMPLATE_INVALID",
                "The approved query template could not be parsed",
            ) from exc
        if len(statements) != 1 or not isinstance(statements[0], (exp.Select, exp.Union)):
            raise ControlPlaneError(
                422,
                "READ_ONLY_TEMPLATE_REQUIRED",
                "Only one SELECT statement is accepted",
            )
        tree = statements[0]
        forbidden_nodes = (
            exp.Insert,
            exp.Update,
            exp.Delete,
            exp.Create,
            exp.Drop,
            exp.Alter,
            exp.Merge,
            exp.Command,
            exp.Transaction,
            exp.Copy,
            exp.Export,
            exp.Into,
            exp.Lock,
            exp.Parameter,
            exp.PropertyEQ,
            exp.ReadCSV,
            exp.SessionParameter,
            exp.Operator,
            exp.Var,
        )
        if any(isinstance(node, forbidden_nodes) for node in tree.walk()):
            raise ControlPlaneError(
                422,
                "READ_ONLY_TEMPLATE_REQUIRED",
                "The query template contains a forbidden operation",
            )
        for function in tree.find_all(exp.Func):
            if (
                isinstance(function, exp.Anonymous)
                or function.sql_name().upper() not in _ALLOWED_SQL_FUNCTIONS
            ):
                raise ControlPlaneError(
                    422,
                    "READ_ONLY_TEMPLATE_REQUIRED",
                    "The query template contains an unapproved function",
                )
        if any(data_type.this == exp.DataType.Type.USERDEFINED for data_type in tree.find_all(exp.DataType)):
            raise ControlPlaneError(
                422,
                "READ_ONLY_TEMPLATE_REQUIRED",
                "The query template contains an unapproved user-defined type",
            )
        if any(column.name.upper() in {"CURRVAL", "NEXTVAL"} for column in tree.find_all(exp.Column)):
            raise ControlPlaneError(
                422,
                "READ_ONLY_TEMPLATE_REQUIRED",
                "The query template contains a stateful sequence expression",
            )
        if any(
            selection.is_star
            for select_node in tree.find_all(exp.Select)
            for selection in select_node.expressions
        ):
            raise ControlPlaneError(
                422,
                "OUTPUT_FIELD_ALLOWLIST_REQUIRED",
                "SELECT star is forbidden; enumerate approved output fields",
            )
        selected_fields = list(tree.named_selects)
        if selected_fields != output_fields:
            raise ControlPlaneError(
                422,
                "OUTPUT_FIELD_ALLOWLIST_MISMATCH",
                "Selected fields must exactly match the ordered output allowlist",
            )
        placeholders = {placeholder.name for placeholder in tree.find_all(exp.Placeholder)}
        if placeholders != parameter_names:
            raise ControlPlaneError(
                422,
                "PARAMETER_BINDING_MISMATCH",
                "Named SQL parameters must exactly match the parameter schema",
            )
        cte_names = {cte.alias_or_name.casefold() for cte in tree.find_all(exp.CTE) if cte.alias_or_name}
        actual_relations = {
            relation
            for table in tree.find_all(exp.Table)
            if (relation := self._table_relation_name(table)) not in cte_names
        }
        allowed = {relation.casefold() for relation in relations}
        if actual_relations != allowed:
            raise ControlPlaneError(
                422,
                "RELATION_NOT_ALLOWLISTED",
                "SQL relations must exactly match the approved relation allowlist",
            )
        return {
            "kind": "DATABASE_SELECT",
            "dialect": dialect,
            "query_template": query_template.strip(),
            "allowed_relations": sorted(relations, key=str.casefold),
        }

    def _verify_excel_dataset_columns(
        self,
        source: sqlite3.Row,
        worksheet_name: str,
        output_fields: list[str],
        parameter_columns: dict[str, str],
    ) -> None:
        self._verified_source_config(source)
        payload = bytes(source["workbook_content"] or b"")
        if hashlib.sha256(payload).hexdigest() != source["workbook_sha256"]:
            raise ControlPlaneError(
                409,
                "WORKBOOK_INTEGRITY_FAILED",
                "Workbook integrity changed",
            )
        workbook = load_workbook(
            io.BytesIO(payload),
            read_only=True,
            data_only=False,
            keep_links=False,
        )
        try:
            if worksheet_name not in workbook.sheetnames:
                raise ControlPlaneError(
                    422,
                    "WORKSHEET_NOT_FOUND",
                    "The worksheet is unavailable",
                )
            worksheet = workbook[worksheet_name]
            row = next(worksheet.iter_rows(values_only=True), ())
            headers = [str(value).strip() if value is not None else "" for value in row]
            required = set(output_fields) | set(parameter_columns.values())
            if (
                len(headers) != len(set(headers))
                or any(not header for header in headers)
                or not required.issubset(headers)
            ):
                raise ControlPlaneError(
                    422,
                    "WORKBOOK_SCHEMA_MISMATCH",
                    "Approved columns are missing or ambiguous",
                )
        finally:
            workbook.close()

    def _validate_runtime_parameters(
        self,
        dataset: sqlite3.Row,
        parameters: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        schema = json.loads(dataset["canonical_parameter_schema_json"])
        expected = {item["name"]: item for item in schema}
        if set(parameters) - set(expected):
            raise ControlPlaneError(
                422,
                "UNKNOWN_QUERY_PARAMETER",
                "The request contains an unknown dataset parameter",
            )
        normalized: dict[str, Any] = {}
        time_scope: dict[str, Any] = {}
        for name, item in expected.items():
            value = parameters.get(name)
            if value is None:
                if item["required"]:
                    raise ControlPlaneError(
                        422,
                        "QUERY_PARAMETER_REQUIRED",
                        "A required dataset parameter is missing",
                    )
                normalized[name] = None
                continue
            normalized_value = self._normalize_parameter_value(
                item["type"],
                value,
            )
            normalized[name] = normalized_value
            if item["type"] == "date":
                time_scope[name] = normalized_value
        return normalized, time_scope

    @staticmethod
    def _normalize_parameter_value(kind: str, value: Any) -> Any:
        if kind == "string":
            if not isinstance(value, str) or len(value) > 500:
                raise ControlPlaneError(
                    422,
                    "QUERY_PARAMETER_INVALID",
                    "A string parameter is invalid",
                )
            return value
        if kind == "integer":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ControlPlaneError(
                    422,
                    "QUERY_PARAMETER_INVALID",
                    "An integer parameter is invalid",
                )
            return value
        if kind == "number":
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ControlPlaneError(
                    422,
                    "QUERY_PARAMETER_INVALID",
                    "A numeric parameter is invalid",
                )
            if not math.isfinite(value):
                raise ControlPlaneError(
                    422,
                    "QUERY_PARAMETER_INVALID",
                    "A numeric parameter must be finite",
                )
            return value
        if kind == "boolean":
            if not isinstance(value, bool):
                raise ControlPlaneError(
                    422,
                    "QUERY_PARAMETER_INVALID",
                    "A boolean parameter is invalid",
                )
            return value
        if not isinstance(value, str):
            raise ControlPlaneError(
                422,
                "QUERY_PARAMETER_INVALID",
                "A date parameter is invalid",
            )
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError as exc:
            raise ControlPlaneError(
                422,
                "QUERY_PARAMETER_INVALID",
                "A date parameter must use YYYY-MM-DD",
            ) from exc

    def _applied_query_context(
        self,
        connection: sqlite3.Connection,
        screen_id: str,
        tenant_id: str,
        deployment_id: str,
    ) -> tuple[sqlite3.Row, sqlite3.Row, dict[str, Any]]:
        binding = connection.execute(
            """
            SELECT * FROM runtime_bindings
            WHERE screen_id = ? AND tenant_id = ? AND deployment_id = ?
            """,
            (screen_id, tenant_id, deployment_id),
        ).fetchone()
        if binding is None or binding["applied_release_target_id"] is None:
            raise ControlPlaneError(
                409,
                "QUERYING_NOT_CONFIGURED",
                "No applied controlled-query release is available",
            )
        target = connection.execute(
            """
            SELECT * FROM release_targets
            WHERE release_target_id = ? AND screen_id = ?
              AND tenant_id = ? AND deployment_id = ?
            """,
            (
                binding["applied_release_target_id"],
                screen_id,
                tenant_id,
                deployment_id,
            ),
        ).fetchone()
        query_row = self._release_snapshot_row(
            connection,
            binding["applied_release_target_id"],
        )
        capability_row = connection.execute(
            """
            SELECT * FROM release_target_capability_snapshots
            WHERE release_target_id = ?
            """,
            (binding["applied_release_target_id"],),
        ).fetchone()
        if target is None or query_row is None or capability_row is None:
            raise ControlPlaneError(
                409,
                "QUERYING_NOT_CONFIGURED",
                "The applied release has no controlled-query snapshot",
            )
        snapshot = self._verified_release_snapshot(connection, query_row)
        capability = self.owner.p2_1._verified_snapshot_payload(
            connection,
            capability_row,
        )
        query_spec = capability["spec"]["querying"]
        if (
            not query_spec["enabled"]
            or query_spec["primary_provider_id"] != "controlled_query"
            or query_spec["fallback_provider_ids"]
            or not snapshot["querying_enabled"]
        ):
            raise ControlPlaneError(
                409,
                "QUERYING_NOT_CONFIGURED",
                "Controlled querying is not enabled for the applied release",
            )
        return binding, target, snapshot

    def _runtime_dataset_list(
        self,
        *,
        screen_id: str,
        binding: sqlite3.Row,
        target: sqlite3.Row,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "api_version": "v1",
            "screen_id": screen_id,
            "digital_human_instance_id": binding["digital_human_instance_id"],
            "release_target_id": target["release_target_id"],
            "query_snapshot_hash": snapshot["query_snapshot_hash"],
            "provider": "controlled_query",
            "state": "available",
            "items": [
                {
                    "dataset_id": ref["dataset_id"],
                    "dataset_version_id": ref["dataset_version_id"],
                    "label": ref["dataset_label"],
                    "metric_definition": ref["metric_definition"],
                    "time_scope_description": ref["time_scope_description"],
                    "freshness_label": ref["freshness_label"],
                    "parameter_schema": ref["parameter_schema"],
                    "output_fields": ref["output_fields"],
                    "row_limit": ref["row_limit"],
                    "timeout_ms": ref["timeout_ms"],
                    "source": {
                        "source_id": ref["source_id"],
                        "engine": ref["engine"],
                        "label": ref["source_label"],
                        "qualification": "DEPLOYMENT_LOCAL_AVAILABLE",
                        "product_certification": "UNVERIFIED",
                    },
                }
                for ref in snapshot["dataset_refs"]
            ],
        }

    def _runtime_dataset_row(
        self,
        connection: sqlite3.Connection,
        ref: dict[str, Any],
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT d.*, v.*, s.engine, s.display_name AS source_display_name,
                   s.state AS source_state,
                   s.qualification_state AS source_qualification_state,
                   sv.canonical_config_json, sv.config_hash,
                   sv.secret_id, sv.secret_version_id, sv.workbook_sha256,
                   sv.workbook_content,
                   qsec.state AS secret_state, qsec.current_version_id,
                   qsv.envelope_key_id, qsv.envelope_nonce,
                   qsv.envelope_ciphertext, qsv.envelope_aad_json,
                   qsv.envelope_aad_hash
            FROM query_datasets d
            JOIN query_dataset_versions v
              ON v.dataset_id = d.dataset_id
             AND v.dataset_version_id = d.head_version_id
            JOIN query_sources s
              ON s.source_id = d.source_id
             AND s.head_version_id = v.source_version_id
            JOIN query_source_versions sv
              ON sv.source_id = s.source_id
             AND sv.source_version_id = s.head_version_id
            LEFT JOIN query_secret_records qsec
              ON qsec.secret_id = sv.secret_id
            LEFT JOIN query_secret_versions qsv
              ON qsv.secret_version_id = sv.secret_version_id
            WHERE d.dataset_id = ? AND v.dataset_version_id = ?
              AND s.source_id = ? AND sv.source_version_id = ?
            """,
            (
                ref["dataset_id"],
                ref["dataset_version_id"],
                ref["source_id"],
                ref["source_version_id"],
            ),
        ).fetchone()
        if row is None:
            raise ControlPlaneError(
                409,
                "QUERY_SOURCE_NOT_AVAILABLE",
                "The approved dataset source is unavailable",
            )
        if row["state"] != "ACTIVE":
            raise ControlPlaneError(
                409,
                "QUERY_DATASET_NOT_AVAILABLE",
                "The approved dataset is unavailable",
            )
        if row["source_state"] != "ACTIVE" or row["source_qualification_state"] != "AVAILABLE":
            raise ControlPlaneError(
                409,
                "QUERY_SOURCE_NOT_AVAILABLE",
                "The approved dataset source is unavailable",
            )
        return row

    def _verified_dataset_refs(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        site_id: str,
        dataset_version_ids: list[str],
        *,
        require_available: bool,
    ) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for dataset_version_id in dataset_version_ids:
            row = connection.execute(
                """
                SELECT d.*, v.*, s.engine, s.display_name AS source_display_name,
                       s.state AS source_state,
                       s.qualification_state AS source_qualification_state,
                       sv.config_hash
                FROM query_dataset_versions v
                JOIN query_datasets d ON d.dataset_id = v.dataset_id
                JOIN query_sources s ON s.source_id = v.source_id
                JOIN query_source_versions sv
                  ON sv.source_version_id = v.source_version_id
                 AND sv.source_id = v.source_id
                WHERE v.dataset_version_id = ?
                  AND v.tenant_id = ? AND v.deployment_id = ?
                  AND v.site_id = ?
                """,
                (
                    dataset_version_id,
                    principal.tenant_id,
                    principal.deployment_id,
                    site_id,
                ),
            ).fetchone()
            if row is None or not self.owner._can_access_site(
                principal,
                site_id,
                "config.edit_technical",
            ):
                raise ControlPlaneError(
                    404,
                    "RESOURCE_NOT_FOUND",
                    "Dataset version was not found",
                )
            if require_available and (
                row["state"] != "ACTIVE"
                or row["source_state"] != "ACTIVE"
                or row["source_qualification_state"] != "AVAILABLE"
            ):
                raise ControlPlaneError(
                    422,
                    "QUERY_SOURCE_NOT_AVAILABLE",
                    "Dataset source is disabled, untested or unavailable",
                )
            refs.append(self._dataset_ref(row))
        return sorted(refs, key=lambda item: item["dataset_id"])

    def _verified_assignment_refs(
        self,
        connection: sqlite3.Connection,
        assignment: sqlite3.Row,
    ) -> list[dict[str, Any]]:
        try:
            refs = json.loads(assignment["canonical_dataset_refs_json"])
        except (json.JSONDecodeError, TypeError) as exc:
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Draft query assignment integrity failed",
            ) from exc
        if (
            not isinstance(refs, list)
            or canonical_json(refs) != assignment["canonical_dataset_refs_json"]
            or hashlib.sha256(assignment["canonical_dataset_refs_json"].encode("utf-8")).hexdigest()
            != assignment["assignment_hash"]
        ):
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Draft query assignment integrity failed",
            )
        for ref in refs:
            row = connection.execute(
                """
                SELECT d.*, v.*, s.engine, s.display_name AS source_display_name,
                       s.state AS source_state,
                       s.qualification_state AS source_qualification_state,
                       sv.config_hash
                FROM query_dataset_versions v
                JOIN query_datasets d ON d.dataset_id = v.dataset_id
                JOIN query_sources s ON s.source_id = v.source_id
                JOIN query_source_versions sv
                  ON sv.source_version_id = v.source_version_id
                 AND sv.source_id = v.source_id
                WHERE v.dataset_id = ? AND v.dataset_version_id = ?
                  AND v.source_id = ? AND v.source_version_id = ?
                """,
                (
                    ref.get("dataset_id"),
                    ref.get("dataset_version_id"),
                    ref.get("source_id"),
                    ref.get("source_version_id"),
                ),
            ).fetchone()
            if row is None or self._dataset_ref(row) != ref:
                raise ControlPlaneError(
                    503,
                    "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                    "Draft query assignment reference changed",
                )
        return refs

    def _dataset_ref(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "dataset_id": row["dataset_id"],
            "dataset_version_id": row["dataset_version_id"],
            "dataset_label": row["display_name"],
            "definition_hash": row["definition_hash"],
            "metric_definition": row["metric_definition"],
            "time_scope_description": row["time_scope_description"],
            "freshness_label": row["freshness_label"],
            "parameter_schema": json.loads(row["canonical_parameter_schema_json"]),
            "output_fields": json.loads(row["canonical_output_fields_json"]),
            "row_limit": row["row_limit"],
            "timeout_ms": row["timeout_ms"],
            "source_id": row["source_id"],
            "source_version_id": row["source_version_id"],
            "source_label": row["source_display_name"],
            "source_config_hash": row["config_hash"],
            "engine": row["engine"],
        }

    @staticmethod
    def _querying_selection(
        capability_resolution: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if capability_resolution is None:
            return {
                "enabled": False,
                "primary_provider_id": None,
                "fallback_provider_ids": [],
            }
        spec = json.loads(capability_resolution["profile_version"]["canonical_spec_json"])
        return spec["querying"]

    @staticmethod
    def composite_capability_activation_eligible(
        capability_resolution: dict[str, Any] | None,
        query_resolution: dict[str, Any] | None,
    ) -> bool:
        if capability_resolution is None:
            return query_resolution is None
        if capability_resolution["activation_eligible"]:
            return True
        if query_resolution is None or not query_resolution["activation_eligible"]:
            return False
        errors = [
            finding
            for finding in capability_resolution["dependency_findings"]
            if finding["severity"] == "ERROR"
        ]
        return bool(errors) and all(
            finding.get("code") == "UNVERIFIED_PROVIDER_BLOCKS_ACTIVATION"
            and finding.get("capability") == "querying"
            and finding.get("provider_id") == "controlled_query"
            for finding in errors
        )

    @staticmethod
    def _query_snapshot_payload(
        *,
        screen_id: str,
        digital_human_instance_id: str,
        assignment_hash: str,
        dataset_refs: list[dict[str, Any]],
        querying_enabled: bool,
    ) -> dict[str, Any]:
        return {
            "schema_version": QUERY_SNAPSHOT_SCHEMA_VERSION,
            "screen_id": screen_id,
            "digital_human_instance_id": digital_human_instance_id,
            "querying_enabled": querying_enabled,
            "provider_id": "controlled_query" if querying_enabled else None,
            "assignment_hash": assignment_hash,
            "dataset_refs": dataset_refs,
            "permission_scope": "screen_bound",
            "fallback_provider_ids": [],
        }

    @staticmethod
    def _draft_assignment_row(
        connection: sqlite3.Connection,
        draft_id: str,
        draft_revision: int,
    ) -> sqlite3.Row | None:
        if not P22ControlPlane._table_exists(
            connection,
            "config_draft_query_assignments",
        ):
            return None
        return connection.execute(
            """
            SELECT * FROM config_draft_query_assignments
            WHERE draft_id = ? AND draft_revision = ?
            """,
            (draft_id, draft_revision),
        ).fetchone()

    @staticmethod
    def _insert_draft_assignment(
        connection: sqlite3.Connection,
        *,
        draft_id: str,
        draft_revision: int,
        principal: Any,
        site_id: str,
        refs_json: str,
        assignment_hash: str,
        now: float,
    ) -> None:
        connection.execute(
            """
            INSERT INTO config_draft_query_assignments(
                draft_id, draft_revision, tenant_id, deployment_id,
                site_id, canonical_dataset_refs_json, assignment_hash,
                assigned_by_user_id, assigned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                draft_id,
                draft_revision,
                principal.tenant_id,
                principal.deployment_id,
                site_id,
                refs_json,
                assignment_hash,
                principal.user_id,
                now,
            ),
        )

    @staticmethod
    def _release_snapshot_row(
        connection: sqlite3.Connection,
        release_target_id: str,
    ) -> sqlite3.Row | None:
        if not P22ControlPlane._table_exists(
            connection,
            "release_target_query_snapshots",
        ):
            return None
        return connection.execute(
            """
            SELECT * FROM release_target_query_snapshots
            WHERE release_target_id = ?
            """,
            (release_target_id,),
        ).fetchone()

    def _verified_release_snapshot(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> dict[str, Any]:
        try:
            snapshot = json.loads(row["canonical_query_snapshot_json"])
        except (json.JSONDecodeError, TypeError) as exc:
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Release query snapshot integrity failed",
            ) from exc
        expected_keys = {
            "schema_version",
            "screen_id",
            "digital_human_instance_id",
            "querying_enabled",
            "provider_id",
            "assignment_hash",
            "dataset_refs",
            "permission_scope",
            "fallback_provider_ids",
        }
        target = connection.execute(
            """
            SELECT rt.*, s.site_id
            FROM release_targets rt
            JOIN screen_instances s ON s.screen_id = rt.screen_id
            WHERE rt.release_target_id = ?
            """,
            (row["release_target_id"],),
        ).fetchone()
        try:
            effective_config = (
                json.loads(target["canonical_effective_config_json"]) if target is not None else None
            )
        except (json.JSONDecodeError, TypeError) as exc:
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Release query snapshot integrity failed",
            ) from exc
        if (
            target is None
            or not isinstance(effective_config, dict)
            or not isinstance(snapshot, dict)
            or set(snapshot) != expected_keys
            or canonical_json(snapshot) != row["canonical_query_snapshot_json"]
            or hashlib.sha256(row["canonical_query_snapshot_json"].encode("utf-8")).hexdigest()
            != row["query_snapshot_hash"]
            or snapshot["schema_version"] != QUERY_SNAPSHOT_SCHEMA_VERSION
            or snapshot["screen_id"] != row["screen_id"]
            or snapshot["screen_id"] != target["screen_id"]
            or snapshot["digital_human_instance_id"] != effective_config.get("digital_human_instance_id")
            or row["tenant_id"] != target["tenant_id"]
            or row["deployment_id"] != target["deployment_id"]
            or row["site_id"] != target["site_id"]
            or snapshot["permission_scope"] != "screen_bound"
            or snapshot["fallback_provider_ids"] != []
            or (snapshot["querying_enabled"] and snapshot["provider_id"] != "controlled_query")
            or (not snapshot["querying_enabled"] and snapshot["provider_id"] is not None)
            or hashlib.sha256(canonical_json(snapshot["dataset_refs"]).encode("utf-8")).hexdigest()
            != snapshot["assignment_hash"]
        ):
            raise ControlPlaneError(
                503,
                "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                "Release query snapshot integrity failed",
            )
        for ref in snapshot["dataset_refs"]:
            dataset = connection.execute(
                """
                SELECT d.*, v.*, s.engine,
                       s.display_name AS source_display_name,
                       s.state AS source_state,
                       s.qualification_state AS source_qualification_state,
                       sv.config_hash
                FROM query_dataset_versions v
                JOIN query_datasets d ON d.dataset_id = v.dataset_id
                JOIN query_sources s ON s.source_id = v.source_id
                JOIN query_source_versions sv
                  ON sv.source_version_id = v.source_version_id
                 AND sv.source_id = v.source_id
                WHERE v.dataset_id = ? AND v.dataset_version_id = ?
                  AND v.source_id = ? AND v.source_version_id = ?
                """,
                (
                    ref.get("dataset_id"),
                    ref.get("dataset_version_id"),
                    ref.get("source_id"),
                    ref.get("source_version_id"),
                ),
            ).fetchone()
            if dataset is None or self._dataset_ref(dataset) != ref:
                raise ControlPlaneError(
                    503,
                    "CRYPTOGRAPHIC_INTEGRITY_FAILURE",
                    "Release query snapshot reference changed",
                )
        snapshot["site_id"] = row["site_id"]
        snapshot["query_snapshot_hash"] = row["query_snapshot_hash"]
        return snapshot

    def _source_row(
        self,
        connection: sqlite3.Connection,
        source_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT s.*, v.source_version_id, v.config_hash,
                   v.canonical_config_json, v.secret_id, v.secret_version_id,
                   v.workbook_sha256, v.workbook_content, sv.fingerprint_suffix,
                   qsec.state AS secret_state, qsec.current_version_id,
                   sv.envelope_key_id, sv.envelope_nonce,
                   sv.envelope_ciphertext, sv.envelope_aad_json,
                   sv.envelope_aad_hash
            FROM query_sources s
            JOIN query_source_versions v
              ON v.source_version_id = s.head_version_id
             AND v.source_id = s.source_id
            LEFT JOIN query_secret_records qsec ON qsec.secret_id = v.secret_id
            LEFT JOIN query_secret_versions sv
              ON sv.secret_version_id = v.secret_version_id
            WHERE s.source_id = ?
            """,
            (source_id,),
        ).fetchone()
        if row is None:
            raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "QuerySource was not found")
        return row

    def _load_source(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        source_id: str,
        permission: str,
    ) -> sqlite3.Row:
        self.owner.require_permission(principal, permission)
        row = self._source_row(connection, source_id)
        if (
            row["tenant_id"] != principal.tenant_id
            or row["deployment_id"] != principal.deployment_id
            or not self.owner._can_access_site(principal, row["site_id"], permission)
        ):
            raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "QuerySource was not found")
        return row

    def _dataset_row(
        self,
        connection: sqlite3.Connection,
        dataset_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT d.*, v.*, s.engine, s.display_name AS source_display_name,
                   s.state AS source_state,
                   s.qualification_state AS source_qualification_state
            FROM query_datasets d
            JOIN query_dataset_versions v
              ON v.dataset_version_id = d.head_version_id
             AND v.dataset_id = d.dataset_id
            JOIN query_sources s ON s.source_id = d.source_id
            WHERE d.dataset_id = ?
            """,
            (dataset_id,),
        ).fetchone()
        if row is None:
            raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "Dataset was not found")
        return row

    def _load_dataset(
        self,
        connection: sqlite3.Connection,
        principal: Any,
        dataset_id: str,
        permission: str,
    ) -> sqlite3.Row:
        self.owner.require_permission(principal, permission)
        row = self._dataset_row(connection, dataset_id)
        if (
            row["tenant_id"] != principal.tenant_id
            or row["deployment_id"] != principal.deployment_id
            or not self.owner._can_access_site(principal, row["site_id"], permission)
        ):
            raise ControlPlaneError(404, "RESOURCE_NOT_FOUND", "Dataset was not found")
        return row

    def _source_response(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "api_version": "v1",
            "source_id": row["source_id"],
            "source_version_id": row["source_version_id"],
            "site_id": row["site_id"],
            "display_name": row["display_name"],
            "engine": row["engine"],
            "state": row["state"],
            "qualification": {
                "state": row["qualification_state"],
                "code": row["qualification_code"],
                "last_tested_at": row["last_tested_at"],
                "deployment_local_evidence": row["qualification_state"] == "AVAILABLE",
                "product_certification": "UNVERIFIED",
            },
            "read_only_account_confirmed": bool(row["read_only_account_confirmed"]),
            "credential": {
                "configured": row["secret_id"] is not None,
                "fingerprint_suffix": row["fingerprint_suffix"],
                "sensitive": True,
                "readable": False,
            },
            "workbook": {
                "configured": row["workbook_sha256"] is not None,
                "content_readable": False,
            },
            "config_hash": row["config_hash"],
            "resource_revision": row["revision"],
            "etag": self.owner._resource_etag(
                "query-source",
                row["source_id"],
                row["revision"],
            ),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "immutable_definition": True,
        }

    def _dataset_response(self, row: sqlite3.Row) -> dict[str, Any]:
        definition = json.loads(row["canonical_definition_json"])
        definition_summary = {
            "kind": definition["kind"],
            "worksheet_configured": definition["kind"] == "EXCEL_FILTER",
            "query_template_configured": definition["kind"] == "DATABASE_SELECT",
            "query_template_readable": False,
            "relation_count": len(definition.get("allowed_relations", [])),
        }
        return {
            "api_version": "v1",
            "dataset_id": row["dataset_id"],
            "dataset_version_id": row["dataset_version_id"],
            "site_id": row["site_id"],
            "display_name": row["display_name"],
            "state": row["state"],
            "source": {
                "source_id": row["source_id"],
                "source_version_id": row["source_version_id"],
                "display_name": row["source_display_name"],
                "engine": row["engine"],
                "state": row["source_state"],
                "qualification_state": row["source_qualification_state"],
            },
            "schema_version": row["schema_version"],
            "metric_definition": row["metric_definition"],
            "time_scope_description": row["time_scope_description"],
            "freshness_label": row["freshness_label"],
            "parameter_schema": json.loads(row["canonical_parameter_schema_json"]),
            "output_fields": json.loads(row["canonical_output_fields_json"]),
            "definition": definition_summary,
            "definition_hash": row["definition_hash"],
            "row_limit": row["row_limit"],
            "timeout_ms": row["timeout_ms"],
            "resource_revision": row["revision"],
            "etag": self.owner._resource_etag(
                "query-dataset",
                row["dataset_id"],
                row["revision"],
            ),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "immutable_definition": True,
        }

    def _verified_source_config(self, row: sqlite3.Row) -> dict[str, Any]:
        try:
            config = json.loads(row["canonical_config_json"])
        except (json.JSONDecodeError, TypeError) as exc:
            raise QueryExecutionFailure(
                "QUERY_SOURCE_INTEGRITY_FAILED",
                "The QuerySource integrity check failed",
            ) from exc
        if (
            not isinstance(config, dict)
            or canonical_json(config) != row["canonical_config_json"]
            or hashlib.sha256(row["canonical_config_json"].encode("utf-8")).hexdigest() != row["config_hash"]
        ):
            raise QueryExecutionFailure(
                "QUERY_SOURCE_INTEGRITY_FAILED",
                "The QuerySource integrity check failed",
            )
        return config

    def _decrypt_source_connection(self, row: sqlite3.Row) -> dict[str, Any]:
        if (
            row["secret_id"] is None
            or row["secret_version_id"] is None
            or row["secret_state"] != "ACTIVE"
            or row["current_version_id"] != row["secret_version_id"]
            or row["envelope_key_id"] != self.owner.keys.key_id("SECRET_ENVELOPE_ENCRYPTION")
            or hashlib.sha256(row["envelope_aad_json"].encode("utf-8")).hexdigest()
            != row["envelope_aad_hash"]
        ):
            raise QueryExecutionFailure(
                "QUERY_SECRET_UNAVAILABLE",
                "The database credential is unavailable",
            )
        try:
            plaintext = self.owner.keys.decrypt_for(
                "SECRET_ENVELOPE_ENCRYPTION",
                Ciphertext(
                    nonce=row["envelope_nonce"],
                    value=row["envelope_ciphertext"],
                ),
                row["envelope_aad_json"].encode("utf-8"),
            )
            payload = json.loads(plaintext)
        except (InvalidTag, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise QueryExecutionFailure(
                "QUERY_SECRET_INTEGRITY_FAILED",
                "The database credential integrity check failed",
            ) from exc
        return self._validate_connection_input(row["engine"], payload)

    def _workbook_path(self, config: dict[str, Any]) -> Path:
        storage_key = config.get("storage_key")
        if (
            not isinstance(storage_key, str)
            or Path(storage_key).name != storage_key
            or not storage_key.endswith(".xlsx")
        ):
            raise QueryExecutionFailure(
                "WORKBOOK_INTEGRITY_FAILED",
                "The workbook storage reference is invalid",
            )
        candidate = (self.source_root / storage_key).resolve()
        if candidate.parent != self.source_root.resolve() or not candidate.is_file():
            raise QueryExecutionFailure(
                "WORKBOOK_UNAVAILABLE",
                "The workbook is unavailable",
            )
        return candidate

    def _disable_envelope(
        self,
        principal: Any,
        *,
        resource_kind: str,
        table: str,
        id_column: str,
        resource_id: str,
        if_match: str,
        idempotency_key: str,
        operation_id: str,
        event_type: str,
    ) -> dict[str, Any]:
        with self._authority_lock(resource_kind, resource_id):
            result = self._disable_envelope_serialized(
                principal,
                resource_kind=resource_kind,
                table=table,
                id_column=id_column,
                resource_id=resource_id,
                if_match=if_match,
                idempotency_key=idempotency_key,
                operation_id=operation_id,
                event_type=event_type,
            )
            self._cancel_jobs_for_authority(
                resource_kind=resource_kind,
                resource_id=resource_id,
                error_code=(
                    "QUERY_SOURCE_NOT_AVAILABLE"
                    if resource_kind == "query-source"
                    else "QUERY_DATASET_NOT_AVAILABLE"
                ),
            )
            return result

    def _disable_envelope_serialized(
        self,
        principal: Any,
        *,
        resource_kind: str,
        table: str,
        id_column: str,
        resource_id: str,
        if_match: str,
        idempotency_key: str,
        operation_id: str,
        event_type: str,
    ) -> dict[str, Any]:
        command = {"resource_id": resource_id, "if_match": if_match}
        request_digest = self.owner._sensitive_request_digest(operation_id, command)
        now = self.owner.clock()
        with self.owner.store.transaction() as connection:
            if table == "query_sources":
                row = self._load_source(
                    connection,
                    principal,
                    resource_id,
                    "config.edit_technical",
                )
            else:
                row = self._load_dataset(
                    connection,
                    principal,
                    resource_id,
                    "config.edit_technical",
                )
            replay = self.owner._idempotency_lookup(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
            )
            if replay is not None:
                return json.loads(replay["result_json"])
            self.owner._require_resource_etag(
                if_match,
                resource_kind,
                resource_id,
                row["revision"],
            )
            if row["state"] != "DISABLED":
                connection.execute(
                    f"""
                    UPDATE {table} SET state = 'DISABLED',
                        updated_at = ?, revision = revision + 1
                    WHERE {id_column} = ? AND revision = ?
                    """,
                    (now, resource_id, row["revision"]),
                )
                self.owner._append_audit(
                    connection,
                    event_type=event_type,
                    actor_type="USER",
                    actor_id=principal.user_id,
                    target_type=resource_kind.upper().replace("-", "_"),
                    target_id=resource_id,
                    outcome="SUCCESS",
                    reason=None,
                    details={"previous_state": row["state"], "state": "DISABLED"},
                    now=now,
                )
            updated = (
                self._source_row(connection, resource_id)
                if table == "query_sources"
                else self._dataset_row(connection, resource_id)
            )
            result = (
                self._source_response(updated)
                if table == "query_sources"
                else self._dataset_response(updated)
            )
            self.owner._idempotency_store(
                connection,
                phase=operation_id,
                principal_key=principal.user_id,
                idempotency_key=idempotency_key,
                request_digest=request_digest,
                result=result,
                now=now,
            )
            return result

    def _acquire_execution_slot(self, screen_id: str) -> tuple[bool, str | None]:
        if not self._global_slots.acquire(blocking=False):
            return False, "GLOBAL_QUERY_BACKPRESSURE"
        with self._jobs_lock:
            current = self._screen_inflight.get(screen_id, 0)
            if current >= MAX_PER_SCREEN_INFLIGHT:
                self._global_slots.release()
                return False, "SCREEN_QUERY_BACKPRESSURE"
            self._screen_inflight[screen_id] = current + 1
        return True, None

    def _release_execution_slot(self, screen_id: str) -> None:
        with self._jobs_lock:
            current = self._screen_inflight.get(screen_id, 0)
            if current <= 1:
                self._screen_inflight.pop(screen_id, None)
            else:
                self._screen_inflight[screen_id] = current - 1
        self._global_slots.release()

    def _release_job_slot_once(self, job: QueryJob) -> None:
        with job.lock:
            if job.slot_released:
                return
            job.slot_released = True
        self._release_execution_slot(job.screen_id)

    def _prune_terminal_jobs(self) -> None:
        with self._jobs_lock:
            overflow = len(self._jobs) - MAX_RETAINED_JOBS
            if overflow <= 0:
                return
            for execution_id, job in tuple(self._jobs.items()):
                with job.lock:
                    removable = job.terminal and job.slot_released
                if removable:
                    self._jobs.pop(execution_id, None)
                    overflow -= 1
                    if overflow == 0:
                        return

    def _authority_lock(self, resource_kind: str, resource_id: str) -> threading.RLock:
        key = (resource_kind, resource_id)
        with self._authority_locks_guard:
            lock = self._authority_locks.get(key)
            if lock is None:
                lock = threading.RLock()
                self._authority_locks[key] = lock
            return lock

    @staticmethod
    def _cancellation_failure(job: QueryJob) -> QueryExecutionFailure:
        code = "QUERY_TIMED_OUT" if job.timed_out else job.authority_error_code or "QUERY_CANCELLED"
        message = {
            "QUERY_TIMED_OUT": "The query timed out",
            "QUERY_SOURCE_NOT_AVAILABLE": "The QuerySource is unavailable",
            "QUERY_DATASET_NOT_AVAILABLE": "The approved dataset is unavailable",
        }.get(code, "The query was cancelled")
        return QueryExecutionFailure(code, message)

    def _cancel_jobs_for_authority(
        self,
        *,
        resource_kind: str,
        resource_id: str,
        error_code: str,
    ) -> None:
        with self._jobs_lock:
            jobs = [
                job
                for job in self._jobs.values()
                if (
                    resource_kind == "query-source"
                    and job.source_id == resource_id
                    or resource_kind == "query-dataset"
                    and job.dataset_id == resource_id
                )
            ]
        for job in jobs:
            with job.lock:
                if job.terminal:
                    continue
                job.authority_error_code = error_code
                job.cancel_event.set()
                cancel_adapter = job.cancel_adapter
                future = job.future
                job.result = {
                    "api_version": "v1",
                    "execution_id": job.execution_id,
                    "request_id": job.request_id,
                    "state": "FAILED",
                    "error": {
                        "code": error_code,
                        "message": self._execution_error_message(error_code),
                        "retryable": False,
                    },
                }
            if cancel_adapter is not None:
                with suppress(Exception):
                    cancel_adapter()
            cancelled_before_start = future.cancel() if future is not None else False
            self._finish_execution(
                job,
                state="FAILED",
                error_code=error_code,
                row_count=None,
                latency_ms=0,
            )
            if cancelled_before_start:
                self._release_job_slot_once(job)
                self._prune_terminal_jobs()

    def _expire_execution(self, job: QueryJob, timeout_ms: int) -> None:
        with job.lock:
            if job.terminal:
                return
            transitioned = self._finish_execution(
                job,
                state="TIMED_OUT",
                error_code="QUERY_TIMED_OUT",
                row_count=None,
                latency_ms=timeout_ms,
            )
            if not transitioned:
                return
            job.timed_out = True
            job.cancel_event.set()
            job.result = {
                "api_version": "v1",
                "execution_id": job.execution_id,
                "request_id": job.request_id,
                "state": "TIMED_OUT",
                "error": {
                    "code": "QUERY_TIMED_OUT",
                    "message": self._execution_error_message("QUERY_TIMED_OUT"),
                    "retryable": True,
                },
            }
            cancel_adapter = job.cancel_adapter
        if cancel_adapter is not None:
            with suppress(Exception):
                cancel_adapter()

    @staticmethod
    def _table_relation_name(table: exp.Table) -> str:
        parts = [
            value
            for value in (
                table.catalog,
                table.db,
                table.name,
            )
            if value
        ]
        return ".".join(parts).casefold()

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
        return (
            connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = ?
                """,
                (table,),
            ).fetchone()
            is not None
        )

    @staticmethod
    def _public_text(value: Any, label: str, minimum: int, maximum: int) -> str:
        if not isinstance(value, str):
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                f"{label} must be text",
            )
        normalized = value.strip()
        if not minimum <= len(normalized) <= maximum or any(
            ord(character) < 32 and character not in "\t" for character in normalized
        ):
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                f"{label} is outside the accepted length or character set",
            )
        return normalized

    @staticmethod
    def _private_connection_text(
        value: Any,
        label: str,
        minimum: int,
        maximum: int,
    ) -> str:
        if not isinstance(value, str):
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                f"{label} must be text",
            )
        normalized = value.strip()
        if not minimum <= len(normalized) <= maximum or any(ord(character) < 32 for character in normalized):
            raise ControlPlaneError(
                422,
                "SCHEMA_VALIDATION_FAILED",
                f"{label} is invalid",
            )
        return normalized

    @staticmethod
    def _json_scalar(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, bool)):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                return None
            return value
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _looks_like_timeout(exc: Exception) -> bool:
        message = str(exc).casefold()
        return any(
            marker in message
            for marker in (
                "timeout",
                "timed out",
                "statement timeout",
                "ora-01013",
                "max_execution_time",
                "canceling statement",
            )
        )

    @staticmethod
    def _qualification_message(code: str) -> str:
        return {
            "CONNECTION_TEST_PASSED": "The QuerySource passed its deployment-local connection test.",
            "QUERY_SOURCE_DISABLED": "The QuerySource is disabled.",
            "WORKBOOK_INTEGRITY_FAILED": "The workbook integrity check failed.",
            "WORKBOOK_UNAVAILABLE": "The workbook is unavailable.",
            "QUERY_SOURCE_UNAVAILABLE": "The source could not be reached with the configured material.",
        }.get(code, "The QuerySource test failed safely.")

    @staticmethod
    def _execution_error_message(code: str | None) -> str:
        return {
            "QUERY_CANCELLED": "The query was cancelled.",
            "QUERY_TIMED_OUT": "The query timed out.",
            "QUERY_SOURCE_UNAVAILABLE": "The QuerySource is unavailable.",
            "QUERY_SOURCE_NOT_AVAILABLE": "The QuerySource is disabled or unqualified.",
            "QUERY_DATASET_NOT_AVAILABLE": "The approved dataset is disabled.",
            "QUERY_PROCESS_RESTARTED": "The query ended when the control-plane process restarted.",
            "QUERY_RESTORE_INTERRUPTED": "The restored query cannot resume without its original worker.",
            "GLOBAL_QUERY_BACKPRESSURE": "The global controlled-query queue is full.",
            "SCREEN_QUERY_BACKPRESSURE": "This screen already has the maximum queued work.",
        }.get(code, "The controlled query failed safely.")
