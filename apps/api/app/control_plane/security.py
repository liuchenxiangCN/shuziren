from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from typing import Any
from unicodedata import normalize

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from argon2.low_level import Type
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PASSWORD_MIN_CODE_POINTS = 15
PASSWORD_MAX_CODE_POINTS = 128
COMMON_PASSWORDS = {
    "123456789012345",
    "admin1234567890",
    "password123456",
    "qwertyuiop12345",
    "shuziren123456",
    "administrator123",
}

PURPOSES = (
    "AUTH_SESSION_VERIFIER_PEPPER",
    "CSRF_TOKEN_VERIFIER_PEPPER",
    "ONE_TIME_TOKEN_VERIFIER_PEPPER",
    "DEVICE_CREDENTIAL_VERIFIER_PEPPER",
    "HIGH_RISK_REQUEST_HMAC",
    "SENSITIVE_IDEMPOTENCY_HMAC",
    "ONE_TIME_RESPONSE_ENCRYPTION",
    "AUDIT_EVENT_CHAIN_HMAC",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def normalize_username(value: str) -> str:
    normalized = normalize("NFKC", value).strip().casefold()
    if not normalized or len(normalized) > 128:
        raise ValueError("Username must contain 1 to 128 normalized characters")
    if any(character.isspace() for character in normalized):
        raise ValueError("Username cannot contain whitespace")
    return normalized


def validate_password(value: str, *, username: str | None = None) -> None:
    length = len(value)
    if length < PASSWORD_MIN_CODE_POINTS or length > PASSWORD_MAX_CODE_POINTS:
        raise ValueError(
            f"Password must contain {PASSWORD_MIN_CODE_POINTS} to "
            f"{PASSWORD_MAX_CODE_POINTS} Unicode code points"
        )
    if not value.isprintable():
        raise ValueError("Password may contain printing characters and spaces only")
    normalized = normalize("NFKC", value).casefold()
    if normalized in COMMON_PASSWORDS:
        raise ValueError("Password is blocked because it is common or compromised")
    if username is not None and normalized == normalize("NFKC", username).strip().casefold():
        raise ValueError("Password cannot equal the username")


class PasswordPolicy:
    def __init__(self) -> None:
        self._hasher = PasswordHasher(
            time_cost=2,
            memory_cost=19456,
            parallelism=1,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )

    def hash(self, password: str, *, username: str | None = None) -> str:
        validate_password(password, username=username)
        return self._hasher.hash(password)

    def verify(self, verifier: str, password: str) -> bool:
        try:
            return self._hasher.verify(verifier, password)
        except (VerifyMismatchError, InvalidHashError):
            return False


@dataclass(frozen=True)
class Ciphertext:
    nonce: bytes
    value: bytes


class PurposeKeyring:
    """Derives non-reused purpose keys from externally supplied root material."""

    def __init__(self, root_key: bytes) -> None:
        if len(root_key) < 32:
            raise ValueError("Control-plane root key must contain at least 256 bits")
        self._keys = {purpose: self._derive(root_key, purpose) for purpose in PURPOSES}
        self._key_ids = {
            purpose: hashlib.sha256(b"key-id:" + self._keys[purpose]).hexdigest()[:24] for purpose in PURPOSES
        }

    @classmethod
    def from_base64(cls, value: str) -> PurposeKeyring:
        try:
            decoded = base64.b64decode(value, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("CONTROL_PLANE_ROOT_KEY_B64 must be valid base64") from exc
        return cls(decoded)

    @staticmethod
    def generate_root_base64() -> str:
        return base64.b64encode(secrets.token_bytes(32)).decode("ascii")

    def key_id(self, purpose: str) -> str:
        return self._key_ids[purpose]

    def digest(self, purpose: str, value: str | bytes) -> str:
        encoded = value.encode("utf-8") if isinstance(value, str) else value
        return hmac.new(self._keys[purpose], encoded, hashlib.sha256).hexdigest()

    def verify(self, purpose: str, value: str | bytes, expected: str) -> bool:
        return hmac.compare_digest(self.digest(purpose, value), expected)

    def encrypt(self, plaintext: bytes, associated_data: bytes) -> Ciphertext:
        nonce = secrets.token_bytes(12)
        cipher = AESGCM(self._keys["ONE_TIME_RESPONSE_ENCRYPTION"])
        return Ciphertext(nonce=nonce, value=cipher.encrypt(nonce, plaintext, associated_data))

    def decrypt(self, ciphertext: Ciphertext, associated_data: bytes) -> bytes:
        cipher = AESGCM(self._keys["ONE_TIME_RESPONSE_ENCRYPTION"])
        return cipher.decrypt(ciphertext.nonce, ciphertext.value, associated_data)

    @staticmethod
    def _derive(root_key: bytes, purpose: str) -> bytes:
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"shuziren:p1.1:purpose-keys:v1",
            info=f"shuziren:{purpose}:v1".encode("ascii"),
        ).derive(root_key)


def opaque_secret() -> str:
    return secrets.token_urlsafe(32)


def opaque_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(16)}"
