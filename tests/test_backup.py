"""The Backup command, run as the Owner runs it, against small sample
Calendars laid out the way the Calendar Server stores them."""

import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

DENTIST = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//personal-calendar//tests//EN
BEGIN:VEVENT
UID:dentist@personal-calendar
DTSTAMP:20261001T090000Z
DTSTART:20261014T090000Z
DTEND:20261014T100000Z
SUMMARY:Dentist
END:VEVENT
END:VCALENDAR
"""

SAMPLE_CALENDAR_FILES = {
    "collection-root/owner/calendar/.Radicale.props": '{"tag": "VCALENDAR"}',
    "collection-root/owner/calendar/dentist.ics": DENTIST,
}


@pytest.fixture
def calendar(tmp_path: Path) -> Path:
    """A Calendar with one event, as Radicale's collections folder holds it."""
    root = tmp_path / "collections"
    events = root / "collection-root" / "owner" / "calendar"
    events.mkdir(parents=True)
    (events / ".Radicale.props").write_text('{"tag": "VCALENDAR"}')
    (events / "dentist.ics").write_text(DENTIST)
    return root


@pytest.fixture
def keypair(tmp_path: Path) -> tuple[str, Path]:
    """An age keypair made for this test: (public key, private key file)."""
    identity = tmp_path / "backup-key.txt"
    subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
    result = subprocess.run(
        ["age-keygen", "-y", str(identity)], check=True, capture_output=True, text=True
    )
    return result.stdout.strip(), identity


def run(*args: str | Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "personal_calendar.backup", *map(str, args)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_backup_is_one_encrypted_file_named_by_when_it_was_taken(
    calendar: Path, keypair: tuple[str, Path], tmp_path: Path
) -> None:
    backups = tmp_path / "backups"
    backups.mkdir()
    public_key, _ = keypair
    before = datetime.now(timezone.utc).replace(microsecond=0)

    result = run("backup", calendar, backups, "--recipient", public_key)

    after = datetime.now(timezone.utc)
    assert result.returncode == 0, result.stderr
    [backup] = backups.iterdir()
    taken = datetime.strptime(backup.name, "calendar-%Y%m%dT%H%M%SZ.age").replace(
        tzinfo=timezone.utc
    )
    assert before <= taken <= after
    assert b"Dentist" not in backup.read_bytes()


def take_backup(calendar: Path, public_key: str, tmp_path: Path) -> Path:
    backups = tmp_path / "backups"
    backups.mkdir(exist_ok=True)
    result = run("backup", calendar, backups, "--recipient", public_key)
    assert result.returncode == 0, result.stderr
    return Path(result.stdout.strip())


def files_in(folder: Path) -> dict[str, str]:
    return {
        str(path.relative_to(folder)): path.read_text()
        for path in folder.rglob("*")
        if path.is_file()
    }


def test_restore_gives_back_exactly_the_same_calendar(
    calendar: Path, keypair: tuple[str, Path], tmp_path: Path
) -> None:
    public_key, identity = keypair
    backup = take_backup(calendar, public_key, tmp_path)
    restored = tmp_path / "restored"

    result = run("restore", backup, restored, "--identity", identity)

    assert result.returncode == 0, result.stderr
    assert files_in(restored) == SAMPLE_CALENDAR_FILES


def test_an_empty_calendar_round_trips(
    keypair: tuple[str, Path], tmp_path: Path
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    public_key, identity = keypair
    backup = take_backup(empty, public_key, tmp_path)
    restored = tmp_path / "restored"

    result = run("restore", backup, restored, "--identity", identity)

    assert result.returncode == 0, result.stderr
    assert restored.is_dir()
    assert list(restored.iterdir()) == []


def test_restore_with_the_wrong_key_fails_clearly(
    calendar: Path, keypair: tuple[str, Path], tmp_path: Path
) -> None:
    public_key, _ = keypair
    backup = take_backup(calendar, public_key, tmp_path)
    other_key = tmp_path / "other-key.txt"
    subprocess.run(["age-keygen", "-o", str(other_key)], check=True, capture_output=True)
    restored = tmp_path / "restored"

    result = run("restore", backup, restored, "--identity", other_key)

    assert result.returncode != 0
    assert "not made for this key" in result.stderr
    assert "Traceback" not in result.stderr
    assert not restored.exists()


def truncate(backup: Path) -> None:
    data = backup.read_bytes()
    backup.write_bytes(data[: len(data) - 100])


def tamper(backup: Path) -> None:
    data = bytearray(backup.read_bytes())
    data[-100] ^= 0x01
    backup.write_bytes(bytes(data))


def tamper_with_header(backup: Path) -> None:
    data = bytearray(backup.read_bytes())
    data[60] ^= 0x01
    backup.write_bytes(bytes(data))


@pytest.mark.parametrize("damage", [truncate, tamper, tamper_with_header])
def test_a_damaged_backup_is_rejected_and_nothing_is_written(
    damage: Callable[[Path], None],
    calendar: Path,
    keypair: tuple[str, Path],
    tmp_path: Path,
) -> None:
    # Bigger than age's 64 KiB chunks, so the damage is past the first chunk.
    long_notes = DENTIST.replace("SUMMARY:Dentist", "DESCRIPTION:" + "x" * 300_000)
    (calendar / "collection-root" / "owner" / "calendar" / "long.ics").write_text(long_notes)
    public_key, identity = keypair
    backup = take_backup(calendar, public_key, tmp_path)
    damage(backup)
    restored = tmp_path / "restored"

    result = run("restore", backup, restored, "--identity", identity)

    assert result.returncode != 0
    assert "damaged" in result.stderr
    assert "Traceback" not in result.stderr
    assert not restored.exists()


def missing_key(tmp_path: Path, public_key: str) -> Path:
    return tmp_path / "no-such-key.txt"


def public_key_instead(tmp_path: Path, public_key: str) -> Path:
    key = tmp_path / "public-key.txt"
    key.write_text(public_key + "\n")
    return key


@pytest.mark.parametrize("bad_key", [missing_key, public_key_instead])
def test_restore_with_an_unusable_key_file_blames_the_key_not_the_backup(
    bad_key: Callable[[Path, str], Path],
    calendar: Path,
    keypair: tuple[str, Path],
    tmp_path: Path,
) -> None:
    public_key, _ = keypair
    backup = take_backup(calendar, public_key, tmp_path)
    key = bad_key(tmp_path, public_key)
    restored = tmp_path / "restored"

    result = run("restore", backup, restored, "--identity", key)

    assert result.returncode != 0
    assert "cannot use the key" in result.stderr
    assert "damaged" not in result.stderr
    assert "Traceback" not in result.stderr
    assert not restored.exists()


def test_restore_refuses_a_folder_that_is_not_empty(
    calendar: Path, keypair: tuple[str, Path], tmp_path: Path
) -> None:
    public_key, identity = keypair
    backup = take_backup(calendar, public_key, tmp_path)
    restored = tmp_path / "restored"
    restored.mkdir()
    (restored / "keep-me.txt").write_text("already here")

    result = run("restore", backup, restored, "--identity", identity)

    assert result.returncode != 0
    assert "not empty" in result.stderr
    assert files_in(restored) == {"keep-me.txt": "already here"}


def test_forced_restore_replaces_what_the_folder_held(
    calendar: Path, keypair: tuple[str, Path], tmp_path: Path
) -> None:
    public_key, identity = keypair
    backup = take_backup(calendar, public_key, tmp_path)
    restored = tmp_path / "restored"
    (restored / "collection-root" / "owner" / "calendar").mkdir(parents=True)
    (restored / "collection-root" / "owner" / "calendar" / "stale.ics").write_text("old")

    result = run("restore", backup, restored, "--identity", identity, "--force")

    assert result.returncode == 0, result.stderr
    assert files_in(restored) == SAMPLE_CALENDAR_FILES


def test_backup_into_a_missing_folder_fails_clearly(
    calendar: Path, keypair: tuple[str, Path], tmp_path: Path
) -> None:
    public_key, _ = keypair
    missing = tmp_path / "missing"

    result = run("backup", calendar, missing, "--recipient", public_key)

    assert result.returncode != 0
    assert "FAIL backup" in result.stderr
    assert "Traceback" not in result.stderr
    assert not missing.exists()


def test_backup_with_a_bad_public_key_fails_clearly_and_writes_nothing(
    calendar: Path, tmp_path: Path
) -> None:
    backups = tmp_path / "backups"
    backups.mkdir()

    result = run("backup", calendar, backups, "--recipient", "not-a-key")

    assert result.returncode != 0
    assert "FAIL backup" in result.stderr
    assert "Traceback" not in result.stderr
    assert list(backups.iterdir()) == []


def test_restore_refuses_a_destination_that_is_a_file(
    calendar: Path, keypair: tuple[str, Path], tmp_path: Path
) -> None:
    public_key, identity = keypair
    backup = take_backup(calendar, public_key, tmp_path)
    restored = tmp_path / "restored"
    restored.write_text("already here")

    result = run("restore", backup, restored, "--identity", identity)

    assert result.returncode != 0
    assert "not a folder" in result.stderr
    assert "Traceback" not in result.stderr
    assert restored.read_text() == "already here"


def test_backup_never_replaces_a_backup_already_there(
    calendar: Path, keypair: tuple[str, Path], tmp_path: Path
) -> None:
    public_key, _ = keypair
    backups = tmp_path / "backups"
    backups.mkdir()
    # A Backup already under every name this run could pick.
    now = datetime.now(timezone.utc)
    for second in range(-1, 10):
        name = (now + timedelta(seconds=second)).strftime("calendar-%Y%m%dT%H%M%SZ.age")
        (backups / name).write_text("an earlier Backup")

    result = run("backup", calendar, backups, "--recipient", public_key)

    assert result.returncode != 0
    assert "already" in result.stderr
    assert "Traceback" not in result.stderr
    assert {path.read_text() for path in backups.iterdir()} == {"an earlier Backup"}
