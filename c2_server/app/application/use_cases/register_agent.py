# c2_server/app/application/use_cases/register_agent.py

"""Use‑case for registering a new agent.

The MQTT broker sends a registration payload on the ``c2/register`` topic.
The payload has the form::

    {
        "agent_id": "myagent",
        "token": "C2_STATIC_TOKEN",
        "capabilities": ["system_info", "file_op", "net_tool"]
    }

The use‑case validates the static token and stores the agent in the DB using
an ``AgentRepository``. It also publishes a confirmation event back to MQTT.
"""

import logging
from typing import Dict, Any, Optional

from typing import Protocol

from ...domain.entities import Agent
from ...infrastructure.repositories import AgentRepository
from ...settings import settings

logger = logging.getLogger(__name__)

class MqttPublisher(Protocol):
    async def publish(self, topic: str, payload: Dict[str, Any], **kwargs: Any) -> None:
        ...


class RegisterAgent:
    """Use case for handling the registration of a new agent."""

    def __init__(self, agent_repository: AgentRepository, mqtt_client: Optional[MqttPublisher] = None):
        """
        Initialize the use case with its dependencies.

        Args:
            agent_repository: Repository for agent data persistence.
            mqtt_client: Optional client to publish registration events.
        """
        self.agent_repository = agent_repository
        self.mqtt_client = mqtt_client

    async def execute(self, payload: Dict[str, Any]) -> Optional[Agent]:
        """
        Validate and persist a new agent.

        This method performs the following steps:
        1. Validates the static token.
        2. Checks if the agent already exists.
        3. Creates a new Agent entity.
        4. Persists the agent using the repository.
        5. Publishes a confirmation event to MQTT (if client is available).

        Args:
            payload: Dict decoded from the MQTT registration message.

        Returns:
            The created Agent entity if registration was successful, None otherwise.
        """
        token = payload.get("token")
        if token != settings.c2_static_token:
            logger.warning(f"Registration attempt with invalid token: {token}")
            # Invalid token – ignore registration
            return None

        agent_id = payload.get("agent_id")
        capabilities = payload.get("capabilities", [])
        
        if not agent_id:
            logger.error("Registration payload missing 'agent_id'")
            return None

        # Check if agent already exists
        existing_agent = self.agent_repository.get_by_id(agent_id)
        if existing_agent:
            logger.info(f"Agent {agent_id} already registered.")
            return existing_agent

        # Persist the agent
        created_agent = self.agent_repository.create(agent_id=agent_id, capabilities=capabilities)
        
        # Publish a confirmation event
        if self.mqtt_client:
            await self.mqtt_client.publish(
                f"c2/registered/{agent_id}",
                {
                    "status": "registered",
                    "agent_id": agent_id,
                    "timestamp": created_agent.registered_at.isoformat(),
                },
            )
            logger.info(f"Agent {agent_id} registered successfully and confirmation published.")
        else:
            logger.info(f"Agent {agent_id} registered successfully (no MQTT client for confirmation).")

        return created_agent
