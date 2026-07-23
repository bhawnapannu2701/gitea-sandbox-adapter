from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    if os.environ.get("GITEA_SANDBOX_RUN_INTEGRATION") == "1":
        return
    skip_integration = pytest.mark.skip(
        reason="set GITEA_SANDBOX_RUN_INTEGRATION=1 to run real integration tests"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
