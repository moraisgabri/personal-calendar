# 04: Desktop Calendar Qube

**What to build:** A dedicated Calendar Qube on the Qubes desktop gives the Owner the Calendar through khal, with vdirsyncer keeping a local copy in two-way Sync with the Calendar Server on a timer. The qube's firewall allows only the Calendar Server. Conflicting edits to the same event on two Devices show up instead of being silently overwritten. The configuration is written so the laptop can reuse it, with only the Calendar Server's address changed.

**Blocked by:** 01 (Calendar Server running, proved by the Sync check)

**Status:** ready-for-agent

Human-only steps: the Owner creates the Calendar Qube and its firewall rule in dom0, using a guided procedure the agent provides.

- [ ] The desktop's Calendar Qube can reach the Calendar Server and nothing else
- [ ] khal shows the Calendar, and events created in khal reach the Calendar Server
- [ ] Events created by another Device appear in khal after Sync
- [ ] Sync runs automatically on a timer
- [ ] With the Calendar Server stopped, khal still reads the Calendar, and edits made in the meantime Sync once it's back
- [ ] Editing the same event on two Devices produces a visible conflict, not a silent overwrite
- [ ] The only difference between the desktop's and the laptop's configuration is the Calendar Server's address
- [ ] No password is committed to the repo
