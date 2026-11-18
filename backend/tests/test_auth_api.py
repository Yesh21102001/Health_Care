import json

from tests.conftest import VALID_REGISTRATION

COOKIE = "healthai_session"


async def register(client, **override):
    return await client.post("/api/auth/register", json={**VALID_REGISTRATION, **override})


async def test_register_creates_account_with_secure_cookie(client):
    res = await register(client)
    assert res.status_code == 201
    body = res.json()
    assert body["user"]["email"] == "asha@example.com" and body["user"]["role"] == "user"
    assert "password" not in json.dumps(body).lower()
    set_cookie = res.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie and "path=/" in set_cookie
    assert res.headers["cache-control"] == "no-store"


async def test_register_cannot_create_admin(client):
    res = await register(client, role="admin")
    assert res.json()["user"]["role"] == "user"


async def test_register_field_errors_use_frontend_format(client):
    res = await register(client, consent=False, confirmPassword="different!!")
    assert res.status_code == 400
    body = res.json()
    assert body["error"] == "Please fix the highlighted fields."
    assert "consent" in body["fieldErrors"]


async def test_password_mismatch_maps_to_confirm_field(client):
    res = await register(client, confirmPassword="something else")
    assert res.status_code == 400
    assert res.json()["fieldErrors"] == {"confirmPassword": "Passwords do not match."}


async def test_duplicate_email_409(client):
    await register(client)
    res = await register(client)
    assert res.status_code == 409
    assert res.json()["fieldErrors"]["email"]


async def test_csrf_blocks_cross_site_and_missing_origin(client):
    res = await client.post("/api/auth/register", json=VALID_REGISTRATION, headers={"origin": "https://evil.example"})
    assert res.status_code == 403
    # Remove the default Origin header.
    req = client.build_request("POST", "/api/auth/register", json=VALID_REGISTRATION)
    del req.headers["origin"]
    assert (await client.send(req)).status_code == 403


async def test_admin_origin_is_allowed(client):
    res = await client.post("/api/auth/login", json={"email": "a@b.co", "password": "x"}, headers={"origin": "http://localhost:3001"})
    assert res.status_code == 401  # got past CSRF, failed on credentials


async def test_rejects_non_json_malformed_and_oversized(client):
    res = await client.post("/api/auth/register", content="a=b", headers={"content-type": "application/x-www-form-urlencoded"})
    assert res.status_code == 415
    res = await client.post("/api/auth/register", content="{not json", headers={"content-type": "application/json"})
    assert res.status_code == 400 and res.json()["error"] == "Invalid JSON."
    res = await client.post("/api/auth/register", json={"name": "x" * 20_000})
    assert res.status_code == 413
    res = await client.post("/api/auth/register", content="[1,2]", headers={"content-type": "application/json"})
    assert res.status_code == 400


async def test_full_session_lifecycle(client):
    await register(client)
    client.cookies.clear()

    bad = await client.post("/api/auth/login", json={"email": "asha@example.com", "password": "nope nope"})
    unknown = await client.post("/api/auth/login", json={"email": "who@example.com", "password": "nope nope"})
    assert bad.status_code == unknown.status_code == 401
    assert bad.json() == unknown.json()  # no hint about which emails exist

    ok = await client.post("/api/auth/login", json={"email": "ASHA@example.com", "password": VALID_REGISTRATION["password"]})
    assert ok.status_code == 200
    token = ok.cookies.get(COOKIE)
    assert token

    client.cookies.clear()
    assert (await client.get("/api/auth/me")).status_code == 401
    client.cookies.set(COOKIE, token)
    me = await client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["user"]["email"] == "asha@example.com"

    out = await client.post("/api/auth/logout", json={})
    assert out.status_code == 200
    assert "max-age=0" in out.headers["set-cookie"].lower()
    # A copied cookie no longer works after logout.
    client.cookies.set(COOKIE, token)
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_login_rate_limited_per_account(client):
    statuses = []
    for i in range(11):
        res = await client.post(
            "/api/auth/login",
            json={"email": "target@example.com", "password": f"guess {i}"},
            headers={"x-forwarded-for": f"198.51.100.{i}"},
        )
        statuses.append(res.status_code)
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


async def test_forgot_password_same_response_for_known_and_unknown(client, capsys):
    await register(client)
    known = await client.post("/api/auth/forgot-password", json={"email": "asha@example.com"})
    unknown = await client.post("/api/auth/forgot-password", json={"email": "ghost@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    out = capsys.readouterr().out
    assert out.count("[dev mail] Open this link") == 1  # only the real account gets a link


async def test_reset_password_via_api(client, capsys):
    await register(client)
    await client.post("/api/auth/forgot-password", json={"email": "asha@example.com"})
    link = next(line for line in capsys.readouterr().out.splitlines() if "Open this link" in line)
    token = link.split("token=")[1].strip()

    res = await client.post("/api/auth/reset-password", json={"token": token, "password": "brand new pass", "confirmPassword": "brand new pass"})
    assert res.status_code == 200
    again = await client.post("/api/auth/reset-password", json={"token": token, "password": "brand new pass", "confirmPassword": "brand new pass"})
    assert again.status_code == 400 and "invalid or has expired" in again.json()["error"]

    client.cookies.clear()
    login = await client.post("/api/auth/login", json={"email": "asha@example.com", "password": "brand new pass"})
    assert login.status_code == 200


async def test_security_headers_and_health(client):
    res = await client.get("/api/health")
    assert res.status_code == 200 and res.json() == {"status": "ok", "database": "ok"}
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
