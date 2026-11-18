import { NextRequest } from "next/server";
import { User } from "@/models/User";
import { Session } from "@/models/Session";
import { PasswordResetToken } from "@/models/PasswordResetToken";
import { RateLimit } from "@/models/RateLimit";
import { connectToDatabase } from "@/lib/mongodb";

export const ORIGIN = "http://localhost:3000";

export const validRegistration = {
  name: "Asha Rao",
  email: "asha@example.com",
  password: "correct horse battery",
  confirmPassword: "correct horse battery",
  consent: true as const,
};

/** Builds a request like the browser would send to our API. */
export function jsonRequest(
  path: string,
  body: unknown,
  opts: { origin?: string | null; cookie?: string; contentType?: string; ip?: string } = {},
): NextRequest {
  const headers = new Headers({ "content-type": opts.contentType ?? "application/json" });
  if (opts.origin !== null) headers.set("origin", opts.origin ?? ORIGIN);
  if (opts.cookie) headers.set("cookie", opts.cookie);
  headers.set("x-forwarded-for", opts.ip ?? "203.0.113.10");
  return new NextRequest(`${ORIGIN}${path}`, {
    method: "POST",
    headers,
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

/** Extracts "name=value" from a Set-Cookie header so it can be sent back. */
export function cookieFrom(res: Response): string {
  const setCookie = res.headers.get("set-cookie") ?? "";
  return setCookie.split(";")[0] ?? "";
}

/** Ensures indexes (unique email, TTL) exist before tests rely on them. */
export async function ensureIndexes() {
  await connectToDatabase();
  await Promise.all([User.syncIndexes(), Session.syncIndexes(), PasswordResetToken.syncIndexes(), RateLimit.syncIndexes()]);
}
