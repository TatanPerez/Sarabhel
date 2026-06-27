# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Common Commands:**  
- `docker compose up -d`: Starts all services (MQTT broker, DB, C2 server, N8n, CLI)  
- `docker compose down`: Stops and removes containers  
- `docker compose run c2_server`: Run the C2 server container  
- `pytest`: Run all tests (requires Docker services running)  
- `pytest <file.py>`: Run specific test file  
- `ruff format`: Format Python code with Ruff  
- `ruff check`: Lint code for issues  
- `mypy`: Run type-checking  
- `python agent/agent.py`: Test the agent process locally  

**High-Level Architecture:**  
1. **Service-Oriented Design**:  
   - Built on Docker Compose with 5 core services:  
     - `mosquitto` (MQTT broker with password auth)  
     - `postgres` (database for persistence)  
     - `c2_server` (FastAPI-based C2 logic)  
     - `n8n` (automation/logging layer)  
     - `cli` (operator interface)  
     - `agent` (Python processes` (Python processes executing commands)  
   - All services communicate over internal Docker network `c2net`.  

2. **Event-Driven Pattern**:  
   - MQTT topics (`c2/results/{agent_id}`, `c2/commands/{agent_id}`) mediate communication  
   - Agents publish results/heartbeats to MQTT, consumed by N8n and stored in DB  

3. **Clean Architecture**:  
   - **Domain layer**: Defines entities (`Agent`, `Command`, `Result`) in `c2_server/app/domain/`  
   - **Infrastructure layer**: Handles MQTT (`aiomqtt`/`paho-mqtt`), DB (SQLAlchemy), and API routing  
   - **Interaction flow**: CLI → FastAPI routes → Application use-cases → Infrastructure  

**Key Files to Understand First:**  
- `docker-compose.yml` (orchestrates all services)  
- `c2_server/app/infrastructure/mqtt_client.py` (MQTT messaging abstraction)  
- `c2_server/app/domain/entities.py` (core domain models)  
- `agent/agent.py` (agent process logic)  

**Security & Patterns:**  
- Secrets stored in environment variables (no hardcoded tokens)  
- Command whitelisting enforced in both agent and server  
- Non-root containers for security  
- Event-driven decoupling between service layers