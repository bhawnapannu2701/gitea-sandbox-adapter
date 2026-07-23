"""Typed exceptions for user-facing command failures."""

from __future__ import annotations


class SandboxError(Exception):
    """Base exception for expected sandbox command failures."""


class ConfigError(SandboxError):
    """Configuration is missing or invalid."""


class CommandError(SandboxError):
    """A host command failed."""


class DockerError(SandboxError):
    """Docker or Docker Compose failed."""


class ApiError(SandboxError):
    """A Gitea API request failed."""


class PopulationError(SandboxError):
    """Deterministic population failed."""


class ValidationError(SandboxError):
    """Validation failed."""


class SnapshotError(SandboxError):
    """Snapshot or restore failed."""
