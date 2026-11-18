"""Test setup: a throwaway MongoDB for the whole run, and a clean database per test.

Uses TEST_MONGODB_URI if set; otherwise downloads and starts a temporary
mongod with pymongo-inmemory (first run takes a minute to download).
"""

import os
from collections.abc import AsyncIterator, Iterator

# Must be set before the app is imported (it reads settings at import).
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("MONGODB_URI", "mongodb://placeholder")
os.environ["FRONTEND_URL"] = "http://localhost:3000"
os.environ["ADMIN_URL"] = "http://localhost:3001"
os.environ["TRUST_PROXY"] = "true"

import httpx
import pytest
from fastapi import FastAPI

from app.core.config import get_settings
from app.db import mongo
from app.main import create_app

ORIGIN = "http://localhost:3000"


@pytest.fixture(scope="session")
def mongo_uri() -> Iterator[str]:
    external = os.environ.get("TEST_MONGODB_URI")
    if external:
        yield external
        return
    from pymongo_inmemory import Mongod
    from pymongo_inmemory.context import Context

    server = Mongod(Context())
    server.start()
    try:
        yield server.connection_string
    finally:
        server.stop()


@pytest.fixture(scope="session")
async def app(mongo_uri: str) -> AsyncIterator[FastAPI]:
    os.environ["MONGODB_URI"] = mongo_uri
    os.environ["MONGODB_DB"] = "healthai_test"
    get_settings.cache_clear()
    application = create_app(get_settings())
    await mongo.connect(get_settings())  # ASGITransport doesn't run the lifespan
    yield application
    await mongo.close()


@pytest.fixture(autouse=True)
async def clean_db(app: FastAPI) -> None:
    db = mongo.get_db()
    for name in await db.list_collection_names():
        await db[name].delete_many({})


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        headers={"origin": ORIGIN, "x-forwarded-for": "203.0.113.10"},
    ) as c:
        yield c


@pytest.fixture
def db():
    return mongo.get_db()


class FakeAI:
    """Stands in for Claude. Records calls so tests can prove the AI was (not) used."""

    def __init__(self) -> None:
        self.chat_calls = 0
        self.report_calls = 0
        self.next_reply = "Thanks. How long have you had this?"
        self.ready = False
        self.title = "Headache for two days"
        self.report_urgency = "self_monitoring"
        self.last_safety_note: str | None = None
        self.fail_with: Exception | None = None

    async def chat_turn(self, history, safety_note=None):
        from app.services.ai_service import ChatTurnDraft

        self.chat_calls += 1
        self.last_safety_note = safety_note
        if self.fail_with:
            raise self.fail_with
        return ChatTurnDraft(reply=self.next_reply, ready_for_report=self.ready, conversation_title=self.title)

    async def generate_report(self, history, safety_note=None):
        from app.services.ai_service import ReportDraft

        self.report_calls += 1
        return ReportDraft(
            symptoms=["Headache"],
            duration="2 days",
            severity="5/10",
            additional_info=["No fever"],
            possible_explanations=[{"name": "Confirmed tension-type headache", "why": "Gradual onset with poor sleep."}],
            warning_signs=["Sudden severe headache"],
            next_steps=["Rest and hydrate", "Take 500 mg paracetamol every 6 hours"],
            urgency_level=self.report_urgency,
            urgency_reason="No warning signs reported.",
        )


@pytest.fixture
def fake_ai(app: FastAPI) -> FakeAI:
    fake = FakeAI()
    app.state.ai = fake
    return fake


async def signup(client: httpx.AsyncClient, email: str = "asha@example.com", consent: bool = True) -> str:
    """Registers a user, optionally grants health-data consent, and returns the session token."""
    client.cookies.clear()
    res = await client.post("/api/auth/register", json={**VALID_REGISTRATION, "email": email})
    assert res.status_code == 201, res.text
    token = res.cookies.get("healthai_session")
    client.cookies.set("healthai_session", token)
    if consent:
        r = await client.put("/api/profile/privacy", json={"healthDataConsent": True, "retentionDays": None})
        assert r.status_code == 200, r.text
    return token


VALID_REGISTRATION = {
    "name": "Asha Rao",
    "email": "asha@example.com",
    "password": "correct horse battery",
    "confirmPassword": "correct horse battery",
    "consent": True,
}
