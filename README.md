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

## Backup

Turns the whole Calendar into one encrypted Backup, named by when it was
taken, and restores one. It encrypts with `age`, so `backup` needs only the
public key; `restore` needs the private key. Standard library only, plus the
`age` package from the template (`sudo dnf install age`):

    age-keygen -o backup-key.txt     # prints the public key, age1...
    python3 src/personal_calendar/backup.py backup /home/user/radicale/collections \
        /backups --recipient age1...
    python3 src/personal_calendar/backup.py restore /backups/calendar-20261005T120000Z.age \
        /home/user/restored --identity backup-key.txt

`restore` checks the whole Backup before writing anything: a wrong key or a
damaged Backup fails and leaves the folder untouched. It refuses a folder that
isn't empty unless given `--force`, which replaces what the folder holds.
A `backup` that can't be taken exits non-zero with `FAIL backup: ...` and
leaves no file behind; it never replaces a Backup already there.

## Scheduled Backups

While the desktop is on, `calendar-server` takes a Backup 5 minutes after it
starts and every 4 hours after that, and delivers it to `calendar-vault`, an
offline vault qube with no network. Run the guided procedure from the qube
holding this repo. It creates the vault qube, the dom0 policy and the
schedule, and finishes with a restore drill:

    scripts/setup-backup-vault.sh

Re-run it now and then and answer "yes" to the first question: that runs
only the restore drill. The drill restores the latest Backup into a fresh,
throwaway Calendar Server and runs the Sync check against it.

How it fits together:

- `calendar-server/calendar-backup` (run by `calendar-backup.timer`, a user
  timer) encrypts the Backup with the public key, hands it to the vault qube
  with `qrexec-client-vm calendar-vault personal-calendar.Backup+<name>`, and
  keeps no copy.
- In the vault qube, the `personal-calendar.Backup` qrexec service
  (`backup-vault/`) runs `backup.py receive`. It stores the Backup in
  `~/backups` under its timestamped name and keeps the newest 60, about a
  month of work days. It refuses anything that isn't an age-encrypted Backup
  with a proper name, a name from the future, and a name already there. The
  service is installed under `/usr/local`, which a Qubes AppVM keeps across
  restarts.
- The dom0 policy, `/etc/qubes/policy.d/30-calendar-backup.policy` (see
  `backup-vault/30-calendar-backup.policy`), allows that one service, only
  from `calendar-server`, only to the vault qube. It also denies everything
  else from `calendar-server` to the vault qube.

**A failed Backup** shows a "Calendar Backup failed" notification on the
desktop. It also leaves `~/BACKUP-FAILED.txt` in `calendar-server` saying
why, and the file goes away after the next Backup that works. The run repeats
every 4 hours, so the notification does too until the problem is fixed. To
try one by hand, in `calendar-server`: `systemctl --user start
calendar-backup.service`. This covers every way a run can fail, but not a
run that never starts, e.g. a broken timer. So now and then, glance at
`ls -l ~/backups` in the vault qube, or run the restore drill.

The restore drill is the one time a decrypted Calendar leaves the vault qube,
and it goes only to the throwaway drill qube, which is removed at the end.

**Where the Backup key lives:**

- The **public key** (`age1...`) is in `calendar-server`, in
  `~/.config/calendar-backup/settings`, and in this repo qube's `.env`. It can
  make Backups but not read them.
- The **private key** is only in the vault qube, at `~/backup-key.txt`, plus
  one **offline copy** the Owner keeps away from the desktop (on paper or an
  encrypted USB stick). That copy is what restores the Calendar if the desktop
  is lost. The private key is never in `calendar-server`, any other qube, or
  this repo.

Known limit: a compromised `calendar-server` can't read Backups, but it could
flood the vault with fresh junk Backups until the good ones are pruned. Only
an off-site Backup, out of scope for now, would protect against that.

## Development

    sudo dnf install nss-tools     # certutil, for Thunderbird's tests
    sudo dnf install age           # for the Backup tests
    python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
    .venv/bin/mypy
    .venv/bin/pytest

The tests start a real Radicale with `calendar-server/radicale.conf` over
HTTPS on localhost and run the Sync check, khal and vdirsyncer with
`calendar-qube/`'s configuration, and Thunderbird's setup against it.
