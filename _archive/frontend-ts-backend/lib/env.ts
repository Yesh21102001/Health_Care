import "server-only";

/**
 * Reads a required server-side environment variable.
 * Throws a clear error at the point of use instead of failing mysteriously later.
 * Values are never logged.
 */
export function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value || value.trim() === "") {
    throw new Error(`Missing required environment variable: ${name}. See .env.example.`);
  }
  return value;
}

export const isProduction = process.env.NODE_ENV === "production";

/** Public base URL of the app, used to build links such as password-reset URLs. */
export function appUrl(): string {
  return (process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000").replace(/\/+$/, "");
}
