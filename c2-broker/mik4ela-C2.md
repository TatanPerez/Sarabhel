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

## 4. Requisitos para el Agente

Para que el agente pueda conectarse, debe cumplir con:

1. Certificados: Poseer ca.crt, agent.crt y agent.key. La conexión fallará si no presenta el certificado firmado por la CA.

2. Persistencia: Si el agente se reinicia, debe mantener un estado de contador para evitar la reutilización de iv (nonce), utilizando la funcionalidad state_file de crypto_lib.

3. Error Handling: Si el descifrado falla (InvalidTag), el agente no debe ejecutar nada y debe reportar un error de autenticación al servidor.

## 5. Gestión de Políticas

- NUNCA incluir psk.key ni archivos .key en el control de versiones (Git).

- Utilizar variables de entorno o archivos locales no versionados para cargar las rutas de los certificados.

- Si una clave es comprometida, debe rotarse inmediatamente en todos los nodos (Agentes y n8n).

## 6. Estructura del Payload

Cualquier mensaje que viaje por el Broker debe seguir estrictamente este formato JSON:

```json
{
  "iv": "base64_string",
  "ciphertext": "base64_string",
  "tag": "base64_string"
}
```

Si el JSON no contiene estos tres campos, el sistema lo descartará automáticamente.
