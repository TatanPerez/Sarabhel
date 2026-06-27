# c2_server/app/infrastructure/mqtt_service.py

"""Infrastructure layer – Asynchronous MQTT client built on ``aiomqtt``.

This service is a pure infrastructure component. It ONLY handles:
1. The MQTT connection lifecycle.
2. Serializing/deserializing messages.
3. Dispatching incoming messages to registered callbacks.

It has NO knowledge of use cases, repositories, or the database.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional

from aiomqtt import Client, Message, MqttError

from ..settings import settings
from ..domain.entities import CommandType

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
        self._client_context = None
        self._connected = asyncio.Event()
        # Define callbacks for specific inbound message types
        self._on_register_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self._on_heartbeat_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self._on_result_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self._on_command_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None

    def on_register(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._on_register_callback = callback

    def on_heartbeat(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        self._on_heartbeat_callback = callback

    def on_result(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        self._on_result_callback = callback

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------
    async def connect(self) -> None:
        """Create the underlying ``aiomqtt.Client`` and connect to the broker."""
        if self._client is not None:
            log.warning("MQTT client is already connected or connecting.")
            return
            
        self._client = Client(
            hostname=settings.mqtt_host,  # 'hostname' es el parámetro correcto en aiomqtt
            port=settings.mqtt_port,
            username=settings.mqtt_user,
            password=settings.mqtt_password,
            identifier=self.client_id,
        )
        
        try:
            self._client_context = self._client
            await self._client_context.__aenter__()
            self._connected.set()
            log.info("Connected to MQTT broker")

            await self._client.subscribe(TOPIC_REGISTER)
            await self._client.subscribe("c2/heartbeat/+")
            await self._client.subscribe("c2/results/+")

            asyncio.create_task(self._message_listener())
                
        except MqttError as exc:
            self._connected.clear()
            raise RuntimeError(f"Failed to connect to MQTT broker: {exc}") from exc

    async def close(self) -> None:
        """Disconnect from the broker and clean up resources."""
        if self._client:
            if self._client_context:
                await self._client_context.__aexit__(None, None, None)
            self._client = None
            self._client_context = None
        self._connected.clear()
        log.info("MQTT client connection closed.")

    async def _message_listener(self):
        """Continuously listen for messages and dispatch them."""
        if not self._client:
            raise RuntimeError("MQTT client not connected. Cannot start listener.")
            
        try:
            async for message in self._client.messages:
                await self._on_message(message)
        except MqttError as e:
            log.error(f"MQTT listener error: {e}")
            await self.close() # Close connection on error

    # ------------------------------------------------------------------
    # Internal message dispatcher
    # ------------------------------------------------------------------
    async def _on_message(self, message: Message) -> None:
        """Dispatches an incoming message to the appropriate callback."""
        topic = str(message.topic)
        try:
            payload = json.loads(message.payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            log.warning("Received non-JSON payload on %s", topic)
            return

        # Dispatch based on topic pattern
        if topic == TOPIC_REGISTER:
            if self._on_register_callback:
                await self._on_register_callback(payload)
            else:
                log.warning("No callback registered for topic: %s", topic)
                
        elif topic.startswith("c2/heartbeat/"):
            agent_id = topic.split("/")[-1]
            if self._on_heartbeat_callback:
                await self._on_heartbeat_callback(agent_id, payload)
            else:
                log.warning("No callback registered for topic: %s", topic)

        elif topic.startswith("c2/results/"):
            agent_id = topic.split("/")[-1]
            if self._on_result_callback:
                await self._on_result_callback(agent_id, payload)
            else:
                log.warning("No callback registered for topic: %s", topic)
                
        # The server normally publishes to command topics, but we handle it just in case
        elif topic.startswith("c2/commands/"):
            agent_id = topic.split("/")[-1]
            if self._on_command_callback:
                await self._on_command_callback(agent_id, payload)
            else:
                log.warning("No callback registered for topic: %s", topic)
        else:
            log.debug("Unhandled MQTT topic %s", topic)

    # ------------------------------------------------------------------
    # Public publish helpers (sin cambios, son perfectos)
    # ------------------------------------------------------------------
    async def publish(self, topic: str, payload: Dict[str, Any], *, qos: int = 1, retain: bool = False) -> None:
        """Publish a generic message to an MQTT topic."""
        if not self._client or not self._connected.is_set():
            raise RuntimeError("MQTT client not connected")
        await self._client.publish(topic, json.dumps(payload), qos=qos, retain=retain)

    async def publish_command(self, agent_id: str, command_type: CommandType, args: Optional[Dict[str, Any]] = None) -> None:
        """Publish a command to a specific agent."""
        topic = TOPIC_COMMAND.format(agent_id=agent_id)
        args = args or {}
        payload = {"type": command_type.value, "args": args}
        if "command_id" in args:
            payload["command_id"] = args["command_id"]
        await self.publish(topic, payload)

    async def publish_heartbeat(self, agent_id: str) -> None:
        """Publish a heartbeat message for an agent."""
        topic = TOPIC_HEARTBEAT.format(agent_id=agent_id)
        await self.publish(topic, {"agent_id": agent_id})


mqtt_service = MqttService()
