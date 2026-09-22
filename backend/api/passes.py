"""Signed join passes: which room, what the caller may do, and which clinic's
receptionist LiveKit sends in with them."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta

from livekit import api as lk

from clinic_agent.config import Settings
from clinic_agent.dispatch import AGENT_NAME, metadata_for

# Long enough to allow the microphone and join; not a call-length limit.
PASS_TTL = timedelta(minutes=5)


@dataclass(frozen=True)
class CallPass:
    url: str
    token: str
    room: str


def call_pass(cfg: Settings, clinic_id: int, slug: str) -> CallPass:
    """A pass for one new, private call. The dispatch is signed into the pass
    with the LiveKit secret, so a caller cannot change which clinic answers."""
    room = f"call-{slug}-{secrets.token_hex(4)}"
    token = (
        lk.AccessToken(cfg.livekit_api_key, cfg.livekit_api_secret)
        .with_identity(f"caller-{secrets.token_hex(4)}")
        .with_name("Caller")
        .with_ttl(PASS_TTL)
        .with_grants(lk.VideoGrants(
            room_join=True,
            room=room,
            can_subscribe=True,
            can_publish=True,
            can_publish_sources=["microphone"],  # a voice call: no camera, no screen
            can_publish_data=False,
        ))
        .with_room_config(lk.RoomConfiguration(
            max_participants=2,  # the caller and the receptionist, nobody else
            empty_timeout=60,
            departure_timeout=10,
            agents=[lk.RoomAgentDispatch(agent_name=AGENT_NAME, metadata=metadata_for(clinic_id))],
        ))
        .to_jwt()
    )
    return CallPass(url=cfg.livekit_url, token=token, room=room)
