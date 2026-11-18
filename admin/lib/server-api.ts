import "server-only";
import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { cache } from "react";

/*
 * Server-side calls from the admin app to the Python backend, forwarding the
 * browser's cookies. The backend checks role=admin on every /api/admin request;
 * this app's checks are only for a friendly UI.
 * Reads cookies, so callers must render inside <Suspense>.
 */

export type AdminIdentity = { id: string; name: string; email: string; role: "user" | "admin" };

export function backendUrl(): string {
  return (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/+$/, "");
}

export async function backendGet<T>(path: string): Promise<T> {
  const cookieHeader = (await cookies()).toString();
  let res: Response;
  try {
    res = await fetch(`${backendUrl()}${path}`, { headers: { cookie: cookieHeader }, cache: "no-store" });
  } catch {
    throw new Error("The HealthAI API can't be reached.");
  }
  if (res.status === 401) redirect("/login");
  if (res.status === 403) redirect("/login?denied=1");
  if (res.status === 404) notFound();
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return (await res.json()) as T;
}

/** The signed-in admin, or redirect to /login. */
export const requireAdmin = cache(async (): Promise<AdminIdentity> => {
  const { user } = await backendGet<{ user: AdminIdentity }>("/api/auth/me");
  if (user.role !== "admin") redirect("/login?denied=1");
  return user;
});
