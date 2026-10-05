"""Backup: turn the whole Calendar into one encrypted, timestamped Backup.

The Calendar folder (Radicale's collections folder) is packed into a tar
archive and encrypted with `age` to the Owner's public key:

    python3 backup.py backup /home/user/radicale/collections /backups \\
        --recipient age1...
    python3 backup.py restore /backups/calendar-....age /home/user/restored \\
        --identity backup-key.txt

Standard library only, plus the `age` command from the template.
"""

import argparse
import io
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path


class BackupFailed(Exception):
    pass


class RestoreFailed(Exception):
    pass


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
    destination = backups / taken.strftime("calendar-%Y%m%dT%H%M%SZ.age")
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

    arguments = parser.parse_args()
    if arguments.operation == "backup":
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
