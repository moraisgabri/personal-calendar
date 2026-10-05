# 02: Calendar Server reachable on the Home Network

**What to build:** Machines on the Home Network can reach the Calendar Server at a fixed address. The desktop gets a static IP in its `sys-net`, outside the router's DHCP range, and only the CalDAV port is forwarded `sys-net` → `sys-firewall` → `calendar-server`, in a way that survives reboots. Nothing is exposed to the internet. The Sync check passes when run from another machine on the Home Network, e.g. the laptop.

**Blocked by:** 01 (Calendar Server running, proved by the Sync check)

**Status:** ready-for-human

The agent can prepare a guided procedure (`/wizard`) for the `sys-net`, `sys-firewall`, dom0 and router steps; the Owner runs it.

- [ ] The desktop's `sys-net` has a static IP that's outside the router's DHCP range
- [ ] Only the CalDAV port is forwarded through to `calendar-server`; no other desktop port is reachable from the Home Network
- [ ] The forwarding persists across a reboot of the desktop
- [ ] The Sync check passes from a machine on the Home Network
- [ ] The Calendar Server is not reachable from the internet
- [ ] The procedure is written down so it can be repeated after a reinstall
