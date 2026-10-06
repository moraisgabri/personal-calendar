"""Thunderbird in a Calendar Qube, set up by calendar-qube/install-thunderbird.sh
against a real Calendar Server. Thunderbird itself isn't run: the tests read
what it would load from its profile (its preferences and its NSS certificate
store) and check that against the Calendar Server."""

import json
import os
import re
import subprocess
from pathlib import Path

from cryptography import x509

from conftest import OWNER, PASSWORD, REPO, CalendarServer, StartServer
from personal_calendar.sync_check import Device

INSTALL = REPO / "calendar-qube" / "install-thunderbird.sh"
PREF = re.compile(r'^user_pref\("([^"]+)",\s*(.+)\);\s*$')


PROFILE = "x1y2z3.default-release"


def make_home(tmp_path: Path, name: str = "home") -> Path:
    """A Calendar Qube's home after the Owner started Thunderbird once."""
    home = tmp_path / name
    profile_of(home).mkdir(parents=True)
    (home / ".thunderbird" / "profiles.ini").write_text(
        f"[Profile0]\nName=default-release\nIsRelative=1\nPath={PROFILE}\n\n"
        "[General]\nStartWithLastProfile=1\nVersion=2\n\n"
        f"[InstallFDC34C9F024745EB]\nDefault={PROFILE}\nLocked=1\n"
    )
    return home


def profile_of(home: Path) -> Path:
    return home / ".thunderbird" / PROFILE


def install(home: Path, server: CalendarServer) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALL), "--server", server.url, "--certificate", str(server.certificate)],
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
        timeout=60,
    )


def prefs(profile: Path) -> dict[str, object]:
    """The preferences Thunderbird starts with: prefs.js, then user.js on top."""
    found: dict[str, object] = {}
    for name in ("prefs.js", "user.js"):
        file = profile / name
        if file.exists():
            for line in file.read_text().splitlines():
                if match := PREF.match(line):
                    found[match[1]] = json.loads(match[2])
    return found


def caldav_calendars(profile: Path) -> list[dict[str, object]]:
    registry: dict[str, dict[str, object]] = {}
    for key, value in prefs(profile).items():
        if key.startswith("calendar.registry."):
            calendar_id, _, setting = key.removeprefix("calendar.registry.").partition(".")
            registry.setdefault(calendar_id, {})[setting] = value
    return [c for c in registry.values() if c.get("type") == "caldav"]


def trusted_for_https(profile: Path, certificate: Path) -> bool:
    """Whether Thunderbird's certificate store accepts this certificate for an
    HTTPS server, whatever name it was stored under."""
    if not usable_as_a_servers_own(certificate):
        return False
    store = f"sql:{profile}"
    wanted = "".join(certificate.read_text().split())
    listed = subprocess.run(["certutil", "-L", "-d", store], capture_output=True, text=True)
    if listed.returncode != 0:  # no certificate store yet
        return False
    listing = listed.stdout.splitlines()[4:]
    for nickname in (line[:60].strip() for line in listing if line.strip()):
        pem = subprocess.run(
            ["certutil", "-L", "-d", store, "-n", nickname, "-a"],
            capture_output=True, text=True, check=True,
        ).stdout
        if "".join(pem.split()) == wanted:
            verify = subprocess.run(
                ["certutil", "-V", "-d", store, "-n", nickname, "-u", "V"],
                capture_output=True, text=True,
            )
            return verify.returncode == 0
    return False


def usable_as_a_servers_own(certificate: Path) -> bool:
    """Thunderbird refuses a CA certificate as a server's own, even a trusted
    one (mozilla::pkix, ERROR_CA_CERT_USED_AS_END_ENTITY). certutil -V doesn't
    apply that rule, so it is checked here."""
    loaded = x509.load_pem_x509_certificate(certificate.read_bytes())
    try:
        constraints = loaded.extensions.get_extension_for_class(x509.BasicConstraints)
    except x509.ExtensionNotFound:
        return True
    return not constraints.value.ca


def the_calendar_on(server: CalendarServer) -> str:
    return Device(server.url, OWNER, PASSWORD, str(server.certificate)).find_calendar()


def test_thunderbird_shows_the_calendar_from_the_calendar_server(
    start_server: StartServer, tmp_path: Path
) -> None:
    server = start_server()
    home = make_home(tmp_path)

    result = install(home, server)

    assert result.returncode == 0, result.stdout + result.stderr
    [calendar] = caldav_calendars(profile_of(home))
    assert calendar["username"] == OWNER
    assert calendar["cache.enabled"] is True
    assert calendar["uri"] == the_calendar_on(server)
    # Thunderbird shows a calendar loaded from its preferences in its views
    # only when this is set, not merely when it is missing.
    assert calendar["calendar-main-in-composite"] is True


def test_thunderbird_trusts_the_calendar_servers_certificate(
    start_server: StartServer, tmp_path: Path
) -> None:
    server = start_server()
    home = make_home(tmp_path)

    result = install(home, server)

    assert result.returncode == 0, result.stdout + result.stderr
    assert trusted_for_https(profile_of(home), server.certificate)


def test_the_laptops_setup_differs_from_the_desktops_only_in_the_address(
    start_server: StartServer, tmp_path: Path
) -> None:
    desktop_server, laptop_server = start_server(), start_server()
    desktop, laptop = make_home(tmp_path, "desktop"), make_home(tmp_path, "laptop")

    assert install(desktop, desktop_server).returncode == 0
    assert install(laptop, laptop_server).returncode == 0

    def without_address(home: Path, server: CalendarServer) -> list[dict[str, object]]:
        [calendar] = caldav_calendars(profile_of(home))
        assert calendar["uri"] == the_calendar_on(server)
        return [{**calendar, "uri": "ADDRESS"}]

    assert without_address(desktop, desktop_server) == without_address(laptop, laptop_server)
    assert trusted_for_https(profile_of(desktop), desktop_server.certificate)
    assert trusted_for_https(profile_of(laptop), laptop_server.certificate)


def test_re_running_with_a_new_address_moves_the_calendar_and_keeps_the_owners_settings(
    start_server: StartServer, tmp_path: Path
) -> None:
    old, new = start_server(), start_server()
    home = make_home(tmp_path)
    (profile_of(home) / "user.js").write_text('user_pref("mail.shell.checkDefaultClient", false);\n')
    assert install(home, old).returncode == 0

    result = install(home, new)

    assert result.returncode == 0, result.stdout + result.stderr
    [calendar] = caldav_calendars(profile_of(home))
    assert calendar["uri"] == the_calendar_on(new)
    assert prefs(profile_of(home))["mail.shell.checkDefaultClient"] is False
    assert trusted_for_https(profile_of(home), new.certificate)


def test_refuses_while_thunderbird_is_open_and_changes_nothing(
    start_server: StartServer, tmp_path: Path
) -> None:
    server = start_server()
    home = make_home(tmp_path)
    profile = profile_of(home)
    # Thunderbird's lock while it runs: a symlink naming its host and process.
    (profile / "lock").symlink_to(f"127.0.0.1:+{os.getpid()}")

    result = install(home, server)

    assert result.returncode != 0
    assert "Close Thunderbird" in result.stderr
    assert caldav_calendars(profile) == []
    assert not trusted_for_https(profile, server.certificate)


def test_a_lock_left_by_a_crashed_thunderbird_does_not_block(
    start_server: StartServer, tmp_path: Path
) -> None:
    server = start_server()
    home = make_home(tmp_path)
    # Above Linux's highest process id, so no process has it.
    (profile_of(home) / "lock").symlink_to(f"127.0.0.1:+{2**22 + 1}")

    result = install(home, server)

    assert result.returncode == 0, result.stdout + result.stderr


def test_says_to_start_thunderbird_once_when_it_has_no_profile_yet(
    start_server: StartServer, tmp_path: Path
) -> None:
    server = start_server()
    home = tmp_path / "home"
    home.mkdir()

    result = install(home, server)

    assert result.returncode != 0
    assert "Start Thunderbird once" in result.stderr
