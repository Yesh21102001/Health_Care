import { Schema, model, models, type InferSchemaType, type Model } from "mongoose";

export const ROLES = ["user", "admin"] as const;
export type Role = (typeof ROLES)[number];

/** Bump when the Terms/Privacy text changes materially, so we can ask users to re-accept. */
export const CURRENT_TERMS_VERSION = "2026-11-18";

const userSchema = new Schema(
  {
    name: { type: String, required: true, trim: true, minlength: 2, maxlength: 80 },
    email: { type: String, required: true, trim: true, lowercase: true, maxlength: 254 },
    // select:false keeps the hash out of every query unless explicitly requested.
    passwordHash: { type: String, required: true, select: false },
    role: { type: String, enum: ROLES, default: "user", required: true },
    consent: {
      termsAcceptedAt: { type: Date, required: true },
      termsVersion: { type: String, required: true },
      ageConfirmed: { type: Boolean, required: true },
    },
    passwordChangedAt: { type: Date },
  },
  { timestamps: true, strict: "throw" },
);

userSchema.index({ email: 1 }, { unique: true });

export type UserDoc = InferSchemaType<typeof userSchema>;

export const User: Model<UserDoc> = (models.User as Model<UserDoc>) ?? model<UserDoc>("User", userSchema);
