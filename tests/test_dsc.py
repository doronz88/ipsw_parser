from pathlib import Path

import pytest

from ipsw_parser import dsc
from ipsw_parser.process import ProcessExecutionError

CRYPTEX_SYMLINK_DSC = "System/Cryptexes/OS/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64e"
CRYPTEX_DSC = "private/preboot/Cryptexes/OS/System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64e"
SYSTEM_DSC = "System/Library/Caches/com.apple.dyld/dyld_shared_cache_arm64e"


def _create(root: Path, path: str) -> Path:
    file = root / path
    file.parent.mkdir(parents=True)
    file.write_bytes(b"dsc")
    return file


@pytest.fixture
def commands(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    commands: list[tuple[str, ...]] = []

    def run(*argv: object) -> str:
        commands.append(tuple(str(arg) for arg in argv))
        return ""

    monkeypatch.setattr(dsc, "run", run)
    return commands


@pytest.mark.parametrize("path", [SYSTEM_DSC, CRYPTEX_DSC, CRYPTEX_SYMLINK_DSC])
def test_split_dsc_finds_the_cache(tmp_path: Path, commands: list[tuple[str, ...]], path: str) -> None:
    cache = _create(tmp_path, path)

    assert dsc.split_dsc(tmp_path) == [cache]
    assert commands == [("ipsw", "dyld", "split", str(cache), "-o", str(tmp_path))]


def test_split_dsc_extracts_a_cache_the_splitter_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = _create(tmp_path, CRYPTEX_DSC)
    commands: list[tuple[str, ...]] = []

    def run(*argv: object) -> str:
        commands.append(tuple(str(arg) for arg in argv))
        if argv[2] == "split":
            raise ProcessExecutionError(list(commands[-1]), 1, "", "code signature for page 0 is incorrect")
        return ""

    monkeypatch.setattr(dsc, "run", run)

    assert dsc.split_dsc(tmp_path) == [cache]
    assert commands == [
        ("ipsw", "dyld", "split", str(cache), "-o", str(tmp_path)),
        ("ipsw", "dyld", "extract", str(cache), "--all", "--output", str(tmp_path)),
    ]


@pytest.mark.parametrize("path", [CRYPTEX_DSC, CRYPTEX_SYMLINK_DSC])
def test_device_support_layout_removes_the_split_cryptex_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, commands: list[tuple[str, ...]], path: str
) -> None:
    device_support = tmp_path / "DeviceSupport"
    symbols = device_support / "Symbols"
    cache = _create(symbols, path)
    monkeypatch.setattr(dsc, "get_device_support_path", lambda *args: device_support)

    assert dsc.create_device_support_layout("iPhone15,2", "16.0", "20A362", symbols) == device_support

    assert len(commands) == 1
    assert not cache.exists()
    assert (device_support / ".finalized").exists()


def test_device_support_layout_is_not_finalized_without_a_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, commands: list[tuple[str, ...]]
) -> None:
    device_support = tmp_path / "DeviceSupport"
    symbols = device_support / "Symbols"
    symbols.mkdir(parents=True)
    monkeypatch.setattr(dsc, "get_device_support_path", lambda *args: device_support)

    with pytest.raises(FileNotFoundError):
        dsc.create_device_support_layout("iPhone15,2", "16.0", "20A362", symbols)

    assert commands == []
    assert not (device_support / ".finalized").exists()
