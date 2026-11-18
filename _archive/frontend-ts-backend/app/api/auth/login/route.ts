import type { NextRequest } from "next/server";
import { setSessionCookie } from "@/lib/auth/cookie";
import { clientIp, errorResponse, jsonResponse, readJsonBody, tooManyRequests } from "@/lib/http";
import { logger } from "@/lib/logger";
import { rateLimit } from "@/lib/rate-limit";
import { fieldErrors, loginSchema } from "@/lib/validations";
import { authenticate } from "@/services/auth-service";
import { createSession } from "@/services/session-service";

const WINDOW = 15 * 60; // 15 minutes

export async function POST(req: NextRequest) {
  const parsed = await readJsonBody(req);
  if (!parsed.ok) return parsed.response;

  try {
    const result = loginSchema.safeParse(parsed.body);
    if (!result.success) {
      return errorResponse(400, "Please fix the highlighted fields.", { fieldErrors: fieldErrors(result.error) });
    }
    const { email, password } = result.data;

    // Two limits: per IP (one attacker, many accounts) and per account (many IPs, one account).
    const [byIp, byEmail] = await Promise.all([
      rateLimit("login:ip", clientIp(req), 30, WINDOW),
      rateLimit("login:email", email, 10, WINDOW),
    ]);
    if (!byIp.ok || !byEmail.ok) {
      return tooManyRequests(Math.max(byIp.retryAfterSeconds, byEmail.retryAfterSeconds));
    }

    const user = await authenticate(email, password);
    if (!user) {
      // Same message for unknown email and wrong password.
      return errorResponse(401, "Incorrect email or password.");
    }

    const session = await createSession(user.id, req.headers.get("user-agent"));
    logger.info("auth.login", { userId: user.id });

    const res = jsonResponse({ user });
    setSessionCookie(res, session.token, session.expiresAt);
    return res;
  } catch (err) {
    logger.error("auth.login.failed", err);
    return errorResponse(500, "Something went wrong. Please try again.");
  }
}
