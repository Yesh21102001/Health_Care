import "server-only";
import { connectToDatabase } from "@/lib/mongodb";
import { hashToken } from "@/lib/tokens";
import { RateLimit } from "@/models/RateLimit";

export type RateLimitResult = { ok: boolean; remaining: number; retryAfterSeconds: number };

/**
 * Fixed-window rate limiter backed by MongoDB, so limits hold across all
 * serverless instances. Identifiers (IPs, emails) are hashed before storage.
 *
 * @param scope   what is being limited, e.g. "login:ip"
 * @param id      who is being limited, e.g. an IP address or email
 * @param limit   max requests per window
 * @param windowSeconds window length
 */
export async function rateLimit(
  scope: string,
  id: string,
  limit: number,
  windowSeconds: number,
): Promise<RateLimitResult> {
  await connectToDatabase();
  const windowMs = windowSeconds * 1000;
  const windowIndex = Math.floor(Date.now() / windowMs);
  const key = `${scope}:${hashToken(id)}:${windowIndex}`;
  const expiresAt = new Date((windowIndex + 1) * windowMs);

  const increment = () =>
    RateLimit.findOneAndUpdate(
      { key },
      { $inc: { count: 1 }, $setOnInsert: { expiresAt } },
      { upsert: true, returnDocument: "after" },
    ).lean();

  let doc;
  try {
    doc = await increment();
  } catch (err) {
    // Two simultaneous first requests can race on the upsert; the retry then updates.
    if ((err as { code?: number }).code === 11000) doc = await increment();
    else throw err;
  }

  const count = doc?.count ?? 1;
  return {
    ok: count <= limit,
    remaining: Math.max(0, limit - count),
    retryAfterSeconds: Math.max(1, Math.ceil((expiresAt.getTime() - Date.now()) / 1000)),
  };
}
