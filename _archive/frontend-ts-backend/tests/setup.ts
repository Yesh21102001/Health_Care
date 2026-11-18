import mongoose from "mongoose";
import { afterAll, beforeEach, inject, vi } from "vitest";

// connection() needs a live Next.js request; handlers are called directly in tests.
vi.mock("next/server", async (importOriginal) => ({
  ...(await importOriginal<typeof import("next/server")>()),
  connection: async () => {},
}));

process.env.MONGODB_URI = inject("mongoUri");
process.env.NEXT_PUBLIC_SITE_URL = "http://localhost:3000";

// Start every test from an empty database (indexes are kept).
beforeEach(async () => {
  if (mongoose.connection.readyState !== 1) return;
  const collections = await mongoose.connection.db!.collections();
  await Promise.all(collections.map((c) => c.deleteMany({})));
});

afterAll(async () => {
  await mongoose.disconnect();
});
