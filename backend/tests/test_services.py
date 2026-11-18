from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import hash_token
from app.db.mongo import RESET_TOKENS, SESSIONS, USERS
from app.schemas.auth import RegisterRequest
from app.services import auth_service
from app.services.rate_limit import rate_limit
from app.services.session_service import create_session, get_user_by_session_token, revoke_session
from tests.conftest import VALID_REGISTRATION

TTL = 3600


def reg(**override) -> RegisterRequest:
    return RegisterRequest.model_validate({**VALID_REGISTRATION, **override})


async def test_register_records_consent_and_forces_user_role(db):
    user = await auth_service.register_user(db, reg())
    assert user.role == "user" and user.email == "asha@example.com"
    stored = await db[USERS].find_one({"email": "asha@example.com"})
    assert stored["consent"]["age_confirmed"] is True
    assert stored["password_hash"].startswith("scrypt$")


async def test_duplicate_email_is_rejected_case_insensitively(db):
    await auth_service.register_user(db, reg())
    with pytest.raises(auth_service.EmailTakenError):
        await auth_service.register_user(db, reg(email="ASHA@Example.com"))


async def test_authenticate(db):
    await auth_service.register_user(db, reg())
    assert (await auth_service.authenticate(db, "asha@example.com", VALID_REGISTRATION["password"])).name == "Asha Rao"
    assert await auth_service.authenticate(db, "asha@example.com", "wrong password") is None
    assert await auth_service.authenticate(db, "nobody@example.com", "whatever") is None


async def test_session_stores_only_hash(db):
    user = await auth_service.register_user(db, reg())
    token, _ = await create_session(db, user.id, TTL)
    assert (await get_user_by_session_token(db, token)).id == user.id
    assert await db[SESSIONS].find_one({"token_hash": token}) is None
    assert await db[SESSIONS].find_one({"token_hash": hash_token(token)}) is not None


async def test_unknown_revoked_and_expired_sessions_fail(db):
    user = await auth_service.register_user(db, reg())
    assert await get_user_by_session_token(db, "made-up-token") is None

    a, _ = await create_session(db, user.id, TTL)
    await revoke_session(db, a)
    assert await get_user_by_session_token(db, a) is None

    b, _ = await create_session(db, user.id, TTL)
    await db[SESSIONS].update_one({"token_hash": hash_token(b)}, {"$set": {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}})
    assert await get_user_by_session_token(db, b) is None


async def test_reset_flow_single_use_and_signs_out_everywhere(db):
    user = await auth_service.register_user(db, reg())
    session, _ = await create_session(db, user.id, TTL)
    assert await auth_service.create_password_reset_token(db, "nobody@example.com", TTL) is None
    token, _name = await auth_service.create_password_reset_token(db, "asha@example.com", TTL)

    assert await auth_service.reset_password(db, token, "a brand new password")
    assert not await auth_service.reset_password(db, token, "another password!!")
    assert await auth_service.authenticate(db, "asha@example.com", VALID_REGISTRATION["password"]) is None
    assert await auth_service.authenticate(db, "asha@example.com", "a brand new password") is not None
    assert await get_user_by_session_token(db, session) is None


async def test_only_newest_reset_link_works_and_expiry_is_enforced(db):
    await auth_service.register_user(db, reg())
    first, _ = await auth_service.create_password_reset_token(db, "asha@example.com", TTL)
    second, _ = await auth_service.create_password_reset_token(db, "asha@example.com", TTL)
    assert not await auth_service.reset_password(db, first, "new password one")

    await db[RESET_TOKENS].update_one(
        {"token_hash": hash_token(second)}, {"$set": {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}}
    )
    assert not await auth_service.reset_password(db, second, "new password two")


async def test_rate_limit_blocks_after_limit_per_identifier(db):
    results = [await rate_limit(db, "test", "1.2.3.4", 3, 60) for _ in range(4)]
    assert [r.ok for r in results] == [True, True, True, False]
    assert results[3].retry_after_seconds > 0
    assert (await rate_limit(db, "test", "other", 3, 60)).ok
