import type { NextRequest } from "next/server";
import { clearSessionCookie } from "@/lib/auth/cookie";
import { clientIp, errorResponse, jsonResponse, readJsonBody, tooManyRequests } from "@/lib/http";
import { logger } from "@/lib/logger";
import { rateLimit } from "@/lib/rate-limit";
import { fieldErrors, resetPasswordSchema } from "@/lib/validations";
import { resetPassword } from "@/services/auth-service";

export async function POST(req: NextRequest) {
  const parsed = await readJsonBody(req);
  if (!parsed.ok) return parsed.response;

  try {
    const limit = await rateLimit("reset:ip", clientIp(req), 20, 60 * 60);
    if (!limit.ok) return tooManyRequests(limit.retryAfterSeconds);

    const result = resetPasswordSchema.safeParse(parsed.body);
    if (!result.success) {
      const errors = fieldErrors(result.error);
      if (errors.token) return errorResponse(400, "This reset link is invalid or has expired.");
      return errorResponse(400, "Please fix the highlighted fields.", { fieldErrors: errors });
    }

    const ok = await resetPassword(result.data.token, result.data.password);
    if (!ok) return errorResponse(400, "This reset link is invalid or has expired.");

    logger.info("auth.password_reset");
    // All sessions were revoked; clear this browser's cookie too so the user signs in fresh.
    const res = jsonResponse({ ok: true });
    clearSessionCookie(res);
    return res;
  } catch (err) {
    logger.error("auth.reset.failed", err);
    return errorResponse(500, "Something went wrong. Please try again.");
  }
}
