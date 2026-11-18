import { Schema, model, models, type InferSchemaType, type Model } from "mongoose";

const passwordResetTokenSchema = new Schema(
  {
    tokenHash: { type: String, required: true },
    userId: { type: Schema.Types.ObjectId, ref: "User", required: true },
    expiresAt: { type: Date, required: true },
  },
  { timestamps: { createdAt: true, updatedAt: false } },
);

passwordResetTokenSchema.index({ tokenHash: 1 }, { unique: true });
passwordResetTokenSchema.index({ userId: 1 });
passwordResetTokenSchema.index({ expiresAt: 1 }, { expireAfterSeconds: 0 });

export type PasswordResetTokenDoc = InferSchemaType<typeof passwordResetTokenSchema>;

export const PasswordResetToken: Model<PasswordResetTokenDoc> =
  (models.PasswordResetToken as Model<PasswordResetTokenDoc>) ??
  model<PasswordResetTokenDoc>("PasswordResetToken", passwordResetTokenSchema);
