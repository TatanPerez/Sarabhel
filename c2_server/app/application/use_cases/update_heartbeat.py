"""Use‑case for handling a heartbeat message from an agent.

The MQTT topic ``c2/heartbeat/<agent_id>`` carries a JSON payload like::

    {"timestamp": 1687755600.123}

The use‑case simply updates the ``last_seen`` column of the corresponding agent.
"""

from ..infrastructure.repositories import AgentRepository
from datetime import datetime, timezone


def update_heartbeat(db_session, agent_id: str, payload: dict) -> None:
    """Update the last‑seen timestamp for *agent_id*.

    If the agent is unknown the function does nothing – registration is handled
    separately by ``register_agent``.
    """
    ts = payload.get("timestamp")
    if ts is None:
        # timestamp may be iso‑string; fallback to now
        ts_dt = datetime.now(timezone.utc)
    else:
        # Accept either a float epoch or an ISO‑8601 string
        if isinstance(ts, (int, float)):
            ts_dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        else:
            try:
                ts_dt = datetime.fromisoformat(ts)
            except Exception:
                ts_dt = datetime.now(timezone.utc)
    repo = AgentRepository(db_session)
    repo.update_last_seen(agent_id, ts_dt)
