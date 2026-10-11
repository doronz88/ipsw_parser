from pathlib import Path

import pytest

from ipsw_parser import build_identity
from ipsw_parser.process import ProcessExecutionError

PROFILES = ["baseline", "com.apple.cloudd", "com.apple.homed", "spotlightknowledged", "spotlightknowledged.updater"]


def _fake_ipsw(calls: list) -> object:
    def run(tool: str, *args: object) -> str:
        calls.append((tool, *map(str, args)))
        assert tool == "ipsw"
        if args[1] == "list":
            return "\n".join(PROFILES) + "\n"
        name = str(args[3])
        if name == "com.apple.homed":
            raise ProcessExecutionError(["ipsw", "sb", "dec"], 1, "", "cannot decode")
        return f"(profile {name})\n"

    return run


def test_every_profile_gets_a_file_of_its_own(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    monkeypatch.setattr(build_identity, "run", _fake_ipsw(calls))
    output = tmp_path / "profiles"

    build_identity._decode_sandbox_profiles(tmp_path / "kernelcache", output)

    # A dotted name keeps all of its parts, and a profile that fails to decode is skipped
    assert {path.name: path.read_text() for path in output.iterdir()} == {
        "baseline.sb": "(profile baseline)\n",
        "com.apple.cloudd.sb": "(profile com.apple.cloudd)\n",
        "spotlightknowledged.sb": "(profile spotlightknowledged)\n",
        "spotlightknowledged.updater.sb": "(profile spotlightknowledged.updater)\n",
    }


def test_profile_type_is_passed_to_list_and_decode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list = []
    monkeypatch.setattr(build_identity, "run", _fake_ipsw(calls))
    kernel = tmp_path / "kernelcache"

    build_identity._decode_sandbox_profiles(kernel, tmp_path / "protobox", profile_type="protobox")

    assert calls[0] == ("ipsw", "sb", "list", str(kernel), "--type", "protobox")
    assert ("ipsw", "sb", "dec", str(kernel), "spotlightknowledged.updater", "--type", "protobox") in calls
