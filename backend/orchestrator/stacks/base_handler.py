# stacks/base_handler.py
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, List, Dict, Any, Awaitable, Callable


RunCommand = Callable[[List[str], Optional[str]], Awaitable[Any]]


class StackHandler(ABC):
"""Base contract for a technology stack handler."""


# canonical stack name, e.g. "laravel", "react"...
name: str = "base"


# default test command (can be overridden via config)
default_test_command: List[str] = []


def __init__(self, *, run_command: RunCommand, logger=None, config: Optional[Dict[str, Any]] = None) -> None:
self.run_command = run_command
self.logger = logger
self.config = config or {}


# --- project I/O hooks -------------------------------------------------
@abstractmethod
async def create_project_skeleton(self, code_path: Path, project_name: Optional[str] = None) -> None:
"""Generate minimal scaffold for the stack inside code_path."""


@abstractmethod
async def install_dependencies(self, code_path: Path) -> bool:
"""Install dependencies needed by this stack in code_path."""


# --- testing -----------------------------------------------------------
def get_test_command(self) -> List[str]:
"""Return the configured test command for this stack."""
cmd = self.config.get("test_command")
if isinstance(cmd, list) and cmd:
return cmd
return list(self.default_test_command)


async def run_tests(self, code_path: Path):
"""Execute the stack's test command in code_path."""
cmd = self.get_test_command()
if not cmd:
if self.logger:
self.logger.warning(f"No test command configured for stack '{self.name}'")
return type("CommandResult", (), {"returncode": 0, "stdout": "", "stderr": ""})()
return await self.run_command(cmd, cwd=str(code_path))