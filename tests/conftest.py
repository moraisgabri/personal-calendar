"""A real Calendar Server (Radicale, using the repo's configuration) running
on localhost, for the Sync check to act against as a Device would."""

import base64
import socket
import ssl
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CONFIG = REPO / "calendar-server" / "radicale.conf"
MAKE_SECRETS = REPO / "calendar-server" / "make_secrets.py"

OWNER = "owner"
PASSWORD = "correct horse battery staple"


@dataclass
class CalendarServer:
    url: str
    certificate: Path


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


def wait_until_listening(port: int, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Radicale exited during startup")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            return
        except OSError:
            time.sleep(0.05)
    raise RuntimeError("Radicale did not start listening")


def create_calendar(server: CalendarServer) -> None:
    """Create the Owner's Calendar, as install.sh does on the real qube."""
    request = urllib.request.Request(
        f"{server.url}{OWNER}/calendar/",
        method="MKCALENDAR",
        headers={
            "Authorization": "Basic "
            + base64.b64encode(f"{OWNER}:{PASSWORD}".encode()).decode()
        },
    )
    context = ssl.create_default_context(cafile=str(server.certificate))
    urllib.request.urlopen(request, context=context).close()


@pytest.fixture(scope="session")
def server_secrets(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("secrets")
    subprocess.run(
        [sys.executable, MAKE_SECRETS, directory, "--user", OWNER,
         "--name", "localhost", "--name", "127.0.0.1"],
        input=f"{PASSWORD}\n".encode(),
        check=True,
    )
    return directory


StartServer = Callable[..., CalendarServer]


@pytest.fixture
def start_server(
    tmp_path: Path, server_secrets: Path
) -> Iterator[StartServer]:
    """Start a Calendar Server. Keyword overrides model a misconfigured one."""
    processes: list[subprocess.Popen[bytes]] = []

    def start(*, ssl_enabled: bool = True, auth_type: str = "htpasswd") -> CalendarServer:
        port = free_port()
        process = subprocess.Popen(
            [
                sys.executable, "-m", "radicale",
                "--config", str(CONFIG),
                "--server-hosts", f"127.0.0.1:{port}",
                "--server-ssl" if ssl_enabled else "--no-server-ssl",
                "--server-certificate", str(server_secrets / "server.crt"),
                "--server-key", str(server_secrets / "server.key"),
                "--auth-type", auth_type,
                "--auth-htpasswd-filename", str(server_secrets / "users"),
                "--storage-filesystem-folder", str(tmp_path / f"collections-{port}"),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        processes.append(process)
        wait_until_listening(port, process)
        scheme = "https" if ssl_enabled else "http"
        server = CalendarServer(
            url=f"{scheme}://localhost:{port}/",
            certificate=server_secrets / "server.crt",
        )
        if ssl_enabled:
            create_calendar(server)
        return server

    yield start
    for process in processes:
        process.terminate()
        process.wait()
