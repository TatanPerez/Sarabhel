# c2_server/app/transport/api/routers.py

"""FastAPI routers that expose the C2 server's public interface.

All endpoints are prefixed with `/api/v1` at the FastAPI application level.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel

# Importa los casos de uso y el contenedor DI
from ...application.use_cases.dispatch_command import DispatchCommand
from ...infrastructure.di import (
    get_dispatch_command_use_case,
)
from ...infrastructure.repositories import AgentRepository, ResultRepository
from ...infrastructure.Base import get_db
from ...settings import settings

router = APIRouter()


# ------------------------------------------------------------
# Pydantic schemas for request/response bodies
# ------------------------------------------------------------
class CommandRequest(BaseModel):
    command_type: str
    args: Optional[dict] = None


class AgentResponse(BaseModel):
    agent_id: str
    capabilities: List[str]
    last_seen: Optional[str] = None
    registered_at: str


class CommandResponse(BaseModel):
    id: int
    agent_id: str
    command_type: str
    status: str
    created_at: str
    completed_at: Optional[str] = None


class ResultResponse(BaseModel):
    command_id: int
    agent_id: str
    stdout: str
    stderr: str
    exit_code: Optional[int] = None
    created_at: str


# ------------------------------------------------------------
# Dependency: API key validation
# ------------------------------------------------------------
def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    """Ensure the caller provides the correct API key."""
    if x_api_key != settings.c2_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ------------------------------------------------------------
# Endpoint: Health check
# ------------------------------------------------------------
@router.get("/health", include_in_schema=False)
async def health_check():
    """Simple liveness/readiness probe."""
    return {"status": "ok"}


# ------------------------------------------------------------
# Endpoint: List all agents
# ------------------------------------------------------------
@router.get("/agents", response_model=List[AgentResponse], dependencies=[Depends(verify_api_key)])
def list_agents(db = Depends(get_db)):
    repo = AgentRepository(db)
    agents = repo.get_all()
    return [
        AgentResponse(
            agent_id=a.agent_id,
            capabilities=a.capabilities,
            last_seen=a.last_seen.isoformat() if a.last_seen else None,
            registered_at=a.registered_at.isoformat() if a.registered_at else None,
        )
        for a in agents
    ]


# ------------------------------------------------------------
# Endpoint: Get a single agent
# ------------------------------------------------------------
@router.get("/agents/{agent_id}", response_model=AgentResponse, dependencies=[Depends(verify_api_key)])
def get_agent(agent_id: str, db = Depends(get_db)):
    repo = AgentRepository(db)
    agent = repo.get_by_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse(
        agent_id=agent.agent_id,
        capabilities=agent.capabilities,
        last_seen=agent.last_seen.isoformat() if agent.last_seen else None,
        registered_at=agent.registered_at.isoformat() if agent.registered_at else None,
    )


# ------------------------------------------------------------
# Endpoint: Dispatch a command to an agent (REFCTORIZADO)
# ------------------------------------------------------------
@router.post("/agents/{agent_id}/command", response_model=CommandResponse, dependencies=[Depends(verify_api_key)])
async def dispatch_command_to_agent(
    agent_id: str,
    request: CommandRequest,
    dispatch_use_case: DispatchCommand = Depends(get_dispatch_command_use_case)
):
    """
    Dispatches a command to a specific agent using the clean architecture use case.
    """
    # El caso de uso ahora maneja toda la lógica: validación, creación, persistencia y publicación.
    command_entity = await dispatch_use_case.execute(
        agent_id=agent_id,
        command_type_str=request.command_type,
        args=request.args
    )
    
    if not command_entity:
        raise HTTPException(status_code=404, detail="Agent not found or command invalid.")

    return CommandResponse(
        id=command_entity.id,
        agent_id=command_entity.agent_id,
        command_type=command_entity.command_type.value,
        status=command_entity.status.value,
        created_at=command_entity.created_at.isoformat() if command_entity.created_at else None,
        completed_at=command_entity.completed_at.isoformat() if command_entity.completed_at else None,
    )


# ------------------------------------------------------------
# Endpoint: List results for an agent
# ------------------------------------------------------------
@router.get("/agents/{agent_id}/results", response_model=List[ResultResponse], dependencies=[Depends(verify_api_key)])
def list_results(agent_id: str, db = Depends(get_db)):
    repo = ResultRepository(db)
    results = repo.list_by_agent(agent_id)
    return [
        ResultResponse(
            command_id=r.command_id,
            agent_id=r.agent_id,
            stdout=r.stdout,
            stderr=r.stderr,
            exit_code=r.exit_code,
            created_at=r.created_at.isoformat() if r.created_at else None,
        )
        for r in results
    ]
