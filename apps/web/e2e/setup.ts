import { execFileSync } from "node:child_process";
import path from "node:path";
export default function setup() {
  const root = path.resolve(__dirname, "../../..");
  const python = path.join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
  execFileSync(python, ["-c", "from ai_team.config import Settings; from ai_team.db import Database; from ai_team.auth import create_owner; db=Database(Settings()); db.initialize(); session=db.session(); s=session.__enter__(); create_owner(s, 'e2e', 'somente-teste-e2e-8493'); session.__exit__(None,None,None)"], {
    cwd: root, env: { ...process.env, AI_TEAM_DATABASE_URL: process.env.AI_TEAM_E2E_DB, AI_TEAM_ENVIRONMENT: "test" },
  });
}
