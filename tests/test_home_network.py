"""The Home Network path: home-network/forward-caldav.sh as sys-net and
sys-firewall run it. Each test runs it against real nftables, in a private
network namespace holding the chains a Qubes OS 4.2 net qube starts with,
and reads back the rules the qube would end up with."""

import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO

FORWARD = REPO / "home-network" / "forward-caldav.sh"
WIZARD = REPO / "scripts" / "setup-home-network.sh"

# The part of a Qubes 4.2 net qube's own `ip qubes` table these rules meet.
QUBES_TABLE = """
table ip qubes {
	chain custom-input {
	}
	chain custom-forward {
	}
	chain forward {
		type filter hook forward priority filter; policy accept;
		jump custom-forward
		ct state established,related accept
		oifgroup 2 counter drop
	}
}
"""

LAN = "192.168.1.250/24"
SYS_NET = ["sys-net", "--lan", LAN, "--interface", "wls6", "--to", "10.138.0.7"]
SYS_FIREWALL = ["sys-firewall", "--lan", LAN, "--to", "10.137.0.20"]


def in_net_qube(script: str, **env: str) -> subprocess.CompletedProcess[str]:
    """Run a shell script as root in a fresh, empty network namespace that
    already holds Qubes' own table, then print the resulting table."""
    return subprocess.run(
        ["unshare", "--map-root-user", "--net", "sh", "-c",
         f"set -e\nnft -f - <<'EOF'\n{QUBES_TABLE}\nEOF\n{script}\nnft list table ip qubes"],
        capture_output=True, text=True, timeout=30,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", **env},
    )


def forward(*args: str) -> str:
    return f"sh {FORWARD} " + " ".join(args)


def rules(table: str, chain: str) -> list[str]:
    """The rules of one chain, as `nft list` prints them, without counts."""
    lines = table.split(f"chain {chain} {{", 1)[1].split("}", 1)[0].splitlines()
    found = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("type "):
            found.append(line.replace("counter packets 0 bytes 0 ", "counter "))
    return found


@pytest.fixture(autouse=True)
def needs_namespaces() -> None:
    if not shutil.which("nft") or not shutil.which("unshare"):
        pytest.skip("needs nft and unshare")
    probe = subprocess.run(["unshare", "--map-root-user", "--net", "nft", "list", "ruleset"],
                           capture_output=True)
    if probe.returncode != 0:
        pytest.skip("can't make a private network namespace here")


def test_sys_net_forwards_only_caldav_from_the_home_network_to_sys_firewall() -> None:
    result = in_net_qube(forward(*SYS_NET))

    assert result.returncode == 0, result.stderr
    assert rules(result.stdout, "caldav-dnat") == [
        'iifname "wls6" ip saddr 192.168.1.0/24 ip daddr 192.168.1.250 '
        "tcp dport 5232 counter dnat to 10.138.0.7"
    ]
    assert rules(result.stdout, "caldav-forward") == [
        'iifname "wls6" ip saddr 192.168.1.0/24 ip daddr 10.138.0.7 '
        "tcp dport 5232 ct state new counter accept"
    ]
    assert rules(result.stdout, "custom-forward") == ["jump caldav-forward"]


def test_sys_firewall_forwards_only_caldav_from_sys_net_to_the_calendar_server() -> None:
    result = in_net_qube(forward(*SYS_FIREWALL))

    assert result.returncode == 0, result.stderr
    assert rules(result.stdout, "caldav-dnat") == [
        "iifgroup 1 ip saddr 192.168.1.0/24 tcp dport 5232 counter dnat to 10.137.0.20"
    ]
    assert rules(result.stdout, "caldav-forward") == [
        "iifgroup 1 ip saddr 192.168.1.0/24 ip daddr 10.137.0.20 "
        "tcp dport 5232 ct state new counter accept"
    ]
    assert rules(result.stdout, "custom-forward") == ["jump caldav-forward"]


def test_running_again_replaces_the_rules_instead_of_adding_more() -> None:
    once = in_net_qube(forward(*SYS_NET))
    moved = SYS_NET[:-1] + ["10.138.0.9"]
    twice = in_net_qube(forward(*SYS_NET) + "\n" + forward(*moved) + "\n" + forward(*moved))

    assert twice.returncode == 0, twice.stderr
    assert rules(twice.stdout, "custom-forward") == ["jump caldav-forward"]
    assert rules(twice.stdout, "caldav-dnat") == [
        rule.replace("10.138.0.7", "10.138.0.9") for rule in rules(once.stdout, "caldav-dnat")
    ]
    assert len(rules(twice.stdout, "caldav-forward")) == 1


def test_owners_other_custom_forward_rules_are_kept() -> None:
    existing = ("nft add rule ip qubes custom-forward ip saddr 10.137.0.30 "
                "ip daddr 10.137.0.20 tcp dport 5232 ct state new accept")
    result = in_net_qube(existing + "\n" + forward(*SYS_FIREWALL) + "\n" + forward(*SYS_FIREWALL))

    assert result.returncode == 0, result.stderr
    assert rules(result.stdout, "custom-forward") == [
        "ip saddr 10.137.0.30 ip daddr 10.137.0.20 tcp dport 5232 ct state new accept",
        "jump caldav-forward",
    ]


@pytest.mark.parametrize("bad", [
    ["sys-net", "--lan", "192.168.1.250", "--interface", "wls6", "--to", "10.138.0.7"],
    ["sys-net", "--lan", "192.168.1.300/24", "--interface", "wls6", "--to", "10.138.0.7"],
    ["sys-net", "--lan", LAN, "--to", "10.138.0.7"],
    ["sys-net", "--lan", LAN, "--interface", "wls6; reboot", "--to", "10.138.0.7"],
    ["sys-firewall", "--lan", LAN, "--to", "calendar-server"],
    ["sys-firewall", "--lan", LAN, "--interface", "eth0", "--to", "10.137.0.20"],
    ["sys-vpn", "--lan", LAN, "--to", "10.137.0.20"],
])
def test_a_mistyped_address_changes_nothing(bad: list[str]) -> None:
    result = in_net_qube(forward(*bad))

    assert result.returncode == 2
    assert "caldav" not in result.stdout


def test_installed_rules_come_back_when_the_qube_restarts(tmp_path: Path) -> None:
    rw_config = tmp_path / "rw-config"
    rw_config.mkdir()
    user_script = rw_config / "qubes-firewall-user-script"
    earlier = ("nft add rule ip qubes custom-forward ip saddr 10.137.0.30 "
               "ip daddr 10.137.0.20 tcp dport 5232 ct state new accept")
    user_script.write_text(earlier + "\n")  # an earlier wizard's rule, no shebang
    env = {"QUBES_RW_CONFIG": str(rw_config)}

    first = in_net_qube(forward(*SYS_FIREWALL, "--install"), **env)
    in_net_qube(forward(*SYS_FIREWALL, "--install"), **env)
    restarted = in_net_qube(str(user_script), **env)

    assert first.returncode == 0, first.stderr
    assert restarted.returncode == 0, restarted.stderr
    assert rules(restarted.stdout, "custom-forward") == [
        "ip saddr 10.137.0.30 ip daddr 10.137.0.20 tcp dport 5232 ct state new accept",
        "jump caldav-forward",
    ]
    assert rules(restarted.stdout, "caldav-forward") == rules(first.stdout, "caldav-forward")
    assert rules(restarted.stdout, "caldav-dnat") == rules(first.stdout, "caldav-dnat")
    lines = user_script.read_text().splitlines()
    assert lines[0] == "#!/bin/sh"
    assert earlier in lines
    assert sum("forward-caldav.sh" in line for line in lines) == 1


def test_print_shows_the_rules_and_needs_no_root() -> None:
    result = subprocess.run(["sh", str(FORWARD), *SYS_NET, "--print"],
                            capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert "dnat to 10.138.0.7" in result.stdout
    assert "dport 5232" in result.stdout


def test_the_wizard_parses() -> None:
    subprocess.run(["bash", "-n", str(WIZARD)], check=True)
