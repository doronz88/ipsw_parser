import plistlib
from pathlib import Path

import pytest

from ipsw_parser import build_identity
from ipsw_parser.archive import DirectoryArchive
from ipsw_parser.ipsw import IPSW


def test_kernelcache_payload_is_sliced_by_arch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "BuildManifest.plist").write_bytes(
        plistlib.dumps({
            "SupportedProductTypes": ["iPhone1,1"],
            "ProductVersion": "1.0",
            "ProductBuildVersion": "1A1",
            "BuildIdentities": [
                {"Info": {"DeviceClass": "N61AP"}, "Manifest": {"KernelCache": {"Info": {"Path": "kernelcache"}}}}
            ],
        })
    )
    (tmp_path / "kernelcache").write_bytes(b"im4p")
    monkeypatch.setattr(build_identity, "_im4p_payload", lambda data: b"fat kernel")

    def lipo(tool: str, *args: object) -> str:
        assert (tool, *map(str, args[:4])) == ("ipsw", "macho", "lipo", "-a", "arm64e")
        kernel = Path(str(args[4]))
        # lipo slices the kernel it is given, so it must already hold the payload
        assert kernel.read_bytes() == b"fat kernel"
        kernel.with_name(f"{kernel.name}.arm64e").write_bytes(b"thin kernel")
        return ""

    monkeypatch.setattr(build_identity, "run", lipo)

    ipsw = IPSW(DirectoryArchive(tmp_path))
    assert ipsw.build_manifest.build_identities[0].get_kernelcache_payload() == b"fat kernel"
    assert ipsw.build_manifest.build_identities[0].get_kernelcache_payload(arch="arm64e") == b"thin kernel"
