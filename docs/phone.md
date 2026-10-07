# The phone: Syncing with the Calendar Server

The GrapheneOS phone Syncs two-way with the Calendar Server over the Home
Network: DAVx⁵ does the Sync, Fossify Calendar shows and edits the Calendar,
both from F-Droid, with no Google services. Fossify Calendar works on the
phone's local copy, so the Calendar is readable and reminders fire with no
network; edits made away from home are sent on the next Sync at home.

The phone can't run a script, so this is a checklist. The same steps, one at a
time and with your own address and fingerprint filled in, come from the wizard
on the desktop, run from the qube holding this repo:

    scripts/setup-phone.sh

Before you start:

- The Calendar Server is reachable on the Home Network at the desktop's fixed
  address, `DESKTOP_LAN_IP` in the repo's `.env` (`scripts/setup-home-network.sh`).
  Below it is written `<DESKTOP_LAN_IP>`.
- The desktop Calendar Qube is set up (`scripts/setup-calendar-qube.sh`): its
  khal is the other Device in the checks.
- The Owner's Calendar password is in your password manager.

Menu names below are DAVx⁵ 4.x's and Fossify Calendar's as of 2026, and
Android 15/16's (GrapheneOS). Android's own settings can be worded slightly
differently between versions.

## 1. The certificate's fingerprint (desktop)

The Calendar Server's certificate is self-signed, so the phone is shown it once
and asked whether to trust it. It is not secret: nothing needs copying to the
phone. What matters is that the certificate the phone is shown is the
Calendar Server's own, not one swapped in by something else on the Wi-Fi. Its
SHA-256 fingerprint, read on the desktop itself, proves that.

- [ ] In a `calendar-server` terminal (dom0: `qvm-run calendar-server xterm`):

      openssl x509 -in ~/radicale/secrets/server.crt -noout -fingerprint -sha256 -ext subjectAltName

- [ ] The subjectAltName lists `IP Address:<DESKTOP_LAN_IP>`. If not, the
      certificate must be re-made first (`scripts/setup-home-network.sh`).
- [ ] Keep the `sha256 Fingerprint=` line on screen for step 4.

Don't install `server.crt` in Android's own certificate settings ("Install a
certificate > CA certificate"): that would make every app on the phone trust
it. DAVx⁵ keeps the certificates you accept to itself, and Fossify Calendar
never connects to anything.

## 2. Install the apps

- [ ] In Vanadium, open <https://f-droid.org>, tap **Download F-Droid**, and
      install it. Android asks to allow Vanadium to install apps: allow it,
      then turn that back off afterwards (Settings > Apps > Special app access
      > Install unknown apps > Vanadium).
- [ ] Open F-Droid and let it update its repositories.
- [ ] In F-Droid, install **DAVx⁵** (bitfire web engineering).
- [ ] In F-Droid, install **Fossify Calendar**.

## 3. Let the apps run in the background

Android pauses apps it thinks are idle. DAVx⁵ then misses its Sync, and
Fossify Calendar's reminders may come late.

- [ ] Open DAVx⁵. At **Regular sync intervals**, allow it to run in the
      background (Android asks to stop optimizing its battery use: **Allow**).
- [ ] At **Tasks support**, tick **I don't need tasks support.**
- [ ] At **Permissions**, turn on **Calendar permissions**, **Notification
      permission**, **Local network permission** (if listed) and **Keep
      permissions**. Leave Contacts off.
- [ ] Android Settings > Apps > DAVx⁵ > **App battery usage**: **Allow
      background usage** on, and **Unrestricted**.
- [ ] The same for Fossify Calendar.

## 4. Add the Calendar Server to DAVx⁵

- [ ] In DAVx⁵, tap **+** > **Login with URL and user name**.
- [ ] **Base URL**: `https://<DESKTOP_LAN_IP>:5232/`
- [ ] **User name**: `owner`; **Password**: the Owner's Calendar password.
      Tap **Login**.
- [ ] DAVx⁵ shows the unknown certificate. Under **FINGERPRINTS**, the line
      starting `SHA256:` must match the desktop's `sha256 Fingerprint=` from
      step 1, every one of the 32 pairs.
      - Matches: tick **I have manually verified the whole fingerprint.** and
        tap **Accept**.
      - Differs: tap **Reject** and stop. The phone did not reach the Calendar
        Server itself (wrong address, or not on the Home Network).
- [ ] **Account name**: `Calendar Server`. Leave **Contact group method** as
      it is. Tap **Add account**.
- [ ] Open the account, **CalDAV** tab, and tick the Calendar (`calendar`).

DAVx⁵ remembers the certificate and won't ask again. If the certificate is ever
re-made on the desktop, DAVx⁵ asks once more: check the new fingerprint the
same way. (App settings > **Reset (un)trusted certificates** forgets them all.)

## 5. Sync settings

In the account, **⋮** > **Account settings**:

- [ ] **Calendars sync. interval**: **Every 15 minutes**, the shortest Android
      allows. DAVx⁵ also Syncs right away after an edit on the phone.
- [ ] **Sync over WiFi only**: on.
- [ ] **WiFi SSID restriction**: the Home Network's Wi-Fi name, exactly as
      Android's Wi-Fi settings show it. DAVx⁵ then doesn't even try to Sync away
      from home.
      This needs Location for DAVx⁵, **Allow all the time** (Android only tells
      apps the Wi-Fi name with location access). If you'd rather not give it
      that, leave it blank: step 6 keeps failures quiet anyway.

## 6. Sync failures don't flood

The Calendar Server runs only while the desktop is on, so every evening DAVx⁵
can't connect. It reports that in its **Network and I/O errors** notification
channel, which is separate from real problems such as a wrong password
(**Synchronization errors**).

- [ ] DAVx⁵ > ☰ > **Settings** > **Notification settings** (or Android
      Settings > Apps > DAVx⁵ > Notifications).
- [ ] Turn off **Network and I/O errors**.
- [ ] Leave **Synchronization errors** on.

## 7. Show the Calendar in Fossify Calendar

- [ ] Fossify Calendar > **⋮** > **Settings** > turn on **CalDAV sync**, allow
      access to calendars, tick `calendar` (account `Calendar Server`), **OK**.
- [ ] Allow **Alarms & reminders** when it asks ("You must allow the app to
      schedule alarms for reminders to work properly."), or in Android
      Settings > Apps > Fossify Calendar > Alarms & reminders.
- [ ] Optional: Android Settings > Apps > Fossify Calendar > turn off
      **Network** (a GrapheneOS permission). It never needs it.

## 8. Checks

The desktop Calendar Qube is the other Device: run its commands in a
`calendar` terminal (dom0: `qvm-run calendar xterm`).

- [ ] **Phone to the Calendar Server.** In Fossify Calendar add "From the
      phone" on 2030-01-04 at 10:00. In DAVx⁵, open the account and tap
      **Synchronize now**. On the desktop:

      calendar-sync && khal list 2030-01-04 1d

      It lists "From the phone".
- [ ] **Elsewhere to the phone.** On the desktop:

      khal new 2030-01-04 12:00 13:00 'From the desktop' && calendar-sync

      In DAVx⁵ tap **Synchronize now**: Fossify Calendar shows "From the
      desktop" on 2030-01-04.
- [ ] **Offline.** Turn on airplane mode, with Wi-Fi off.
  - [ ] Fossify Calendar still shows 2030-01-04 with both events.
  - [ ] Add "Reminder test" starting in 5 minutes, with a reminder at the
        start. Lock the phone: the reminder fires.
  - [ ] Rename "From the phone" to "Edited offline".
  - [ ] Turn airplane mode off, on the Home Network. In DAVx⁵ tap
        **Synchronize now**. On the desktop:

        calendar-sync && khal list 2030-01-04 1d && khal list today 1d

        It lists "Edited offline" (not "From the phone") and "Reminder test".
- [ ] **Calendar Server off.** In a `calendar-server` terminal:

      sudo systemctl stop radicale.service

  - [ ] In DAVx⁵ tap **Synchronize now** two or three times: no notification
        appears. Fossify Calendar still shows every event.
  - [ ] Start it again with `sudo systemctl start radicale.service`;
        **Synchronize now** succeeds.
- [ ] Clean up: delete "Edited offline", "From the desktop" and "Reminder
      test" in Fossify Calendar, tap **Synchronize now**, and on the desktop
      `calendar-sync && khal list 2030-01-04 1d` lists nothing. (If they were
      the Calendar's only events: `vdirsyncer sync --force-delete calendar`.)

