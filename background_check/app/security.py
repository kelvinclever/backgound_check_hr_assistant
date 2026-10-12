import base64
import hashlib
import hmac
import secrets
from functools import lru_cache

from cryptography.fernet import Fernet
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.config import get_settings

_EMPLOYER_SALT = "employer-reference-v1"


@lru_cache
def _fernet() -> Fernet:
    s = get_settings()
    if s.encryption_key:
        return Fernet(s.encryption_key.encode())
    derived = base64.urlsafe_b64encode(hashlib.sha256(s.secret_key.encode()).digest())
    return Fernet(derived)


class EncryptedString(TypeDecorator):
    """Transparently encrypts PII (national ID, KRA PIN) at rest."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return _fernet().encrypt(value.encode()).decode() if value is not None else None

    def process_result_value(self, value, dialect):
        return _fernet().decrypt(value.encode()).decode() if value is not None else None


def _hmac(value: str) -> str:
    return hmac.new(get_settings().secret_key.encode(), value.encode(), hashlib.sha256).hexdigest()


def hash_identifier(value: str) -> str:
    """Deterministic keyed hash, used for uniqueness lookups on encrypted fields."""
    return _hmac("id:" + value)


def generate_otp() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def hash_otp(candidate_id: str, otp: str) -> str:
    return _hmac(f"otp:{candidate_id}:{otp}")


class TokenError(Exception):
    pass


class TokenExpiredError(TokenError):
    pass


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt=_EMPLOYER_SALT)


def make_employer_token(reference_id: str) -> str:
    return _serializer().dumps({"ref": reference_id})


def read_employer_token(token: str) -> str:
    max_age = get_settings().employer_token_ttl_days * 86400
    try:
        return _serializer().loads(token, max_age=max_age)["ref"]
    except SignatureExpired as e:
        raise TokenExpiredError("Token expired") from e
    except (BadSignature, KeyError, TypeError) as e:
        raise TokenError("Invalid token") from e
