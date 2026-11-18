import { NextResponse, type NextRequest } from "next/server";

/*
 * Optimistic check: no session cookie -> /login. The backend enforces the
 * admin role on every API call; this only avoids rendering pages for nobody.
 */
const SESSION_COOKIES = ["__Host-healthai_session", "healthai_session"];

export function proxy(request: NextRequest) {
  if (SESSION_COOKIES.some((n) => request.cookies.has(n))) return NextResponse.next();
  return NextResponse.redirect(new URL("/login", request.url));
}

export const config = {
  // Everything except the login page, API proxy, and static assets.
  matcher: ["/((?!login|api|_next|favicon.ico).*)"],
};
