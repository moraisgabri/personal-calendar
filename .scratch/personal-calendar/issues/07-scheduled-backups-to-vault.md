# 07: Scheduled Backups into the vault qube

**What to build:** While the desktop is on, Backups run on a schedule on `calendar-server` and are delivered to an offline vault qube over a single qrexec service. Old Backups are pruned to a fixed number, and a failed run is visible. A restore into a fresh Calendar Server, verified with the Sync check, proves the whole chain.

**Blocked by:** 01 (Calendar Server running, proved by the Sync check), 06 (Backup command)

**Status:** ready-for-agent

Human-only steps: the Owner creates the vault qube (no network) and adds a dom0 policy allowing only this one service from `calendar-server` to the vault qube, using a guided procedure the agent provides.

- [ ] Backups run on a schedule while the desktop is on
- [ ] Each Backup arrives in the vault qube, which has no network
- [ ] The dom0 policy allows only the Backup delivery service, only from `calendar-server` to the vault qube
- [ ] Only the public key is on `calendar-server`; the private key is in the vault qube, plus an offline copy kept by the Owner
- [ ] Old Backups are pruned to a fixed number
- [ ] A failed scheduled run leaves a visible warning
- [ ] Restoring the latest Backup into a fresh Calendar Server passes the Sync check
- [ ] Where the Backup key lives is written down
