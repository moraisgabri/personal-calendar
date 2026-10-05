"""Generate the Calendar Server's secrets: a long-lived self-signed
certificate and a password file for the Owner.

Run once inside the `calendar-server` qube (install.sh does this). The
Owner's password is read from stdin, never from the command line. The output
directory holds the private key and password hash, so it must never be
committed.
"""

import argparse
import datetime
import ipaddress
import os
import sys
from pathlib import Path

import bcrypt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

# Long enough that the Owner never re-trusts it on every Device.
CERTIFICATE_LIFETIME = datetime.timedelta(days=20 * 365)


def subject_alternative_name(names: list[str]) -> x509.SubjectAlternativeName:
    entries: list[x509.GeneralName] = []
    for name in names:
        try:
            entries.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            entries.append(x509.DNSName(name))
    return x509.SubjectAlternativeName(entries)


def write_certificate(directory: Path, names: list[str]) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Calendar Server")])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + CERTIFICATE_LIFETIME)
        .add_extension(subject_alternative_name(names), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(key, hashes.SHA256())
    )
    write_private(
        directory / "server.key",
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    (directory / "server.crt").write_bytes(
        certificate.public_bytes(serialization.Encoding.PEM)
    )


def write_password_file(directory: Path, user: str, password: str) -> None:
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    write_private(directory / "users", f"{user}:{hashed}\n".encode())


def write_private(path: Path, content: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="where to write the secrets")
    parser.add_argument("--user", default="owner", help="the Owner's user name")
    parser.add_argument(
        "--name",
        action="append",
        required=True,
        help="a host name or IP address Devices use to reach the Calendar "
        "Server (repeatable)",
    )
    parser.add_argument(
        "--certificate-only",
        action="store_true",
        help="re-make only the certificate, keeping the existing password",
    )
    args = parser.parse_args()

    args.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not args.certificate_only:
        password = sys.stdin.readline().rstrip("\n")
        if not password:
            sys.exit("No password given on stdin.")
        write_password_file(args.directory, args.user, password)
    write_certificate(args.directory, args.name)


if __name__ == "__main__":
    main()
