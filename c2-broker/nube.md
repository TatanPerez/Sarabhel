# C2 Broker — Nube

## Qué se hizo

Se levantó el C2 Broker completo en una VM gratuita de Oracle Cloud (Ubuntu 24.04). Todo corre dentro de contenedores Docker:

- **Broker Mosquitto** — recibe conexiones MQTT con TLS en puerto `8883`
- **Bridge HTTP** — API Flask que traduce HTTP ↔ MQTT en puerto `5000`

## Dónde está

```
IP pública: 157.137.238.112
Sistema:    Ubuntu 24.04 (Oracle Cloud Free Tier)
```

## Cómo acceder

### 1. Vía Bridge HTTP (recomendado para n8n y scripts)

Sin certificados, solo HTTP:

```bash
# Health check
curl http://157.137.238.112:5000/api/health

# Enviar comando a un agente
curl -X POST http://157.137.238.112:5000/api/command \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"AG001","command":"whoami","task_id":"T1"}'

# Ver resultados pendientes
curl http://157.137.238.112:5000/api/results
```

### 2. Vía MQTT directo (agentes)

Cada agente necesita sus certificados (`ca.crt`, `AGxxx.crt`, `AGxxx.key`) y conecta así:

```python
import paho.mqtt.client as mqtt

client = mqtt.Client(
    client_id="AG001",
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    protocol=mqtt.MQTTv5,
)
client.tls_set("ca.crt", certfile="AG001.crt", keyfile="AG001.key")
client.tls_insecure_set(True)  # el cert dice CN=c2-broker, no la IP
client.connect("157.137.238.112", 8883)
client.loop_start()
```

### 3. Vía SSH (admin)

```bash
ssh ubuntu@157.137.238.112
```

### Puertos

| Puerto | Protocolo | Uso |
|---|---|---|
| 8883 | TCP/TLS | Broker MQTT |
| 5000 | TCP | Bridge HTTP |
| 22 | TCP | SSH |

### Notas

- **No se usa usuario/contraseña**. La autenticación es por certificado TLS.
- El certificado del servidor tiene `CN=c2-broker`. Al conectar por IP hay que usar `tls_insecure_set(True)` para saltear la verificación de hostname (el cifrado TLS sigue intacto).
- Para generar certificados para nuevos agentes: `bash scripts/gen-agent-cert.sh <ID_AGENTE>`.
