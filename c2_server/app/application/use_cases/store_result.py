"""Use‑case for storing a command result received from an agent.

Agents publish to ``c2/results/<agent_id>`` a payload of the form::

    {
        "agent_id": "myagent",
        "command_id": 12,               # Optional – correlation ID from the server
        "result": {
            "stdout": "...",
            "stderr": "...",
            "exit_code": 0
        }
    }

The use‑case creates a ``Result`` record, links it to the command (if present) and
updates the command status to ``COMPLETED``.
"""

from datetime import datetime
from typing import Dict, Any

from ..infrastructure.repositories import ResultRepository, CommandRepository
from ..domain.entities import Result


def store_result(db_session, payload: Dict[str, Any]) -> Result:
    """Persist the result and update the related command status.

    Args:
        db_session: SQLAlchemy session.
        payload: Decoded JSON payload from the MQTT ``c2/results`` topic.
    Returns:
        The created ``Result`` domain object.
    """
    agent_id = payload.get("agent_id")
    command_id = payload.get("command_id")
    result_data = payload.get("result", {})
    stdout = result_data.get("stdout", "")
    stderr = result_data.get("stderr", "")
    exit_code = result_data.get("exit_code")

    # First persist the Result row
    result_repo = ResultRepository(db_session)
    result = result_repo.create(
        command_id=command_id,
        agent_id=agent_id,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
    )

    # If we have a command_id, mark it as completed
    if command_id:
        cmd_repo = CommandRepository(db_session)
        from ..domain.entities import CommandStatus
        cmd_repo.set_status(
            command_id=command_id,
            new_status=CommandStatus.COMPLETED,
            completed_at=datetime.utcnow(),
        )

    return result
