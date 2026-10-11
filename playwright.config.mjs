import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests/browser", timeout: 30000, use: {baseURL: "http://127.0.0.1:8129", headless: true},
  webServer: {command: "python scripts/serve_demo.py", url: "http://127.0.0.1:8129/tests/browser/demo.html", reuseExistingServer: !process.env.CI}
});
