import "server-only";
import { connectToDatabase } from "@/lib/mongodb";
import { getDummyHash, hashPassword, verifyPassword } from "@/lib/password";
import { generateToken, hashToken } from "@/lib/tokens";
import type { RegisterInput } from "@/lib/validations";
import { PasswordResetToken } from "@/models/PasswordResetToken";
import { CURRENT_TERMS_VERSION, User } from "@/models/User";
import { revokeAllSessions } from "@/services/session-service";
import type { PublicUser } from "@/types/auth";

export const RESET_TOKEN_TTL_SECONDS = 60 * 30; // 30 minutes

export class EmailTakenError extends Error {
  constructor() {
    super("An account with this email already exists.");
    this.name = "EmailTakenError";
  }
}

function toPublicUser(u: { _id: unknown; name: string; email: string; role: PublicUser["role"] }): PublicUser {
  return { id: String(u._id), name: u.name, email: u.email, role: u.role };
}

/** Creates a user. Input must already be validated with registerSchema. */
export async function registerUser(input: RegisterInput): Promise<PublicUser> {
  await connectToDatabase();
  const passwordHash = await hashPassword(input.password);
  try {
    const user = await User.create({
      name: input.name,
      email: input.email,
      passwordHash,
      role: "user", // never taken from input: nobody can self-register as admin
      consent: { termsAcceptedAt: new Date(), termsVersion: CURRENT_TERMS_VERSION, ageConfirmed: true },
    });
    return toPublicUser(user);
  } catch (err) {
    // Unique index on email; relying on it (not a prior lookup) avoids race conditions.
    if ((err as { code?: number }).code === 11000) throw new EmailTakenError();
    throw err;
  }
}

/** Returns the user if the email/password pair is correct, otherwise null. */
export async function authenticate(email: string, password: string): Promise<PublicUser | null> {
  await connectToDatabase();
  const user = await User.findOne({ email }).select("+passwordHash").lean();
  if (!user) {
    await verifyPassword(password, await getDummyHash()); // equalise timing
    return null;
  }
  const ok = await verifyPassword(password, user.passwordHash);
  return ok ? toPublicUser(user) : null;
}

/**
 * Creates a single-use reset token for the account, if it exists.
 * Returns null for unknown emails; callers must respond identically either way.
 */
export async function createPasswordResetToken(email: string): Promise<{ token: string; name: string } | null> {
  await connectToDatabase();
  const user = await User.findOne({ email }).lean();
  if (!user) return null;
  // Only the newest link should work.
  await PasswordResetToken.deleteMany({ userId: user._id });
  const token = generateToken();
  await PasswordResetToken.create({
    tokenHash: hashToken(token),
    userId: user._id,
    expiresAt: new Date(Date.now() + RESET_TOKEN_TTL_SECONDS * 1000),
  });
  return { token, name: user.name };
}

/** Sets a new password using a reset token. Returns false if the token is invalid, used or expired. */
export async function resetPassword(token: string, newPassword: string): Promise<boolean> {
  await connectToDatabase();
  // findOneAndDelete makes the token single-use even under concurrent requests.
  const record = await PasswordResetToken.findOneAndDelete({
    tokenHash: hashToken(token),
    expiresAt: { $gt: new Date() },
  }).lean();
  if (!record) return false;

  const passwordHash = await hashPassword(newPassword);
  const updated = await User.updateOne({ _id: record.userId }, { $set: { passwordHash, passwordChangedAt: new Date() } });
  if (updated.matchedCount === 0) return false;

  // Sign out everywhere: whoever had the old password loses access.
  await revokeAllSessions(String(record.userId));
  return true;
}
