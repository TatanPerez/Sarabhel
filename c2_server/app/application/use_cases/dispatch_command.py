"""Use‑case for dispatching a command to an agent.

1. Persist the command in the ``commands`` table.
2. Publish the MQTT message so the agent receives it.

The function returns the created ``Command`` domain object (including its DB id) so the API can report it back to the caller.
"""

from ..infrastructure.repositories import CommandRepository
from ..infrastructure.mqtt_client import mqtt_service
from ..domain.entities import CommandType


async def dispatch_command(db_session, agent_id: str, command_type: str, args: dict | None = None):
    """Create a ``Command`` record and publish it via MQTT.

    Args:
        db_session: SQLAlchemy session.
        agent_id: Target agent identifier.
        command_type: String matching ``CommandType`` enum values.
        args: Optional dict of command arguments.
    Returns:
        The newly created ``Command`` domain object.
    """
    # Persist the command first so we have an ID for correlation
    repo = CommandRepository(db_session)
    cmd = repo.create(
        agent_id=agent_id,
        command_type=CommandType(command_type),
        args=args,
    )
    # Publish to MQTT – the payload includes the generated command id for correlation
    await mqtt_service.publish_command(
        agent_id=agent_id,
        command_type=cmd.command_type,
        args={"command_id": cmd.id, **(args or {})},
    )
    return cmd
