"""Use‑case for registering a new agent.

The MQTT broker sends a registration payload on the ``c2/register`` topic.
The payload has the form::

    {
        "agent_id": "myagent",
        "token": "C2_STATIC_TOKEN",
        "capabilities": ["system_info", "file_op", "net_tool"]
    }

The use‑case validates the static token (configured via ``settings.c2_static_token``)
and stores the agent in the DB using ``AgentRepository``.
"""

from ..infrastructure.repositories import AgentRepository
from ..settings import settings


def register_agent(db_session, payload: dict) -> None:
    """Validate and persist a new agent.

    Args:
        db_session: SQLAlchemy session (provided by ``Base.get_db``).
        payload: Dict decoded from the MQTT registration message.
    """
    token = payload.get("token")
    if token != settings.c2_static_token:
        # Invalid token – ignore registration (could also raise an error / log)
        return
    agent_id = payload.get("agent_id")
    capabilities = payload.get("capabilities", [])
    if not agent_id:
        return
    repo = AgentRepository(db_session)
    # ``create`` is idempotent – ignore if already exists
    if repo.get_by_id(agent_id) is None:
        repo.create(agent_id=agent_id, capabilities=capabilities)
