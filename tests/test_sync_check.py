"""The Sync check, run as the Owner runs it, against a real Calendar Server."""

import os
import subprocess
import sys
from pathlib import Path

from conftest import MAKE_SECRETS, OWNER, PASSWORD, CalendarServer, StartServer, free_port


def sync_check(
    url: str, certificate: Path, password: str = PASSWORD
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "personal_calendar.sync_check",
         url, "--user", OWNER, "--certificate", str(certificate)],
        env={**os.environ, "CALENDAR_PASSWORD": password},
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_passes_against_a_working_calendar_server(start_server: StartServer) -> None:
    server: CalendarServer = start_server()

    result = sync_check(server.url, server.certificate)

    assert result.returncode == 0, result.stdout + result.stderr


def failed_steps(result: subprocess.CompletedProcess[str]) -> list[str]:
    return [
        line.removeprefix("FAIL").strip().split(":")[0]
        for line in result.stdout.splitlines()
        if line.startswith("FAIL")
    ]


def test_fails_when_the_calendar_server_lets_anyone_in(
    start_server: StartServer,
) -> None:
    server = start_server(auth_type="none")

    result = sync_check(server.url, server.certificate)

    assert result.returncode != 0
    assert failed_steps(result) == ["wrong password is refused"]


def test_fails_when_the_calendar_server_serves_plain_http(
    start_server: StartServer,
) -> None:
    server = start_server(ssl_enabled=False)
    https_url = server.url.replace("http://", "https://")

    result = sync_check(https_url, server.certificate)

    assert result.returncode != 0
    assert "plain HTTP is refused" in failed_steps(result)


def first_failure(result: subprocess.CompletedProcess[str]) -> str:
    return next(line for line in result.stdout.splitlines() if line.startswith("FAIL"))


def test_says_when_the_password_is_wrong(start_server: StartServer) -> None:
    server = start_server()

    result = sync_check(server.url, server.certificate, password="not the password")

    assert result.returncode != 0
    assert "refused the password" in first_failure(result)


def test_says_when_the_certificate_is_not_the_calendar_servers(
    start_server: StartServer, tmp_path: Path
) -> None:
    server = start_server()
    other = tmp_path / "other"
    subprocess.run(
        [sys.executable, MAKE_SECRETS, other, "--name", "localhost"],
        input="x\n", text=True, check=True,
    )

    result = sync_check(server.url, other / "server.crt")

    assert result.returncode != 0
    assert "certificate is not the one given" in first_failure(result)


def test_says_when_the_calendar_server_cannot_be_reached(
    start_server: StartServer,
) -> None:
    server = start_server()
    unused = f"https://localhost:{free_port()}/"

    result = sync_check(unused, server.certificate)

    assert result.returncode != 0
    assert "cannot reach" in first_failure(result)
