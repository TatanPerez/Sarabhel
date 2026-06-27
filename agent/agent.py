"""
C2 Lab Agent – lightweight Python process that registers with the C2 server
via MQTT, executes whitelisted commands, and publishes results.

Environment variables (provided by docker-compose):
- AGENT_ID: unique identifier for this agent
- C2_STATIC_TOKEN: shared secret used for registration (static token)
- MQTT_HOST: hostname of the Mosquitto broker (default: mosquitto)
- MQTT_PORT: port of the broker (default: 1883)
- MQTT_USER: username for broker authentication
- MQTT_PASSWORD: password for broker authentication
"""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Dict, Optional

import paho.mqtt.client as mqtt

# ----------------------------------------------------------------------
# Configuration from environment
# ----------------------------------------------------------------------
AGENT_ID = os.getenv("AGENT_ID", f"agent-{os.getpid()}")
STATIC_TOKEN = os.getenv("C2_STATIC_TOKEN", "CHANGE_ME")
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "c2_user")
MQTT_PASS = os.getenv("MQTT_PASSWORD", "c2_pass")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "30"))

# Whitelisted command categories (must match server expectations)
ALLOWED_COMMANDS = {"system_info", "file_op", "net_tool"}

# Mapping from command type to a shell command (for MVP we use simple static commands)
COMMAND_MAP = {
    "system_info": "uname -a",
    "file_op": "ls -la /tmp",
    "net_tool": "ping -c 2 8.8.8.8",
}


def _execute_command(cmd_type: str, args: dict) -> tuple[str, str, int]:
    """
    Execute the shell command associated with ``cmd_type``.
    Returns (stdout, stderr, returncode).
    For MVP we ignore ``args`` – they could be used to parameterise the command
    in a more advanced implementation.
    """
    if cmd_type not in COMMAND_MAP:
        return "", f"Unsupported command type: {cmd_type}", 1
    shell_cmd = COMMAND_MAP[cmd_type]
    try:
        completed = subprocess.run(
            shell_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return (
            completed.stdout.strip() if completed.stdout else "",
            completed.stderr.strip() if completed.stderr else "",
            completed.returncode,
        )
    except subprocess.TimeoutExpired as exc:
        return "", f"Command timed out after {exc.timeout}s", 1
    except Exception as exc:  # pragma: no cover
        return "", f"Error executing command: {exc}", 1


# ----------------------------------------------------------------------
# MQTT callbacks
# ----------------------------------------------------------------------
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[{AGENT_ID}] Connected to MQTT broker")
        # Register ourselves
        register_payload = {
            "agent_id": AGENT_ID,
            "token": STATIC_TOKEN,
            # In a real implementation we might advertise capabilities here.
            "capabilities": list(ALLOWED_COMMANDS),
        }
        client.publish("c2/register", json.dumps(register_payload), qos=1)
        # Subscribe to command topic for this agent
        cmd_topic = f"c2/commands/{AGENT_ID}"
        client.subscribe(cmd_topic, qos=1)
        print(f"[{AGENT_ID}] Subscribed to {cmd_topic}")
        # Start heartbeat thread
        threading.Thread(target=_heartbeat_loop, daemon=True).start()
    else:
        print(f"[{AGENT_ID}] Connection failed with code {rc}", file=sys.stderr)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        print(f"[{AGENT_ID}] Invalid JSON on topic {msg.topic}", file=sys.stderr)
        return

    if msg.topic.startswith(f"c2/commands/{AGENT_ID}"):
        cmd_type = payload.get("type")
        cmd_args = payload.get("args", {})
        print(f"[{AGENT_ID}] Received command: {cmd_type} args={cmd_args}")

        if cmd_type not in ALLOWED_COMMANDS:
            result = {
                "stdout": "",
                "stderr": f"Command not allowed: {cmd_type}",
                "exit_code": 1,
            }
        else:
            stdout, stderr, rc = _execute_command(cmd_type, cmd_args)
            result = {"stdout": stdout, "stderr": stderr, "exit_code": rc}

        # Publish result
        result_payload = {
            "agent_id": AGENT_ID,
            "command_id": payload.get("command_id", None),  # optional correlation id
            "result": result,
        }
        client.publish(f"c2/results/{AGENT_ID}", json.dumps(result_payload), qos=1)
        print(f"[{AGENT_ID}] Published result for {cmd_type}")


def _heartbeat_loop():
    """Publish a heartbeat every HEARTBEAT_INTERVAL seconds."""
    while True:
        time.sleep(HEARTBEAT_INTERVAL)
        hb = {"agent_id": AGENT_ID, "timestamp": time.time()}
        try:
            mqtt_client.publish("c2/heartbeat/{}".format(AGENT_ID), json.dumps(hb), qos=1)
        except Exception as e:  # pragma: no cover
            print(f"[{AGENT_ID}] Heartbeat publish failed: {e}", file=sys.stderr)


def _setup_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(client_id=AGENT_ID)
    client.username_pw_set(MQTT_USER, MQTT_PASS)
    client.on_connect = on_connect
    client.on_message = on_message
    # Enable automatic reconnect
    client.reconnect_delay_set(min_delay=1, max_delay=120)
    return client


def main():
    print(f"[{AGENT_ID}] Starting agent...")
    global mqtt_client
    mqtt_client = _setup_mqtt_client()
    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        print(f"[{AGENT_ID}] Shutting down...")
    finally:
        mqtt_client.disconnect()


if __name__ == "__main__":
    main()

# # agent/agent.py

# import asyncio
# import json
# import logging
# import os
# import subprocess
# import uuid
# from datetime import datetime, timezone
# from typing import Dict, Any, Optional

# import paho.mqtt.client as mqtt

# # --- Configuración desde variables de entorno ---
# AGENT_ID = os.getenv("AGENT_ID", f"agent-{uuid.uuid4().hex[:8]}")
# C2_STATIC_TOKEN = os.getenv("C2_STATIC_TOKEN", "default-token")
# MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
# MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
# MQTT_USER = os.getenv("MQTT_USER", "c2_user")
# MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "c2_pass")
# HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", 30))

# # --- Configuración de Seguridad (Whitelist) ---
# # Comandos permitidos por el agente. Esto es CRÍTICO para la seguridad.
# WHITELISTED_COMMANDS = {
#     "system_info": "systeminfo",  # Windows
#     "shell": "cmd",               # Windows
#     "ls": "ls",                   # Linux/macOS
#     "whoami": "whoami",           # Linux/macOS
#     "pwd": "pwd",                 # Linux/macOS
#     # Añade aquí los comandos que tu agente pueda ejecutar
# }

# # --- Configuración de Logging ---
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# log = logging.getLogger(__name__)


# class C2Agent:
#     """A simple C2 agent that connects to an MQTT broker and executes commands."""

#     def __init__(self):
#         self.agent_id = AGENT_ID
#         self.client = mqtt.Client(client_id=self.agent_id)
#         self.command_topic = f"c2/commands/{self.agent_id}"
#         self.result_topic = f"c2/results/{self.agent_id}"
#         self.heartbeat_topic = f"c2/heartbeat/{self.agent_id}"
        
#         # Configurar callbacks de MQTT
#         self.client.on_connect = self._on_connect
#         self.client.on_message = self._on_message
#         self.client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

#     def _on_connect(self, client, userdata, flags, rc):
#         """Callback llamado cuando el agente se conecta al broker MQTT."""
#         if rc == 0:
#             log.info(f"✅ Agent '{self.agent_id}' connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
#             # Suscribirse al topic de comandos para este agente
#             client.subscribe(self.command_topic)
#             log.info(f"🔔 Subscribed to command topic: {self.command_topic}")
#             # Enviar registro inicial y heartbeat
#             self._register_agent()
#             self._send_heartbeat()
#         else:
#             log.error(f"❌ Failed to connect, return code {rc}\n")

#     def _on_message(self, client, userdata, msg):
#         """Callback llamado cuando se recibe un mensaje."""
#         try:
#             payload = json.loads(msg.payload.decode())
#             log.info(f"📨 Received command on topic {msg.topic}: {payload}")
#             # Procesar el comando en un hilo separado para no bloquear el loop de MQTT
#             asyncio.run(self.process_command(payload))
#         except json.JSONDecodeError:
#             log.error("⚠️ Received non-JSON message.")
#         except Exception as e:
#             log.error(f"⚠️ Error processing message: {e}")

#     def _register_agent(self):
#         """Registra el agente en el servidor C2."""
#         registration_payload = {
#             "agent_id": self.agent_id,
#             "token": C2_STATIC_TOKEN,
#             "capabilities": list(WHITELISTED_COMMANDS.keys())
#         }
#         self.client.publish("c2/register", json.dumps(registration_payload))
#         log.info(f"📮 Sent registration to 'c2/register'")

#     def _send_heartbeat(self):
#         """Envía un heartbeat periódico."""
#         heartbeat_payload = {"timestamp": datetime.now(timezone.utc).isoformat()}
#         self.client.publish(self.heartbeat_topic, json.dumps(heartbeat_payload))
#         log.info("💓 Sent heartbeat")

#     # --- ESTA ES LA LÓGICA QUE NECESITABAS AÑADIR ---
#     async def process_command(self, command_data: Dict[str, Any]):
#         """Procesa un comando recibido del servidor C2."""
#         command_type = command_data.get("type")
#         args = command_data.get("args", {})
#         command_id = command_data.get("id", "unknown-id")

#         log.info(f"⚙️ Processing command '{command_type}' with args: {args}")

#         if command_type not in WHITELISTED_COMMANDS:
#             await self._send_result(command_id, "error", f"Command '{command_type}' is not whitelisted.")
#             return

#         # Construir el comando a ejecutar
#         base_command = WHITELISTED_COMMANDS[command_type]
        
#         # Manejar comandos especiales que necesitan más lógica
#         if command_type == "shell":
#             # Para el comando 'shell', el payload es el comando completo a ejecutar
#             full_command = args.get("cmd", "")
#             if not full_command:
#                 await self._send_result(command_id, "error", "Shell command requires 'cmd' argument.")
#                 return
#         else:
#             # Para otros comandos, los args son los argumentos del comando base
#             full_command = f"{base_command} {' '.join(args.values())}"

#         try:
#             # Ejecutar el comando de forma segura con un timeout
#             process = await asyncio.create_subprocess_shell(
#                 full_command,
#                 stdout=asyncio.subprocess.PIPE,
#                 stderr=asyncio.subprocess.PIPE,
#                 text=True
#             )
            
#             stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=15.0)

#             if process.returncode == 0:
#                 await self._send_result(command_id, "success", stdout, stderr)
#             else:
#                 await self._send_result(command_id, "error", stdout, stderr)

#         except asyncio.TimeoutError:
#             await self._send_result(command_id, "error", "Command execution timed out.")
#         except Exception as e:
#             await self._send_result(command_id, "error", f"Failed to execute command: {str(e)}")

#     async def _send_result(self, command_id: str, status: str, stdout: str = "", stderr: str = ""):
#         """Envía el resultado de un comando de vuelta al servidor C2."""
#         result_payload = {
#             "command_id": command_id,
#             "status": status,
#             "stdout": stdout,
#             "stderr": stderr,
#             "timestamp": datetime.now(timezone.utc).isoformat()
#         }
#         # Publicamos de forma síncrona ya que paho-mqtt no es asíncrono por defecto
#         self.client.publish(self.result_topic, json.dumps(result_payload))
#         log.info(f"📤 Sent result for command '{command_id}' with status '{status}'")

#     def run(self):
#         """Conecta el agente al broker y empieza el loop de eventos."""
#         try:
#             self.client.connect(MQTT_HOST, MQTT_PORT, 60)
#             # Programar el heartbeat periódico
#             self.client.loop_start()
#             while True:
#                 self._send_heartbeat()
#                 asyncio.sleep(HEARTBEAT_INTERVAL)
#         except KeyboardInterrupt:
#             log.info("🛑 Agent stopped by user.")
#         finally:
#             self.client.loop_stop()
#             self.client.disconnect()
#             log.info("🔌 Disconnected from MQTT broker.")


# if __name__ == "__main__":
#     agent = C2Agent()
#     agent.run()
