// Reaching into the throwaway e2e database (e2e/start-api.sh), for what a
// browser can't do: a worker checking in. Never real data.
import { execFileSync } from "node:child_process";
import path from "node:path";

const BACKEND = path.resolve(__dirname, "../../backend");

/** A worker checking in (both language lines up), as clinic_agent/heartbeat.py does; `ageSeconds`
 *  back-dates it (an old beat = a worker that stopped). */
export function heartbeat(ageSeconds = 0) {
  execFileSync("uv", ["run", "python", "-c", [
    "from datetime import timedelta",
    "from clinic_agent.store import repo",
    "from clinic_agent.store.db import sessions_for",
    "from clinic_agent.store.models import utc_now",
    "with sessions_for('sqlite:///data/e2e.db')() as s:",
    `    repo.beat(s, 'AW_e2e', 'e2e', ['en', 'hi'], utc_now() - timedelta(seconds=${Number(ageSeconds)}))`,
  ].join("\n")], { cwd: BACKEND, stdio: "pipe" });
}

/** A finished staff test call that booked "Test Patient" tomorrow at `hour`,
 *  as a real one would. Returns its call id. */
export function testCallThatBooked(hour = 11): number {
  const out = execFileSync("uv", ["run", "python", "-c", [
    "from datetime import datetime, time, timedelta",
    "from clinic_agent.context import clinic_now",
    "from clinic_agent.store import repo",
    "from clinic_agent.store.db import sessions_for",
    "from clinic_agent.store.models import utc_now",
    "with sessions_for('sqlite:///data/e2e.db')() as s:",
    "    clinic = repo.list_clinics(s)[0]",
    "    day = clinic_now(clinic.timezone).date() + timedelta(days=1)",
    `    appt = repo.book(s, clinic.id, clinic.doctors[0].id, datetime.combine(day, time(${Number(hour)})), 'Test Patient', '9000000099')`,
    "    started = utc_now() - timedelta(minutes=5)",
    "    c = repo.start_call(s, clinic.id, 'test-e2e', 'stack', 'en', started, True)",
    "    repo.finish_call(s, c.id, ended_at=started + timedelta(minutes=2), end_reason='agent_ended', outcome='booked',",
    "                     turn_count=2, error_count=0, appointments=[{'id': appt.id, 'action': 'booked'}], events=[],",
    "                     transcript=[{'t_ms': 0, 'role': 'caller', 'text': 'Book me tomorrow at 11'}],",
    "                     purge_after=started + timedelta(days=30))",
    "    print(c.id)",
  ].join("\n")], { cwd: BACKEND, stdio: ["ignore", "pipe", "pipe"] });
  return Number(String(out).trim());
}
