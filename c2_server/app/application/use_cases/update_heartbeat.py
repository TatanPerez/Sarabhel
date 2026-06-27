"""Use‑case for handling a heartbeat message from an agent.

The MQTT topic ``c2/heartbeat/<agent_id>`` carries a JSON payload like::

    {"timestamp": 1687755600.123}

The use‑case simply updates the ``last_seen`` column of the corresponding agent.
"""

from datetime import datetime, timezone

from ...infrastructure.repositories import AgentRepository


class UpdateHeartbeat:
    def __init__(self, agent_repository: AgentRepository):
        self.agent_repository = agent_repository

    async def execute(self, agent_id: str, payload: dict):
        ts_dt = _parse_timestamp(payload)
        return self.agent_repository.update_last_seen(agent_id, ts_dt)


def _parse_timestamp(payload: dict) -> datetime:
    ts = payload.get("timestamp")
    if ts is None:
        return datetime.now(timezone.utc)

    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(float(ts), tz=timezone.utc)

    try:
        return datetime.fromisoformat(ts)
    except Exception:
        return datetime.now(timezone.utc)


def update_heartbeat(db_session, agent_id: str, payload: dict) -> None:
    """Update the last‑seen timestamp for *agent_id*.

    If the agent is unknown the function does nothing – registration is handled
    separately by ``register_agent``.
    """
    ts_dt = _parse_timestamp(payload)
    repo = AgentRepository(db_session)
    repo.update_last_seen(agent_id, ts_dt)
