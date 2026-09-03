"""Expose one approved shell command as a model-callable tool."""

import json
import os
import subprocess
from collections.abc import Callable

from . import workspace

COMMAND_TIMEOUT_SECONDS = 30
ApprovalFunction = Callable[[str], bool]

RUN_COMMAND_TOOL = {
    "type": "function",
    "name": "run_command",
    "description": "Run one shell command from the agent workspace after the person approves it.",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The exact shell command to run.",
            }
        },
        "required": ["command"],
        "additionalProperties": False,
    },
    "strict": True,
}


def command_result(
    command: str,
    *,
    approved: bool,
    exit_code: int | None = None,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
    error: str | None = None,
) -> str:
    """Return one command result as JSON for the model."""
    return json.dumps(
        {
            "command": command,
            "approved": approved,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": timed_out,
            "error": error,
        }
    )


def run_command(command: str, approve: ApprovalFunction) -> str:
    """Run one command after explicit approval."""
    if not approve(command):
        return command_result(
            command,
            approved=False,
            error="Denied by user",
        )

    environment = os.environ.copy()
    environment.pop("OPENAI_API_KEY", None)
    environment.pop("UV_ENV_FILE", None)

    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=workspace.resolve_path("."),
            env=environment,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
        )
        return command_result(
            command,
            approved=True,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode(errors="replace") if isinstance(error.stdout, bytes) else error.stdout
        stderr = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else error.stderr
        return command_result(
            command,
            approved=True,
            stdout=stdout or "",
            stderr=stderr or "",
            timed_out=True,
            error=f"Timed out after {COMMAND_TIMEOUT_SECONDS} seconds",
        )
    except Exception as error:
        return command_result(
            command,
            approved=True,
            error=f"{type(error).__name__}: {error}",
        )
