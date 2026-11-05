import { defineConfig } from "@playwright/test";
import path from "node:path";

const root = path.resolve(__dirname, "../..");
const database = process.env.AI_TEAM_E2E_DB || `sqlite:///${path.join(root, ".data", `e2e-${Date.now()}.db`).replaceAll("\\", "/")}`;
const vault = path.join(root, ".data", `e2e-vault-${Date.now()}`);
process.env.AI_TEAM_E2E_DB = database;
const python = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
export default defineConfig({
  testDir: "./e2e", fullyParallel: false, workers: 1, retries: 0,
  globalSetup: "./e2e/setup.ts", reporter: "list",
  use: { baseURL: "http://localhost:3100", trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: [
    { command: `"${python}" -m uvicorn ai_team.main:app --host 127.0.0.1 --port 8100`, cwd: root,
      url: "http://127.0.0.1:8100/health", reuseExistingServer: false,
      env: { AI_TEAM_DATABASE_URL: database, AI_TEAM_MEMORY_VAULT: vault, AI_TEAM_PUBLIC_ORIGIN: "http://localhost:3100", AI_TEAM_ENVIRONMENT: "test" } },
    { command: "npm run dev -- --port 3100", url: "http://localhost:3100/login", reuseExistingServer: false,
      timeout: 120000, env: { AI_TEAM_API_URL: "http://127.0.0.1:8100", AI_TEAM_E2E: "1" } },
  ],
});
