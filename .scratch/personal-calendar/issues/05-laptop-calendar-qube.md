# 05: Laptop Calendar Qube

**What to build:** The Qubes laptop gets its own Calendar Qube, set up the same way as the desktop's, Syncing with the Calendar Server over the Home Network. After this, all three Devices (phone, desktop, laptop) agree on the Calendar.

**Blocked by:** 02 (Calendar Server reachable on the Home Network), 04 (Desktop Calendar Qube)

**Status:** ready-for-agent

Human-only steps: the Owner creates the Calendar Qube and its firewall rule in the laptop's dom0, using the procedure from 04.

- [ ] The laptop's Calendar Qube can reach the Calendar Server over the Home Network and nothing else
- [ ] It reuses ticket 04's configuration, changing only the Calendar Server's address
- [ ] An event created on the laptop appears on the desktop and the phone after Sync, and the reverse
- [ ] Away from the Home Network, the laptop still reads the Calendar, and edits Sync on return
