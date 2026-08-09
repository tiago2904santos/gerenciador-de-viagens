import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["static/js/**/*.test.js"],
    clearMocks: true,
    restoreMocks: true,
    coverage: {
      provider: "v8",
      all: true,
      include: [
        "static/js/core/http.js",
        "static/js/core/app.js",
        "static/js/components/masks.js",
        "static/js/components/collection.js",
      ],
      reporter: ["text", "json-summary"],
      reportsDirectory: "coverage-js",
    },
  },
});
