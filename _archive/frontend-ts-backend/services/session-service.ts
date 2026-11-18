import "server-only";
import { Types } from "mongoose";
import { connectToDatabase } from "@/lib/mongodb";
import { generateToken, hashToken } from "@/lib/tokens";
import { Session } from "@/models/Session";
import { User } from "@/models/User";
import type { PublicUser } from "@/types/auth";

export const SESSION_TTL_SECONDS = 60 * 60 * 24 * 7; // 7 days

export async function createSession(
  userId: string,
  userAgent?: string | null,
): Promise<{ token: string; expiresAt: Date }> {
  await connectToDatabase();
  const token = generateToken();
  const expiresAt = new Date(Date.now() + SESSION_TTL_SECONDS * 1000);
  await Session.create({
    tokenHash: hashToken(token),
    userId: new Types.ObjectId(userId),
    expiresAt,
    userAgent: userAgent?.slice(0, 256),
  });
  return { token, expiresAt };
}

/** Returns the signed-in user for a session token, or null if missing/expired/revoked. */
export async function getUserBySessionToken(token: string | undefined | null): Promise<PublicUser | null> {
  if (!token || token.length > 200) return null;
  await connectToDatabase();
  // Check expiry explicitly: MongoDB's TTL cleanup can lag by up to a minute.
  const session = await Session.findOne({ tokenHash: hashToken(token), expiresAt: { $gt: new Date() } }).lean();
  if (!session) return null;
  const user = await User.findById(session.userId).lean();
  if (!user) return null;
  return { id: String(user._id), name: user.name, email: user.email, role: user.role };
}

export async function revokeSession(token: string | undefined | null): Promise<void> {
  if (!token) return;
  await connectToDatabase();
  await Session.deleteOne({ tokenHash: hashToken(token) });
}

export async function revokeAllSessions(userId: string): Promise<void> {
  await connectToDatabase();
  await Session.deleteMany({ userId: new Types.ObjectId(userId) });
}
