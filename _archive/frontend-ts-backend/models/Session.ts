import { Schema, model, models, type InferSchemaType, type Model } from "mongoose";

const sessionSchema = new Schema(
  {
    // SHA-256 of the cookie token. The raw token is never stored.
    tokenHash: { type: String, required: true },
    userId: { type: Schema.Types.ObjectId, ref: "User", required: true },
    expiresAt: { type: Date, required: true },
    userAgent: { type: String, maxlength: 256 },
  },
  { timestamps: { createdAt: true, updatedAt: false } },
);

sessionSchema.index({ tokenHash: 1 }, { unique: true });
sessionSchema.index({ userId: 1 });
// MongoDB deletes expired sessions automatically (checked roughly every 60s).
sessionSchema.index({ expiresAt: 1 }, { expireAfterSeconds: 0 });

export type SessionDoc = InferSchemaType<typeof sessionSchema>;

export const Session: Model<SessionDoc> =
  (models.Session as Model<SessionDoc>) ?? model<SessionDoc>("Session", sessionSchema);
