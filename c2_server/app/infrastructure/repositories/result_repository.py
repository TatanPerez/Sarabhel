"""Repository for Result entity handling CRUD via SQLAlchemy."""

from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from ..models import ResultModel, CommandModel
from ...domain.entities import Result


class ResultRepository:
    """Encapsulates persistence of Result models, maintaining integration with commands."""

    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------------------
    # CREATE
    # ---------------------------------------------------------------------
    def create(
        self,
        command_id: int,
        agent_id: str,
        stdout: str,
        stderr: str,
        exit_code: int | None = None
    ) -> Result:
        """Create a Result row linked to a Command and Agent."""
        db_result = ResultModel(
            command_id=command_id,
            agent_id=agent_id,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
        )
        self.db.add(db_result)
        self.db.commit()
        self.db.refresh(db_result)
        return Result(
            id=db_result.id,
            command_id=db_result.command_id,
            agent_id=db_result.agent_id,
            stdout=db_result.stdout,
            stderr=db_result.stderr,
            exit_code=db_result.exit_code,
            created_at=db_result.created_at,
        )

    # ---------------------------------------------------------------------
    # READ
    # ---------------------------------------------------------------------
    def get_by_command_id(self, command_id: int) -> Optional[Result]:
        """Fetch a Result by its associated command ID."""
        db_result = self.db.query(ResultModel).filter(ResultModel.command_id == command_id).first()
        if not db_result:
            return None
        return Result(
            id=db_result.id,
            command_id=db_result.command_id,
            agent_id=db_result.agent_id,
            stdout=db_result.stdout,
            stderr=db_result.stderr,
            exit_code=db_result.exit_code,
            created_at=db_result.created_at,
        )

    def list_by_agent(self, agent_id: str) -> List[Result]:
        """Fetch all results for a specific agent."""
        db_results = self.db.query(ResultModel).filter(ResultModel.agent_id == agent_id).all()
        return [
            Result(
                id=res.id,
                command_id=res.command_id,
                agent_id=res.agent_id,
                stdout=res.stdout,
                stderr=res.stderr,
                exit_code=res.exit_code,
                created_at=res.created_at,
            )
            for res in db_results
        ]

    # ---------------------------------------------------------------------
    # UPDATE
    # ---------------------------------------------------------------------
    def update_result(self, result_id: int, new_stdout: str = None, new_stderr: str = None, new_exit_code: int | None = None) -> Optional[Result]:
        """Update fields of an existing Result."""
        db_result = self.db.query(ResultModel).filter(ResultModel.id == result_id).first()
        if not db_result:
            return None
        if new_stdout is not None:
            db_result.stdout = new_stdout
        if new_stderr is not None:
            db_result.stderr = new_stderr
        if new_exit_code is not None:
            db_result.exit_code = new_exit_code
        self.db.commit()
        self.db.refresh(db_result)
        return Result(
            id=db_result.id,
            command_id=db_result.command_id,
            agent_id=db_result.agent_id,
            stdout=db_result.stdout,
            stderr=db_result.stderr,
            exit_code=db_result.exit_code,
            created_at=db_result.created_at,
        )
