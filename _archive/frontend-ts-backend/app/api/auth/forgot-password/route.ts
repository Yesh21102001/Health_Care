import type { NextRequest } from "next/server";
import { appUrl } from "@/lib/env";
import { clientIp, errorResponse, jsonResponse, readJsonBody, tooManyRequests } from "@/lib/http";
import { logger } from "@/lib/logger";
import { sendPasswordResetEmail } from "@/lib/mailer";
import { rateLimit } from "@/lib/rate-limit";
import { fieldErrors, forgotPasswordSchema } from "@/lib/validations";
import { createPasswordResetToken } from "@/services/auth-service";

// Identical response whether or not the email exists, so this can't be used to discover accounts.
const GENERIC_MESSAGE = "If an account exists for that email, we've sent a link to reset the password.";

export async function POST(req: NextRequest) {
  const parsed = await readJsonBody(req);
  if (!parsed.ok) return parsed.response;

  try {
    const result = forgotPasswordSchema.safeParse(parsed.body);
    if (!result.success) {
      return errorResponse(400, "Please fix the highlighted fields.", { fieldErrors: fieldErrors(result.error) });
    }
    const { email } = result.data;

    const [byIp, byEmail] = await Promise.all([
      rateLimit("forgot:ip", clientIp(req), 10, 60 * 60),
      rateLimit("forgot:email", email, 3, 60 * 60),
    ]);
    if (!byIp.ok || !byEmail.ok) {
      return tooManyRequests(Math.max(byIp.retryAfterSeconds, byEmail.retryAfterSeconds));
    }

    const reset = await createPasswordResetToken(email);
    if (reset) {
      const url = `${appUrl()}/reset-password?token=${encodeURIComponent(reset.token)}`;
      await sendPasswordResetEmail(email, reset.name, url);
    }
    return jsonResponse({ message: GENERIC_MESSAGE });
  } catch (err) {
    logger.error("auth.forgot.failed", err);
    return errorResponse(500, "Something went wrong. Please try again.");
  }
}
