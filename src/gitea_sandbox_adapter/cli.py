"""Command line interface for the Gitea sandbox adapter."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import cast

from gitea_sandbox_adapter import __version__
from gitea_sandbox_adapter.browser_validation import validate_browser
from gitea_sandbox_adapter.config import SandboxConfig, load_config
from gitea_sandbox_adapter.diagnostics import diagnose
from gitea_sandbox_adapter.docker import DockerRunner
from gitea_sandbox_adapter.errors import SandboxError
from gitea_sandbox_adapter.population import populate
from gitea_sandbox_adapter.redaction import redact
from gitea_sandbox_adapter.snapshot import (
    create_snapshot,
    reset_sandbox,
    restore_snapshot,
)
from gitea_sandbox_adapter.validation import (
    validate_api,
    validate_postgres,
    validate_runtime,
)

COMMANDS: tuple[str, ...] = (
    "start",
    "stop",
    "status",
    "populate",
    "validate",
    "snapshot",
    "restore",
    "reset",
    "diagnose",
)

Handler = Callable[[argparse.Namespace], int]


def _config_and_docker() -> tuple[SandboxConfig, DockerRunner]:
    config = load_config()
    return config, DockerRunner(config)


def _handle_start(_args: argparse.Namespace) -> int:
    config, docker = _config_and_docker()
    docker.check_docker_available()
    docker.compose_config()
    docker.ensure_images()
    docker.up()
    statuses = docker.wait_for_healthy()
    print("Gitea sandbox started.")
    for status in statuses:
        print(f"{status.service}: state={status.state} health={status.health}")
    print(f"Gitea URL: {config.root_url}")
    print(f"Gitea SSH endpoint: ssh://localhost:{config.ssh_port}")
    return 0


def _handle_stop(_args: argparse.Namespace) -> int:
    config, docker = _config_and_docker()
    docker.down_preserve_volumes()
    print("Gitea sandbox stopped. Persistent named volumes were preserved.")
    return 0


def _handle_status(_args: argparse.Namespace) -> int:
    config, docker = _config_and_docker()
    statuses = docker.all_statuses()
    for status in statuses:
        print(f"{status.service}: state={status.state} health={status.health}")
    print(f"HTTP endpoint: {config.root_url}")
    print(f"SSH endpoint: ssh://localhost:{config.ssh_port}")
    return 0 if all(status.is_healthy for status in statuses) else 1


def _handle_populate(_args: argparse.Namespace) -> int:
    config, docker = _config_and_docker()
    docker.wait_for_healthy()
    result = populate(config, docker)
    print(json.dumps(result, indent=2))
    return 0


def _handle_validate(args: argparse.Namespace) -> int:
    config, docker = _config_and_docker()
    result: dict[str, object] = {}
    if not args.browser_only:
        result["runtime"] = validate_runtime(config, docker)
        result["postgres"] = validate_postgres(config, docker)
        result["api"] = validate_api(config, docker)
    if not args.api_only:
        screenshot_dir = Path(args.screenshot_dir) if args.screenshot_dir else None
        result["browser"] = validate_browser(
            config,
            save_screenshots=not args.no_screenshots,
            screenshot_dir=screenshot_dir,
        )
    print(json.dumps(result, indent=2))
    return 0


def _handle_snapshot(args: argparse.Namespace) -> int:
    config, docker = _config_and_docker()
    output = Path(args.output).resolve() if args.output else None
    path = create_snapshot(config, docker, output=output)
    print(f"Snapshot created: {path.relative_to(config.repo_root)}")
    return 0


def _handle_restore(args: argparse.Namespace) -> int:
    config, docker = _config_and_docker()
    result = restore_snapshot(
        config,
        docker,
        Path(args.bundle),
        force=args.force,
        safety_snapshot=not args.no_safety_snapshot,
    )
    print(json.dumps(result, indent=2))
    return 0


def _handle_reset(args: argparse.Namespace) -> int:
    config, docker = _config_and_docker()
    result = reset_sandbox(
        config,
        docker,
        force=args.force,
        safety_snapshot=not args.no_safety_snapshot,
    )
    print(json.dumps(result, indent=2))
    return 0


def _handle_diagnose(args: argparse.Namespace) -> int:
    exit_code, output = diagnose(as_json=args.json)
    print(output)
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitea-sandbox",
        description="Manage a local Gitea and PostgreSQL Docker sandbox.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(
        dest="command_name",
        metavar="<command>",
    )
    start = subparsers.add_parser("start", help="start the Docker sandbox")
    start.set_defaults(command_name="start", handler=_handle_start)

    stop = subparsers.add_parser("stop", help="stop the sandbox and preserve volumes")
    stop.set_defaults(command_name="stop", handler=_handle_stop)

    status = subparsers.add_parser("status", help="inspect sandbox health")
    status.set_defaults(command_name="status", handler=_handle_status)

    populate_parser = subparsers.add_parser(
        "populate", help="populate deterministic data"
    )
    populate_parser.set_defaults(command_name="populate", handler=_handle_populate)

    validate = subparsers.add_parser(
        "validate", help="validate runtime, API, and browser"
    )
    validate_mode = validate.add_mutually_exclusive_group()
    validate_mode.add_argument("--api-only", action="store_true")
    validate_mode.add_argument("--browser-only", action="store_true")
    screenshot_mode = validate.add_mutually_exclusive_group()
    screenshot_mode.add_argument(
        "--screenshot-dir",
        help=(
            "write browser screenshots to this repository-local directory; "
            "tracked evidence paths are used only when explicitly requested"
        ),
    )
    screenshot_mode.add_argument(
        "--no-screenshots",
        action="store_true",
        help="run browser validation without writing screenshots",
    )
    validate.set_defaults(command_name="validate", handler=_handle_validate)

    snapshot = subparsers.add_parser(
        "snapshot", help="create a portable snapshot bundle"
    )
    snapshot.add_argument("--output", help="snapshot output directory")
    snapshot.set_defaults(command_name="snapshot", handler=_handle_snapshot)

    restore = subparsers.add_parser("restore", help="restore a snapshot bundle")
    restore.add_argument("bundle", help="snapshot bundle directory")
    restore.add_argument(
        "--force", action="store_true", help="required destructive confirmation"
    )
    restore.add_argument(
        "--no-safety-snapshot",
        action="store_true",
        help="skip the automatic pre-restore safety snapshot",
    )
    restore.set_defaults(command_name="restore", handler=_handle_restore)

    reset = subparsers.add_parser("reset", help="rebuild the sandbox from scratch")
    reset.add_argument(
        "--force", action="store_true", help="required destructive confirmation"
    )
    reset.add_argument(
        "--no-safety-snapshot",
        action="store_true",
        help="skip the automatic pre-reset safety snapshot",
    )
    reset.set_defaults(command_name="reset", handler=_handle_reset)

    diagnose_parser = subparsers.add_parser(
        "diagnose", help="run read-only diagnostics"
    )
    diagnose_parser.add_argument(
        "--json", action="store_true", help="emit sanitized JSON"
    )
    diagnose_parser.set_defaults(command_name="diagnose", handler=_handle_diagnose)

    return parser


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0

    return cast(Handler, handler)(args)


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(argv)
    except SandboxError as exc:
        print(_console_safe(redact(str(exc))))
        return 1


def _console_safe(text: str) -> str:
    return text.encode("ascii", errors="backslashreplace").decode("ascii")
