"""The worker checking in, so the dashboards know the receptionist is up.

Beats start when LiveKit registers the worker (connected, ready to be sent
calls), not when the process starts, and go on every BEAT_EVERY seconds.
A worker that crashes, hangs or loses LiveKit for good stops beating, and
clinic_agent/incidents.py raises "receptionist offline" after three missed
beats. The console doesn't beat: it answers no patients.
"""

from __future__ import annotations

import asyncio
import logging
import socket

from livekit.agents import AgentServer

from clinic_agent.store import repo
from clinic_agent.store.db import Sessions
from clinic_agent.store.models import utc_now

logger = logging.getLogger("clinic-agent.heartbeat")

BEAT_EVERY = 30  # seconds; incidents.HEARTBEAT_STALE allows three to go missing


def attach(server: AgentServer, sessions: Sessions) -> None:
    worker: dict[str, str] = {}  # the current LiveKit worker id; a reconnect registers a new one
    tasks: list[asyncio.Task] = []  # held so the loop isn't garbage-collected

    def on_registered(worker_id: str, _info) -> None:
        worker["id"] = worker_id
        if not tasks:
            tasks.append(asyncio.get_running_loop().create_task(_beat_forever(sessions, worker), name="heartbeat"))

    server.on("worker_registered", on_registered)


async def _beat_forever(sessions: Sessions, worker: dict[str, str]) -> None:
    host = socket.gethostname()
    while True:
        try:
            await asyncio.to_thread(_beat, sessions, worker["id"], host)
        except Exception:  # noqa: BLE001 - a missed beat must never stop the worker
            logger.exception("heartbeat: could not check in")
        await asyncio.sleep(BEAT_EVERY)


def _beat(sessions: Sessions, worker_id: str, host: str) -> None:
    with sessions() as s:
        repo.beat(s, worker_id, host, utc_now())
