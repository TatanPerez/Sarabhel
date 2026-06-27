"""Use‑case for dispatching a command to an agent.

1. Persist the command in the ``commands`` table.
2. Publish the MQTT message so the agent receives it.

The function returns the created ``Command`` domain object (including its DB id) so the API can report it back to the caller.
"""

from ...domain.entities import CommandType
from ...infrastructure.repositories import AgentRepository, CommandRepository
from ...infrastructure.mqtt_client import mqtt_service


class DispatchCommand:
    def __init__(
        self,
        agent_repository: AgentRepository,
        command_repository: CommandRepository,
        mqtt_client=mqtt_service,
    ):
        self.agent_repository = agent_repository
        self.command_repository = command_repository
        self.mqtt_client = mqtt_client

    async def execute(self, agent_id: str, command_type_str: str, args: dict | None = None):
        if not self.agent_repository.get_by_id(agent_id):
            return None

        command_type = CommandType(command_type_str)
        cmd = self.command_repository.create(
            agent_id=agent_id,
            command_type=command_type,
            args=args,
        )
        await self.mqtt_client.publish_command(
            agent_id=agent_id,
            command_type=command_type,
            args={"command_id": cmd.id, **(args or {})},
        )
        return cmd


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
