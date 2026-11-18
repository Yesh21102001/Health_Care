import type { NextRequest } from "next/server";
import { setSessionCookie } from "@/lib/auth/cookie";
import { clientIp, errorResponse, jsonResponse, readJsonBody, tooManyRequests } from "@/lib/http";
import { logger } from "@/lib/logger";
import { rateLimit } from "@/lib/rate-limit";
import { fieldErrors, registerSchema } from "@/lib/validations";
import { EmailTakenError, registerUser } from "@/services/auth-service";
import { createSession } from "@/services/session-service";

export async function POST(req: NextRequest) {
  const parsed = await readJsonBody(req);
  if (!parsed.ok) return parsed.response;

  try {
    const limit = await rateLimit("register:ip", clientIp(req), 10, 60 * 60);
    if (!limit.ok) return tooManyRequests(limit.retryAfterSeconds);

    const result = registerSchema.safeParse(parsed.body);
    if (!result.success) {
      return errorResponse(400, "Please fix the highlighted fields.", { fieldErrors: fieldErrors(result.error) });
    }

    const user = await registerUser(result.data);
    const session = await createSession(user.id, req.headers.get("user-agent"));
    logger.info("auth.register", { userId: user.id });

    const res = jsonResponse({ user }, 201);
    setSessionCookie(res, session.token, session.expiresAt);
    return res;
  } catch (err) {
    if (err instanceof EmailTakenError) {
      return errorResponse(409, err.message, { fieldErrors: { email: err.message } });
    }
    logger.error("auth.register.failed", err);
    return errorResponse(500, "Something went wrong. Please try again.");
  }
}
