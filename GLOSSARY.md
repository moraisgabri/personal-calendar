# Personal Calendar

A single personal calendar, owned and used by one person, kept in agreement across their Qubes and GrapheneOS devices as part of leaving Google.

## Language

**Calendar**:
The one personal set of events belonging to the owner; not shared with anyone else.
_Avoid_: Agenda, schedule

**Owner**:
The single person who reads and edits the Calendar.
_Avoid_: User, account

**Device**:
A place where the Owner reads and edits the Calendar: the GrapheneOS phone, or the Calendar Qube on the Qubes desktop or the Qubes laptop.
_Avoid_: Dispositive, client, machine

**Calendar Qube**:
The dedicated Qubes AppVM on one Qubes machine that holds the Calendar for that machine; no other qube touches it. Each Qubes machine has its own.
_Avoid_: Calendar VM, personal qube

**Calendar Server**:
The one self-hosted place where the authoritative copy of the Calendar lives, at home on the Qubes desktop and kept apart from that machine's Calendar Qube; every Device Syncs with it, never with each other.
_Avoid_: Backend, cloud, main server

**Home Network**:
The Owner's home LAN, from which Devices reach the Calendar Server directly; away from it, Devices work offline until a remote path exists.
_Avoid_: LAN, local network, Wi-Fi

**Backup**:
An encrypted, point-in-time copy of the whole Calendar kept outside the Calendar Server, from which the Calendar can be restored.
_Avoid_: Export, snapshot, dump

**Sync**:
Two-way agreement between Devices: an edit on any Device appears on every other, and each Device can read the Calendar while offline and send its edits later.
_Avoid_: Mirror, replicate
