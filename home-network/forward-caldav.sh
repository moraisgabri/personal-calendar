#!/bin/sh
#
# Forward the CalDAV port, and only it, from the Home Network towards the
# Calendar Server: sys-net -> sys-firewall -> calendar-server (Qubes OS 4.2,
# nftables). Run it as root, in sys-net and in sys-firewall:
#
#   sh forward-caldav.sh sys-net --lan <desktop's Home Network IP>/<prefix> \
#       --interface <sys-net's Home Network interface> --to <sys-firewall's IP>
#   sh forward-caldav.sh sys-firewall --lan <desktop's Home Network IP>/<prefix> \
#       --to <calendar-server's IP>
#
# Only TCP 5232, only from the Home Network, is forwarded; nothing else is
# opened. Safe to re-run: it replaces its own rules instead of adding more.
#
# --install also copies this script to /rw/config and calls it from
# /rw/config/qubes-firewall-user-script, so the rules come back on every
# start of the qube. --print shows the rules and changes nothing.

set -eu

PORT=5232
RW_CONFIG=${QUBES_RW_CONFIG:-/rw/config}
USER_SCRIPT=$RW_CONFIG/qubes-firewall-user-script
INSTALLED=$RW_CONFIG/forward-caldav.sh

usage() {
  sed -n '7,10p' "$0" | sed 's/^# \{0,1\}//' >&2
  exit 2
}

fail() { echo "forward-caldav.sh: $1" >&2; exit 2; }

ipv4() {
  echo "$1" | grep -Eq '^((25[0-5]|2[0-4][0-9]|1?[0-9]?[0-9])\.){3}(25[0-5]|2[0-4][0-9]|1?[0-9]?[0-9])$'
}

[ $# -ge 1 ] || usage
role=$1; shift
case "$role" in sys-net | sys-firewall) ;; *) usage ;; esac

lan="" interface="" to="" print=false install=false
while [ $# -gt 0 ]; do
  case "$1" in
    --lan) [ $# -ge 2 ] || usage; lan=$2; shift 2 ;;
    --interface) [ $# -ge 2 ] || usage; interface=$2; shift 2 ;;
    --to) [ $# -ge 2 ] || usage; to=$2; shift 2 ;;
    --print) print=true; shift ;;
    --install) install=true; shift ;;
    *) fail "unknown argument: $1" ;;
  esac
done

address=${lan%/*}
prefix=${lan#*/}
{ [ "$lan" != "$address" ] && ipv4 "$address" &&
  echo "$prefix" | grep -Eq '^([89]|[12][0-9]|30)$'; } ||
  fail "--lan must be the desktop's Home Network IP with its prefix, e.g. 192.168.1.250/24"
ipv4 "$to" || fail "--to must be an IPv4 address, e.g. 10.138.0.5"
if [ "$role" = sys-net ]; then
  echo "$interface" | grep -Eq '^[A-Za-z0-9_.-]{1,15}$' ||
    fail "--interface must be sys-net's Home Network interface, e.g. wls6 or ens6"
  # Packets for the desktop's Home Network IP, from the Home Network,
  # arriving on the physical interface, go on to sys-firewall.
  match="iifname \"$interface\" ip saddr $lan"
  dnat_match="$match ip daddr $address"
  call="$INSTALLED sys-net --lan $lan --interface $interface --to $to"
else
  [ -z "$interface" ] || fail "--interface is only for sys-net"
  # In sys-firewall, Qubes puts the interface towards sys-net in group 1.
  match="iifgroup 1 ip saddr $lan"
  dnat_match="$match"
  call="$INSTALLED sys-firewall --lan $lan --to $to"
fi

# Our own chains, emptied and refilled on every run, so a re-run never stacks
# up duplicates. The forward chain is reached by one jump from Qubes'
# custom-forward chain, the place Qubes keeps for the Owner's own rules.
ruleset="table ip qubes {
	chain caldav-dnat {
		type nat hook prerouting priority filter + 1; policy accept;
	}
	chain caldav-forward {
	}
}
flush chain ip qubes caldav-dnat
flush chain ip qubes caldav-forward
add rule ip qubes caldav-dnat $dnat_match tcp dport $PORT counter dnat to $to
add rule ip qubes caldav-forward $match ip daddr $to tcp dport $PORT ct state new counter accept"

if $print; then
  printf '%s\n' "$ruleset"
  exit 0
fi

if $install; then
  mkdir -p "$RW_CONFIG"
  if [ "$(readlink -f "$0")" != "$(readlink -f "$INSTALLED")" ]; then
    cp "$0" "$INSTALLED"
  fi
  chmod 755 "$INSTALLED"
  # The firewall service runs the user script directly, so it needs a
  # shebang. Keep whatever else is in it; replace any earlier call of ours.
  [ -s "$USER_SCRIPT" ] || printf '#!/bin/sh\n' > "$USER_SCRIPT"
  head -n 1 "$USER_SCRIPT" | grep -q '^#!' || sed -i '1i #!/bin/sh' "$USER_SCRIPT"
  sed -i '/forward-caldav\.sh/d' "$USER_SCRIPT"
  printf '%s  # forward-caldav.sh: CalDAV from the Home Network\n' "$call" >> "$USER_SCRIPT"
  chmod 755 "$USER_SCRIPT"
fi

printf '%s\n' "$ruleset" | nft -f -
nft list chain ip qubes custom-forward | grep -q 'jump caldav-forward' ||
  nft add rule ip qubes custom-forward jump caldav-forward
echo "Forwarding TCP $PORT from $lan to $to ($role)."
