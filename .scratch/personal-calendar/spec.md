# Spec: Personal Calendar — Calendar Server, Devices and Backup

**Status:** ready-for-agent

## Problem Statement

The Owner is leaving Google and has no Calendar that stays in agreement across their Devices: a GrapheneOS phone, a Qubes desktop and a Qubes laptop. Tuta, which the Owner already uses for email, offers an encrypted calendar, but it is a closed system with no CalDAV and no API, so it can't be used from ordinary clients or scripted (see ADR-0001). The Owner wants a Calendar they control, that every Device can read offline and edit, and that is safe from data loss now that no provider is keeping a copy for them. The Owner is also new to AI-assisted development and wants part of this to be a real, small coding project.

## Solution

A self-hosted CalDAV Calendar Server runs at home on the Qubes desktop, in its own qube, during work hours. Every Device Syncs two-way with it over HTTPS with a password: the phone over the Home Network with DAVx5 + Fossify Calendar, and each Qubes machine through its own dedicated Calendar Qube running khal + vdirsyncer. Devices keep a local copy, so the Calendar is readable offline and edits made while the Calendar Server is unreachable are sent on the next Sync. A Backup command, written test-first, takes encrypted point-in-time copies of the whole Calendar on a schedule and stores them in an offline vault qube, from which the Calendar can be restored.

The first deliverable is the smallest useful slice: the Calendar Server running on the desktop and the phone Syncing with it over the Home Network.

## User Stories

### Calendar Server

1. As the Owner, I want the Calendar to live on a Calendar Server in my own home, so that no third party holds my events.
2. As the Owner, I want the Calendar Server isolated in its own qube, so that a compromise of any other qube, including a Calendar Qube, does not expose the server's storage directly.
3. As the Owner, I want the Calendar Server to start when the desktop starts, so that Sync is available throughout work hours without manual steps.
4. As the Owner, I want the Calendar Server to require a password, so that nothing else on the Home Network can read or change my Calendar.
5. As the Owner, I want the Calendar Server to speak only HTTPS, so that my password and events are never readable on the Wi-Fi.
6. As the Owner, I want plain HTTP requests to be refused rather than silently served, so that a misconfigured Device fails loudly instead of leaking.
7. As the Owner, I want a single self-signed certificate that I accept once per Device, so that I get encryption without buying or exposing a domain.
8. As the Owner, I want the certificate to stay valid for a long time, so that I'm not re-trusting it on every Device every few months.
9. As the Owner, I want the Calendar Server to store events as plain files, so that the storage is easy to inspect and to back up.
10. As the Owner, I want the Calendar Server reachable at a fixed address on the Home Network, so that Devices never need reconfiguring when the router reboots.
11. As the Owner, I want that fixed address to sit outside the router's DHCP range, so that no other device on the Home Network is ever handed the same address.
12. As the Owner, I want only the CalDAV port forwarded through to the Calendar Server's qube, so that nothing else on the desktop is exposed to the Home Network.
13. As the Owner, I want the Calendar Server unreachable from the internet, so that the first deliverable adds no public attack surface.

### Sync check

14. As the Owner, I want one Sync check command I can run from any networked qube, so that I can prove the Calendar Server works without touching a phone.
15. As the Owner, I want the Sync check to create, read back and delete a test event, so that a pass means real two-way access works end to end.
16. As the Owner, I want the Sync check to confirm a wrong password is refused, so that I know authentication is actually enforced.
17. As the Owner, I want the Sync check to confirm plain HTTP is refused, so that I know encryption is actually enforced.
18. As the Owner, I want the Sync check to clean up after itself even when a step fails, so that test events never pollute my Calendar.
19. As the Owner, I want the Sync check to say clearly which step failed, so that I can tell a network problem from a password problem from a certificate problem.
20. As the Owner, I want the Sync check to be runnable from the laptop over the Home Network, so that I can verify the network path separately from the phone setup.

### Phone

21. As the Owner, I want my GrapheneOS phone to Sync with the Calendar Server without any Google services, so that de-Googling isn't undermined.
22. As the Owner, I want to install the sync and calendar apps from F-Droid, so that my phone stays free of the Play Store for this.
23. As the Owner, I want to create an event on the phone and see it on the Calendar Server, so that the phone is a full editing Device.
24. As the Owner, I want an event created elsewhere to appear on the phone after Sync, so that the phone always shows the whole Calendar.
25. As the Owner, I want to read my Calendar on the phone with no network, so that I can check my day when away from home.
26. As the Owner, I want edits I make on the phone while away to be sent on the next Sync at home, so that nothing I enter offline is lost.
27. As the Owner, I want the phone to accept the Calendar Server's certificate once and remember it, so that Sync doesn't nag me each time.
28. As the Owner, I want the phone's Sync to fail quietly when the Calendar Server is off outside work hours, so that I'm not flooded with errors every evening.
29. As the Owner, I want phone reminders to fire from the local copy, so that alarms work even when the Calendar Server is off.

### Calendar Qubes

30. As the Owner, I want a dedicated Calendar Qube on the desktop, so that the Calendar is kept apart from my other qubes.
31. As the Owner, I want a dedicated Calendar Qube on the laptop too, so that both Qubes machines have the Calendar with the same isolation.
32. As the Owner, I want each Calendar Qube's firewall to allow only the Calendar Server, so that a compromised Calendar Qube can't reach anything else.
33. As the Owner, I want to view and edit the Calendar from a terminal client in the Calendar Qube, so that it's lightweight and scriptable.
34. As the Owner, I want the Calendar Qube to keep the Calendar as local files, so that I can read it offline and later write my own scripts against it.
35. As the Owner, I want the Calendar Qube to Sync on a timer, so that I don't have to remember to Sync manually.
36. As the Owner, I want an edit in a Calendar Qube to reach the phone and the other Calendar Qube, so that all three Devices agree.
37. As the Owner, I want the laptop's Calendar Qube to Sync over the Home Network the same way the phone does, so that there's one network path to reason about.
38. As the Owner, I want the laptop's Calendar Qube set up the same way as the desktop's, so that I fix problems once, not twice.
39. As the Owner, I want conflicting edits to the same event on two Devices to be resolved predictably and visibly, so that I never silently lose a change.

### Backup

40. As the Owner, I want a command that turns the whole Calendar into a single Backup, so that I have a point-in-time copy I can keep.
41. As the Owner, I want every Backup encrypted, so that a copied or stolen Backup reveals nothing.
42. As the Owner, I want a command that restores a Backup into an empty Calendar Server, so that I can recover from a dead disk or a bad edit.
43. As the Owner, I want a restored Calendar to contain exactly the events that were backed up, so that I can trust a restore.
44. As the Owner, I want a Backup that's been corrupted or tampered with to be reported as broken, not partly restored, so that I never restore garbage over a good Calendar.
45. As the Owner, I want restoring without the right key to fail clearly, so that I know the encryption actually protects the Backup.
46. As the Owner, I want restore to refuse to overwrite a Calendar Server that already holds events unless I explicitly ask, so that a mistaken restore can't destroy current data.
47. As the Owner, I want Backups to run on a schedule while the desktop is on, so that I don't depend on remembering.
48. As the Owner, I want Backups delivered to an offline vault qube, so that they're out of reach of anything networked, including the Calendar Server's qube.
49. As the Owner, I want each Backup named by when it was taken, so that I can pick which point in time to restore.
50. As the Owner, I want old Backups pruned to a sensible number, so that the vault qube doesn't fill up.
51. As the Owner, I want to know when a scheduled Backup failed, so that I don't discover months later that I have none.
52. As the Owner, I want to prove a restore works end to end by restoring into a fresh Calendar Server and passing the Sync check, so that I trust my Backups before I need them.
53. As the Owner, I want the Backup command built test-first with AI assistance, so that it doubles as my learning project in AI-assisted development.

### Operations

54. As the Owner, I want the dom0, router and phone steps that only I can do written down as a guided procedure, so that I can repeat them on the laptop or after a reinstall.
55. As the Owner, I want the Calendar Server's password and the Backup key kept out of the repository, so that publishing or sharing the repo never leaks them.
56. As the Owner, I want to know where the Backup key is kept, so that I can still restore if the desktop is lost.

## Implementation Decisions

- **Calendar Server software:** Radicale, single user, storing the Calendar as plain files. Chosen over Baïkal and Nextcloud for size and because plain files simplify Backup. Self-hosting over Tuta is recorded in ADR-0001.
- **Placement:** the Calendar Server runs in a dedicated `calendar-server` AppVM on the Qubes desktop, separate from the desktop's Calendar Qube. It runs while the desktop is on (work hours); there is no availability target beyond that.
- **Transport and auth:** HTTPS only, using a long-lived self-signed certificate generated once; plain HTTP is not served. Single-user password authentication with a hashed password file. Secrets live only on the qubes that need them, never in the repo.
- **Home Network path:** the desktop gets a static IP set in its `sys-net`, outside the router's DHCP range. Inbound CalDAV traffic is forwarded `sys-net` → `sys-firewall` → `calendar-server`, persisted through Qubes' own firewall-user-script mechanism so it survives reboots. Only the CalDAV port is forwarded. Nothing is exposed to the internet.
- **Qube-to-qube path on the desktop:** the desktop's Calendar Qube reaches `calendar-server` inside the machine, without going through the Home Network.
- **Calendar Qubes:** one dedicated AppVM per Qubes machine, running khal (client) + vdirsyncer (two-way Sync to local files on a timer). Firewall restricted to the Calendar Server only. Both machines use the same configuration, which differs only in the Calendar Server's address.
- **Phone:** DAVx5 for Sync and Fossify Calendar for viewing and editing, both from F-Droid. The self-signed certificate is accepted once in DAVx5.
- **Conflict handling:** rely on CalDAV's ETag-based conflict detection, with vdirsyncer's conflict resolution configured explicitly rather than left to defaults, so that a conflict is surfaced rather than silently overwritten.
- **Sync check module:** a small command-line CalDAV client that acts as a Device against a given Calendar Server address. Its interface is a single command taking the Calendar Server's address and credentials. It runs the create → read → delete cycle on a uniquely named test event, checks that a wrong password and plain HTTP are refused, and exits non-zero with the name of the failing step. It always attempts cleanup.
- **Backup module:** a command-line program with two operations, `backup` and `restore`.
  - `backup` reads the Calendar Server's storage and writes one encrypted, timestamped Backup file.
  - `restore` decrypts and verifies a Backup and writes it into an empty storage location. It refuses a non-empty target unless explicitly forced, and refuses a Backup that fails integrity verification without writing anything.
  - Encryption uses `age` with a keypair. Only the public key is present on `calendar-server`. The private key lives only in the vault qube, plus an offline copy kept by the Owner, so a compromised `calendar-server` can't read old Backups.
  - Integrity is checked by the encryption's authentication plus a manifest of the events included.
- **Backup delivery:** a timer on `calendar-server` runs `backup` while the desktop is on and hands the file to the vault qube over a qrexec service. A dom0 policy allows only that one service from `calendar-server` to the vault qube. The vault qube has no network. Old Backups are pruned to a fixed count. A failed run leaves a visible marker or notification.
- **Human-only steps:** creating qubes, dom0 qrexec policy, `sys-net`/`sys-firewall` forwarding, the router's DHCP range, and phone setup are done by the Owner. The agent provides guided procedures (e.g. via `/wizard`) for these.
- **Glossary:** Calendar, Owner, Device, Calendar Qube, Calendar Server, Sync, Home Network and Backup are used as defined in `GLOSSARY.md`.

## Testing Decisions

- **A good test exercises external behaviour only:** what a Device or the Owner observes. It never tests internals such as file layout, function names or library calls. If the internals are rewritten, the tests should still pass unchanged.
- **Seam 1: the Sync check against the Calendar Server, over CalDAV/HTTPS.** This is the highest seam: exactly what every Device sees. It verifies the Calendar Server, the Home Network path, and any restore. The phone and Calendar Qube setups are verified by hand against the same check: an event made on the Device appears in the check's listing, and the reverse.
- **Seam 2: the Backup command's inputs and outputs, tested by round trip.** The Backup module is built with `/tdd`. Tests run against small sample Calendars (sample event files) in temporary directories, never the real Calendar. Cases:
  - backup → restore yields identical events
  - restore with the wrong key fails
  - a truncated or tampered Backup is rejected and writes nothing
  - restore into a non-empty target is refused unless forced
  - an empty Calendar round-trips
- **Not automated:** Qubes networking, dom0 policy and the phone apps. The Sync check, plus the manual cross-Device checks, prove they work.
- **Prior art:** none. The repo has no code yet, so these tests set the pattern for later work.

## Out of Scope

- **Remote access away from the Home Network** (Headscale, CGNAT check, deSEC dynamic DNS). Devices work offline while away. Needs its own interview and spec.
- **Qubes provisioning** (Salt or scripted creation of the qubes and firewall rules). The setup is manual, guided by procedures, until then.
- **Daily digest** of the Calendar to the phone or email.
- **Invitation import** from the Tuta mailbox.
- **Off-site Backup** (e.g. S3). For now, only the vault qube.
- **Sharing the Calendar** with anyone else, or multiple calendars. The Calendar has a single Owner.
- **Migration from Google Calendar.** The Owner is starting fresh.
- **A web interface** for the Calendar, and any Device beyond the three named.

## Further Notes

- Backlog order after this spec: (5) remote access via Headscale, (6) Qubes provisioning, (7) daily digest, (8) invitation import. Each starts with `/grill-with-docs`.
- Because the Calendar Server runs only in work hours, the phone and laptop will show Sync failures outside them. That's expected, not a fault.
- The Backup module is the Owner's first AI-assisted coding project and should be kept deliberately small, readable and well tested.
