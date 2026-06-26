#!/usr/bin/env python3
"""Prueba de comunicación MQTT desde terminal.

Uso:
    python3 test_comms.py                   # test rápido (1 mensaje)
    python3 test_comms.py --interactive     # modo conversación
"""

import json
import sys
import time
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
publish_acks = {}


def on_connect(client, userdata, flags, rc, properties=None):
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


def on_publish(client, userdata, mid, reason_code, properties=None):
    if reason_code < 128:
        publish_acks[mid] = "ok"
    else:
        publish_acks[mid] = f"fail({reason_code})"
        print(f"  ⚠️ Broker RECHAZÓ publicación (mid={mid}, rc={reason_code}) — revisar ACL")


def wait_ack(description, timeout=5):
    """Espera hasta TIMEOUT segundos a que el broker acepte una publicación."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for mid, status in list(publish_acks.items()):
            if status == "ok":
                del publish_acks[mid]
                return True
            elif status.startswith("fail"):
                del publish_acks[mid]
                return False
        time.sleep(0.1)
    print(f"  ⚠️ Timeout esperando ack del broker para {description}")
    return None


client = mqtt.Client(
    client_id=AGENT_ID,
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    protocol=mqtt.MQTTv5,
)
client.tls_set(CA, certfile=AGENT_CERT, keyfile=AGENT_KEY)
# Desarrollo local: el cert tiene CN=c2-broker, no localhost
# TLS sigue cifrando y autenticando, solo salta el check de hostname
client.tls_insecure_set(True)
client.on_connect = on_connect
client.on_message = on_message
client.on_publish = on_publish

print(f"[~] Conectando a {BROKER}:{PORT}...")
client.connect(BROKER, PORT, 60)
client.loop_start()
time.sleep(1)

# ── 1. Enviar REGISTER ─────────────────────
print("\n[1] Enviando REGISTER...")
register = {
    "agent_id": AGENT_ID,
    "hostname": "test-terminal",
    "os": "Linux",
    "username": "test"
}
info = client.publish("c2/agents/register", json.dumps(register), qos=1)
ack = wait_ack("REGISTER")
if ack:
    print(f"    ✅ Broker aceptó REGISTER")
elif ack is False:
    print(f"    ❌ Broker RECHAZÓ REGISTER — revisar ACL")
    sys.exit(1)

# ── 2. Enviar RESULT ───────────────────────
print("\n[2] Enviando RESULT...")
from crypto_lib.cipher import Cipher
from pathlib import Path

psk_path = Path("crypto_lib/psk.key")
if psk_path.exists():
    key = psk_path.read_bytes()
    cipher = Cipher(key, state_file="/tmp/test_comms.state")
    result_dict = cipher.encrypt(json.dumps({
        "task_id": "TEST001",
        "agent_id": AGENT_ID,
        "status": "completed",
        "output": "HOLA MUNDO DESDE EL TERMINAL"
    }))
    info = client.publish(f"c2/res/{AGENT_ID}", json.dumps(result_dict), qos=1)
    ack = wait_ack("RESULT")
    if ack:
        print(f"    ✅ Broker aceptó RESULT cifrado")
        print(f"    Payload cifrado: {json.dumps(result_dict, indent=2)}")
    elif ack is False:
        print(f"    ❌ Broker RECHAZÓ RESULT — revisar ACL")
else:
    print("    [!] psk.key no encontrado, enviando sin cifrar")
    result = json.dumps({
        "task_id": "TEST001",
        "agent_id": AGENT_ID,
        "status": "completed",
        "output": "HOLA MUNDO DESDE EL TERMINAL"
    })
    client.publish(f"c2/res/{AGENT_ID}", result, qos=1)

# ── 3. Esperar COMMAND ─────────────────────
print("\n[3] Esperando COMMAND (esperá 15s o mandalo desde otra terminal)...")
print("    Para mandar un comando, abrí otra terminal y ejecutá:")
print(f"    python3 -c \"")
print(f"import paho.mqtt.client as mqtt, json, time")
print(f"c = mqtt.Client(client_id='test-pub', callback_api_version=mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)")
print(f"c.tls_set('{CA}', certfile='{AGENT_CERT}', keyfile='{AGENT_KEY}')")
print(f"c.tls_insecure_set(True)")
print(f"c.connect('{BROKER}', {PORT})")
print(f"c.loop_start()")
print(f"info = c.publish('c2/cmd/{AGENT_ID}', json.dumps({{'task_id':'TASK001','command':'whoami','command_type':'shell'}}), qos=1)")
print(f"time.sleep(0.5)")
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
