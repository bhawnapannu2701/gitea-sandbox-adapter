from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.integration
def test_real_runtime_status_and_api_validation() -> None:
    status = subprocess.run(
        [sys.executable, "-m", "gitea_sandbox_adapter", "status"],
        capture_output=True,
        check=False,
        text=True,
        timeout=180,
    )
    assert status.returncode == 0, status.stdout + status.stderr

    validation = subprocess.run(
        [sys.executable, "-m", "gitea_sandbox_adapter", "validate", "--api-only"],
        capture_output=True,
        check=False,
        text=True,
        timeout=300,
    )
    assert validation.returncode == 0, validation.stdout + validation.stderr
