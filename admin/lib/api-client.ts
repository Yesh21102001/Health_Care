/** Browser-side helper for calling the API (same origin; proxied to the Python backend). */
export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; error: string; fieldErrors?: Record<string, string> };

export async function apiRequest<T>(method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE", url: string, body?: unknown): Promise<ApiResult<T>> {
  let res: Response;
  try {
    res = await fetch(url, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    return { ok: false, status: 0, error: "Can't reach the server. Check your connection and try again." };
  }

  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    // Non-JSON response (e.g. a proxy error page when the backend is down).
  }

  if (res.ok) return { ok: true, data: data as T };
  const payload = (data ?? {}) as { error?: string; fieldErrors?: Record<string, string> };
  const fallback =
    res.status >= 500 && !payload.error
      ? "The HealthAI server isn't responding. Please try again shortly."
      : "Something went wrong. Please try again.";
  return { ok: false, status: res.status, error: payload.error ?? fallback, fieldErrors: payload.fieldErrors };
}

export function postJson<T>(url: string, body: unknown): Promise<ApiResult<T>> {
  return apiRequest<T>("POST", url, body);
}
