import pytest
from pydantic import ValidationError

from app.core.security import generate_token, hash_password, hash_token, verify_password
from app.schemas.auth import LoginRequest, RegisterRequest
from tests.conftest import VALID_REGISTRATION


async def test_password_hash_roundtrip():
    stored = await hash_password("s3cret-passphrase")
    assert stored.startswith("scrypt$")
    assert "s3cret-passphrase" not in stored
    assert await verify_password("s3cret-passphrase", stored)
    assert not await verify_password("wrong-passphrase", stored)


async def test_unique_salt_per_hash():
    assert await hash_password("same") != await hash_password("same")


async def test_malformed_hash_is_rejected_not_crashing():
    assert not await verify_password("x", "not-a-hash")
    assert not await verify_password("x", "scrypt$a$b$c$d$e")


def test_tokens_are_random_and_hashed():
    a = generate_token()
    assert a != generate_token()
    assert len(a) >= 43
    assert len(hash_token(a)) == 64


def test_register_normalises_email():
    data = RegisterRequest.model_validate({**VALID_REGISTRATION, "email": "  Asha@Example.COM "})
    assert data.email == "asha@example.com"


@pytest.mark.parametrize(
    ("override", "field"),
    [
        ({"password": "short", "confirmPassword": "short"}, "password"),
        ({"consent": False}, "consent"),
        ({"email": "not-an-email"}, "email"),
        ({"name": "A"}, "name"),
    ],
)
def test_register_rejects_invalid_fields(override, field):
    with pytest.raises(ValidationError) as exc:
        RegisterRequest.model_validate({**VALID_REGISTRATION, **override})
    assert any(e["loc"] and e["loc"][0] == field for e in exc.value.errors())


def test_register_ignores_role():
    data = RegisterRequest.model_validate({**VALID_REGISTRATION, "role": "admin"})
    assert not hasattr(data, "role")


def test_login_rejects_oversized_password():
    with pytest.raises(ValidationError):
        LoginRequest.model_validate({"email": "a@b.co", "password": "x" * 129})
