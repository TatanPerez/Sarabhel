# Sarabhel
Hackathon Talento Tech 2

## Overview
This repository implements a **local, Docker‑Compose‑orchestrated Command & Control (C2) lab** for a cybersecurity hackathon.  All components run in containers, communicate via MQTT, and persist state in PostgreSQL.

## Quick Start
```bash
# 1. Build and start the whole stack
docker compose up -d

# 2. Verify the server is alive
curl http://localhost:8000/health   # → {"status":"ok"}
```

## Running an Agent
```bash
# In a separate terminal (the image is built from ./agent)
docker run --rm \
  --network sarabhel_c2net \
  -e AGENT_ID=myagent1 \
  -e C2_STATIC_TOKEN=C2_STATIC_TOKEN \
  -e MQTT_HOST=mosquitto \
  -e MQTT_PORT=1883 \
  -e MQTT_USER=c2_user \
  -e MQTT_PASSWORD=c2_pass \
  sarabhel/agent
```
The agent registers itself, sends a heartbeat every 30 s and subscribes to `c2/commands/<agent_id>`.

## Using the Operator CLI
```bash
# Execute commands inside the CLI container
docker exec c2_cli python cli.py list-agents          # show registered agents
docker exec c2_cli python cli.py send myagent1 system_info   # dispatch a command
docker exec c2_cli python cli.py watch myagent1               # stream results
docker exec c2_cli python cli.py events                      # monitor MQTT logs
```
> **Note:** The CLI talks to the FastAPI server via the REST API (`/api/v1`).

## Current Implementation Status
- **Docker‑Compose** – fully functional, all services start.
- **C2 Server** – FastAPI health endpoint works; routes for agents/commands exist.
- **Agent** – connects to MQTT, registers, sends heartbeats, executes whitelisted commands.
- **CLI** – can list agents and send commands, but the server‑side callbacks that persist agents, heartbeats and results are **not yet wired**.
- **MQTT broker** – password authentication requires a `password_file`; create it or set `allow_anonymous true` in `mosquitto.conf` for quick testing.
- **Database** – tables are auto‑created on server start (`Base.metadata.create_all`).
- **Missing pieces** (to be completed):
  1. Persist registration/heartbeat/result messages via the repository layer.
  2. Publish commands from the API to the proper MQTT topic.
  3. Implement the *application* use‑case classes (register agent, dispatch command, store result, update heartbeat).
  4. Add the `agent` service definition to `docker-compose.yml` (currently only Dockerfiles exist).

## Development Commands
- **Run tests** – `pytest` (requires the stack to be up).
- **Run a single test** – `pytest tests/<test_file>.py`.
- **Lint/format** – `ruff format && ruff check`.
- **Type checking** – `mypy`.

## Security Notes
- Secrets are injected via environment variables (`C2_STATIC_TOKEN`, `C2_API_KEY`, `MQTT_USER`, `MQTT_PASSWORD`).
- Containers run as non‑root users.
- MQTT communication is internal‑network only; enable TLS if external exposure is ever required.

---
For more detailed guidance (common commands, architecture overview, key files) see **CLAUDE.md** in the repository root.
