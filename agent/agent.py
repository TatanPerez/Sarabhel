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
            cleaned := (c.strip() if (c := getattr(comp, "stdout", "")) else ""),
            cleaned_err := (c.strip() if (c := getattr(comp, "stderr", "")) else ""),
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