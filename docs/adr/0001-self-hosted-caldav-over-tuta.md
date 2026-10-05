# Self-hosted CalDAV Calendar Server instead of Tuta Calendar

The Owner already pays for Tuta, whose calendar is end-to-end encrypted and needs no maintenance, but it has no CalDAV and no public API, so nothing outside Tuta's own apps can read or write it. We self-host a CalDAV Calendar Server at home on the Qubes desktop instead, accepting that we run and back it up ourselves, because open standards let any client (khal/vdirsyncer on Qubes, DAVx5 on GrapheneOS) Sync with it and leave room for our own code (Backups, provisioning, digests). Tuta stays for email only.

## Considered Options

- **Tuta Calendar**: rejected for being a closed system with no way to script against it.
- **Paid CalDAV provider (Fastmail, Posteo, mailbox.org)**: rejected; it would be a second paid account, and the provider could read events.

## Consequences

- Sync only happens while the desktop is running (work hours); Devices rely on offline mode the rest of the time.
- Backups are our responsibility, not a provider's.
