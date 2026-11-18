import "server-only";
import { createHash, randomBytes } from "node:crypto";

/** 256-bit random token, URL-safe. Given to the user (cookie or link), never stored. */
export function generateToken(): string {
  return randomBytes(32).toString("base64url");
}

/** What we store instead of the token, so a database leak can't be replayed as sessions or reset links. */
export function hashToken(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}
