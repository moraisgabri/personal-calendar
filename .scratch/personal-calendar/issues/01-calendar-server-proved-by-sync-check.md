# 01: Calendar Server running, proved by the Sync check

**What to build:** The Calendar Server (Radicale) runs in its own `calendar-server` qube on the Qubes desktop. It starts with the desktop, serves only HTTPS with a long-lived self-signed certificate, and requires the Owner's password. A Sync check command, run from another qube on the desktop and acting as a Device, proves it works: it creates, reads back and deletes a test event, and confirms that a wrong password and plain HTTP are both refused. This is the tracer bullet the rest of the Calendar builds on. Spec: `.scratch/personal-calendar/spec.md`, Seam 1.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

Human-only steps: the Owner creates the qubes in dom0 and allows qube-to-qube traffic. The agent provides a guided procedure (`/wizard`) for these.

- [ ] The Calendar Server starts automatically when the `calendar-server` qube starts
- [ ] It serves HTTPS only; a plain HTTP request is refused, not served
- [ ] Requests without the correct password are refused
- [ ] The Calendar is stored as plain files inside the `calendar-server` qube
- [ ] The Sync check takes the Calendar Server's address and credentials, and runs create → read → delete on a uniquely named test event
- [ ] The Sync check also verifies that a wrong password and plain HTTP are refused
- [ ] The Sync check always attempts to clean up its test event, even when a step fails
- [ ] On failure, the Sync check exits non-zero and names the step that failed
- [ ] The Sync check passes from another qube on the desktop
- [ ] No password, private key or certificate key is committed to the repo
- [ ] A guided procedure covers the dom0 steps
