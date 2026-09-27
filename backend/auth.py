"""
Auth helpers: password hashing and signed session tokens.

Owner: Member 4 (Interface)

Deliberately stdlib-only (hashlib, hmac, secrets) rather than pulling in
passlib/PyJWT, so there's nothing extra to install/verify — appropriate for
a class project, not meant to replace a real auth library in production.

Token format: "<user_id>.<expiry_timestamp>.<signature>"
The signature is an HMAC over "<user_id>.<expiry_timestamp>" using a secret
key, so a token can't be forged or its expiry extended without the key.
"""

import hashlib
import hmac
import os
import secrets
import time

# In production this must come from an environment variable, not be
# hardcoded. Generate one with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY = os.environ.get("FPL_SECRET_KEY", "dev-only-insecure-key-change-me")
TOKEN_LIFETIME_SECONDS = 60 * 60 * 24 * 7  # 7 days


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Returns (password_hash, salt). Generates a new salt if none given."""
    if salt is None:
        salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return pw_hash.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    candidate_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate_hash, password_hash)


def create_token(user_id: int) -> str:
    expiry = int(time.time()) + TOKEN_LIFETIME_SECONDS
    payload = f"{user_id}.{expiry}"
    signature = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_token(token: str) -> int | None:
    """Returns the user_id if the token is valid and unexpired, else None."""
    try:
        user_id_str, expiry_str, signature = token.split(".")
    except ValueError:
        return None

    payload = f"{user_id_str}.{expiry_str}"
    expected_signature = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    if int(expiry_str) < time.time():
        return None  # expired

    return int(user_id_str)
