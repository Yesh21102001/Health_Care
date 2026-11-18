import type { NextRequest } from "next/server";
import { SESSION_COOKIE, clearSessionCookie } from "@/lib/auth/cookie";
import { errorResponse, isSameOrigin, jsonResponse } from "@/lib/http";
import { logger } from "@/lib/logger";
import { revokeSession } from "@/services/session-service";

export async function POST(req: NextRequest) {
  // Origin check stops other sites from logging users out.
  if (!isSameOrigin(req)) return errorResponse(403, "Request origin not allowed.");

  const res = jsonResponse({ ok: true });
  try {
    await revokeSession(req.cookies.get(SESSION_COOKIE)?.value);
  } catch (err) {
    // Still clear the cookie so the browser is signed out; the DB session expires on its own.
    logger.error("auth.logout.failed", err);
  }
  clearSessionCookie(res);
  return res;
}
