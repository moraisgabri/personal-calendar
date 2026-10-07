#!/usr/bin/env bash
#
# Make this qube the vault for the Calendar's Backups. Run it in the vault
# qube, as `user`, from the copied backup-vault/ folder, with backup.py copied
# next to that folder (one qvm-copy of both does that):
#
#   bash install.sh
#
# It installs the personal-calendar.Backup qrexec service, makes ~/backups for
# the Backups, and makes the Backup key ~/backup-key.txt if there is none yet.
# It prints the key's public half, which calendar-server needs. Safe to
# re-run: the key and the Backups are kept.
#
# The service and backup.py go under /usr/local, which a Qubes AppVM keeps
# across restarts (it lives on /rw), so no /rw/config/rc.local hook is needed.
# The key and the Backups live under /home/user, which is kept too.

set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
PROGRAM=$HERE/../backup.py
KEY=$HOME/backup-key.txt

if [[ -n "$(qubesdb-read /qubes-ip 2>/dev/null || true)" ]]; then
  echo "This qube has a network. The vault qube must not: in dom0, run" >&2
  echo "  qvm-prefs $(qubesdb-read /name) netvm ''" >&2
  echo "then restart this qube and run this again." >&2
  exit 1
fi
if [[ ! -f "$PROGRAM" ]]; then
  echo "$PROGRAM is missing: copy src/personal_calendar/backup.py together with" >&2
  echo "the backup-vault/ folder (qvm-copy backup-vault src/personal_calendar/backup.py)." >&2
  exit 1
fi
if ! command -v age-keygen >/dev/null; then
  echo "age is missing: install it in this qube's template (sudo dnf install age)," >&2
  echo "then restart this qube." >&2
  exit 1
fi

echo "== Installing the personal-calendar.Backup service"
sudo install -D -m 644 "$PROGRAM" /usr/local/lib/personal-calendar/backup.py
sudo install -D -m 755 "$HERE/personal-calendar.Backup" \
  /usr/local/etc/qubes-rpc/personal-calendar.Backup
install -d -m 700 "$HOME/backups"

if [[ -f "$KEY" ]]; then
  echo "== Keeping the existing Backup key $KEY"
else
  echo "== Making the Backup key $KEY"
  (umask 077 && age-keygen -o "$KEY" 2>/dev/null)
fi

echo
echo "Done. The Backup key's public half, for calendar-server, is:"
echo
echo "  $(age-keygen -y "$KEY")"
echo
echo "The private key, $KEY, never leaves this qube. Keep one offline copy."
