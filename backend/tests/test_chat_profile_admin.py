from app.db.mongo import AI_USAGE, CONVERSATIONS, USERS
from app.services.ai_service import AIUnavailableError
from tests.conftest import VALID_REGISTRATION, signup


# ---------------- chat ----------------


async def test_chat_requires_login(client, fake_ai):
    client.cookies.clear()
    assert (await client.post("/api/chat", json={"message": "hi"})).status_code == 401


async def test_chat_requires_health_data_consent(client, fake_ai):
    await signup(client, consent=False)
    res = await client.post("/api/chat", json={"message": "I have a headache"})
    assert res.status_code == 403 and res.json()["error"] == "consent_required"
    assert fake_ai.chat_calls == 0


async def test_conversation_flow_title_report_and_history(client, fake_ai):
    await signup(client)
    first = (await client.post("/api/chat", json={"message": "I have a headache"})).json()
    conv = first["conversation"]
    assert conv["title"] == "Headache for two days"
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant"]
    assert conv["canGenerateReport"] is False

    fake_ai.ready = True  # AI says it has enough information
    second = (await client.post("/api/chat", json={"conversationId": conv["id"], "message": "2 days, about 5/10"})).json()
    assert second["assessmentId"]
    assert second["conversation"]["status"] == "completed"

    report = (await client.get(f"/api/assessment/{second['assessmentId']}")).json()["assessment"]
    assert report["possibleExplanations"][0]["name"] == "tension-type headache"  # "Confirmed" stripped
    assert all("mg" not in s for s in report["nextSteps"])  # dosing stripped

    listing = (await client.get("/api/conversations")).json()["conversations"]
    assert len(listing) == 1 and listing[0]["messageCount"] == 4
    assert (await client.get("/api/conversations?q=headache")).json()["conversations"]
    assert not (await client.get("/api/conversations?q=zzz")).json()["conversations"]
    assert len((await client.get("/api/assessments")).json()["assessments"]) == 1


async def test_no_report_before_minimum_information(client, fake_ai):
    await signup(client)
    fake_ai.ready = True  # even if the AI claims it's ready after one message
    first = (await client.post("/api/chat", json={"message": "I have a headache"})).json()
    assert first["assessmentId"] is None
    res = await client.post("/api/assessment", json={"conversationId": first["conversation"]["id"]})
    assert res.status_code == 409


async def test_manual_report_generation(client, fake_ai):
    await signup(client)
    c = (await client.post("/api/chat", json={"message": "I have a cough"})).json()["conversation"]
    c = (await client.post("/api/chat", json={"conversationId": c["id"], "message": "5 days"})).json()["conversation"]
    assert c["canGenerateReport"] is True
    res = await client.post("/api/assessment", json={"conversationId": c["id"]})
    assert res.status_code == 200 and res.json()["assessment"]["urgencyLevel"] == "self_monitoring"


async def test_ai_unavailable_returns_503_and_rolls_back_cleanly(client, fake_ai, db):
    await signup(client)
    fake_ai.fail_with = AIUnavailableError("The AI assistant isn't configured on this server yet.")
    res = await client.post("/api/chat", json={"message": "I have a headache"})
    assert res.status_code == 503 and "isn't configured" in res.json()["error"]
    assert await db[CONVERSATIONS].count_documents({}) == 0  # empty new conversation removed

    fake_ai.fail_with = None
    conv = (await client.post("/api/chat", json={"message": "I have a headache"})).json()["conversation"]
    fake_ai.fail_with = AIUnavailableError()
    res = await client.post("/api/chat", json={"conversationId": conv["id"], "message": "two days"})
    assert res.status_code == 503
    stored = await db[CONVERSATIONS].find_one({})
    assert [m["content"] for m in stored["messages"] if m["role"] == "user"] == ["I have a headache"]


async def test_message_length_limit(client, fake_ai):
    await signup(client)
    res = await client.post("/api/chat", json={"message": "x" * 2001})
    assert res.status_code == 400


# ---------------- access control ----------------


async def test_users_cannot_access_each_others_records(client, fake_ai):
    await signup(client, "a@example.com")
    first = (await client.post("/api/chat", json={"message": "I have a headache"})).json()
    cid = first["conversation"]["id"]
    fake_ai.ready = True
    done = (await client.post("/api/chat", json={"conversationId": cid, "message": "2 days"})).json()
    aid = done["assessmentId"]

    await signup(client, "b@example.com")
    assert (await client.get(f"/api/conversations/{cid}")).status_code == 404
    assert (await client.get(f"/api/assessment/{aid}")).status_code == 404
    assert (await client.delete(f"/api/conversations/{cid}")).status_code == 404
    assert (await client.post("/api/chat", json={"conversationId": cid, "message": "hi"})).status_code == 404
    assert (await client.get("/api/conversations")).json()["conversations"] == []
    assert (await client.get("/api/conversations/not-an-id")).status_code == 404


async def test_delete_conversation_removes_report(client, fake_ai):
    await signup(client)
    c = (await client.post("/api/chat", json={"message": "I have a headache"})).json()["conversation"]
    fake_ai.ready = True
    aid = (await client.post("/api/chat", json={"conversationId": c["id"], "message": "2 days"})).json()["assessmentId"]
    assert (await client.delete(f"/api/conversations/{c['id']}")).status_code == 200
    assert (await client.get(f"/api/assessment/{aid}")).status_code == 404


# ---------------- profile & privacy ----------------


async def test_profile_update_and_email_change_requires_password(client, fake_ai):
    await signup(client)
    p = (await client.get("/api/profile")).json()["profile"]
    assert p["privacy"]["healthDataConsent"] is True and p["memberSince"]

    res = await client.put("/api/profile", json={"name": "Asha R", "email": "asha@example.com"})
    assert res.status_code == 200 and res.json()["profile"]["name"] == "Asha R"

    res = await client.put("/api/profile", json={"name": "Asha R", "email": "new@example.com"})
    assert res.status_code == 400 and "currentPassword" in res.json()["fieldErrors"]
    res = await client.put("/api/profile", json={"name": "Asha R", "email": "new@example.com", "currentPassword": VALID_REGISTRATION["password"]})
    assert res.status_code == 200 and res.json()["profile"]["email"] == "new@example.com"


async def test_change_password_keeps_current_session_only(client, fake_ai):
    token = await signup(client)
    client.cookies.clear()
    other = (await client.post("/api/auth/login", json={"email": "asha@example.com", "password": VALID_REGISTRATION["password"]})).cookies.get("healthai_session")
    client.cookies.set("healthai_session", token)

    bad = await client.post("/api/profile/password", json={"currentPassword": "wrong one", "newPassword": "new password 1", "confirmPassword": "new password 1"})
    assert bad.status_code == 400
    ok = await client.post("/api/profile/password", json={"currentPassword": VALID_REGISTRATION["password"], "newPassword": "new password 1", "confirmPassword": "new password 1"})
    assert ok.status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 200  # this device stays signed in
    client.cookies.set("healthai_session", other)
    assert (await client.get("/api/auth/me")).status_code == 401  # other device signed out


async def test_retention_sets_expiry_and_withdrawing_consent_deletes_health_data(client, fake_ai, db):
    await signup(client)
    await client.post("/api/chat", json={"message": "I have a headache"})
    res = await client.put("/api/profile/privacy", json={"healthDataConsent": True, "retentionDays": 30})
    assert res.json()["profile"]["privacy"]["retentionDays"] == 30
    assert (await db[CONVERSATIONS].find_one({}))["expires_at"] is not None

    await client.put("/api/profile/privacy", json={"healthDataConsent": False, "retentionDays": None})
    assert await db[CONVERSATIONS].count_documents({}) == 0
    assert (await client.post("/api/chat", json={"message": "hi"})).status_code == 403


async def test_delete_account_requires_password_and_removes_everything(client, fake_ai, db):
    await signup(client)
    await client.post("/api/chat", json={"message": "I have a headache"})
    assert (await client.request("DELETE", "/api/profile", json={"password": "wrong pass"})).status_code == 400
    res = await client.request("DELETE", "/api/profile", json={"password": VALID_REGISTRATION["password"]})
    assert res.status_code == 200
    assert await db[USERS].count_documents({}) == 0
    assert await db[CONVERSATIONS].count_documents({}) == 0
    assert (await client.get("/api/auth/me")).status_code == 401


# ---------------- admin ----------------


async def make_admin(db, email):
    await db[USERS].update_one({"email": email}, {"$set": {"role": "admin"}})


async def test_admin_endpoints_require_admin_role(client, fake_ai):
    await signup(client)
    for path in ("/api/admin/dashboard", "/api/admin/users", "/api/admin/audit"):
        assert (await client.get(path)).status_code == 403
    client.cookies.clear()
    assert (await client.get("/api/admin/dashboard")).status_code == 401


async def test_admin_dashboard_has_stats_but_no_health_content(client, fake_ai, db):
    await signup(client, "patient@example.com")
    await client.post("/api/chat", json={"message": "I have a secret rash on my elbow"})
    await client.post("/api/chat", json={"message": "I can't breathe"})
    await db[AI_USAGE].insert_one({"kind": "chat", "ok": True, "input_tokens": 10, "output_tokens": 5, "latency_ms": 100, "created_at": __import__("datetime").datetime.now(__import__("datetime").UTC)})

    await signup(client, "admin@example.com")
    await make_admin(db, "admin@example.com")
    res = await client.get("/api/admin/dashboard")
    assert res.status_code == 200
    data = res.json()
    assert data["totals"]["users"] == 2 and data["totals"]["conversations"] == 2
    assert data["assessmentsByUrgency"]["emergency"] == 1
    assert data["aiUsage"]["requests7d"] == 1
    dumped = res.text.lower()
    assert "rash" not in dumped and "breathe" not in dumped and "patient@example.com" not in dumped

    users = (await client.get("/api/admin/users?q=patient")).json()
    assert users["total"] == 1 and users["users"][0]["conversationCount"] == 2
    assert "rash" not in str(users)


async def test_admin_role_change_is_audited_and_cannot_demote_self(client, fake_ai, db):
    await signup(client, "user@example.com")
    target = (await client.get("/api/auth/me")).json()["user"]["id"]
    await signup(client, "admin@example.com")
    await make_admin(db, "admin@example.com")
    me = (await client.get("/api/auth/me")).json()["user"]["id"]

    assert (await client.patch(f"/api/admin/users/{me}", json={"role": "user"})).status_code == 400
    res = await client.patch(f"/api/admin/users/{target}", json={"role": "admin"})
    assert res.status_code == 200 and res.json()["user"]["role"] == "admin"
    entries = (await client.get("/api/admin/audit")).json()["entries"]
    assert entries[0]["action"] == "user.role_changed" and entries[0]["target"] == "user@example.com"
