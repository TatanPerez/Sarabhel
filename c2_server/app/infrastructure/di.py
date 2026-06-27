# c2_server/app/infrastructure/di.py

"""Dependency Injection (DI) container for the application.

This file provides factory functions to create instances of use cases
with all their required dependencies (repositories, services, etc.).
FastAPI's `Depends()` will use these factories.
"""

from sqlalchemy.orm import Session
from fastapi import Depends

from .Base import get_db
from .mqtt_client import mqtt_service
from ..application.use_cases.register_agent import RegisterAgent
from ..application.use_cases.dispatch_command import DispatchCommand
from ..application.use_cases.store_result import StoreResult
from ..application.use_cases.update_heartbeat import UpdateHeartbeat
from .repositories.agent_repository import AgentRepository
from .repositories.command_repository import CommandRepository
from .repositories.result_repository import ResultRepository


def get_register_agent_use_case(
    db: Session = Depends(get_db)
) -> RegisterAgent:
    """Factory for the RegisterAgent use case."""
    agent_repo = AgentRepository(db)
    # mqtt_service no se necesita aquí, ya que el caso de uso no publica eventos
    return RegisterAgent(agent_repository=agent_repo, mqtt_client=None)


def get_dispatch_command_use_case(
    db: Session = Depends(get_db)
) -> DispatchCommand:
    """Factory for the DispatchCommand use case."""
    agent_repo = AgentRepository(db)
    command_repo = CommandRepository(db)
    # Inyectamos el singleton mqtt_service
    return DispatchCommand(
        agent_repository=agent_repo,
        command_repository=command_repo,
        mqtt_client=mqtt_service
    )


def get_store_result_use_case(
    db: Session = Depends(get_db)
) -> StoreResult:
    """Factory for the StoreResult use case."""
    result_repo = ResultRepository(db)
    command_repo = CommandRepository(db)
    return StoreResult(result_repository=result_repo, command_repository=command_repo)


def get_update_heartbeat_use_case(
    db: Session = Depends(get_db)
) -> UpdateHeartbeat:
    """Factory for the UpdateHeartbeat use case."""
    agent_repo = AgentRepository(db)
    return UpdateHeartbeat(agent_repository=agent_repo)
