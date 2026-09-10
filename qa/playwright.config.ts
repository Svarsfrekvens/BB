import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";

// I sandlådan finns Chromium redan installerad; använd den om Playwrights egen
// nedladdning saknas. I CI lämnas sökvägen tom och Playwright hämtar själv.
const lokalChromium = process.env.CHROMIUM_PATH ?? "/opt/ms-playwright/chromium-1194/chrome-linux/chrome";
const executablePath = existsSync(lokalChromium) ? lokalChromium : undefined;

export default defineConfig({
  testDir: "e2e",
  timeout: 420_000,
  use: { baseURL: "http://127.0.0.1:8080", headless: true, launchOptions: { executablePath } },
  webServer: {
    command: "npx vite dev --port 8080 --host 127.0.0.1",
    url: "http://127.0.0.1:8080",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
