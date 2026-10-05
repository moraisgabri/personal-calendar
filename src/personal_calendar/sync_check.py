"""Sync check: prove a Calendar Server works, acting as a Device would.

Creates, reads back and deletes a uniquely named test event in the Owner's
Calendar, then confirms that a wrong password and plain HTTP are both
refused. Prints one line per step and exits non-zero if any step failed.

Standard library only, so it runs on any qube with Python 3.11+:

    CALENDAR_PASSWORD=... python3 sync_check.py https://calendar-server:5232/ \\
        --user owner --certificate server.crt

Without CALENDAR_PASSWORD the password is prompted for.
"""

import argparse
import base64
import getpass
import http.client
import os
import secrets
import ssl
import sys
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

TIMEOUT_SECONDS = 15

DAV = "{DAV:}"
CALDAV = "{urn:ietf:params:xml:ns:caldav}"


class StepFailed(Exception):
    pass


@dataclass
class Response:
    status: int
    body: bytes


class Device:
    """Talks CalDAV over HTTPS to one Calendar Server, as one Owner."""

    def __init__(self, url: str, user: str, password: str, certificate: str) -> None:
        self.url = url
        self.user = user
        self.password = password
        self.context = ssl.create_default_context(cafile=certificate)

    def request(
        self,
        method: str,
        url: str,
        body: str = "",
        headers: dict[str, str] | None = None,
        password: str | None = None,
    ) -> Response:
        parts = urlsplit(url)
        credentials = f"{self.user}:{password or self.password}".encode()
        all_headers = {
            "Authorization": "Basic " + base64.b64encode(credentials).decode(),
            **(headers or {}),
        }
        connection = http.client.HTTPSConnection(
            parts.netloc, timeout=TIMEOUT_SECONDS, context=self.context
        )
        try:
            connection.request(method, parts.path or "/", body.encode(), all_headers)
            response = connection.getresponse()
            return Response(response.status, response.read())
        except ssl.SSLCertVerificationError as error:
            raise StepFailed(
                f"the Calendar Server's certificate is not the one given "
                f"({error.verify_message})"
            ) from error
        except ssl.SSLError as error:
            raise StepFailed(f"HTTPS handshake failed ({error})") from error
        except OSError as error:
            raise StepFailed(f"cannot reach {parts.netloc} ({error})") from error
        finally:
            connection.close()

    def propfind(self, url: str, prop: str, depth: str) -> ET.Element:
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'
            f"<d:prop>{prop}</d:prop></d:propfind>"
        )
        response = self.request(
            "PROPFIND",
            url,
            body,
            {"Depth": depth, "Content-Type": "application/xml; charset=utf-8"},
        )
        if response.status == 401:
            raise StepFailed("the Calendar Server refused the password")
        if response.status != 207:
            raise StepFailed(f"PROPFIND {url} answered {response.status}")
        return ET.fromstring(response.body)

    def href(self, url: str, prop: str, element: str) -> str:
        found = self.propfind(url, prop, "0").find(f".//{element}/{DAV}href")
        if found is None or not found.text:
            raise StepFailed(f"{url} did not report {element}")
        return urljoin(url, found.text)

    def find_calendar(self) -> str:
        principal = self.href(
            self.url, "<d:current-user-principal/>", f"{DAV}current-user-principal"
        )
        home = self.href(
            principal, "<c:calendar-home-set/>", f"{CALDAV}calendar-home-set"
        )
        listing = self.propfind(home, "<d:resourcetype/>", "1")
        for response in listing.iter(f"{DAV}response"):
            href = response.find(f"{DAV}href")
            is_calendar = response.find(f".//{DAV}resourcetype/{CALDAV}calendar")
            if href is not None and href.text and is_calendar is not None:
                return urljoin(home, href.text)
        raise StepFailed(f"no Calendar found under {home}")


def make_test_event(uid: str) -> str:
    return "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//personal-calendar//sync-check//EN",
            "BEGIN:VEVENT",
            f"UID:{uid}",
            "DTSTAMP:20260101T000000Z",
            "DTSTART:20260101T090000Z",
            "DTEND:20260101T091500Z",
            "SUMMARY:Sync check test event (safe to delete)",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )


class SyncCheck:
    def __init__(self, device: Device) -> None:
        self.device = device
        self.failed = False
        self.calendar = ""
        self.event_url = ""
        self.uid = f"sync-check-{uuid.uuid4()}"
        self.event_may_exist = False

    def step(self, name: str, action: Callable[[], None]) -> bool:
        try:
            action()
        except StepFailed as error:
            print(f"FAIL  {name}: {error}")
            self.failed = True
            return False
        print(f"ok    {name}")
        return True

    def skip(self, name: str) -> None:
        print(f"skip  {name}")

    def run(self) -> bool:
        """Run every step; return True if all of them passed."""
        crud = [
            ("find the Calendar", self.find_calendar),
            ("create the test event", self.create),
            ("read the test event back", self.read),
            ("delete the test event", self.delete),
        ]
        try:
            for index, (name, action) in enumerate(crud):
                if not self.step(name, action):
                    for skipped, _ in crud[index + 1 :]:
                        self.skip(skipped)
                    break
        finally:
            if self.event_may_exist:
                self.step("clean up the test event", self.clean_up)
        self.step("wrong password is refused", self.wrong_password_refused)
        self.step("plain HTTP is refused", self.plain_http_refused)
        return not self.failed

    def find_calendar(self) -> None:
        self.calendar = self.device.find_calendar()
        self.event_url = urljoin(self.calendar, f"{self.uid}.ics")

    def create(self) -> None:
        # Set before sending: the PUT may land even if its reply is lost.
        self.event_may_exist = True
        response = self.device.request(
            "PUT",
            self.event_url,
            make_test_event(self.uid),
            {"Content-Type": "text/calendar; charset=utf-8", "If-None-Match": "*"},
        )
        if response.status not in (200, 201, 204):
            raise StepFailed(f"PUT answered {response.status}")

    def read(self) -> None:
        response = self.device.request("GET", self.event_url)
        if response.status != 200:
            raise StepFailed(f"GET answered {response.status}")
        if self.uid.encode() not in response.body:
            raise StepFailed("the event read back is not the one created")

    def delete(self) -> None:
        response = self.device.request("DELETE", self.event_url)
        if response.status not in (200, 204):
            raise StepFailed(f"DELETE answered {response.status}")
        self.event_may_exist = False
        if self.device.request("GET", self.event_url).status != 404:
            raise StepFailed("the event is still there after DELETE")

    def clean_up(self) -> None:
        response = self.device.request("DELETE", self.event_url)
        if response.status not in (200, 204, 404):
            raise StepFailed(f"DELETE answered {response.status}")

    def wrong_password_refused(self) -> None:
        wrong = secrets.token_urlsafe(16)
        response = self.device.request(
            "PROPFIND", self.device.url, headers={"Depth": "0"}, password=wrong
        )
        if response.status != 401:
            raise StepFailed(f"a wrong password got {response.status}, not 401")

    def plain_http_refused(self) -> None:
        netloc = urlsplit(self.device.url).netloc
        connection = http.client.HTTPConnection(netloc, timeout=TIMEOUT_SECONDS)
        try:
            connection.request("GET", "/")
            status = connection.getresponse().status
        except (ConnectionRefusedError, TimeoutError) as error:
            # Nothing listening proves nothing about how HTTP is treated.
            raise StepFailed(f"cannot reach {netloc} ({error})") from error
        except (OSError, http.client.HTTPException):
            # Connected, but the server dropped the plain HTTP request.
            return
        finally:
            connection.close()
        raise StepFailed(f"plain HTTP to {netloc} was served ({status})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prove a Calendar Server works, acting as a Device."
    )
    parser.add_argument("url", help="the Calendar Server's address, e.g. https://calendar-server:5232/")
    parser.add_argument("--user", required=True, help="the Owner's user name")
    parser.add_argument(
        "--certificate",
        required=True,
        help="the Calendar Server's certificate (server.crt) to trust",
    )
    args = parser.parse_args()
    if urlsplit(args.url).scheme != "https":
        parser.error("the address must start with https://")

    password = os.environ.get("CALENDAR_PASSWORD") or getpass.getpass(
        f"Password for {args.user}: "
    )
    device = Device(args.url, args.user, password, args.certificate)
    passed = SyncCheck(device).run()
    print("Sync check passed." if passed else "Sync check FAILED.")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
