# Despliegue en la Web

Este documento guarda el contexto y la ruta sugerida para llevar Sarabhel desde un laboratorio local con Docker Compose hacia un entorno accesible desde internet, usando servicios como n8n web y Supabase.

> Uso previsto: entorno autorizado, controlado y de laboratorio. No se debe exponer ni usar como herramienta ofensiva fuera de un ambiente permitido.

## Objetivo

Pasar de un stack local:

```text
CLI -> C2 Server local -> PostgreSQL local
              |
              v
          Mosquitto local
              |
              v
           Agent local
```

a un modelo remoto/autorizado donde agentes puedan conectarse desde distintas redes:

```text
Agentes externos
   |
   v
HTTPS / MQTT seguro
   |
   v
C2 Server accesible remotamente
   |
   v
Supabase PostgreSQL

n8n web conectado por API, webhooks o eventos
```

## Que Falta Para Usarlo Desde Cualquier Lugar

### 1. Endpoint Remoto

Actualmente el `c2_server` vive dentro de Docker local y expone `localhost:8000`. Para usarlo desde fuera se necesita:

- Un dominio o URL publica.
- HTTPS obligatorio.
- Un despliegue del servidor en nube o un tunel/VPN hacia la maquina local.

No se recomienda exponer directamente:

- PostgreSQL.
- Mosquitto sin TLS/autenticacion fuerte.
- Puertos internos de Docker.

### 2. Autenticacion Mas Fuerte

El proyecto usa una API key y un token estatico para agentes. Para un entorno remoto hace falta endurecer esto:

- API keys por operador o JWT.
- Tokens unicos por agente.
- Revocacion de agentes.
- Rotacion de secretos.
- Auditoria de comandos enviados.

El token `C2_STATIC_TOKEN` sirve para laboratorio, pero no deberia ser el unico control en un despliegue remoto.

### 3. MQTT Remoto Seguro

Ahora Mosquitto funciona dentro de la red Docker. Para agentes externos se necesita una de estas opciones:

- Broker MQTT con TLS, usando `mqtts`.
- MQTT sobre WebSockets seguro.
- Broker gestionado en la nube.
- Broker accesible solo por VPN o Zero Trust.

Lo ideal es que los agentes siempre hagan conexiones salientes hacia el servidor/broker. No deberian requerir abrir puertos entrantes en la maquina donde corre el agente.

### 4. Supabase Como Base de Datos

Supabase puede reemplazar PostgreSQL local.

Tablas principales:

- `agents`
- `commands`
- `results`
- `events`

Recomendaciones:

- El backend FastAPI debe conectarse usando credenciales seguras del servidor.
- No se debe exponer la `service_role key` a clientes publicos.
- Si se usa Row Level Security, definir politicas con cuidado.
- Los agentes no deberian escribir directamente comandos ni resultados en Supabase sin pasar por controles del backend, salvo que se disene un flujo muy controlado.

### 5. n8n Web

n8n puede ayudar bastante, pero es mejor usarlo como capa auxiliar y no como nucleo del C2.

Usos recomendados:

- Recibir webhooks desde el C2.
- Alertar cuando un agente se registre.
- Alertar cuando un comando falle.
- Crear reportes.
- Enviar notificaciones a correo, Discord, Telegram, Slack, etc.
- Automatizar workflows de laboratorio.
- Construir paneles simples o integraciones.

El nucleo del sistema deberia seguir siendo:

```text
FastAPI -> Casos de uso -> MQTT/PostgreSQL
```

## Opciones de Despliegue

### Opcion A: Todo Local con Tunel o VPN

```text
Tu PC local con Docker
   |
Cloudflare Tunnel / Tailscale / VPN
   |
Agentes remotos autorizados
```

Ventajas:

- Rapido para demo.
- No requiere mover todo a la nube.
- Mantiene tu entorno local casi igual.

Desventajas:

- Si tu PC se apaga, el C2 deja de operar.
- Depende de tu red local.
- Hay que configurar bien el tunel o VPN.

Esta opcion sirve bien para una hackathon o demo controlada.

### Opcion B: C2 Server en Nube y Base de Datos en Supabase

```text
Agentes externos
   |
   v
C2 Server en VPS / Render / Fly.io / Railway
   |
   v
Supabase PostgreSQL
```

Ventajas:

- Mas estable.
- Accesible desde cualquier lado.
- Supabase maneja la base de datos.

Desventajas:

- Requiere configurar despliegue, variables y seguridad.
- Hay que decidir que hacer con MQTT: broker en nube, broker gestionado o reemplazo por otro canal.

Esta es la ruta recomendada para algo mas parecido a un servicio remoto real.

### Opcion C: Todo en la Nube

```text
C2 Server en nube
Broker MQTT en nube
Supabase PostgreSQL
n8n web
Agentes externos
```

Ventajas:

- Mas disponible.
- Mas cercano a produccion.
- Menos dependencia de la maquina local.

Desventajas:

- Requiere mas hardening.
- Requiere gestionar secretos, TLS, dominios, logs y costos.

### Opcion D: Hibrida

Ejemplo:

```text
C2 Server local
Supabase remoto
n8n web
MQTT local por tunel/VPN
```

Puede funcionar, pero si el servidor local se apaga, el sistema no opera aunque Supabase siga disponible.

## Recomendacion de Ruta

Para avanzar ordenado:

1. Mantener el stack local funcionando como base estable.
2. Mover persistencia a Supabase.
3. Desplegar `c2_server` en nube con HTTPS.
4. Definir estrategia MQTT remota segura.
5. Ajustar agentes para usar URL/broker remoto.
6. Conectar n8n a eventos, webhooks o API.
7. Agregar autenticacion fuerte, auditoria y logs.

## Implementacion Sugerida por Fases

### Fase 1: Preparar Configuracion

- Mover secretos a `.env`.
- Separar configuracion local y remota.
- Evitar secretos hardcodeados en `docker-compose.yml`.
- Documentar variables necesarias.

Variables importantes:

```text
C2_API_KEY
C2_STATIC_TOKEN
MQTT_HOST
MQTT_PORT
MQTT_USER
MQTT_PASSWORD
DB_HOST
DB_PORT
DB_USER
DB_PASSWORD
DB_NAME
DATABASE_URL
```

### Fase 2: Supabase

- Crear proyecto en Supabase.
- Crear tablas equivalentes a las actuales.
- Cambiar `c2_server` para leer `DATABASE_URL`.
- Probar `list-agents`, `send`, `watch`.
- Confirmar que comandos y resultados quedan persistidos.

### Fase 3: Desplegar FastAPI

Opciones posibles:

- VPS con Docker Compose.
- Render.
- Fly.io.
- Railway.
- Cualquier plataforma que soporte contenedores.

Requisitos:

- HTTPS.
- Variables de entorno.
- Healthcheck.
- Logs.
- Reinicio automatico.

### Fase 4: MQTT Remoto

Opciones:

- Mosquitto en VPS con TLS.
- Broker MQTT gestionado.
- MQTT detras de VPN/Tailscale.
- MQTT sobre WebSockets si la plataforma lo facilita.

Pendiente importante:

- No dejar Mosquitto abierto sin autenticacion real.
- No depender de `allow_anonymous true` fuera del laboratorio local.

### Fase 5: n8n

Usar n8n para:

- Alertas de registro de agentes.
- Alertas de comandos completados o fallidos.
- Reportes automaticos.
- Webhooks desde FastAPI.
- Integraciones con canales externos.

Ejemplo de flujo:

```text
C2 Server recibe resultado
   |
   v
Webhook a n8n
   |
   v
n8n envia alerta o actualiza dashboard
```

## Que Puede Quedar Local

No todo tiene que estar en la nube.

Puede quedar local:

- CLI de operador.
- Agentes de laboratorio.
- Entorno de desarrollo.
- n8n local si solo es para pruebas.

Conviene poner remoto:

- `c2_server`, si quieres acceso desde cualquier lugar.
- Base de datos, si quieres persistencia estable.
- Broker MQTT, si los agentes estan fuera de tu red.

## Riesgos y Cuidados

- No exponer PostgreSQL directamente a internet.
- No exponer Mosquitto sin TLS/autenticacion.
- No usar secretos de desarrollo en produccion.
- No permitir comandos arbitrarios sin whitelist.
- Registrar quien envio cada comando.
- Mantener logs de auditoria.
- Definir revocacion de agentes.
- Usar HTTPS siempre.
- Limitar origenes, rate limits y permisos.

## Pendientes Tecnicos Antes de Remotizar

- Quitar `version: "3.9"` de `docker-compose.yml`.
- Actualizar API de callbacks de `paho-mqtt` para quitar warnings.
- Agregar migraciones con Alembic.
- Mejorar validacion de comandos.
- Crear modelo de tokens por agente.
- Agregar tabla de eventos/auditoria.
- Crear configuracion `.env.example`.
- Definir despliegue objetivo: VPS, Render, Fly.io, Railway u otro.

## Resumen de Decision

No es obligatorio tener todo en la nube.

Para demo rapida:

```text
Local + Cloudflare Tunnel/Tailscale
```

Para algo estable:

```text
C2 Server en nube + Supabase + MQTT seguro
```

Para algo mas completo:

```text
C2 Server en nube + Broker MQTT seguro + Supabase + n8n web
```

La ruta recomendada es empezar con Supabase para persistencia, luego desplegar FastAPI con HTTPS y finalmente decidir la estrategia segura de MQTT remoto.

