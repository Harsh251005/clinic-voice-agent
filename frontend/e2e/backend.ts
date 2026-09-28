// Reaching into the throwaway e2e database (e2e/start-api.sh), for what a
// browser can't do: a worker checking in. Never real data.
import { execFileSync } from "node:child_process";
import path from "node:path";

const BACKEND = path.resolve(__dirname, "../../backend");

/** A worker checking in, as clinic_agent/heartbeat.py does; `ageSeconds`
 *  back-dates it (an old beat = a worker that stopped). */
export function heartbeat(ageSeconds = 0) {
  execFileSync("uv", ["run", "python", "-c", [
    "from datetime import timedelta",
    "from clinic_agent.store import repo",
    "from clinic_agent.store.db import sessions_for",
    "from clinic_agent.store.models import utc_now",
    "with sessions_for('sqlite:///data/e2e.db')() as s:",
    `    repo.beat(s, 'AW_e2e', 'e2e', utc_now() - timedelta(seconds=${Number(ageSeconds)}))`,
  ].join("\n")], { cwd: BACKEND, stdio: "pipe" });
}
