# Transporte y Criptografia

Se diseña un canal C2 con MQTT, donde se utiliza contenedores docker para aislar el Broker. El Broker actuara como un proxy asincrono y tendra en cuenta los siguientes puntos:

- Se elige AES en modo GCM, ya que proporciona cifrado y auth simultaneamente. Se genera un Nonce Script criptograficamente seguro y aleatorio para cada mensaje enviado.

- Calidad de servicio QoS, para no perder mensajes si el agente esta dormido. Se configura el Pub y en Sub con QoS1 o QoS2 para retener el mensaje mientras el agente despierta.

- Topicos Opacos, tendran identificadores unicos y una estructura plana.

## Integración del Sistema C2 (Sarabhel)

Este documento define el contrato de comunicación e integración entre el servidor (n8n), el Broker MQTT y los Agentes.

## 1. Arquitectura de Seguridad

La infraestructura utiliza **mTLS** para el transporte de red y **AES-256-GCM** para la envoltura de los mensajes (payload).

- **Broker:** `c2-broker` (Escucha en puerto 8883)
- **Módulo de Criptografía:** `crypto_lib`
- **Protocolo:** MQTT 3.1.1 o 5.0

## 2. Contrato de Comunicación (Tópicos)

Para mantener el orden, se deben seguir estrictamente estas estructuras de tópicos:

- **Comandos:** `c2/cmd/{agent_id}` (n8n publica aquí)
- **Resultados:** `c2/res/{agent_id}` (Agente publica aquí)

_Nota: Reemplazar `{agent_id}` por el identificador único del agente._

## 3. Uso del Módulo `crypto_lib`

El equipo de desarrollo debe importar el módulo desde la raíz del proyecto.

### Ejemplo de uso (Python):

```python
from crypto_lib.cipher import Cipher

# 1. Cargar la clave PSK (Pre-Shared Key) de forma segura
with open("psk.key", "rb") as f:
    psk = f.read()

# 2. Inicializar cifrador
cipher = Cipher(psk)

# 3. Cifrar (para enviar)
mensaje_cifrado = cipher.encrypt_to_json("whoami")

# 4. Descifrar (al recibir)
comando_bytes = cipher.decrypt_from_json(mensaje_cifrado)
comando_str = comando_bytes.decode('utf-8')
```
