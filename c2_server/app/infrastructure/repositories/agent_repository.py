"""Repository that abstracts SQLAlchemy operations for the Agent entity."""

from datetime import datetime
from sqlalchemy.orm import Session
from ..models import AgentModel
from ...domain.entities import Agent
from typing import Optional, List


class AgentRepository:
    """CRUD operations for AgentModel mapped to domain ``Agent`` entities."""

    def __init__(self, db: Session):
        self.db = db

    # --------------------------------------------------------------------- #
    # CREATE
    # --------------------------------------------------------------------- #
    def create(self, agent_id: str, capabilities: List[str]) -> Agent:
        """Create a new AgentModel and persist it."""
        db_agent = AgentModel(agent_id=agent_id, capabilities=capabilities)
        self.db.add(db_agent)
        self.db.commit()
        self.db.refresh(db_agent)
        return Agent(
            agent_id=agent_id,
            capabilities=capabilities,
            last_seen=None,
            registered_at=datetime.fromisoformat(db_agent.registered_at.isoformat()),  # type: ignore
        )

    # --------------------------------------------------------------------- #
    # READ
    # --------------------------------------------------------------------- #
    def get_by_id(self, agent_id: str) -> Optional[Agent]:
        """Fetch an Agent by its ``agent_id``."""
        db_agent = self.db.query(AgentModel).filter(AgentModel.agent_id == agent_id).first()
        if db_agent is None:
            return None
        return Agent(
            agent_id=db_agent.agent_id,
            capabilities=db_agent.capabilities,
            last_seen=db_agent.last_seen,
            registered_at=datetime.fromisoformat(db_agent.registered_at.isoformat()),  # type: ignore
        )

    def get_all(self) -> List[Agent]:
        """Fetch all agents."""
        db_agents = self.db.query(AgentModel).all()
        return [
            Agent(
                agent_id=am.agent_id,
                capabilities=am.capabilities,
                last_seen=am.last_seen,
                registered_at=datetime.fromisoformat(am.registered_at.isoformat()),  # type: ignore
            )
            for am in db_agents
        ]

    # --------------------------------------------------------------------- #
    # UPDATE
    # --------------------------------------------------------------------- #
    def update_last_seen(self, agent_id: str, last_seen: datetime) -> Optional[Agent]:
        """Update the ``last_seen`` timestamp for a given agent."""
        db_agent = self.db.query(AgentModel).filter(AgentModel.agent_id == agent_id).first()
        if db_agent is None:
            return None
        db_agent.last_seen = last_seen
        self.db.commit()
        self.db.refresh(db_agent)
        return Agent(
            agent_id=db_agent.agent_id,
            capabilities=db_agent.capabilities,
            last_seen=db_agent.last_seen,
            registered_at=datetime.fromisoformat(db_agent.registered_at.isoformat()),  # type: ignore
        )

    # --------------------------------------------------------------------- #
    # DELETE
    # --------------------------------------------------------------------- #
    def delete(self, agent_id: str) -> bool:
        """Delete an Agent (and its relationships) by ``agent_id``."""
        db_agent = self.db.query(AgentModel).filter(AgentModel.agent_id == agent_id).first()
        if db_agent is None:
            return False
        self.db.delete(db_agent)
        self.db.commit()
        return True
