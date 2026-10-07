# Personal Calendar

A self-hosted Calendar Server (Radicale) on the Qubes desktop that every
Device Syncs with. See the spec in [issue #1](https://github.com/moraisgabri/personal-calendar/issues/1) and `GLOSSARY.md`.

## Set up the Calendar Server

Run the guided procedure from the qube holding this repo. It walks through the
dom0 and sys-firewall steps, installs the Calendar Server, and finishes with
the Sync check:

    scripts/setup-calendar-server.sh

## Calendar Server on the Home Network

The phone and the laptop reach the Calendar Server at the desktop's fixed
Home Network address, port 5232. Run the guided procedure from the qube
holding this repo, after the Calendar Server is set up, and again after a
reinstall of the desktop:

    scripts/setup-home-network.sh

It walks through these steps, saving the addresses to `.env` (git-ignored):

1. **Router:** read the DHCP range, pick a fixed address for the desktop
   outside it, and check the router forwards nothing to the desktop (no port
   forwarding, no DMZ, no UPnP): the Calendar Server is not reachable from the
   internet.
2. **sys-net:** give its Home Network connection that fixed address with
   `nmcli`. Qubes keeps NetworkManager connections in
   `/rw/config/NM-system-connections`, so it survives restarts.
3. **sys-net, then sys-firewall:** forward TCP 5232, and nothing else, from
   the Home Network: sys-net → sys-firewall → calendar-server.
   `home-network/forward-caldav.sh` writes the nftables rules into chains of
   its own (`caldav-dnat`, `caldav-forward`) and, with `--install`, calls itself
   from `/rw/config/qubes-firewall-user-script`, which Qubes runs on every start
   of the qube. Re-running it replaces its rules; `--print` shows them.
4. **calendar-server:** `install.sh` already accepts port 5232. The
   certificate must name the fixed address: if it doesn't, re-make it with
   `install.sh --name <calendar-server IP> --name <fixed address>
   --renew-certificate`, and give every Device the new `server.crt` (the
   wizard shows how for the Calendar Qube and Thunderbird; the phone and the
   laptop accept it in their own setup).
5. **Laptop:** run the Sync check against `https://<fixed address>:5232/`,
   check that other ports on the desktop are closed, and that the home's
   public address doesn't answer on 5232 from mobile data.
6. **Reboot the desktop** and run the Sync check again.

## Set up the desktop Calendar Qube

The Owner reads and edits the Calendar with khal (`khal list`, or the
interactive `ikhal`) in a dedicated qube that can reach only the Calendar
Server. vdirsyncer keeps a local copy in Sync every 5 minutes, so khal works
offline. Run the guided procedure from the qube holding this repo:

    scripts/setup-calendar-qube.sh

`calendar-sync` syncs by hand. When the same event was edited on two Devices,
it notifies and leaves both versions alone; choose one with
`calendar-sync --keep local` or `calendar-sync --keep server`. Deleting the
Calendar's very last event needs `vdirsyncer sync --force-delete calendar`,
because vdirsyncer won't empty the Calendar Server on its own.

### Thunderbird

The same wizard also adds the Calendar to Thunderbird in the Calendar Qube, for
a graphical view next to khal. Thunderbird talks CalDAV straight to the
Calendar Server itself, alongside vdirsyncer, through the same firewall rule.
It trusts `server.crt` and keeps the password in its own password store;
`calendar-qube/install-thunderbird.sh` writes no password. Thunderbird refuses
a CA certificate as a server's own, and Calendar Servers set up before
Thunderbird was added have one; the wizard checks for it and walks you through
re-making it with `install.sh --renew-certificate`. Thunderbird keeps
its own offline copy, so the Calendar stays readable while the Calendar Server
is unreachable. Editing then needs File > Offline > Work Offline first:
Thunderbird keeps those edits and sends them when you go back online. Without
it, Thunderbird may refuse edits it can't send.

The script re-applies the Calendar's address, name and refresh interval every
time Thunderbird starts, so change those by re-running it, not in
Thunderbird's settings.

Thunderbird and khal see each other's edits through the Calendar Server: khal
after `calendar-sync`, Thunderbird after its next refresh. When the same event
was edited in Thunderbird and on another Device, Thunderbird notices as it
sends its edit and asks whether to overwrite the Calendar Server's version or
discard its own change. That hasn't been checked for edits made while working
offline. `calendar-sync --keep` only settles conflicts in khal's local copy.

## Sync check

Proves a Calendar Server works, acting as a Device: it creates, reads back and
deletes a test event, and checks that a wrong password and plain HTTP are
refused. Standard library only, so it can be copied to any qube:

    python3 src/personal_calendar/sync_check.py https://<address>:5232/ \
        --user owner --certificate server.crt

## Development

    sudo dnf install nss-tools     # certutil, for Thunderbird's tests
    python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
    .venv/bin/mypy
    .venv/bin/pytest

The tests start a real Radicale with `calendar-server/radicale.conf` over
HTTPS on localhost and run the Sync check, khal and vdirsyncer with
`calendar-qube/`'s configuration, and Thunderbird's setup against it.
