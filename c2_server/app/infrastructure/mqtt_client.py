"""Infrastructure layer – Asynchronous MQTT client built on ``aiomqtt``.

The server uses this wrapper to publish and subscribe to the internal
Mosquitto broker.  Only the minimal set of methods required for the MVP
are implemented; additional helpers can be added later.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from aiomqtt import Client
from aiomqtt.error import AiomqttException

from ..settings import settings
from ..domain.enums import CommandType, EventType

log = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# MQTT topic constants – the single source of truth for the whole system.
# ----------------------------------------------------------------------
TOPIC_REGISTER = "c2/register"
TOPIC_HEARTBEAT = "c2/heartbeat/{agent_id}"
TOPIC_COMMAND = "c2/commands/{agent_id}"
TOPIC_RESULT = "c2/results/{agent_id}"
TOPIC_LOG = "c2/logs/{source}"


class MqttService:
    """Async wrapper around ``aiomqtt.Client``.

    The service is deliberately lightweight – it provides ``publish`` and
    ``subscribe`` helpers and maintains an internal ``asyncio`` event that is
    set once the connection is established.
    """

    def __init__(self, client_id: str = "c2-server"):
        self.client_id = client_id
        self._client: Optional[Client] = None
        self._connected = asyncio.Event()
        # optional external callbacks for incoming messages
        self._command_handler: Optional[Callable[[str, Dict[str, Any]], Any]] = None
        self._result_handler: Optional[Callable[[str, Dict[str, Any]], Any]] = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------
    async def connect(self) -> None:
        """Create the underlying ``aiomqtt.Client`` and connect to the broker."""
        if self._client is not None:
            return
        self._client = Client(
            broker=settings.mqtt_host,
            port=settings.mqtt_port,
            username=settings.mqtt_user,
            password=settings.mqtt_password,
            client_id=self.client_id,
        )
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        try:
            await self._client.connect()
        except AiomqttException as exc:
            raise RuntimeError(f"Failed to connect to MQTT broker: {exc}") from exc
        await self._connected.wait()  # block until on_connect fires

    async def close(self) -> None:
        if self._client:
            await self._client.disconnect()
        self._client = None
        self._connected.clear()

    # ------------------------------------------------------------------
    # Internal callbacks
    # ------------------------------------------------------------------
    async def _on_connect(self) -> None:
        log.info("✅ Connected to MQTT broker")
        self._connected.set()
        # Subscribe to topics we need to receive from agents
        await self._client.subscribe(TOPIC_REGISTER)
        await self._client.subscribe(TOPIC_HEARTBEAT.format(agent_id="+"))
        await self._client.subscribe(TOPIC_RESULT.format(agent_id="+"))
        # Command topics are subscription‑per‑agent and will be added lazily

    async def _on_message(self, message) -> None:  # type: ignore
        topic = message.topic
        try:
            payload = json.loads(message.payload)
        except json.JSONDecodeError:
            log.warning("Received non‑JSON payload on %s", topic)
            return

        # Dispatch based on topic pattern – simple string matching is sufficient for MVP
        if topic == TOPIC_REGISTER:
            # Persist registration via use‑case
            from ..application.use_cases.register_agent import register_agent
            from ..infrastructure.Base import SessionLocal
            with SessionLocal() as db:
                register_agent(db, payload)
        elif topic.startswith("c2/heartbeat/"):
            agent_id = topic.split("/")[-1]
            from ..application.use_cases.update_heartbeat import update_heartbeat
            from ..infrastructure.Base import SessionLocal
            with SessionLocal() as db:
                update_heartbeat(db, agent_id, payload)
        elif topic.startswith("c2/results/"):
            agent_id = topic.split("/")[-1]
            if self._result_handler:
                await self._result_handler(agent_id, payload)
            else:
                # Default persistence via use‑case
                from ..application.use_cases.store_result import store_result
                from ..infrastructure.Base import SessionLocal
                with SessionLocal() as db:
                    store_result(db, payload)
        elif topic.startswith("c2/commands/"):
            # The server normally publishes to this topic; receiving is rare but supported.
            agent_id = topic.split("/")[-1]
            if self._command_handler:
                await self._command_handler(agent_id, payload)
        else:
            log.debug("Unhandled MQTT topic %s", topic)

    # ------------------------------------------------------------------
    # Public publish helpers used by the application layer
    # ------------------------------------------------------------------
    async def publish(self, topic: str, payload: Dict[str, Any], *, qos: int = 1, retain: bool = False) -> None:
        if not self._client:
            raise RuntimeError("MQTT client not connected")
        await self._client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    async def publish_command(self, agent_id: str, command_type: CommandType, args: Optional[Dict[str, Any]] = None) -> None:
        topic = TOPIC_COMMAND.format(agent_id=agent_id)
        payload = {"type": command_type.value, "args": args or {}}
        await self.publish(topic, payload)

    async def publish_heartbeat(self, agent_id: str) -> None:
        topic = TOPIC_HEARTBEAT.format(agent_id=agent_id)
        payload = {"timestamp": datetime.now(timezone.utc).isoformat()}
        await self.publish(topic, payload)

    async def publish_log(self, source: str, level: str, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        topic = TOPIC_LOG.format(source=source)
        payload = {"level": level, "message": message}
        if extra:
            payload.update(extra)
        await self.publish(topic, payload)

    # ------------------------------------------------------------------
    # Callback registration – used by the application layer to react to inbound data
    # ------------------------------------------------------------------
    def set_command_handler(self, fn: Callable[[str, Dict[str, Any]], Any]) -> None:
        self._command_handler = fn

    def set_result_handler(self, fn: Callable[[str, Dict[str, Any]], Any]) -> None:
        self._result_handler = fn


# Export a singleton for convenience throughout the codebase
mqtt_service = MqttService()