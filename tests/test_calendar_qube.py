"""A Calendar Qube (khal + vdirsyncer, using the repo's configuration) in Sync
with a real Calendar Server. Each Calendar Qube gets its own home directory,
so two of them model two Devices."""

import hashlib
import os
import shutil
import ssl
import subprocess
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from conftest import OWNER, PASSWORD, REPO, CalendarServer, StartServer
from personal_calendar.sync_check import Device

VDIRSYNCER_CONF = REPO / "calendar-qube" / "vdirsyncer.conf"
KHAL_CONF = REPO / "calendar-qube" / "khal.conf"
CALENDAR_SYNC = REPO / "calendar-qube" / "calendar-sync"
BIN = Path(sys.executable).parent

DAY = "2030-03-15"


@dataclass
class CalendarQube:
    home: Path
    certificate: Path

    def point_at(self, server_url: str) -> None:
        """Write the configuration as install.sh does: only the address varies."""
        config = self.home / ".config" / "vdirsyncer" / "config"
        config.write_text(VDIRSYNCER_CONF.read_text().replace("@SERVER@", server_url))

    def run(self, *command: str) -> subprocess.CompletedProcess[str]:
        # notify-send is replaced by a stand-in that records the notification.
        path = f"{self.home / 'bin'}:{BIN}:{os.environ['PATH']}"
        return subprocess.run(
            list(command),
            env={**os.environ, "HOME": str(self.home), "PATH": path},
            capture_output=True,
            text=True,
            timeout=60,
        )

    def sync(self, *options: str) -> subprocess.CompletedProcess[str]:
        return self.run(str(CALENDAR_SYNC), *options)

    def notifications(self) -> str:
        log = self.home / "notifications"
        return log.read_text() if log.exists() else ""

    def titles(self) -> list[str]:
        result = self.run("khal", "list", "--format", "{title}", DAY, "1d")
        assert result.returncode == 0, result.stderr
        return [line for line in result.stdout.splitlines() if line and DAY not in line]

    def new_event(self, title: str) -> None:
        result = self.run("khal", "new", DAY, "10:00", "11:00", title)
        assert result.returncode == 0, result.stderr

    def event_files(self) -> list[Path]:
        return sorted((self.home / ".local/share/calendar/events").glob("*.ics"))


MakeCalendarQube = Callable[[CalendarServer], CalendarQube]


@pytest.fixture
def make_calendar_qube(tmp_path: Path) -> MakeCalendarQube:
    def make(server: CalendarServer) -> CalendarQube:
        home = tmp_path / f"qube-{uuid.uuid4().hex[:8]}"
        (home / ".config/vdirsyncer").mkdir(parents=True)
        (home / ".config/khal").mkdir(parents=True)
        (home / ".local/share/calendar/events").mkdir(parents=True)
        shutil.copy(server.certificate, home / ".config/vdirsyncer/server.crt")
        (home / ".config/vdirsyncer/password").write_text(PASSWORD + "\n")
        shutil.copy(KHAL_CONF, home / ".config/khal/config")
        notify_send = home / "bin" / "notify-send"
        notify_send.parent.mkdir()
        notify_send.write_text(f'#!/bin/sh\necho "$@" >> {home / "notifications"}\n')
        notify_send.chmod(0o755)
        qube = CalendarQube(home, server.certificate)
        qube.point_at(server.url)
        discover = qube.run("vdirsyncer", "discover", "calendar")
        assert discover.returncode == 0, discover.stdout + discover.stderr
        return qube

    return make


def another_device(server: CalendarServer) -> tuple[Device, str]:
    device = Device(server.url, OWNER, PASSWORD, str(server.certificate))
    return device, device.find_calendar()


def event(uid: str, title: str) -> str:
    return "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//personal-calendar//test//EN",
        "BEGIN:VEVENT", f"UID:{uid}", "DTSTAMP:20300101T000000Z",
        "DTSTART:20300315T090000Z", "DTEND:20300315T093000Z", f"SUMMARY:{title}",
        "END:VEVENT", "END:VCALENDAR", "",
    ])


def put_event(server: CalendarServer, uid: str, title: str) -> None:
    device, calendar = another_device(server)
    response = device.request(
        "PUT", f"{calendar}{uid}.ics", event(uid, title),
        {"Content-Type": "text/calendar; charset=utf-8"},
    )
    assert response.status in (201, 204), response.status


def server_titles(server: CalendarServer) -> list[str]:
    device, calendar = another_device(server)
    listing = device.propfind(calendar, "<d:getetag/>", "1")
    titles = []
    for href in listing.iter("{DAV:}href"):
        if href.text and href.text.endswith(".ics"):
            body = device.request("GET", f"{calendar}{href.text.rsplit('/', 1)[1]}").body
            titles += [
                line.removeprefix("SUMMARY:")
                for line in body.decode().splitlines()
                if line.startswith("SUMMARY:")
            ]
    return sorted(titles)


def test_an_event_from_another_device_appears_in_khal(
    start_server: StartServer, make_calendar_qube: MakeCalendarQube
) -> None:
    server = start_server()
    qube = make_calendar_qube(server)
    put_event(server, "from-phone", "Dentist")

    result = qube.sync()

    assert result.returncode == 0, result.stdout + result.stderr
    assert qube.titles() == ["Dentist"]


def test_an_event_created_in_khal_reaches_the_calendar_server(
    start_server: StartServer, make_calendar_qube: MakeCalendarQube
) -> None:
    server = start_server()
    qube = make_calendar_qube(server)
    qube.new_event("Haircut")

    result = qube.sync()

    assert result.returncode == 0, result.stdout + result.stderr
    assert server_titles(server) == ["Haircut"]


def test_deleting_an_event_file_deletes_it_on_the_calendar_server(
    start_server: StartServer, make_calendar_qube: MakeCalendarQube
) -> None:
    server = start_server()
    qube = make_calendar_qube(server)
    put_event(server, "keep", "Dentist")
    qube.new_event("Calendar Qube test")
    assert qube.sync().returncode == 0
    [test_event] = [f for f in qube.event_files() if "Calendar Qube test" in f.read_text()]

    test_event.unlink()
    result = qube.sync()

    assert result.returncode == 0, result.stdout + result.stderr
    assert server_titles(server) == ["Dentist"]


def test_emptying_the_local_copy_needs_force_delete(
    start_server: StartServer, make_calendar_qube: MakeCalendarQube
) -> None:
    """A wiped local copy must not wipe the Calendar Server by itself."""
    server = start_server()
    qube = make_calendar_qube(server)
    qube.new_event("Calendar Qube test")
    assert qube.sync().returncode == 0
    [test_event] = qube.event_files()
    test_event.unlink()

    refused = qube.sync()

    assert refused.returncode != 0
    assert server_titles(server) == ["Calendar Qube test"]

    forced = qube.run("vdirsyncer", "sync", "--force-delete", "calendar")

    assert forced.returncode == 0, forced.stdout + forced.stderr
    assert server_titles(server) == []


def test_khal_works_while_the_calendar_server_is_unreachable(
    start_server: StartServer, make_calendar_qube: MakeCalendarQube
) -> None:
    server = start_server()
    qube = make_calendar_qube(server)
    put_event(server, "before", "Dentist")
    assert qube.sync().returncode == 0

    qube.point_at("https://localhost:1/")  # nothing listens there
    offline = qube.sync()
    qube.new_event("Haircut")

    assert offline.returncode != 0
    assert sorted(qube.titles()) == ["Dentist", "Haircut"]

    qube.point_at(server.url)
    back = qube.sync()

    assert back.returncode == 0, back.stdout + back.stderr
    assert server_titles(server) == ["Dentist", "Haircut"]


def edit_on_two_devices(
    server: CalendarServer, make_calendar_qube: MakeCalendarQube
) -> CalendarQube:
    """Edit one event on the desktop and the laptop; Sync only the desktop.
    Returns the laptop, whose next Sync meets the conflict."""
    desktop, laptop = make_calendar_qube(server), make_calendar_qube(server)
    put_event(server, "shared", "Dentist")
    assert desktop.sync().returncode == 0
    assert laptop.sync().returncode == 0
    for qube, title in ((desktop, "Dentist at 9"), (laptop, "Dentist at 10")):
        [file] = qube.event_files()
        file.write_text(file.read_text().replace("SUMMARY:Dentist", f"SUMMARY:{title}"))
    assert desktop.sync().returncode == 0
    return laptop


def test_editing_one_event_on_two_devices_is_a_conflict_not_an_overwrite(
    start_server: StartServer, make_calendar_qube: MakeCalendarQube
) -> None:
    server = start_server()
    laptop = edit_on_two_devices(server, make_calendar_qube)

    conflict = laptop.sync()

    assert conflict.returncode != 0
    assert "One item changed on both sides" in conflict.stdout
    assert "Calendar conflict" in laptop.notifications()
    assert server_titles(server) == ["Dentist at 9"]
    assert laptop.titles() == ["Dentist at 10"]


def test_an_unreachable_calendar_server_does_not_notify(
    start_server: StartServer, make_calendar_qube: MakeCalendarQube
) -> None:
    qube = make_calendar_qube(start_server())
    qube.point_at("https://localhost:1/")

    assert qube.sync().returncode != 0
    assert qube.notifications() == ""


@pytest.mark.parametrize(
    ("keep", "title"), [("local", "Dentist at 10"), ("server", "Dentist at 9")]
)
def test_the_owner_resolves_a_conflict_by_choosing_a_side(
    start_server: StartServer, make_calendar_qube: MakeCalendarQube, keep: str, title: str
) -> None:
    server = start_server()
    laptop = edit_on_two_devices(server, make_calendar_qube)
    assert laptop.sync().returncode != 0

    resolved = laptop.sync("--keep", keep)

    assert resolved.returncode == 0, resolved.stdout + resolved.stderr
    assert server_titles(server) == [title]
    assert laptop.titles() == [title]
    assert laptop.sync().returncode == 0


def fingerprint(pem: str) -> str:
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()


def test_the_laptop_syncs_by_ip_with_a_certificate_fetched_over_the_network(
    start_server: StartServer, make_calendar_qube: MakeCalendarQube
) -> None:
    """The laptop's Calendar Qube differs from the desktop's only in the
    address: the desktop's IP on the Home Network. It fetches the certificate
    from that address, as setup-calendar-qube.sh --laptop has the Owner do,
    and trusts it once its fingerprint matches the Calendar Server's own."""
    server = start_server()
    port = int(server.url.rstrip("/").rsplit(":", 1)[1])
    by_ip = f"https://127.0.0.1:{port}/"
    fetched = ssl.get_server_certificate(("127.0.0.1", port))
    assert fingerprint(fetched) == fingerprint(server.certificate.read_text())
    desktop, laptop = make_calendar_qube(server), make_calendar_qube(server)
    (laptop.home / ".config/vdirsyncer/server.crt").write_text(fetched)
    laptop.point_at(by_ip)
    assert laptop.run("vdirsyncer", "discover", "calendar").returncode == 0  # as install.sh does
    put_event(server, "from-desktop", "Dentist")

    result = laptop.sync()

    assert result.returncode == 0, result.stdout + result.stderr
    assert laptop.titles() == ["Dentist"]
    desktop_config = (desktop.home / ".config/vdirsyncer/config").read_text()
    laptop_config = (laptop.home / ".config/vdirsyncer/config").read_text()
    assert laptop_config == desktop_config.replace(server.url, by_ip)
