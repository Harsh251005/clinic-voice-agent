#!/usr/bin/env bash
# Starts (or restarts) the clinic app: API, receptionist worker, dashboard.
# Safe to run again after a code change: it stops the running copies first,
# so no old worker keeps answering calls with old code.

set -e

ROOT="$HOME/Code/clinic-voice-agent"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

if ! command -v xterm >/dev/null 2>&1; then
    echo "xterm is required. Install it with: sudo dnf install xterm"
    exit 1
fi

# Stop what an earlier run started: its three windows (titles below), then
# anything of this app's still running from its own folders. Nothing from
# other projects is touched.
pkill -f "xterm -T Clinic (API|Receptionist|Dashboard)" 2>/dev/null && echo "Closed the old windows." || true
stop_in() {
    local dir="$1" pattern="$2" pid
    for pid in $(pgrep -f "$pattern" 2>/dev/null); do
        [ "$(readlink "/proc/$pid/cwd" 2>/dev/null)" = "$dir" ] && kill "$pid" 2>/dev/null && echo "Stopped $pattern ($pid)"
    done
    return 0
}
sleep 1
stop_in "$BACKEND" "python -m api"
stop_in "$BACKEND" "main.py start"
stop_in "$FRONTEND" "next start|next-server"
sleep 2

echo "Branch: $(git -C "$ROOT" branch --show-current) ($(git -C "$ROOT" log -1 --format='%h %s'))"

# The API and worker refuse an old database schema: bring it up to date.
(cd "$BACKEND" && uv run python -m clinic_agent.store.migrations)

open_terminal() {
    local title="$1"
    local command="$2"

    xterm -T "$title" -e bash -lc \
        "$command; status=\$?; echo; echo \"Process exited with code \$status\"; exec bash" &
}

# Terminal 1: API
open_terminal "Clinic API :8080" \
    "cd '$BACKEND' && uv run python -m api"

# Terminal 2: Receptionist worker
open_terminal "Clinic Receptionist Worker" \
    "cd '$BACKEND' && uv run python main.py start"

# Terminal 3: Production dashboard
open_terminal "Clinic Dashboard :3000" \
    "cd '$FRONTEND' && npm run build && npm start"

echo "Opened all three service terminals."
echo "Dashboard: http://localhost:3000/admin"
