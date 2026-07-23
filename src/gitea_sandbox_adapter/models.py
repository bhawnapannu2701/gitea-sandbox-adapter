"""Small data models shared by runtime modules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class ServiceStatus:
    service: str
    container_id: str | None
    container_name: str | None
    state: str
    health: str | None

    @property
    def is_healthy(self) -> bool:
        return self.state == "running" and self.health == "healthy"
