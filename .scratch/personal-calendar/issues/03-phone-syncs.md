# 03: Phone Syncs with the Calendar Server

**What to build:** The Owner's GrapheneOS phone Syncs two-way with the Calendar Server over the Home Network, using DAVx5 and Fossify Calendar from F-Droid, with no Google services. The Calendar Server's certificate is accepted once. Events created on the phone reach the Calendar Server, events created elsewhere appear on the phone, and the phone reads the Calendar and fires reminders with no network. This completes the first deliverable.

**Blocked by:** 02 (Calendar Server reachable on the Home Network)

**Status:** ready-for-human

- [ ] DAVx5 and Fossify Calendar are installed from F-Droid
- [ ] DAVx5 trusts the Calendar Server's self-signed certificate after accepting it once
- [ ] An event created on the phone appears in the Sync check's listing (or another Device) after Sync
- [ ] An event created by another Device or by hand on the Calendar Server appears on the phone after Sync
- [ ] With the phone in airplane mode, the Calendar is readable and a reminder still fires
- [ ] An edit made offline reaches the Calendar Server on the next Sync on the Home Network
- [ ] When the Calendar Server is off, Sync failures don't flood the phone with notifications
