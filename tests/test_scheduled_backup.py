"""A scheduled Backup run on calendar-server, delivering to the vault qube.

calendar-server gets its own home directory, laid out as
calendar-server/install-backups.sh leaves it. qrexec can't run here, so a
stand-in `qrexec-client-vm` plays dom0's policy (only the vault qube, only the
Backup service) and hands the Backup to the repo's real vault service, which
stores it in a folder standing in for the vault qube. A stand-in
`notify-send` records notifications. What dom0 and real qrexec do is checked
by hand (scripts/setup-backup-vault.sh)."""

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from conftest import (
    REPO, SAMPLE_CALENDAR_FILES, StartServer, files_in, make_sample_calendar,
)
from test_calendar_qube import put_event, server_titles
from test_sync_check import sync_check

CALENDAR_BACKUP = REPO / "calendar-server" / "calendar-backup"
VAULT_SERVICE = REPO / "backup-vault" / "personal-calendar.Backup"
BACKUP_PROGRAM = REPO / "src" / "personal_calendar" / "backup.py"
VAULT_QUBE = "calendar-vault"


@dataclass
class CalendarServerQube:
    home: Path
    vault: Path

    @property
    def calendar(self) -> Path:
        return self.home / "radicale" / "collections"

    @property
    def failure_marker(self) -> Path:
        return self.home / "BACKUP-FAILED.txt"

    def settings(self, vault: str = VAULT_QUBE, recipient: str = "") -> None:
        settings = self.home / ".config" / "calendar-backup" / "settings"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text(f"VAULT={vault}\nRECIPIENT={recipient}\n")

    def run_scheduled_backup(self) -> subprocess.CompletedProcess[str]:
        path = f"{self.home / 'bin'}:{Path(sys.executable).parent}:{os.environ['PATH']}"
        return subprocess.run(
            [str(CALENDAR_BACKUP)],
            env={**os.environ, "HOME": str(self.home), "PATH": path},
            capture_output=True,
            text=True,
            timeout=60,
        )

    def notifications(self) -> str:
        log = self.home / "notifications"
        return log.read_text() if log.exists() else ""

    def backups_left_behind(self) -> list[Path]:
        return list(self.home.rglob("*.age"))


def stand_in(path: Path, script: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + script)
    path.chmod(0o755)


@pytest.fixture
def server_qube(tmp_path: Path) -> CalendarServerQube:
    home = tmp_path / "calendar-server"
    vault = tmp_path / "calendar-vault" / "backups"
    vault.mkdir(parents=True)
    make_sample_calendar(home / "radicale" / "collections")
    program = home / ".local" / "lib" / "personal-calendar" / "backup.py"
    program.parent.mkdir(parents=True)
    shutil.copy(BACKUP_PROGRAM, program)
    stand_in(home / "bin" / "notify-send", f'echo "$@" >> {home / "notifications"}\n')
    stand_in(home / "bin" / "qrexec-client-vm", f"""
[ "$1" = {VAULT_QUBE} ] || {{ echo "Request refused" >&2; exit 126; }}
case "$2" in
  personal-calendar.Backup+*) ;;
  *) echo "Request refused" >&2; exit 126 ;;
esac
export VAULT_BACKUPS={vault} BACKUP_PROGRAM={BACKUP_PROGRAM}
# Like qrexec, hand back only the service's stdout.
exec {VAULT_SERVICE} "${{2#personal-calendar.Backup+}}" 2>/dev/null
""")
    return CalendarServerQube(home, vault)


def restore(backup: Path, identity: Path, destination: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "personal_calendar.backup", "restore",
         str(backup), str(destination), "--identity", str(identity)],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_a_scheduled_run_delivers_a_backup_the_vault_can_restore(
    server_qube: CalendarServerQube, keypair: tuple[str, Path], tmp_path: Path
) -> None:
    public_key, identity = keypair
    server_qube.settings(recipient=public_key)

    result = server_qube.run_scheduled_backup()

    assert result.returncode == 0, result.stdout + result.stderr
    [backup] = server_qube.vault.iterdir()
    assert f"{backup.name} delivered to {VAULT_QUBE}" in result.stdout
    restore(backup, identity, tmp_path / "restored")
    assert files_in(tmp_path / "restored") == SAMPLE_CALENDAR_FILES
    assert server_qube.backups_left_behind() == []
    assert server_qube.notifications() == ""
    assert not server_qube.failure_marker.exists()


def vault_unreachable(qube: CalendarServerQube, public_key: str) -> str:
    qube.settings(vault="not-the-vault", recipient=public_key)
    return "Request refused"


def bad_public_key(qube: CalendarServerQube, public_key: str) -> str:
    qube.settings(recipient="not-a-key")
    return "FAIL backup"


def vault_refuses(qube: CalendarServerQube, public_key: str) -> str:
    qube.settings(recipient=public_key)
    qube.vault.rmdir()
    return "FAIL receive"


def no_settings(qube: CalendarServerQube, public_key: str) -> str:
    return "settings"


@pytest.mark.parametrize(
    "break_it", [vault_unreachable, bad_public_key, vault_refuses, no_settings]
)
def test_a_failed_run_leaves_a_visible_warning(
    break_it: Callable[[CalendarServerQube, str], str],
    server_qube: CalendarServerQube,
    keypair: tuple[str, Path],
) -> None:
    public_key, _ = keypair
    reason = break_it(server_qube, public_key)

    result = server_qube.run_scheduled_backup()

    assert result.returncode != 0
    assert "--urgency=critical Calendar Backup failed" in server_qube.notifications()
    assert reason in server_qube.failure_marker.read_text()
    assert reason in result.stderr
    assert server_qube.backups_left_behind() == []


def test_the_warning_stays_until_a_run_succeeds(
    server_qube: CalendarServerQube, keypair: tuple[str, Path]
) -> None:
    public_key, _ = keypair
    server_qube.settings(vault="not-the-vault", recipient=public_key)
    assert server_qube.run_scheduled_backup().returncode != 0
    assert server_qube.run_scheduled_backup().returncode != 0
    assert server_qube.failure_marker.exists()

    server_qube.settings(recipient=public_key)
    result = server_qube.run_scheduled_backup()

    assert result.returncode == 0, result.stderr
    assert not server_qube.failure_marker.exists()


def test_restoring_the_latest_backup_into_a_fresh_calendar_server_passes_the_sync_check(
    server_qube: CalendarServerQube,
    keypair: tuple[str, Path],
    start_server: StartServer,
    tmp_path: Path,
) -> None:
    public_key, identity = keypair
    server_qube.settings(recipient=public_key)
    calendar_server = start_server(storage=server_qube.calendar)
    put_event(calendar_server, "restore-drill", "Restore drill")
    # A vault already holding as many Backups as it keeps.
    for minute in range(60):
        (server_qube.vault / f"calendar-20260101T12{minute:02}00Z.age").write_bytes(
            b"age-encryption.org/v1\nan older Backup"
        )

    result = server_qube.run_scheduled_backup()

    assert result.returncode == 0, result.stderr
    backups = sorted(server_qube.vault.iterdir())
    assert len(backups) == 60
    assert "calendar-20260101T120000Z.age" not in [path.name for path in backups]
    fresh = tmp_path / "fresh-calendar-server"
    restore(backups[-1], identity, fresh)
    fresh_server = start_server(storage=fresh)
    check = sync_check(fresh_server.url, fresh_server.certificate)
    assert check.returncode == 0, check.stdout + check.stderr
    assert "Restore drill" in server_titles(fresh_server)
