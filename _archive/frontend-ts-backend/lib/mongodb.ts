import "server-only";
import mongoose from "mongoose";
import { requireEnv } from "@/lib/env";

/*
 * Reuses one connection per server instance. In development, Next.js reloads
 * modules on every change, so the connection promise is kept on globalThis to
 * avoid opening a new connection pool on each reload.
 */
type MongooseCache = { promise: Promise<typeof mongoose> | null };

const globalForMongoose = globalThis as unknown as { __mongoose?: MongooseCache };
const cache: MongooseCache = globalForMongoose.__mongoose ?? { promise: null };
globalForMongoose.__mongoose = cache;

export async function connectToDatabase(): Promise<typeof mongoose> {
  if (!cache.promise) {
    cache.promise = mongoose
      .connect(requireEnv("MONGODB_URI"), {
        // Fail fast instead of queueing queries while disconnected.
        bufferCommands: false,
        serverSelectionTimeoutMS: 10_000,
      })
      .catch((err) => {
        // Allow the next request to retry instead of caching the failure forever.
        cache.promise = null;
        throw err;
      });
  }
  return cache.promise;
}
