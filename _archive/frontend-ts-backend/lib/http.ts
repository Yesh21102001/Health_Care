import "server-only";
import { NextResponse, type NextRequest } from "next/server";
import { appUrl } from "@/lib/env";

const NO_STORE = { "Cache-Control": "no-store" };

export function jsonResponse(data: unknown, status = 200, headers: Record<string, string> = {}): NextResponse {
  return NextResponse.json(data, { status, headers: { ...NO_STORE, ...headers } });
}

export function errorResponse(
  status: number,
  message: string,
  extra: { fieldErrors?: Record<string, string>; headers?: Record<string, string> } = {},
): NextResponse {
  return jsonResponse(
    { error: message, ...(extra.fieldErrors ? { fieldErrors: extra.fieldErrors } : {}) },
    status,
    extra.headers,
  );
}

/**
 * CSRF protection (second layer after SameSite cookies): state-changing
 * requests must come from our own origin. Browsers always send Origin on
 * cross-origin and same-origin POST/PUT/DELETE fetches.
 */
export function isSameOrigin(req: NextRequest): boolean {
  const origin = req.headers.get("origin");
  if (!origin) return false;
  let originHost: string;
  try {
    originHost = new URL(origin).host;
  } catch {
    return false;
  }
  const allowed = new Set<string>([new URL(appUrl()).host]);
  const host = req.headers.get("x-forwarded-host") ?? req.headers.get("host");
  if (host) allowed.add(host);
  return allowed.has(originHost);
}

/** Best-effort client IP. On Vercel, x-forwarded-for is set by the platform. */
export function clientIp(req: NextRequest): string {
  const forwarded = req.headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0]!.trim();
  return req.headers.get("x-real-ip") ?? "unknown";
}

const MAX_BODY_BYTES = 16 * 1024;

/**
 * Checks origin + content type and parses a small JSON body.
 * Returns either the parsed body or a ready-to-return error response.
 */
export async function readJsonBody(
  req: NextRequest,
): Promise<{ ok: true; body: unknown } | { ok: false; response: NextResponse }> {
  if (!isSameOrigin(req)) {
    return { ok: false, response: errorResponse(403, "Request origin not allowed.") };
  }
  if (!req.headers.get("content-type")?.toLowerCase().startsWith("application/json")) {
    return { ok: false, response: errorResponse(415, "Expected application/json.") };
  }
  const declared = Number(req.headers.get("content-length") ?? "0");
  if (declared > MAX_BODY_BYTES) {
    return { ok: false, response: errorResponse(413, "Request body too large.") };
  }
  const text = await req.text();
  if (text.length > MAX_BODY_BYTES) {
    return { ok: false, response: errorResponse(413, "Request body too large.") };
  }
  try {
    return { ok: true, body: JSON.parse(text) };
  } catch {
    return { ok: false, response: errorResponse(400, "Invalid JSON.") };
  }
}

export function tooManyRequests(retryAfterSeconds: number): NextResponse {
  return errorResponse(429, "Too many attempts. Please wait and try again.", {
    headers: { "Retry-After": String(retryAfterSeconds) },
  });
}
