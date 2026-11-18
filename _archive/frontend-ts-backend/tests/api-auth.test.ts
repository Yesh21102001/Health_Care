import { NextRequest } from "next/server";
import { beforeAll, describe, expect, it } from "vitest";
import { POST as forgot } from "@/app/api/auth/forgot-password/route";
import { POST as login } from "@/app/api/auth/login/route";
import { POST as logout } from "@/app/api/auth/logout/route";
import { GET as me } from "@/app/api/auth/me/route";
import { POST as register } from "@/app/api/auth/register/route";
import { ORIGIN, cookieFrom, ensureIndexes, jsonRequest, validRegistration } from "./helpers";

beforeAll(ensureIndexes);

function meRequest(cookie?: string) {
  return new NextRequest(`${ORIGIN}/api/auth/me`, { headers: cookie ? { cookie } : {} });
}

describe("POST /api/auth/register", () => {
  it("creates the account and sets a secure session cookie", async () => {
    const res = await register(jsonRequest("/api/auth/register", validRegistration));
    expect(res.status).toBe(201);
    const body = await res.json();
    expect(body.user).toMatchObject({ email: "asha@example.com", role: "user" });
    expect(JSON.stringify(body)).not.toMatch(/password/i);

    const setCookie = res.headers.get("set-cookie")!;
    expect(setCookie).toMatch(/HttpOnly/i);
    expect(setCookie).toMatch(/SameSite=lax/i);
    expect(res.headers.get("cache-control")).toBe("no-store");
  });

  it("cannot be used to create an admin", async () => {
    const res = await register(jsonRequest("/api/auth/register", { ...validRegistration, role: "admin" }));
    expect((await res.json()).user.role).toBe("user");
  });

  it("returns field errors for invalid input", async () => {
    const res = await register(jsonRequest("/api/auth/register", { ...validRegistration, consent: false }));
    expect(res.status).toBe(400);
    expect((await res.json()).fieldErrors.consent).toBeTruthy();
  });

  it("returns 409 for a duplicate email", async () => {
    await register(jsonRequest("/api/auth/register", validRegistration));
    const res = await register(jsonRequest("/api/auth/register", validRegistration));
    expect(res.status).toBe(409);
  });

  it("blocks cross-site and origin-less requests (CSRF)", async () => {
    expect((await register(jsonRequest("/api/auth/register", validRegistration, { origin: "https://evil.example" }))).status).toBe(403);
    expect((await register(jsonRequest("/api/auth/register", validRegistration, { origin: null }))).status).toBe(403);
  });

  it("rejects non-JSON and malformed bodies", async () => {
    expect((await register(jsonRequest("/api/auth/register", "a=b", { contentType: "application/x-www-form-urlencoded" }))).status).toBe(415);
    expect((await register(jsonRequest("/api/auth/register", "{not json"))).status).toBe(400);
    expect((await register(jsonRequest("/api/auth/register", { name: "x".repeat(20_000) }))).status).toBe(413);
  });
});

describe("login, me and logout", () => {
  it("full session lifecycle", async () => {
    await register(jsonRequest("/api/auth/register", validRegistration));

    const bad = await login(jsonRequest("/api/auth/login", { email: "asha@example.com", password: "nope nope" }));
    expect(bad.status).toBe(401);
    const unknown = await login(jsonRequest("/api/auth/login", { email: "who@example.com", password: "nope nope" }));
    expect(await unknown.json()).toEqual(await bad.json()); // no hint about which emails exist

    const ok = await login(jsonRequest("/api/auth/login", { email: "ASHA@example.com", password: validRegistration.password }));
    expect(ok.status).toBe(200);
    const cookie = cookieFrom(ok);

    expect((await me(meRequest())).status).toBe(401);
    const meRes = await me(meRequest(cookie));
    expect(meRes.status).toBe(200);
    expect((await meRes.json()).user.email).toBe("asha@example.com");

    const out = await logout(jsonRequest("/api/auth/logout", {}, { cookie }));
    expect(out.status).toBe(200);
    expect(out.headers.get("set-cookie")).toMatch(/Max-Age=0|Expires=Thu, 01 Jan 1970/i);
    // The old cookie no longer works even if someone kept a copy.
    expect((await me(meRequest(cookie))).status).toBe(401);
  });

  it("rate-limits repeated attempts on one account", async () => {
    const statuses: number[] = [];
    for (let i = 0; i < 11; i++) {
      const res = await login(
        jsonRequest("/api/auth/login", { email: "target@example.com", password: "guess " + i }, { ip: `198.51.100.${i}` }),
      );
      statuses.push(res.status);
    }
    expect(statuses.slice(0, 10).every((s) => s === 401)).toBe(true);
    expect(statuses[10]).toBe(429);
  });

  it("rejects cross-site logout", async () => {
    expect((await logout(jsonRequest("/api/auth/logout", {}, { origin: "https://evil.example" }))).status).toBe(403);
  });
});

describe("POST /api/auth/forgot-password", () => {
  it("responds identically for known and unknown emails", async () => {
    await register(jsonRequest("/api/auth/register", validRegistration));
    const known = await forgot(jsonRequest("/api/auth/forgot-password", { email: "asha@example.com" }));
    const unknown = await forgot(jsonRequest("/api/auth/forgot-password", { email: "ghost@example.com" }));
    expect(known.status).toBe(200);
    expect(unknown.status).toBe(200);
    expect(await known.json()).toEqual(await unknown.json());
  });
});
