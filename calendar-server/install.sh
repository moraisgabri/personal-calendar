#!/usr/bin/env bash
#
# Install the Calendar Server (Radicale) inside the `calendar-server` qube.
# Run it in that qube, as `user`, from the copied calendar-server/ folder:
#
#   bash install.sh --name <this qube's IP> [--name <Home Network address>]
#
# Each --name is an address Devices will use to reach the Calendar Server;
# all of them go into the certificate. Safe to re-run: existing secrets and
# the existing Calendar are kept. To change the addresses, add
# --renew-certificate; every Device must then trust the new certificate.
#
# Everything persistent lives under /home/user/radicale and /rw/config, the
# only places that survive a restart of a Qubes AppVM.

set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
BASE=/home/user/radicale
OWNER=owner
PORT=5232
RADICALE_VERSION=3.8.1

names=(--name calendar-server)
renew=false
while (($#)); do
  case "$1" in
    --name) names+=(--name "$2"); shift 2 ;;
    --renew-certificate) renew=true; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done
if ((${#names[@]} < 4)); then
  echo "Give at least one --name: the address Devices use to reach this qube." >&2
  exit 2
fi

echo "== Installing Radicale into $BASE/venv"
mkdir -p "$BASE/collections"
python3 -m venv "$BASE/venv"
"$BASE/venv/bin/pip" install --quiet "radicale[bcrypt]==$RADICALE_VERSION" cryptography
install -m 644 "$HERE/radicale.conf" "$BASE/radicale.conf"

if [[ -f "$BASE/secrets/server.crt" ]] && $renew; then
  echo "== Re-making the certificate, keeping the password"
  "$BASE/venv/bin/python" "$HERE/make_secrets.py" "$BASE/secrets" --certificate-only "${names[@]}"
elif [[ -f "$BASE/secrets/server.crt" ]]; then
  echo "== Keeping the existing certificate and password"
  wanted=$(printf '%s\n' "${names[@]}" | grep -v '^--name$' | sort -u)
  have=$("$BASE/venv/bin/python" -c '
import sys
from cryptography import x509
cert = x509.load_pem_x509_certificate(open(sys.argv[1], "rb").read())
for name in cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value:
    print(name.value)
' "$BASE/secrets/server.crt" | sort -u)
  if [[ "$wanted" != "$have" ]]; then
    echo "The existing certificate names: $(echo $have)" >&2
    echo "but you asked for:              $(echo $wanted)" >&2
    echo "Re-run with --renew-certificate to replace it." >&2
    exit 1
  fi
else
  echo "== Creating the certificate and the Owner's password"
  read -rsp "Choose the Owner's Calendar password: " password; echo
  read -rsp "Type it again: " again; echo
  if [[ -z "$password" || "$password" != "$again" ]]; then
    echo "Passwords were empty or did not match." >&2
    exit 1
  fi
  printf '%s\n' "$password" |
    "$BASE/venv/bin/python" "$HERE/make_secrets.py" "$BASE/secrets" --user "$OWNER" "${names[@]}"
fi

echo "== Starting the Calendar Server with the qube"
sudo install -m 644 "$HERE/radicale.service" /rw/config/radicale.service
hook=/rw/config/rc.local.d/radicale.rc
sudo mkdir -p /rw/config/rc.local.d
sudo tee "$hook" >/dev/null <<EOF
#!/bin/sh
# Installed by personal-calendar/calendar-server/install.sh
cp /rw/config/radicale.service /etc/systemd/system/radicale.service
systemctl daemon-reload
# Accept CalDAV connections forwarded by sys-firewall; nothing else is opened.
nft list chain ip qubes custom-input | grep -q "tcp dport $PORT " ||
  nft add rule ip qubes custom-input tcp dport $PORT ct state new accept
# Don't hold up the qube's boot while the network comes up.
systemctl --no-block restart radicale.service
EOF
sudo chmod 755 "$hook"
sudo "$hook"

echo "== Waiting for the Calendar Server"
up=false
for _ in $(seq 50); do
  if curl --silent --output /dev/null --cacert "$BASE/secrets/server.crt" \
      "https://calendar-server:$PORT/" --resolve "calendar-server:$PORT:127.0.0.1"; then
    up=true
    break
  fi
  sleep 0.2
done
if ! $up; then
  echo "The Calendar Server did not start. Its log:" >&2
  sudo journalctl -b -u radicale.service --no-pager -n 20 >&2
  exit 1
fi

echo "== Creating the Calendar (if it does not exist yet)"
read -rsp "The Owner's Calendar password: " password; echo
status=$(curl --silent --output /dev/null --write-out '%{http_code}' \
  --cacert "$BASE/secrets/server.crt" --resolve "calendar-server:$PORT:127.0.0.1" \
  --user "$OWNER:$password" --request MKCALENDAR \
  "https://calendar-server:$PORT/$OWNER/calendar/")
case "$status" in
  201) echo "Created $OWNER/calendar/." ;;
  405 | 409) echo "The Calendar already exists." ;;
  *) echo "Creating the Calendar failed with HTTP $status." >&2; exit 1 ;;
esac

echo
echo "Done. The certificate every Device must trust is:"
echo "  $BASE/secrets/server.crt"
echo "Copy only that file to other qubes (qvm-copy). Never copy server.key or users."
