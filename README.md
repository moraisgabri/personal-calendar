# Personal Calendar

A self-hosted Calendar Server (Radicale) on the Qubes desktop that every
Device Syncs with. See `.scratch/personal-calendar/spec.md` and `GLOSSARY.md`.

## Set up the Calendar Server

Run the guided procedure from the qube holding this repo. It walks through the
dom0 and sys-firewall steps, installs the Calendar Server, and finishes with
the Sync check:

    scripts/setup-calendar-server.sh

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
HTTPS on localhost and run the Sync check against it.
