"""Repository for Command entity handling CRUD via SQLAlchemy."""

from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from ..models import CommandModel, AgentModel
from ..domain.entities import Command, CommandStatus, CommandType


class CommandRepository:
    """Encapsulates persistence of Command models, returning domain objects."""

    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------------------
    def create(
        self,
        agent_id: str,
        command_type: CommandType,
        args: dict | None = None,
    ) -> Command:
        """Create a Command row and return the domain ``Command`` object."""
        args = args or {}
        db_cmd = CommandModel(
            agent_id=agent_id,
            command_type=command_type,
            args=args,
            status=CommandStatus.QUEUED,
        )
        self.db.add(db_cmd)
        self.db.commit()
        self.db.refresh(db_cmd)
        return Command(
            id=db_cmd.id,
            agent_id=db_cmd.agent_id,
            command_type=db_cmd.command_type,
            args=db_cmd.args,
            status=db_cmd.status,
            created_at=db_cmd.created_at,
            completed_at=db_cmd.completed_at,
        )

    # ---------------------------------------------------------------------
    # READ
    # ---------------------------------------------------------------------
    def get(self, command_id: int) -> Optional[Command]:
        db_cmd = self.db.query(CommandModel).filter(CommandModel.id == command_id).first()
        if not db_cmd:
            return None
        return Command(
            id=db_cmd.id,
            agent_id=db_cmd.agent_id,
            command_type=db_cmd.command_type,
            args=db_cmd.args,
            status=db_cmd.status,
            created_at=db_cmd.created_at,
            completed_at=db_cmd.completed_at,
        )

    def list_by_agent(self, agent_id: str) -> List[Command]:
        db_cmds = self.db.query(CommandModel).filter(CommandModel.agent_id == agent_id).all()
        return [
            Command(
                id=cmd.id,
                agent_id=cmd.agent_id,
                command_type=cmd.command_type,
                args=cmd.args,
                status=cmd.status,
                created_at=cmd.created_at,
                completed_at=cmd.completed_at,
            )
            for cmd in db_cmds
        ]

    # ---------------------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------------------
    def set_status(
        self, command_id: int, new_status: CommandStatus, completed_at: datetime | None = None
    ) -> Optional[Command]:
        db_cmd = self.db.query(CommandModel).filter(CommandModel.id == command_id).first()
        if not db_cmd:
            return None
        db_cmd.status = new_status
        if completed_at:
            db_cmd.completed_at = completed_at
        self.db.commit()
        self.db.refresh(db_cmd)
        return Command(
            id=db_cmd.id,
            agent_id=db_cmd.agent_id,
            command_type=db_cmd.command_type,
            args=db_cmd.args,
            status=db_cmd.status,
            created_at=db_cmd.created_at,
            completed_at=db_cmd.completed_at,
        )
