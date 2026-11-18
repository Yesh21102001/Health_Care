import { beforeAll, describe, expect, it } from "vitest";
import { rateLimit } from "@/lib/rate-limit";
import { hashToken } from "@/lib/tokens";
import { PasswordResetToken } from "@/models/PasswordResetToken";
import { Session } from "@/models/Session";
import { User } from "@/models/User";
import {
  EmailTakenError,
  authenticate,
  createPasswordResetToken,
  registerUser,
  resetPassword,
} from "@/services/auth-service";
import { createSession, getUserBySessionToken, revokeSession } from "@/services/session-service";
import { ensureIndexes, validRegistration } from "./helpers";

beforeAll(ensureIndexes);

describe("registerUser", () => {
  it("creates a normal user with consent recorded and no hash exposed", async () => {
    const user = await registerUser(validRegistration);
    expect(user).toEqual({ id: expect.any(String), name: "Asha Rao", email: "asha@example.com", role: "user" });

    const stored = await User.findById(user.id).lean();
    expect(stored?.consent?.ageConfirmed).toBe(true);
    expect(stored?.consent?.termsAcceptedAt).toBeInstanceOf(Date);
    expect(stored).not.toHaveProperty("passwordHash"); // select:false
  });

  it("rejects a duplicate email regardless of case", async () => {
    await registerUser(validRegistration);
    // The model lowercases emails itself, as a second line of defence behind the zod schema.
    await expect(registerUser({ ...validRegistration, email: "ASHA@Example.com" })).rejects.toBeInstanceOf(
      EmailTakenError,
    );
  });
});

describe("authenticate", () => {
  it("accepts correct credentials and rejects wrong or unknown ones", async () => {
    await registerUser(validRegistration);
    expect(await authenticate("asha@example.com", validRegistration.password)).toMatchObject({ name: "Asha Rao" });
    expect(await authenticate("asha@example.com", "wrong password")).toBeNull();
    expect(await authenticate("nobody@example.com", "whatever")).toBeNull();
  });
});

describe("sessions", () => {
  it("resolves a valid token, and stores only its hash", async () => {
    const user = await registerUser(validRegistration);
    const { token } = await createSession(user.id, "vitest");
    expect(await getUserBySessionToken(token)).toMatchObject({ id: user.id });
    expect(await Session.findOne({ tokenHash: token })).toBeNull();
    expect(await Session.findOne({ tokenHash: hashToken(token) })).not.toBeNull();
  });

  it("rejects unknown, revoked and expired tokens", async () => {
    const user = await registerUser(validRegistration);
    expect(await getUserBySessionToken("made-up-token")).toBeNull();

    const a = await createSession(user.id);
    await revokeSession(a.token);
    expect(await getUserBySessionToken(a.token)).toBeNull();

    const b = await createSession(user.id);
    await Session.updateOne({ tokenHash: hashToken(b.token) }, { expiresAt: new Date(Date.now() - 1000) });
    expect(await getUserBySessionToken(b.token)).toBeNull();
  });
});

describe("password reset", () => {
  it("returns null for unknown emails", async () => {
    expect(await createPasswordResetToken("nobody@example.com")).toBeNull();
  });

  it("changes the password, is single-use, and signs out all sessions", async () => {
    const user = await registerUser(validRegistration);
    const session = await createSession(user.id);
    const reset = await createPasswordResetToken("asha@example.com");
    expect(reset).not.toBeNull();

    expect(await resetPassword(reset!.token, "a brand new password")).toBe(true);
    expect(await resetPassword(reset!.token, "another password!!")).toBe(false); // single use

    expect(await authenticate("asha@example.com", validRegistration.password)).toBeNull();
    expect(await authenticate("asha@example.com", "a brand new password")).not.toBeNull();
    expect(await getUserBySessionToken(session.token)).toBeNull();
  });

  it("only the newest link works, and expired links fail", async () => {
    await registerUser(validRegistration);
    const first = await createPasswordResetToken("asha@example.com");
    const second = await createPasswordResetToken("asha@example.com");
    expect(await resetPassword(first!.token, "new password one")).toBe(false);

    await PasswordResetToken.updateOne(
      { tokenHash: hashToken(second!.token) },
      { expiresAt: new Date(Date.now() - 1000) },
    );
    expect(await resetPassword(second!.token, "new password two")).toBe(false);
  });
});

describe("rateLimit", () => {
  it("allows up to the limit then blocks", async () => {
    const results = [];
    for (let i = 0; i < 4; i++) results.push(await rateLimit("test", "1.2.3.4", 3, 60));
    expect(results.map((r) => r.ok)).toEqual([true, true, true, false]);
    expect(results[3]!.retryAfterSeconds).toBeGreaterThan(0);
  });

  it("counts different identifiers separately", async () => {
    for (let i = 0; i < 3; i++) await rateLimit("test", "a", 3, 60);
    expect((await rateLimit("test", "b", 3, 60)).ok).toBe(true);
  });
});
