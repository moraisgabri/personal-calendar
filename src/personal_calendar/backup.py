"""Backup: turn the whole Calendar into one encrypted, timestamped Backup.

The Calendar folder (Radicale's collections folder) is packed into a tar
archive and encrypted with `age` to the Owner's public key:

    python3 backup.py backup /home/user/radicale/collections /backups \\
        --recipient age1...
    python3 backup.py restore /backups/calendar-....age /home/user/restored \\
        --identity backup-key.txt

In the vault qube, `receive` stores a Backup delivered on stdin by the
personal-calendar.Backup qrexec service, keeping only the newest ones:

    python3 backup.py receive /home/user/backups calendar-....age < Backup

Standard library only, plus the `age` command from the template.
"""

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


class BackupFailed(Exception):
    pass


class RestoreFailed(Exception):
    pass


class ReceiveFailed(Exception):
    pass


# calendar-20261005T120000Z.age: when the Backup was taken, in UTC.
NAME_FORMAT = "calendar-%Y%m%dT%H%M%SZ.age"
BACKUP_NAME = re.compile(r"calendar-\d{8}T\d{6}Z\.age")
AGE_HEADER = b"age-encryption.org/v1\n"
# About a month of work days, at a few Backups a day.
KEEP = 60


def pack(calendar: Path) -> bytes:
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as tar:
        tar.add(calendar, arcname=".")
    return archive.getvalue()


def backup(calendar: Path, backups: Path, recipient: str) -> Path:
    for folder in (calendar, backups):
        if not folder.is_dir():
            raise BackupFailed(f"{folder} is not a folder")
    taken = datetime.now(timezone.utc)
    destination = backups / taken.strftime(NAME_FORMAT)
    # age --output would silently replace a Backup taken in the same second.
    try:
        output = destination.open("xb")
    except FileExistsError:
        raise BackupFailed(f"{destination} is already there; not replacing it")
    with output:
        encrypted = subprocess.run(
            ["age", "--encrypt", "--recipient", recipient],
            input=pack(calendar),
            stdout=output,
            stderr=subprocess.PIPE,
        )
    if encrypted.returncode != 0:
        destination.unlink(missing_ok=True)
        raise BackupFailed(encrypted.stderr.decode().strip())
    return destination


def restore(backup_file: Path, destination: Path, identity: Path,
            force: bool = False) -> None:
    if destination.exists() and not destination.is_dir():
        raise RestoreFailed(f"{destination} is not a folder")
    if not force and destination.exists() and any(destination.iterdir()):
        raise RestoreFailed(f"{destination} is not empty; --force replaces what it holds")
    decrypted = subprocess.run(
        ["age", "--decrypt", "--identity", str(identity), str(backup_file)],
        capture_output=True,
    )
    error = decrypted.stderr.decode().strip()
    if f'reading "{identity}"' in error:
        raise RestoreFailed(f"cannot use the key {identity}: {error}")
    # age can't tell a wrong key from a damaged header, so neither can we.
    if "no identity matched" in error:
        raise RestoreFailed(
            f"{backup_file} was not made for this key ({identity}), or it is damaged"
        )
    # age may print the readable start of a damaged Backup before it fails,
    # so nothing is used unless the whole Backup decrypted.
    if decrypted.returncode != 0:
        raise RestoreFailed(f"{backup_file} is damaged: {error}")
    archive = decrypted.stdout
    # Only now, with the whole Backup in hand, is it safe to clear the folder.
    if destination.exists():
        shutil.rmtree(destination)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(destination, filter="data")


def receive(backups: Path, name: str, backup: bytes, keep: int = KEEP) -> None:
    """Store a delivered Backup in the vault, then keep only the newest ones."""
    if keep < 1:
        raise ReceiveFailed("--keep must keep at least one Backup")
    if not backups.is_dir():
        raise ReceiveFailed(f"{backups} is not a folder")
    # The name comes from another qube, so it is only ever a plain Backup name.
    try:
        if not BACKUP_NAME.fullmatch(name):
            raise ValueError
        taken = datetime.strptime(name, NAME_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        raise ReceiveFailed(f"{name!r} is not a Backup's name")
    # A name from the future would sort after every real Backup, which would
    # then be pruned instead. An hour's leeway allows for clocks differing.
    if taken > datetime.now(timezone.utc) + timedelta(hours=1):
        raise ReceiveFailed(f"{name} was taken in the future; is a clock wrong?")
    if not backup.startswith(AGE_HEADER):
        raise ReceiveFailed(f"{name} is not an age-encrypted Backup")
    # Write it under a temporary name first, so a half-written Backup never
    # carries a Backup's name; linking it into place fails if the name is taken.
    with tempfile.NamedTemporaryFile(dir=backups, prefix=".receiving-") as incoming:
        incoming.write(backup)
        incoming.flush()
        os.fsync(incoming.fileno())
        try:
            os.link(incoming.name, backups / name)
        except FileExistsError:
            raise ReceiveFailed(f"{name} is already in the vault; not replacing it")
    prune(backups, keep)


def prune(backups: Path, keep: int) -> None:
    # Backup names sort by when they were taken; nothing else is touched.
    taken = sorted(path for path in backups.iterdir() if BACKUP_NAME.fullmatch(path.name))
    for old in taken[:-keep]:
        old.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    operations = parser.add_subparsers(dest="operation", required=True)

    backup_parser = operations.add_parser("backup", help="take a Backup of the Calendar")
    backup_parser.add_argument("calendar", type=Path, help="the Calendar folder")
    backup_parser.add_argument("backups", type=Path, help="folder to put the Backup in")
    backup_parser.add_argument("--recipient", required=True, help="the age public key")

    restore_parser = operations.add_parser("restore", help="restore a Backup")
    restore_parser.add_argument("backup", type=Path, help="the Backup file")
    restore_parser.add_argument("destination", type=Path, help="an empty folder")
    restore_parser.add_argument("--identity", type=Path, required=True,
                                help="the age private key file")
    restore_parser.add_argument("--force", action="store_true",
                                help="replace whatever the folder holds")

    receive_parser = operations.add_parser(
        "receive", help="store a Backup read from stdin (in the vault qube)")
    receive_parser.add_argument("backups", type=Path, help="the vault's Backups folder")
    receive_parser.add_argument("name", help="the Backup's name, as it was taken")
    receive_parser.add_argument("--keep", type=int, default=KEEP,
                                help=f"how many Backups to keep (default {KEEP})")

    arguments = parser.parse_args()
    if arguments.operation == "receive":
        try:
            receive(arguments.backups, arguments.name, sys.stdin.buffer.read(),
                    arguments.keep)
        except ReceiveFailed as failure:
            sys.exit(f"FAIL receive: {failure}")
        print(f"stored {arguments.name}")
    elif arguments.operation == "backup":
        try:
            print(backup(arguments.calendar, arguments.backups, arguments.recipient))
        except BackupFailed as failure:
            sys.exit(f"FAIL backup: {failure}")
    else:
        try:
            restore(arguments.backup, arguments.destination, arguments.identity,
                    arguments.force)
        except RestoreFailed as failure:
            sys.exit(f"FAIL restore: {failure}")


if __name__ == "__main__":
    main()
