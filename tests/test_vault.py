"""The vault qube receiving Backups, as the qrexec service runs it: the
Backup arrives on stdin and its name is the service argument."""

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

NAME = "calendar-20261005T120000Z.age"
# What every age-encrypted file starts with; the rest stands in for a Backup.
BACKUP = b"age-encryption.org/v1\n-> X25519 stand-in\n--- stand-in\nencrypted"


def receive(
    vault: Path, name: str, backup: bytes = BACKUP, *options: str
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, "-m", "personal_calendar.backup",
         "receive", str(vault), name, *options],
        input=backup,
        capture_output=True,
        timeout=60,
    )


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    folder = tmp_path / "backups"
    folder.mkdir()
    return folder


def test_a_received_backup_is_stored_under_its_name(vault: Path) -> None:
    result = receive(vault, NAME)

    assert result.returncode == 0, result.stderr
    assert result.stdout.decode().strip() == f"stored {NAME}"
    assert [path.name for path in vault.iterdir()] == [NAME]
    assert (vault / NAME).read_bytes() == BACKUP


def everything_under(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*"))


@pytest.mark.parametrize("name", [
    "",
    "../calendar-20261005T120000Z.age",
    "calendar-20261005T120000Z.age/../../escaped",
    "/tmp/calendar-20261005T120000Z.age",
    "calendar-latest.age",
    "calendar-20261399T996099Z.age",
    "calendar-20261005T120000Z.age.sh",
    ".bashrc",
])
def test_a_backup_with_a_garbage_name_is_refused_and_nothing_is_written(
    name: str, vault: Path, tmp_path: Path
) -> None:
    before = everything_under(tmp_path)

    result = receive(vault, name)

    assert result.returncode != 0
    assert b"FAIL receive" in result.stderr
    assert b"Traceback" not in result.stderr
    assert everything_under(tmp_path) == before


@pytest.mark.parametrize("garbage", [b"", b"BEGIN:VCALENDAR\nnot encrypted\n"])
def test_something_that_is_not_an_encrypted_backup_is_refused(
    garbage: bytes, vault: Path
) -> None:
    result = receive(vault, NAME, garbage)

    assert result.returncode != 0
    assert b"FAIL receive" in result.stderr
    assert b"Traceback" not in result.stderr
    assert list(vault.iterdir()) == []


def test_a_backup_already_in_the_vault_is_never_replaced(vault: Path) -> None:
    (vault / NAME).write_bytes(b"age-encryption.org/v1\nthe first delivery")

    result = receive(vault, NAME)

    assert result.returncode != 0
    assert b"already" in result.stderr
    assert b"Traceback" not in result.stderr
    assert [path.name for path in vault.iterdir()] == [NAME]
    assert (vault / NAME).read_bytes() == b"age-encryption.org/v1\nthe first delivery"


def test_only_the_newest_backups_are_kept(vault: Path) -> None:
    for day in ("01", "02", "03"):
        (vault / f"calendar-202610{day}T120000Z.age").write_bytes(BACKUP)
    (vault / "notes.txt").write_text("the Owner's own file")

    result = receive(vault, NAME, BACKUP, "--keep", "3")

    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in vault.iterdir()) == [
        "calendar-20261002T120000Z.age",
        "calendar-20261003T120000Z.age",
        NAME,
        "notes.txt",
    ]


def test_by_default_the_newest_60_backups_are_kept(vault: Path) -> None:
    for minute in range(60):
        (vault / f"calendar-20261001T12{minute:02}00Z.age").write_bytes(BACKUP)

    result = receive(vault, NAME)

    assert result.returncode == 0, result.stderr
    kept = sorted(path.name for path in vault.iterdir())
    assert len(kept) == 60
    assert "calendar-20261001T120000Z.age" not in kept
    assert NAME in kept


def test_receiving_into_a_missing_folder_fails_clearly(tmp_path: Path) -> None:
    result = receive(tmp_path / "missing", NAME)

    assert result.returncode != 0
    assert b"FAIL receive" in result.stderr
    assert b"Traceback" not in result.stderr


def test_keeping_no_backups_at_all_is_refused(vault: Path) -> None:
    result = receive(vault, NAME, BACKUP, "--keep", "0")

    assert result.returncode != 0
    assert b"Traceback" not in result.stderr
    assert list(vault.iterdir()) == []


def test_a_backup_named_in_the_future_is_refused(vault: Path) -> None:
    # It would sort after every real Backup, so they would be pruned instead.
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)

    result = receive(vault, tomorrow.strftime("calendar-%Y%m%dT%H%M%SZ.age"))

    assert result.returncode != 0
    assert b"future" in result.stderr
    assert list(vault.iterdir()) == []
