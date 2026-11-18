import { describe, expect, it } from "vitest";
import { safeRedirectPath } from "@/lib/auth/redirect";
import { hashPassword, verifyPassword } from "@/lib/password";
import { generateToken, hashToken } from "@/lib/tokens";
import { loginSchema, registerSchema } from "@/lib/validations";
import { validRegistration } from "./helpers";

describe("password hashing", () => {
  it("verifies the right password and rejects a wrong one", async () => {
    const hash = await hashPassword("s3cret-passphrase");
    expect(hash.startsWith("scrypt$")).toBe(true);
    expect(hash).not.toContain("s3cret-passphrase");
    expect(await verifyPassword("s3cret-passphrase", hash)).toBe(true);
    expect(await verifyPassword("wrong-passphrase", hash)).toBe(false);
  });

  it("uses a unique salt per hash", async () => {
    expect(await hashPassword("same")).not.toBe(await hashPassword("same"));
  });

  it("rejects malformed stored hashes instead of throwing", async () => {
    expect(await verifyPassword("x", "not-a-hash")).toBe(false);
  });
});

describe("tokens", () => {
  it("are random and stored only as a hash", () => {
    const a = generateToken();
    expect(a).not.toBe(generateToken());
    expect(a.length).toBeGreaterThanOrEqual(43);
    expect(hashToken(a)).toMatch(/^[0-9a-f]{64}$/);
  });
});

describe("registerSchema", () => {
  it("accepts valid input and normalises the email", () => {
    const r = registerSchema.safeParse({ ...validRegistration, email: "  Asha@Example.COM " });
    expect(r.success && r.data.email).toBe("asha@example.com");
  });

  it.each([
    ["short password", { password: "short", confirmPassword: "short" }, "password"],
    ["mismatched passwords", { confirmPassword: "something else" }, "confirmPassword"],
    ["missing consent", { consent: false }, "consent"],
    ["invalid email", { email: "not-an-email" }, "email"],
    ["one-letter name", { name: "A" }, "name"],
  ])("rejects %s", (_label, override, field) => {
    const r = registerSchema.safeParse({ ...validRegistration, ...override });
    expect(r.success).toBe(false);
    expect(r.error?.issues.some((i) => i.path[0] === field)).toBe(true);
  });

  it("ignores attempts to set a role", () => {
    const r = registerSchema.safeParse({ ...validRegistration, role: "admin" });
    expect(r.success && "role" in r.data).toBe(false);
  });
});

describe("loginSchema", () => {
  it("rejects oversized passwords", () => {
    expect(loginSchema.safeParse({ email: "a@b.co", password: "x".repeat(129) }).success).toBe(false);
  });
});

describe("safeRedirectPath", () => {
  it.each([
    ["/chat", "/chat"],
    [null, "/dashboard"],
    ["https://evil.example", "/dashboard"],
    ["//evil.example", "/dashboard"],
    ["/\\evil.example", "/dashboard"],
  ])("%s -> %s", (input, expected) => {
    expect(safeRedirectPath(input)).toBe(expected);
  });
});
