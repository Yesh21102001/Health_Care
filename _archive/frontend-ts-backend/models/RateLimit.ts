import { Schema, model, models, type InferSchemaType, type Model } from "mongoose";

/** One document per (key, time window). Shared by all server instances, unlike in-memory counters. */
const rateLimitSchema = new Schema({
  key: { type: String, required: true },
  count: { type: Number, required: true, default: 0 },
  expiresAt: { type: Date, required: true },
});

rateLimitSchema.index({ key: 1 }, { unique: true });
rateLimitSchema.index({ expiresAt: 1 }, { expireAfterSeconds: 0 });

export type RateLimitDoc = InferSchemaType<typeof rateLimitSchema>;

export const RateLimit: Model<RateLimitDoc> =
  (models.RateLimit as Model<RateLimitDoc>) ?? model<RateLimitDoc>("RateLimit", rateLimitSchema);
