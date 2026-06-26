# Sarabhel — Canal C2 con MQTT

**Hackeaton Talento Tech 2**

Sistema de Comando y Control (C2) asíncrono basado en MQTT con doble capa de seguridad:
**mTLS** para el transporte y **AES-256-GCM** para el cifrado de payloads.

---

## Índice

- [1. Arquitectura y Diseño](#1-arquitectura-y-diseño)
- [2. Contrato de Comunicación (Tópicos)](#2-contrato-de-comunicación-tópicos)
- [3. Arquitectura de Seguridad](#3-arquitectura-de-seguridad)
- [4. Primeros Pasos](#4-primeros-pasos)
- [5. Integración de un Agente (Python)](#5-integración-de-un-agente-python)
- [6. Integración con n8n (Bridge HTTP)](#6-integración-con-n8n-bridge-http)
- [7. Gestión de Certificados](#7-gestión-de-certificados)
- [8. Políticas de Acceso (ACL)](#8-políticas-de-acceso-acl)
- [9. Gestión de Políticas de Seguridad](#9-gestión-de-políticas-de-seguridad)
- [10. Checklist de Integración](#10-checklist-de-integración)
- [11. Troubleshooting — "Sin Morir en el Intento"](#11-troubleshooting--sin-morir-en-el-intento)
- [12. Comandos de Verificación Rápida](#12-comandos-de-verificación-rápida)
- [13. Estructura del Proyecto](#13-estructura-del-proyecto)

---

## 1. Arquitectura y Diseño

### Principios de diseño

- **AES-256-GCM**: cifrado y autenticación simultáneos. Nonce de 12 bytes generado con contador persistente para evitar reuso (nonce reuse = muerte del canal).
- **QoS 1**: calidad de servicio para no perder mensajes si el agente está dormido. El broker retiene el mensaje hasta que el agente lo recibe.
- **Tópicos opacos**: identificadores únicos y estructura plana para evitar fuga de información por naming.
- **Docker**: el broker corre aislado en un contenedor con mínimo privilegio (`no-new-privileges`).

### Componentes del sistema

```
┌─────────────────────────────────────────────────────────┐
│                        n8n                              │
│  (orquestador - HTTP hacia el bridge)                   │
└──────────┬──────────────────────────────────────────┘
           │ POST /api/command │ GET /api/results
           ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│                  Bridge HTTP (bridge.py)                 │
│  cifra/descifra con crypto_lib, traduce HTTP ↔ MQTT     │
│  CN del cert: crypto-bridge                              │
└──────────────────────┬─────────────────────────────────┘
                       │ MQTT + TLS (puerto 8883)
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Mosquitto Broker (Docker)                  │
│  Puerto 8883 (MQTTS), require_certificate: true         │
│  use_identity_as_username: true, ACL por tópico         │
└──────┬─────────────────────────────────────┬───────────┘
       │ MQTT + TLS                          │ MQTT + TLS
       ▼                                     ▼
┌──────────────┐                    ┌──────────────┐
│  Agente 1    │    ...             │  Agente N    │
│ CN=AG001     │                    │ CN=AGXXX     │
│ crypto_lib   │                    │ crypto_lib   │
└──────────────┘                    └──────────────┘
```

### Flujo de datos

```
1. REGISTER: AGENT → broker → bridge → n8n
   El agente anuncia: "llegué, soy AG001, soy Windows"
   (plano, solo TLS)

2. COMMAND: n8n → bridge → broker → AGENT
   El servidor ordena: "ejecutá ipconfig"
   (cifrado con AES-GCM)

3. RESULT: AGENT → broker → bridge → n8n
   El agente responde: "completado, salida: ..."
   (cifrado con AES-GCM)
```

---

## 2. Contrato de Comunicación (Tópicos)

El sistema tiene **3 flujos** bien definidos. Cada uno usa un tópico específico,
una dirección fija y un nivel de cifrado determinado.

| # | Flujo | Dirección | Tópico | Cifrado |
|---|-------|-----------|--------|---------|
| 1 | **Register** | Agente → Broker → n8n | `c2/agents/register` | **Plano** (solo TLS) |
| 2 | **Command** | n8n → Broker → Agente | `c2/cmd/{agent_id}` | **AES-256-GCM** |
| 3 | **Result** | Agente → Broker → n8n | `c2/res/{agent_id}` | **AES-256-GCM** |

> ⚠️ `{agent_id}` DEBE coincidir con el CN del certificado del agente.
> El broker usa `use_identity_as_username true`, por lo que el CN del cert
> es el username del cliente MQTT y el identificador contra el cual se evalúan las ACLs.

### Flujo 1 — Register (plano)

El agente anuncia su presencia al sistema. El payload **no va cifrado**
porque es metadata pública (hostname, OS, username) y la identidad ya está
autenticada por el certificado TLS en la capa de transporte.

```
Topic: c2/agents/register
Payload (plano):
{
  "agent_id": "AG001",
  "hostname": "PC-LAB01",
  "os": "Windows 11",
  "username": "agente"
}
```

### Flujo 2 — Command (cifrado)

El servidor envía un comando a un agente específico. El payload completo
va cifrado con AES-GCM dentro del formato `{"iv", "ciphertext", "tag"}`.

```
Topic: c2/cmd/AG001
Payload (cifrado):
{
  "iv": "base64...",
  "ciphertext": "base64...",
  "tag": "base64..."
}
```

Contenido descifrado:

```json
{
  "task_id": "TASK001",
  "command": "ipconfig",
  "command_type": "shell"
}
```

### Flujo 3 — Result (cifrado)

El agente responde con el resultado de la ejecución. Misma estructura cifrada.

```
Topic: c2/res/AG001
Payload (cifrado):
{
  "iv": "base64...",
  "ciphertext": "base64...",
  "tag": "base64..."
}
```

Contenido descifrado:

```json
{
  "task_id": "TASK001",
  "agent_id": "AG001",
  "status": "completed",
  "output": "Windows IP Configuration..."
}
```

---

## 3. Arquitectura de Seguridad

Dos capas obligatorias, una NO reemplaza a la otra:

| Capa | Tecnología | Protege |
|---|---|---|
| **Transporte** | mTLS (TLS mutuo con certificados) | Identidad, conexión, metadata (tópicos MQTT) |
| **Payload** | AES-256-GCM con crypto_lib | Contenido del mensaje (extremo a extremo) |

### ¿Por qué dos capas?

- **Solo TLS**: el broker ve el contenido de los mensajes. Si el broker es comprometido, los comandos y resultados quedan expuestos.
- **Solo AES-GCM**: los tópicos MQTT viajan en claro, permitiendo a un atacante identificar patrones de comunicación aunque no pueda leer el payload.
- **Ambas**: cifrado extremo a extremo + protección de metadata.

### El Register es la excepción

El flujo de Register va **plano** (solo TLS) porque:
- El hostname, OS y username son metadata pública.
- La autenticación real la da el certificado TLS, no el contenido del payload.
- No implementar crypto en el register ahorra complejidad sin perder seguridad significativa.

### Módulo crypto_lib

```
crypto_lib/
├── __init__.py
└── cipher.py        ← AES-256-GCM con nonce persistence
```

El módulo implementa:

```
(C, T) = AES-GCM_k(P, N)

P = comando en texto plano
N = nonce de 12 bytes (8 bytes contador + 4 bytes random)
k = PSK de 256 bits (32 bytes)
C = texto cifrado
T = tag de autenticación de 16 bytes
```

**El nonce contador es obligatorio.** Sin `state_file`, un reinicio del agente
puede reusar un nonce. En AES-GCM, un solo nonce reusado permite al atacante
recuperar la clave de autenticación y forjar mensajes.

---

## 4. Primeros Pasos

### Requisitos

- Docker + Docker Compose (para el broker Mosquitto)
- Python 3.10+ con `pip` (para agents, bridge y crypto_lib)

### Instalación de dependencias

```bash
# Para agents en Python
pip install cryptography paho-mqtt

# Para el bridge (adicional a lo anterior)
pip install cryptography paho-mqtt flask
```

### Generar PSK (una sola vez)

La PSK (Pre-Shared Key) es la clave AES-256 que comparten todos los nodos
para cifrar/descifrar payloads. Se genera una única vez:

```bash
cd c2-broker
python3 crypto_lib/cipher.py genkey crypto_lib/psk.key
```

⚠️ **No subir archivos `*.key` a Git.** El `.gitignore` ya los excluye.

### Prender el broker

```bash
cd c2-broker
docker compose up -d
docker compose ps
# → c2_redirector   Up   0.0.0.0:8883->8883/tcp
```

El broker Mosquitto escucha en el puerto **8883** (MQTT sobre TLS) y requiere
certificado de cliente para toda conexión.

### Prender el bridge (para n8n)

```bash
cd c2-broker
python3 bridge/bridge.py
# → HTTP API en http://localhost:5000
# → Conexión MQTT automática al broker
```

---

## 5. Integración de un Agente (Python)

### Archivos necesarios

Cada agente necesita estos archivos para conectarse:

| Archivo | Descripción |
|---|---|
| `ca.crt` | Certificado de la CA del proyecto |
| `AGXXX.crt` | Certificado del agente firmado por la CA |
| `AGXXX.key` | Clave privada del agente |
| `crypto_lib/psk.key` | PSK compartida (la misma para todos los nodos) |
| `crypto_lib/` | Módulo de cifrado AES-GCM |

### Código mínimo del agente

```python
import json
import socket
import platform
import getpass
import paho.mqtt.client as mqtt
from crypto_lib.cipher import Cipher

# ── Configuración ──
AGENT_ID = "AG001"              # DEBE coincidir con el CN del cert
MQTT_HOST = "IP_DEL_BROKER"     # IP o hostname del broker
MQTT_PORT = 8883
PSK_FILE = "crypto_lib/psk.key"
STATE_FILE = "/data/nonce.state"  # Ruta persistente (no /tmp!)

# ── Inicializar crypto ──
with open(PSK_FILE, "rb") as f:
    key = f.read()
cipher = Cipher(key, state_file=STATE_FILE)

# ── Inicializar MQTT (V2 callback + MQTT5 para validación contra broker) ──
client = mqtt.Client(
    client_id=AGENT_ID,
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    protocol=mqtt.MQTTv5,
)
client.tls_set("ca.crt", certfile=f"{AGENT_ID}.crt", keyfile=f"{AGENT_ID}.key")
# El server cert tiene CN=c2-broker. Si conectás por IP/hostname distinto,
# necesitás saltear la verificación de hostname:
client.tls_insecure_set(True)
client.reconnect_delay_set(min_delay=1, max_delay=30)

# ── Callbacks ──
def on_connect(client, userdata, flags, rc, properties=None):
    """Al conectarse: suscribirse a comandos y registrar presencia."""
    if rc != 0:
        print(f"Error de conexión MQTT (rc={rc})")
        return
    client.subscribe(f"c2/cmd/{AGENT_ID}", qos=1)

    # Register: plano (solo TLS), metadata pública
    info = client.publish("c2/agents/register", json.dumps({
        "agent_id": AGENT_ID,
        "hostname": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "username": getpass.getuser(),
    }), qos=1)
    # NOTA: publish() rc=0 solo significa "encolado".
    # La aceptación del broker se recibe en on_publish.

def on_publish(client, userdata, mid, reason_code, properties=None):
    """Verifica que el broker haya aceptado cada publicación.
    reason_code < 128 → éxito; >= 128 → error (ej: ACL denegó).
    """
    if reason_code >= 128:
        print(f"⚠️ Broker rechazó publicación (mid={mid}, rc={reason_code})")

def on_message(client, userdata, msg):
    """Al recibir un comando: descifrar, ejecutar, cifrar resultado."""
    try:
        # Descifrar comando
        comando = json.loads(cipher.decrypt_from_json(msg.payload.decode()))
        print(f"Ejecutando: {comando['command']} (task: {comando.get('task_id')})")

        # Ejecutar comando (implementar según necesidad)
        resultado = ejecutar_comando(comando["command"])

        # Cifrar y publicar resultado
        payload = cipher.encrypt_to_json({
            "task_id": comando["task_id"],
            "agent_id": AGENT_ID,
            "status": "completed",
            "output": resultado,
        })
        client.publish(f"c2/res/{AGENT_ID}", payload, qos=1)

    except Exception as e:
        print(f"Error procesando comando: {e}")

def ejecutar_comando(comando: str) -> str:
    """Ejecuta un comando del sistema y devuelve la salida."""
    import subprocess
    try:
        result = subprocess.run(comando, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout or result.stderr
    except Exception as e:
        return str(e)

client.on_connect = on_connect
client.on_publish = on_publish
client.on_message = on_message
client.connect(MQTT_HOST, MQTT_PORT)
client.loop_forever()
```

### Consideraciones importantes para el agente

| Aspecto | Recomendación |
|---|---|
| **`state_file`** | Debe ir en un volumen persistente (ej: `/data/nonce.state` montado como bind mount). Si el agente corre en Docker sin volumen, el contador se pierde al reiniciar. |
| **client_id** | Usar el `AGENT_ID` como client_id MQTT para trazabilidad en los logs del broker. |
| **QoS** | Usar QoS 1 tanto para publish como para subscribe. QoS 2 duplica tráfico sin beneficio real para C2. |
| **Error handling** | Si `decrypt` lanza `InvalidTag`, NO ejecutar el comando. Reportar el error al servidor. |
| **Reconexión** | `paho-mqtt` maneja reconexión automática si no se llama a `disconnect()`. |

---

## 6. Integración con n8n (Bridge HTTP)

### El problema

n8n ejecuta JavaScript/Node.js. crypto_lib está escrito en Python.
Implementar AES-256-GCM idéntico en Node.js es técnicamente posible pero
es una fuente constante de bugs de compatibilidad (orden de bytes, formato
del tag, encoding). Para una hackathon, **no vale el riesgo**.

### La solución: Bridge HTTP

El bridge (`bridge/bridge.py`) es un servidor Flask que:

- Se conecta al broker MQTT con TLS (certificado propio CN=crypto-bridge)
- Escucha comandos HTTP desde n8n
- Cifra comandos con crypto_lib y los publica en MQTT
- Recibe resultados desde MQTT, los descifra y los bufferiza para n8n
- Recibe registros desde MQTT y los bufferiza para n8n

### Arquitectura bridge + n8n

```
n8n ──HTTP──→ bridge.py (:5000) ──MQTT+TLS──→ broker (:8883) ──MQTT+TLS──→ agentes
                │
                ├─ crypto_lib (cifra/descifra)
                ├─ buffers de resultados y registros
                └─ conexión persistente al broker
```

### Endpoints del bridge

| Método | Endpoint | Descripción | Uso en n8n |
|---|---|---|---|
| `POST` | `/api/command` | Enviar comando a un agente | Nodo HTTP Request |
| `GET` | `/api/results` | Obtener resultados pendientes | Nodo HTTP Request (polling) |
| `GET` | `/api/agents` | Obtener registros pendientes | Nodo HTTP Request (polling) |
| `GET` | `/api/health` | Verificar estado del bridge | Monitoreo |

### Enviar un comando (POST /api/command)

```bash
curl -X POST http://localhost:5000/api/command \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "AG001",
    "command": "ipconfig",
    "command_type": "shell",
    "task_id": "TASK001"
  }'
```

Respuesta:

```json
{
  "status": "accepted",
  "topic": "c2/cmd/AG001",
  "task_id": "TASK001",
  "agent_id": "AG001"
}
```

> 💡 La respuesta es `202 Accepted` — el bridge encoló el mensaje, pero la entrega al broker es asíncrona (QoS 1). Si el broker rechaza el mensaje (ACL), se loguea en el bridge.

### Recibir resultados (GET /api/results)

```bash
curl http://localhost:5000/api/results
```

Respuesta:

```json
[
  {
    "task_id": "TASK001",
    "agent_id": "AG001",
    "status": "completed",
    "output": "Windows IP Configuration...\n..."
  }
]
```

Los resultados se descifran automáticamente antes de entregarlos a n8n.
n8n **nunca toca crypto**.

### Recibir registros (GET /api/agents)

```bash
curl http://localhost:5000/api/agents
```

Respuesta:

```json
[
  {
    "agent_id": "AG001",
    "hostname": "PC-LAB01",
    "os": "Windows 11",
    "username": "agente"
  }
]
```

### Configurar n8n

En n8n, se usan **nodos HTTP Request** para hablar con el bridge:

1. **Workflow de comando**: nodo HTTP Request → `POST http://localhost:5000/api/command`
2. **Workflow de resultados**: nodo HTTP Request → `GET http://localhost:5000/api/results` (polling cada 5-10 segundos con un nodo Schedule Trigger)
3. **Workflow de registros**: nodo HTTP Request → `GET http://localhost:5000/api/agents` (igual, polling)

> 💡 El bridge bufferiza los resultados en memoria (máximo 1000 mensajes).
> Cada GET consume y limpia el buffer, así que no hay duplicados.

---

## 7. Gestión de Certificados

### Jerarquía de certificados

```
CA (SarabhelCA)
 ├── server.crt (CN=c2-broker)     → para Mosquitto
 ├── AG001.crt (CN=AG001)          → para el agente 1
 ├── AG002.crt (CN=AG002)          → para el agente 2
 ├── bridge.crt (CN=crypto-bridge) → para el bridge HTTP
 └── n8n-server.crt (si aplica)    → para n8n (si se conecta directo)
```

### Regenerar todos los certificados

Si es necesario regenerar desde cero (por ejemplo, si la CA se pierde):

```bash
cd c2-broker
bash scripts/gen-certs.sh
```

Esto genera:
- `config/certs/ca.crt` + `ca.key` — CA
- `config/certs/server.crt` + `server.key` — certificado del broker (CN=c2-broker)
- `config/certs/AG001.crt` + `AG001.key` — certificado del agente de ejemplo (CN=AG001)
- `config/certs/bridge.crt` + `bridge.key` — certificado del bridge (CN=crypto-bridge)

### Generar certificado para un agente nuevo

```bash
cd c2-broker
bash scripts/gen-agent-cert.sh AG002
# → genera config/certs/AG002.crt + AG002.key
```

Luego se distribuye al agente: `ca.crt`, `AG002.crt`, `AG002.key`.

### Verificar un certificado

```bash
# Verificar que está firmado por la CA
openssl verify -CAfile config/certs/ca.crt config/certs/AG001.crt

# Verificar el CN (debe coincidir con agent_id)
openssl x509 -in config/certs/AG001.crt -noout -subject

# Verificar fechas de validez
openssl x509 -in config/certs/AG001.crt -noout -dates
```

---

## 8. Políticas de Acceso (ACL)

### Archivo `config/acl.conf`

El broker Mosquitto utiliza un archivo ACL para controlar qué clientes
pueden publicar y suscribirse a cada tópico. Las reglas usan `%u` que es
el username del cliente (en nuestro caso, el CN del certificado).

```aconf
# ACL para C2 - Sarabhel
# %u = username (CN del certificado), %c = client_id

# ---- n8n: orquestación remota ----
user n8n-server
topic write c2/cmd/#
topic read c2/res/#
topic read c2/agents/register

# ---- Bridge HTTP: proxy criptográfico entre n8n y MQTT ----
user crypto-bridge
topic write c2/cmd/#
topic read c2/res/#
topic read c2/agents/register

# ---- Reglas anónimas (aplican a todos los clientes) ----
pattern write c2/agents/register
pattern read c2/cmd/%u
pattern write c2/res/%u
```

### Cómo funciona

| Cliente | Puede hacer | No puede hacer |
|---|---|---|
| **AG001** (CN=AG001) | Escribir `c2/agents/register`, leer `c2/cmd/AG001`, escribir `c2/res/AG001` | Leer comandos de AG002, escribir en tópicos de otros |
| **AG002** (CN=AG002) | Escribir `c2/agents/register`, leer `c2/cmd/AG002`, escribir `c2/res/AG002` | Igual, aislado de AG001 |
| **crypto-bridge** | Publicar en cualquier `c2/cmd/#`, leer cualquier `c2/res/#` | N/A (tiene todos los permisos que necesita) |

---

## 9. Gestión de Políticas de Seguridad

### Reglas obligatorias

| Regla | Detalle |
|---|---|
| **No versionar claves** | `*.key` está en `.gitignore`. Si alguien sube una clave, **rotar inmediatamente**. |
| **Cada agente tiene su cert** | No compartir certificados entre agents. Cada uno tiene el suyo con su propio CN. |
| **El CN es el agent_id** | El identificador del agente en el sistema DEBE coincidir con el CN de su certificado. |
| **Nonce state en volumen persistente** | El `state_file` de crypto_lib nunca debe ir en `/tmp` o en un filesystem efímero. |
| **Rotación de claves** | Si una PSK o clave privada se compromete, regenerar TODO y redistribuir. |
| **No compartir la PSK por canales inseguros** | La PSK viaja en persona o por canal cifrado (Signal, etc.), nunca por Slack/GitHub. |

---

## 10. Checklist de Integración

Antes de decir "ya funciona", verificar:

### Para cada agente

- [ ] El agente tiene `ca.crt`, `AGXXX.crt`, `AGXXX.key`
- [ ] El CN del cert del agente coincide con su `agent_id`
- [ ] La PSK (`crypto_lib/psk.key`) se cargó desde un archivo local (no de Git)
- [ ] El `state_file` apunta a un volumen persistente
- [ ] El agente usa QoS 1 para publish y subscribe
- [ ] El agente maneja `InvalidTag` (no ejecuta comandos inválidos)

### Para el broker

- [ ] `docker compose up -d` funciona sin errores
- [ ] `config/acl.conf` está configurado y montado
- [ ] Los puertos 8883 están accesibles desde la red de los agents

### Para n8n

- [ ] n8n apunta al bridge en `http://<bridge-ip>:5000`
- [ ] El bridge está corriendo y conectado al broker
- [ ] `curl http://localhost:5000/api/health` responde `{"status": "ok"}`

### End-to-end

- [ ] Un agente se conecta y su register aparece en `GET /api/agents`
- [ ] Se envía un comando vía `POST /api/command` y el agente lo recibe
- [ ] El resultado del comando aparece en `GET /api/results`

---

## 11. Troubleshooting — "Sin Morir en el Intento"

Los errores que matan tiempo en la demo, ordenados por probabilidad de ocurrencia.

### ❌ Certificados (lo más común)

| Error | Síntoma | Solución |
|---|---|---|
| **El CN del cert no coincide con agent_id** | Conexión exitosa pero ACL deniega todo | `openssl x509 -in agent.crt -noout -subject` → verificar CN |
| **Falta `ca.crt` en el agente** | `TLS handshake failed` | Copiar `config/certs/ca.crt` al agente |
| **Certificado vencido** | `certificate expired` | `openssl x509 -in agent.crt -noout -dates` → regenerar |
| **CA.key con passphrase** | Mosquitto no arranca | Regenerar CA con `-nodes` (usar `scripts/gen-certs.sh`) |

### ❌ Broker

| Error | Síntoma | Solución |
|---|---|---|
| **Puerto no mapeado** | `Connection refused` | `docker compose ps` → verificar que `8883` esté en `PORTS` |
| **ACL no cargada** | Operaciones denegadas sin motivo claro | Verificar que `acl_file` esté en `mosquitto.conf` y el archivo exista |
| **allow_anonymous true** | Cualquiera se conecta | Verificar que esté en `false` |
| **Container no corre** | `docker ps` no muestra `c2_redirector` | `docker compose logs` para ver el error |

### ❌ Crypto

| Error | Síntoma | Solución |
|---|---|---|
| **state_file en /tmp dentro del container** | Nonce se reusa al reiniciar, AES-GCM explota silenciosamente | Montar volumen Docker para el state file |
| **PSK diferente entre bridge y agente** | `InvalidTag` al descifrar siempre | Usar el MISMO archivo `crypto_lib/psk.key` en todos los nodos |
| **Payload no tiene iv/ciphertext/tag** | `KeyError` o `InvalidTag` | El payload MQTT debe ser `{"iv","ciphertext","tag"}`. Si es plano, no pasa por crypto_lib. |

### ❌ Bridge

| Error | Síntoma | Solución |
|---|---|---|
| **Bridge no conecta al broker (cert CN ≠ hostname)** | `/api/health` → `mqtt_connected: false`, log: `hostname mismatch` | El server cert tiene `CN=c2-broker`. Si el bridge conecta a `localhost`, el hostname no coincide. El bridge ya incluye `tls_insecure_set(True)` para desarrollo. En producción, usar un DNS que resuelva al CN del cert o regenerar el cert con SAN. |
| **n8n no llega al bridge** | `Connection refused` desde n8n | `curl http://localhost:5000/api/health` desde la misma máquina que n8n |
| **Bridge no encuentra PSK** | `PSK file not found: crypto_lib/psk.key` | `python3 crypto_lib/cipher.py genkey crypto_lib/psk.key` o apuntar `PSK_FILE` a la ruta correcta |

### ❌ Red

| Error | Síntoma | Solución |
|---|---|---|
| **Agente no llega al broker** | `Connection refused` o timeout | Verificar IP/firewall. El broker escucha en `0.0.0.0:8883` |
| **Agente y bridge en redes diferentes** | Conexiones lentas o timeout | Asegurar que todos los componentes estén en la misma red o que los puertos estén abiertos |
| **MQTT sin TLS** | `Connection refused` (broker no escucha en 1883) | Conectar siempre a `8883` con TLS |

---

## 12. Comandos de Verificación Rápida

```bash
# 1. Broker está vivo?
docker compose ps
# → c2_redirector   Up   0.0.0.0:8883->8883/tcp

# 2. Bridge responde?
curl http://localhost:5000/api/health
# → {"status":"ok","mqtt_connected":true,"results_buffered":0,"registers_buffered":0}

# 3. Crypto funciona?
cd crypto_lib && python3 -c "
from cipher import Cipher, generate_key
key = generate_key()
c = Cipher(key, state_file='/tmp/test.state')
e = c.encrypt_to_json('ping')
print('cifrado:', e)
d = c.decrypt_from_json(e)
print('descifrado:', d.decode())
"

# 4. Verificar CN de un certificado
openssl x509 -in config/certs/AG001.crt -noout -subject
# → CN=AG001

# 5. Verificar que está firmado por CA
openssl verify -CAfile config/certs/ca.crt config/certs/AG001.crt
# → AG001.crt: OK

# 6. Probar conexión MQTT (si mosquitto_clients está instalado)
# mosquitto_pub --cafile config/certs/ca.crt --cert config/certs/bridge.crt \
#   --key config/certs/bridge.key -h localhost -p 8883 -t "c2/agents/register" \
#   -m '{"agent_id":"test"}' -d
```

---

## 13. Estructura del Proyecto

```
c2-broker/                         ← Directorio raíz del C2 Broker
│
├── bridge/                         ← Bridge HTTP para n8n
│   ├── bridge.py                   ←   API Flask (cifra/descifra, HTTP ↔ MQTT)
│   ├── Dockerfile                  ←   Imagen Docker para el bridge
│   └── requirements.txt            ←   Dependencias Python
│
├── config/                         ← Configuración del broker Mosquitto
│   ├── acl.conf                    ←   Reglas de acceso por tópico
│   ├── certs/                      ←   Certificados TLS
│   │   ├── ca.crt                  ←     CA (distribuir a todos)
│   │   ├── ca.key                  ←     CA (NUNCA distribuir)
│   │   ├── server.crt              ←     Broker (CN=c2-broker)
│   │   ├── server.key              ←     Broker (NUNCA distribuir)
│   │   ├── agent.crt               ←     Agente ejemplo (CN=AG001)
│   │   ├── agent.key               ←     Agente ejemplo
│   │   ├── bridge.crt              ←     Bridge (CN=crypto-bridge)
│   │   └── bridge.key              ←     Bridge
│   ├── mosquitto.conf              ←   Config principal del broker
│
├── crypto_lib/                     ← Módulo de cifrado AES-256-GCM
│   ├── __init__.py                 ←   Exporta Cipher, generate_key
│   ├── cipher.py                   ←   Implementación AES-GCM con nonce persistence
│   ├── test_cipher.py              ←   Tests unitarios de cipher.py
│   └── psk.key                     ←   PSK (NO versionar)
│
├── scripts/                        ← Utilidades
│   ├── gen-certs.sh                ←   Regenerar todos los certificados
│   ├── gen-agent-cert.sh           ←   Generar cert para un agente nuevo
│   └── deploy.sh                   ←   Deploy automático a VM
│
├── data/                           ← Persistencia del broker (Docker volume)
├── log/                            ← Logs del broker (Docker volume)
│
├── docker-compose.yml              ← Orquestación del broker + bridge
├── test_comms.py                   ← Prueba de comunicación MQTT desde terminal
├── test_full.py                    ← Prueba completa (register + command + result)
├── README.md                       ← Este documento
└── mik4ela-C2.md                   ← (Symlink/pointer a README.md)
```
