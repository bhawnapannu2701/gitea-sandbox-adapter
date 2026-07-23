"""Command line interface for the Phase 1 foundation."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from typing import cast

from gitea_sandbox_adapter import __version__

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


def _handle_unimplemented(args: argparse.Namespace) -> int:
    command_name = str(getattr(args, "command_name"))
    print(f"Command '{command_name}' is not implemented in Phase 1.")
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitea-sandbox",
        description="Phase 1 CLI foundation for gitea-sandbox-adapter.",
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
    for command_name in COMMANDS:
        command_parser = subparsers.add_parser(
            command_name,
            help=f"{command_name} command (not implemented in Phase 1)",
            description=f"{command_name} command (not implemented in Phase 1).",
        )
        command_parser.set_defaults(
            command_name=command_name,
            handler=_handle_unimplemented,
        )

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
    return run(argv)
