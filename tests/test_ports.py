from __future__ import annotations

from gitea_sandbox_adapter.ports import select_ports


def test_select_ports_chooses_alternatives_for_occupied_defaults() -> None:
    unavailable = {3000, 2222}

    http_port, ssh_port = select_ports(
        3000,
        2222,
        is_available=lambda port: port not in unavailable,
    )

    assert http_port != 3000
    assert ssh_port != 2222
    assert http_port != ssh_port
