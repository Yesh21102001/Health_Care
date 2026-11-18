import { connection, type NextRequest } from "next/server";
import { SESSION_COOKIE } from "@/lib/auth/cookie";
import { errorResponse, jsonResponse } from "@/lib/http";
import { logger } from "@/lib/logger";
import { getUserBySessionToken } from "@/services/session-service";

export async function GET(req: NextRequest) {
  // Per-user response: must never be prerendered or cached at build time.
  await connection();
  try {
    const user = await getUserBySessionToken(req.cookies.get(SESSION_COOKIE)?.value);
    if (!user) return errorResponse(401, "Not signed in.");
    return jsonResponse({ user });
  } catch (err) {
    logger.error("auth.me.failed", err);
    return errorResponse(500, "Something went wrong.");
  }
}
