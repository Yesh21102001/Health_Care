import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const root = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  resolve: {
    alias: [
      { find: /^@\//, replacement: `${root}/` },
      // "server-only" throws outside Next's server bundler; it's a no-op in tests.
      { find: /^server-only$/, replacement: `${root}/tests/stubs/server-only.ts` },
    ],
  },
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
    globalSetup: ["tests/global-setup.ts"],
    setupFiles: ["tests/setup.ts"],
    // Tests share one in-memory database, so run files one at a time.
    fileParallelism: false,
    testTimeout: 30_000,
    hookTimeout: 180_000, // first run downloads a MongoDB binary
  },
});
