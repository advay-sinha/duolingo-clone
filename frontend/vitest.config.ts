/**
 * Vitest, for component tests only.
 *
 * The project runs two test runners on purpose, split by file extension:
 *
 *   *.test.ts   -> node --test    pure logic, no DOM, no dependencies
 *   *.test.tsx  -> vitest + jsdom components, which Node cannot load at all
 *
 * That is not indecision. Node's built-in runner cannot parse JSX, so component
 * tests genuinely need a bundler-backed runner; but the ~90 pure-logic tests
 * already run in milliseconds with zero dependencies, and moving them would add
 * cost for no benefit. The `include` below keeps the two from overlapping.
 */

import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Mirrors the `@/*` path alias in tsconfig.json.
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    include: ["**/*.test.tsx"],
    setupFiles: ["./vitest.setup.ts"],
  },
});
