import plistlib
from pathlib import Path

from ipsw_parser.archive import DirectoryArchive
from ipsw_parser.ipsw import IPSW


def test_firmware_maps_manifest_files_by_prefix(tmp_path: Path) -> None:
    (tmp_path / "BuildManifest.plist").write_bytes(
        plistlib.dumps({
            "SupportedProductTypes": ["iPhone1,1"],
            "ProductVersion": "1.0",
            "ProductBuildVersion": "1A1",
            "BuildIdentities": [],
        })
    )
    firmware = tmp_path / "Firmware/all_flash/all_flash.n61ap.production"
    firmware.mkdir(parents=True)
    (firmware / "manifest").write_bytes(
        b"LLB.n61.RELEASE.img3\napplelogo@2x.s5l8960x.img3\nunknown.img3\nsep-firmware.n61.RELEASE.im4p\n"
    )

    files = IPSW(DirectoryArchive(tmp_path)).get_firmware("Firmware/all_flash/all_flash.n61ap.production").get_files()

    prefix = "Firmware/all_flash/all_flash.n61ap.production"
    assert files == {
        "LLB": f"{prefix}/LLB.n61.RELEASE.img3",
        "AppleLogo": f"{prefix}/applelogo@2x.s5l8960x.img3",
        "RestoreSEP": f"{prefix}/sep-firmware.n61.RELEASE.im4p",
    }
