#!/usr/bin/env python3
"""Prueba de comunicación MQTT desde terminal.

Uso:
    python3 test_comms.py                   # test rápido (1 mensaje)
    python3 test_comms.py --interactive     # modo conversación
"""

import json
import sys
import paho.mqtt.client as mqtt

# ── Config ──────────────────────────────────
BROKER = "localhost"
PORT = 8883
CA = "config/certs/ca.crt"
AGENT_CERT = "config/certs/agent.crt"
AGENT_KEY = "config/certs/agent.key"
AGENT_ID = "AG001"
# ────────────────────────────────────────────

messages = []


def on_connect(client, userdata, flags, rc):
    print(f"[+] Conectado al broker {BROKER}:{PORT} (rc={rc})")
    client.subscribe(f"c2/cmd/{AGENT_ID}", qos=1)


def on_message(client, userdata, msg):
    print(f"\n[📩] Mensaje recibido en {msg.topic}")
    try:
        payload = json.loads(msg.payload)
        print(f"    Payload: {json.dumps(payload, indent=2)}")
    except json.JSONDecodeError:
        print(f"    Payload (raw): {msg.payload.decode()}")
    messages.append(msg)


client = mqtt.Client(client_id=AGENT_ID, protocol=mqtt.MQTTv311)
client.tls_set(CA, certfile=AGENT_CERT, keyfile=AGENT_KEY)
# Desarrollo local: el cert tiene CN=c2-broker, no localhost
# TLS sigue cifrando y autenticando, solo salta el check de hostname
client.tls_insecure_set(True)
client.on_connect = on_connect
client.on_message = on_message

print(f"[~] Conectando a {BROKER}:{PORT}...")
client.connect(BROKER, PORT, 60)
client.loop_start()

import time
time.sleep(1)

# ── 1. Enviar REGISTER ─────────────────────
print("\n[1] Enviando REGISTER...")
register = {
    "agent_id": AGENT_ID,
    "hostname": "test-terminal",
    "os": "Linux",
    "username": "test"
}
client.publish("c2/agents/register", json.dumps(register), qos=1)
time.sleep(0.5)

# ── 2. Enviar RESULT ───────────────────────
print("[2] Enviando RESULT...")
from crypto_lib.cipher import Cipher
from pathlib import Path

psk_path = Path("crypto_lib/psk.key")
if psk_path.exists():
    key = psk_path.read_bytes()
    cipher = Cipher(key, state_file="/tmp/test.state")
    result_dict = cipher.encrypt(json.dumps({
        "task_id": "TEST001",
        "agent_id": AGENT_ID,
        "status": "completed",
        "output": "HOLA MUNDO DESDE EL TERMINAL"
    }))
    client.publish(f"c2/res/{AGENT_ID}", json.dumps(result_dict), qos=1)
    print(f"    Payload cifrado: {json.dumps(result_dict, indent=2)}")
else:
    print("    [!] psk.key no encontrado, enviando sin cifrar")
    result = json.dumps({
        "task_id": "TEST001",
        "agent_id": AGENT_ID,
        "status": "completed",
        "output": "HOLA MUNDO DESDE EL TERMINAL"
    })
    client.publish(f"c2/res/{AGENT_ID}", result, qos=1)

time.sleep(0.5)

# ── 3. Esperar COMMAND ─────────────────────
print("\n[3] Esperando COMMAND (esperá 15s o mandalo desde otra terminal)...")
print("    Para mandar un comando, abrí otra terminal y ejecutá:")
print(f"    python3 -c \"")
print(f"import paho.mqtt.client as mqtt, json")
print(f"c = mqtt.Client(client_id='test-pub')")
print(f"c.tls_set('{CA}', certfile='{AGENT_CERT}', keyfile='{AGENT_KEY}')")
print(f"c.connect('{BROKER}', {PORT})")
print(f"c.loop_start()")
print(f"c.publish('c2/cmd/{AGENT_ID}', json.dumps({{'task_id':'TASK001','command':'whoami','command_type':'shell'}}), qos=1)")
print(f"c.disconnect()")
print(f"\"")
print()

for i in range(15):
    if messages:
        break
    time.sleep(1)
    print(f"    ... {i+1}/15s", end="\r")

if not messages:
    print("\n    ⏰ No se recibieron comandos (timeout)")
else:
    print("\n    ✅ Comando recibido!")

client.loop_stop()
client.disconnect()
print("\n[✓] Prueba completada")
