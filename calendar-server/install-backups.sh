#!/usr/bin/env bash
#
# Schedule Backups of the Calendar to the vault qube. Run it in the
# `calendar-server` qube, as `user`, from the copied calendar-server/ folder,
# with backup.py copied next to that folder (one qvm-copy of both does that):
#
#   bash install-backups.sh --vault calendar-vault --recipient age1...
#
# --recipient is the public half of the Backup key, which backup-vault/install.sh
# printed in the vault qube. Only that public key is kept here: calendar-server
# can make Backups but never read them. Safe to re-run, e.g. to change either.
#
# Everything lives under /home/user, which survives a restart of a Qubes AppVM.

set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
PROGRAM=$HERE/../backup.py

vault=""
recipient=""
while (($#)); do
  case "$1" in
    --vault) vault="$2"; shift 2 ;;
    --recipient) recipient="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
# Both go into a settings file that calendar-backup reads as shell code.
if [[ ! "$vault" =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]]; then
  echo "Give --vault <the vault qube's name>." >&2
  exit 2
fi
if [[ ! "$recipient" =~ ^age1[0-9a-z]+$ ]]; then
  echo "Give --recipient age1...: the public key the vault qube printed." >&2
  echo "Never the private AGE-SECRET-KEY-...: that one stays in the vault qube." >&2
  exit 2
fi
if [[ ! -f "$PROGRAM" ]]; then
  echo "$PROGRAM is missing: copy src/personal_calendar/backup.py together with" >&2
  echo "the calendar-server/ folder (qvm-copy calendar-server src/personal_calendar/backup.py)." >&2
  exit 1
fi
if ! command -v age >/dev/null; then
  echo "age is missing: install it in this qube's template (sudo dnf install age)," >&2
  echo "then restart this qube." >&2
  exit 1
fi

echo "== Installing the Backup command"
install -D -m 644 "$PROGRAM" "$HOME/.local/lib/personal-calendar/backup.py"
install -D -m 755 "$HERE/calendar-backup" "$HOME/.local/bin/calendar-backup"
mkdir -p "$HOME/.config/calendar-backup"
printf 'VAULT=%s\nRECIPIENT=%s\n' "$vault" "$recipient" \
  > "$HOME/.config/calendar-backup/settings"

echo "== Backing up to $vault soon after the desktop starts, then every 4 hours"
mkdir -p "$HOME/.config/systemd/user"
install -m 644 "$HERE/calendar-backup.service" "$HERE/calendar-backup.timer" \
  "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now calendar-backup.timer

echo "== Taking the first Backup now"
if ! "$HOME/.local/bin/calendar-backup"; then
  echo "The first Backup failed (see above). Fix it, then re-run this script." >&2
  exit 1
fi

echo
echo "Done. A failed Backup shows a notification and leaves ~/BACKUP-FAILED.txt."
