"""Password hashing and token helpers.

Passwords: scrypt (Python standard library) with OWASP-recommended parameters
N=2^17, r=8, p=1. Stored as  scrypt$<N>$<r>$<p>$<salt_b64>$<hash_b64>
so the parameters can be raised later without breaking existing hashes.
Hashing is CPU-heavy, so it runs in a worker thread to keep the server responsive.
"""

import asyncio
import base64
import hashlib
import hmac
import secrets
import unicodedata

N = 2**17
R = 8
P = 1
KEY_LEN = 64
MAX_MEM = 256 * 1024 * 1024


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int, key_len: int) -> bytes:
    normalized = unicodedata.normalize("NFKC", password).encode("utf-8")
    return hashlib.scrypt(normalized, salt=salt, n=n, r=r, p=p, maxmem=MAX_MEM, dklen=key_len)


def _hash_sync(password: str) -> str:
    salt = secrets.token_bytes(16)
    key = _scrypt(password, salt, N, R, P, KEY_LEN)
    return "$".join(
        ["scrypt", str(N), str(R), str(P), base64.b64encode(salt).decode(), base64.b64encode(key).decode()]
    )


def _verify_sync(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        return False
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt = base64.b64decode(parts[4])
        expected = base64.b64decode(parts[5])
    except ValueError:
        return False
    key = _scrypt(password, salt, n, r, p, len(expected))
    return hmac.compare_digest(key, expected)


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hash_sync, password)


async def verify_password(password: str, stored: str) -> bool:
    return await asyncio.to_thread(_verify_sync, password, stored)


_dummy_hash: str | None = None


async def get_dummy_hash() -> str:
    """A real hash of a random password. Checking against it when an email is unknown
    makes that path take as long as a wrong password, so timing can't reveal accounts."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = await hash_password(secrets.token_hex(16))
    return _dummy_hash


def generate_token() -> str:
    """256-bit random token, URL-safe. Given to the user; never stored as-is."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """What we store instead of a token, so a database leak can't be replayed."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
