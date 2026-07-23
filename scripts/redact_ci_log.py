"""Redact raw CI diagnostic logs before artifact upload."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from gitea_sandbox_adapter.ci_redaction import redact_ci_log_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="raw log path")
    parser.add_argument("output", help="redacted log path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    redact_ci_log_file(Path(args.input), Path(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
