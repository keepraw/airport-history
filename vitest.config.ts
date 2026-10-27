import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    // Explicit research downloads under work/ may contain other projects' tests.
    include: ["test/**/*.test.ts"],
  },
});
