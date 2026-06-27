# Sarabhel

Hackathon Talento Tech 2

Sarabhel es un laboratorio local de Command & Control (C2) para una hackathon de ciberseguridad. El stack se levanta con Docker Compose, usa MQTT para la comunicacion entre servidor y agentes, expone una API REST con FastAPI y persiste agentes, comandos y resultados en PostgreSQL.

> Uso previsto: entorno local/autorizado de laboratorio. No esta pensado para uso ofensivo fuera de un ambiente controlado.

## Estado Actual

El stack principal ya levanta y el flujo basico esta funcionando:

- `c2_server`: servidor FastAPI activo en el puerto `8000`.
- `cli`: contenedor de operador persistente, usado con `docker exec`.
- `agent`: agente de prueba `myagent1`, conectado por MQTT.
- `mosquitto`: broker MQTT interno.
- `postgres`: base de datos para agentes, comandos y resultados.
- `n8n`: servicio auxiliar disponible en el puerto `5678`.

Flujo validado:

1. El agente se conecta a Mosquitto.
2. El agente publica registro en `c2/register`.
3. El servidor persiste el agente en PostgreSQL.
4. El CLI lista agentes por API REST.
5. El CLI envia comandos al servidor.
6. El servidor persiste el comando y lo publica por MQTT.
7. El agente ejecuta comandos permitidos.
8. El agente publica resultados en MQTT.
9. El servidor guarda resultados y marca el comando como `COMPLETED`.

## Arquitectura

```text
CLI -> FastAPI C2 Server -> PostgreSQL
              |
              v
          Mosquitto MQTT
              |
              v
            Agent
```

Servicios principales:

- `c2_server`: API REST, callbacks MQTT, casos de uso y persistencia.
- `cli`: interfaz de operador para listar agentes, enviar comandos y ver resultados.
- `agent`: proceso que se registra, envia heartbeats, recibe comandos y publica resultados.
- `mosquitto`: broker MQTT para eventos internos.
- `postgres`: almacenamiento de agentes, comandos y resultados.
- `n8n`: automatizacion/observabilidad para extender el laboratorio.

Topicos MQTT usados:

- `c2/register`: registro inicial del agente.
- `c2/heartbeat/<agent_id>`: heartbeat periodico del agente.
- `c2/commands/<agent_id>`: comandos enviados al agente.
- `c2/results/<agent_id>`: resultados publicados por el agente.
- `c2/logs/<source>`: canal reservado para eventos/logs.

## Levantar el Stack

Desde la raiz del proyecto:

```bash
docker compose up -d --build
```

Ver estado de contenedores:

```bash
docker compose ps
```

Ver logs:

```bash
docker compose logs -f c2_server
docker compose logs -f agent
docker compose logs -f mosquitto
```

Detener el stack:

```bash
docker compose down
```

## Verificar Salud del Servidor

Health check desde el host:

```bash
curl http://localhost:8000/health
```

Respuesta esperada:

```json
{"status":"ok"}
```

Tambien existe el health bajo el prefijo de API:

```bash
curl http://localhost:8000/api/v1/health
```

## Uso del CLI

El contenedor `cli` queda vivo para operar con `docker exec`.

Listar agentes registrados:

```bash
docker exec c2_cli python cli.py list-agents
```

Enviar comando `system_info` al agente por defecto:

```bash
docker exec c2_cli python cli.py send myagent1 system_info
```

Ver resultados guardados del agente:

```bash
docker exec c2_cli python cli.py watch myagent1
```

Monitorear eventos MQTT de logs:

```bash
docker exec c2_cli python cli.py events
```

## Comandos Permitidos por el Agente

El agente actual solo ejecuta comandos whitelisted:

- `system_info`: ejecuta `uname -a`.
- `file_op`: lista `/tmp`.
- `net_tool`: ejecuta `ping -c 2 8.8.8.8`.

Ejemplos:

```bash
docker exec c2_cli python cli.py send myagent1 system_info
docker exec c2_cli python cli.py send myagent1 file_op
docker exec c2_cli python cli.py send myagent1 net_tool
```

Luego consultar resultados:

```bash
docker exec c2_cli python cli.py watch myagent1
```

## API REST

La API publica sus rutas bajo `/api/v1`.

Headers requeridos para rutas protegidas:

```text
X-API-Key: supersecretapikey
```

Endpoints principales:

- `GET /health`: health check raiz.
- `GET /api/v1/health`: health check de la API.
- `GET /api/v1/agents`: lista agentes registrados.
- `GET /api/v1/agents/{agent_id}`: obtiene un agente.
- `POST /api/v1/agents/{agent_id}/command`: envia un comando.
- `GET /api/v1/agents/{agent_id}/results`: lista resultados del agente.

Ejemplo con `curl`:

```bash
curl -H "X-API-Key: supersecretapikey" http://localhost:8000/api/v1/agents
```

Enviar comando por API:

```bash
curl -X POST \
  -H "X-API-Key: supersecretapikey" \
  -H "Content-Type: application/json" \
  -d '{"command_type":"system_info","args":{}}' \
  http://localhost:8000/api/v1/agents/myagent1/command
```

## Base de Datos

PostgreSQL se levanta como servicio `postgres` con el contenedor `db`.

Credenciales actuales de desarrollo:

- Usuario: `c2_user`
- Password: `secret_password`
- Base de datos: `c2db`

Entrar a `psql`:

```bash
docker exec -it db psql -U c2_user -d c2db
```

Consultas utiles:

```sql
select agent_id, capabilities, last_seen, registered_at from agents;
select id, agent_id, command_type, status, completed_at from commands order by id;
select command_id, agent_id, exit_code, created_at from results order by id;
```

Las tablas se crean automaticamente al arrancar `c2_server`.

## Configuracion

Las variables principales estan en `docker-compose.yml`:

- `C2_STATIC_TOKEN`: token compartido para registro del agente.
- `C2_API_KEY`: API key usada por el CLI y clientes REST.
- `MQTT_HOST`, `MQTT_PORT`, `MQTT_USER`, `MQTT_PASSWORD`: conexion MQTT.
- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`: conexion PostgreSQL.

El broker Mosquitto esta configurado para desarrollo local con:

```text
allow_anonymous true
```

Aunque los contenedores pasan usuario/password MQTT, el broker no esta exigiendo autenticacion en este modo de laboratorio.

## Cambios Realizados Recientemente

- Se corrigio el Dockerfile del servidor para copiar el paquete en `/app/app`.
- Se agregaron dependencias faltantes: `aiomqtt` y `pydantic-settings`.
- Se actualizo `BaseSettings` para Pydantic v2.
- Se corrigieron imports internos en repositorios, DI y casos de uso.
- Se implemento el contenedor DI en `c2_server/app/infrastructure/di.py`.
- Se ajusto `aiomqtt` a la API actual (`identifier`, `MqttError`).
- Se corrigieron las entidades `Command` y `Result`.
- Se conectaron callbacks MQTT para registro, heartbeat y resultados.
- Se corrigio la publicacion de comandos con `command_id`.
- Se corrigio el bug del agente al devolver stdout/stderr.
- Se dejo el CLI como contenedor persistente para uso con `docker exec`.
- Se agrego healthcheck para que `agent` y `cli` esperen a que `c2_server` este listo.

## Pendientes y Mejoras

- Quitar `version: "3.9"` de `docker-compose.yml`; Docker Compose lo marca como obsoleto.
- Actualizar callbacks de `paho-mqtt` en el agente para eliminar el `DeprecationWarning`.
- Mejorar autenticacion real de Mosquitto con `password_file` si se quiere salir del modo laboratorio.
- Agregar tests automatizados para API, repositorios y flujo MQTT.
- Agregar migraciones formales con Alembic en lugar de depender solo de `Base.metadata.create_all`.
- Endurecer validacion de comandos y argumentos antes de publicarlos al agente.

## Comandos de Desarrollo

```bash
pytest
ruff format
ruff check
mypy
```

Si se cambian dependencias o Dockerfiles:

```bash
docker compose up -d --build
```

Si solo se quiere reiniciar un servicio:

```bash
docker compose restart c2_server
docker compose restart agent
```

## Seguridad

- Este proyecto debe usarse solo en ambientes autorizados.
- Los comandos del agente estan limitados por whitelist.
- Los secretos actuales son de desarrollo y estan visibles en `docker-compose.yml`.
- Para un entorno mas serio, mover secretos a `.env`, habilitar autenticacion real en Mosquitto, limitar redes y revisar permisos de comandos.

