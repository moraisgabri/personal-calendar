#!/usr/bin/env bash
#
# Install the Calendar (khal + vdirsyncer) inside a Calendar Qube. Run it in
# that qube, as `user`, from the copied calendar-qube/ folder:
#
#   bash install.sh --server https://<Calendar Server address>:5232/ \
#       --certificate ~/QubesIncoming/calendar-server/server.crt
#
# The server address is the only difference between Calendar Qubes. Safe to
# re-run, e.g. to change the address: the local copy of the Calendar and the
# saved password are kept.
#
# Everything lives under /home/user, the only place that survives a restart
# of a Qubes AppVM.

set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
VENV=$HOME/.local/share/calendar/venv
EVENTS=$HOME/.local/share/calendar/events
VDIRSYNCER_DIR=$HOME/.config/vdirsyncer
VDIRSYNCER_VERSION=0.21.0
KHAL_VERSION=0.14.1

server=""
certificate=""
while (($#)); do
  case "$1" in
    --server) server="$2"; shift 2 ;;
    --certificate) certificate="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
if [[ -z "$server" || -z "$certificate" ]]; then
  echo "Give --server https://<address>:5232/ and --certificate <server.crt>." >&2
  exit 2
fi
[[ "$server" == */ ]] || server="$server/"

echo "== Installing khal and vdirsyncer into $VENV"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet "vdirsyncer==$VDIRSYNCER_VERSION" "khal==$KHAL_VERSION"
mkdir -p "$HOME/.local/bin" "$EVENTS" "$VDIRSYNCER_DIR" "$HOME/.config/khal"
ln -sf "$VENV/bin/khal" "$VENV/bin/ikhal" "$VENV/bin/vdirsyncer" "$HOME/.local/bin/"
install -m 755 "$HERE/calendar-sync" "$HOME/.local/bin/calendar-sync"

echo "== Configuring for the Calendar Server at $server"
install -m 644 "$certificate" "$VDIRSYNCER_DIR/server.crt"
sed "s|@SERVER@|$server|" "$HERE/vdirsyncer.conf" > "$VDIRSYNCER_DIR/config"
install -m 644 "$HERE/khal.conf" "$HOME/.config/khal/config"

if [[ ! -s "$VDIRSYNCER_DIR/password" ]]; then
  read -rsp "The Owner's Calendar password: " password; echo
  (umask 077 && printf '%s\n' "$password" > "$VDIRSYNCER_DIR/password")
fi

echo "== Connecting to the Calendar Server"
export PATH="$VENV/bin:$PATH"
if ! vdirsyncer discover calendar; then
  echo "Could not reach the Calendar. Check the address, the firewall rules," >&2
  echo "and the password (delete $VDIRSYNCER_DIR/password to be asked again)." >&2
  exit 1
fi
"$HOME/.local/bin/calendar-sync"

echo "== Syncing every 5 minutes"
mkdir -p "$HOME/.config/systemd/user"
install -m 644 "$HERE/calendar-sync.service" "$HERE/calendar-sync.timer" \
  "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now calendar-sync.timer

echo
echo "Done. Try:  khal list   (or the interactive  ikhal)"
