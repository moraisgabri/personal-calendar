# Personal Calendar

A self-hosted Calendar Server (Radicale) on the Qubes desktop that every
Device Syncs with. See the spec in [issue #1](https://github.com/moraisgabri/personal-calendar/issues/1) and `GLOSSARY.md`.

## Set up the Calendar Server

Run the guided procedure from the qube holding this repo. It walks through the
dom0 and sys-firewall steps, installs the Calendar Server, and finishes with
the Sync check:

    scripts/setup-calendar-server.sh

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

## Sync check

Proves a Calendar Server works, acting as a Device: it creates, reads back and
deletes a test event, and checks that a wrong password and plain HTTP are
refused. Standard library only, so it can be copied to any qube:

    python3 src/personal_calendar/sync_check.py https://<address>:5232/ \
        --user owner --certificate server.crt

## Development

    python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
    .venv/bin/mypy
    .venv/bin/pytest

The tests start a real Radicale with `calendar-server/radicale.conf` over
HTTPS on localhost and run the Sync check, and khal and vdirsyncer with
`calendar-qube/`'s configuration, against it.
