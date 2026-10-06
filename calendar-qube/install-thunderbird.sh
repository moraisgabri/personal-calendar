#!/usr/bin/env bash
#
# Add the Calendar to Thunderbird in a Calendar Qube. Run it in that qube, as
# `user`, from the copied calendar-qube/ folder, after starting Thunderbird
# once and closing it, so its profile exists:
#
#   bash install-thunderbird.sh --server https://<Calendar Server address>:5232/ \
#       --certificate ~/.config/vdirsyncer/server.crt
#
# Thunderbird talks CalDAV straight to the Calendar Server, next to
# vdirsyncer, and keeps its own offline copy. The certificate is the one
# install.sh saved. The server address is the only
# difference between Calendar Qubes. Safe to re-run, e.g. to change the
# address. The password is not asked for here: Thunderbird asks for it the
# first time it connects and keeps it in its own password store.

set -euo pipefail

THUNDERBIRD_DIR=$HOME/.thunderbird
# Thunderbird's id for the Calendar. Fixed, so a re-run updates the same one.
CALENDAR_ID=5d1c7a0e-3b8f-4c6e-9a2d-c41e0d7b9f35
CERTIFICATE_NAME="Calendar Server"
BEGIN_MARK="// BEGIN personal-calendar (install-thunderbird.sh rewrites this block)"
END_MARK="// END personal-calendar"

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

# The profile Thunderbird starts with: the one its install section names,
# else the one marked Default=1.
default_profile() {
  awk -F= '
    /^\[/ { install = /^\[Install/; profile = /^\[Profile/ }
    install && $1 == "Default" && !chosen { chosen = $2 }
    profile && $1 == "Path" { path = $2 }
    profile && $1 == "Default" && $2 == "1" { marked = path }
    END { print (chosen != "" ? chosen : marked) }
  ' "$THUNDERBIRD_DIR/profiles.ini"
}

profile=""
[[ -f "$THUNDERBIRD_DIR/profiles.ini" ]] && profile=$(default_profile)
if [[ -z "$profile" ]]; then
  echo "No Thunderbird profile in $THUNDERBIRD_DIR. Start Thunderbird once," >&2
  echo "close it, and run this again." >&2
  exit 1
fi
[[ "$profile" == /* ]] || profile="$THUNDERBIRD_DIR/$profile"

# Thunderbird rewrites its files as it exits, so it must be closed. While it
# runs, its profile holds a "lock" symlink naming its host and process id.
lock=$(readlink "$profile/lock" 2>/dev/null || true)
if [[ -n "$lock" ]] && kill -0 "${lock##*+}" 2>/dev/null; then
  echo "Close Thunderbird first, then run this again." >&2
  exit 1
fi

echo "== Adding the Calendar at ${server}owner/calendar/ to $profile"
# user.js is applied on every start, so the Calendar stays pointed at the
# Calendar Server. Lines outside the marked block are the Owner's and kept.
pref="calendar.registry.$CALENDAR_ID"
block=$(cat <<EOF
$BEGIN_MARK
user_pref("$pref.type", "caldav");
user_pref("$pref.uri", "${server}owner/calendar/");
user_pref("$pref.username", "owner");
user_pref("$pref.name", "Calendar");
// Its own offline copy, so the Calendar stays readable when unreachable.
user_pref("$pref.cache.enabled", true);
// Refresh as often as calendar-sync runs.
user_pref("$pref.refreshInterval", "5");
user_pref("$pref.calendar-main-default", true);
// Shown in Thunderbird's views: without it the Calendar is listed but hidden.
user_pref("$pref.calendar-main-in-composite", true);
$END_MARK
EOF
)
user_js="$profile/user.js"
if grep -qxF "$BEGIN_MARK" "$user_js" 2>/dev/null && ! grep -qxF "$END_MARK" "$user_js"; then
  echo "$user_js has the start of the Calendar's block but not its end." >&2
  echo "Put back the line '$END_MARK' after it, or delete the block, and run this again." >&2
  exit 1
fi
kept=""
[[ -f "$user_js" ]] && kept=$(sed "\|^$BEGIN_MARK\$|,\|^$END_MARK\$|d" "$user_js")
printf '%s\n%s\n' "$kept" "$block" | sed '/./,$!d' > "$user_js.new"
mv "$user_js.new" "$user_js"

echo "== Trusting the Calendar Server's certificate"
# Thunderbird's own certificate store, so it connects without a warning.
# Replaces a certificate trusted earlier, e.g. before the server's was renewed.
store="sql:$profile"
[[ -f "$profile/cert9.db" ]] || certutil -N --empty-password -d "$store"
certutil -D -n "$CERTIFICATE_NAME" -d "$store" 2>/dev/null || true
# C makes Thunderbird trust it; P makes NSS's own checker (certutil -V) agree
# that a server's own certificate is trusted.
certutil -A -n "$CERTIFICATE_NAME" -t "CP,," -i "$certificate" -d "$store"

echo
echo "Done. Start Thunderbird and enter the Owner's Calendar password when asked."
