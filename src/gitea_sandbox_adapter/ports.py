"""Host port detection helpers."""

from __future__ import annotations

import socket
from collections.abc import Callable


def port_is_available(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind((host, port))
        except OSError:
            return False
    return True


def find_available_port(
    preferred: int,
    *,
    is_available: Callable[[int], bool] = port_is_available,
) -> int:
    if is_available(preferred):
        return preferred
    for candidate in range(preferred + 1, preferred + 200):
        if is_available(candidate):
            return candidate
    raise RuntimeError(f"No available port found near {preferred}.")


def select_ports(
    http_port: int,
    ssh_port: int,
    *,
    is_available: Callable[[int], bool] = port_is_available,
) -> tuple[int, int]:
    selected_http = find_available_port(http_port, is_available=is_available)
    selected_ssh = find_available_port(ssh_port, is_available=is_available)
    if selected_ssh == selected_http:
        selected_ssh = find_available_port(selected_ssh + 1, is_available=is_available)
    return selected_http, selected_ssh
