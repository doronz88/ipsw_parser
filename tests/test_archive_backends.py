import plistlib
from pathlib import Path
from zipfile import ZipFile, ZipInfo

from ipsw_parser.archive import DirectoryArchive, ZipArchive
from ipsw_parser.ipsw import IPSW


def _build_manifest() -> bytes:
    return plistlib.dumps({
        "SupportedProductTypes": ["iPhone1,1"],
        "ProductVersion": "1.0",
        "ProductBuildVersion": "1A1",
        "BuildIdentities": [],
    })


def _write_ipsw_layout(root: Path) -> None:
    (root / "BuildManifest.plist").write_bytes(_build_manifest())
    (root / "RestoreVersion.plist").write_bytes(b"restore-version")
    (root / "SystemVersion.plist").write_bytes(b"system-version")
    firmware = root / "Firmware"
    firmware.mkdir()
    (firmware / "devel-file.bin").write_bytes(b"dev")
    release = root / "Release"
    release.mkdir()
    (release / "normal-file.bin").write_bytes(b"release")


def test_directory_archive_supports_ipsw_loading(tmp_path: Path) -> None:
    _write_ipsw_layout(tmp_path)

    ipsw = IPSW(DirectoryArchive(tmp_path))

    assert ipsw.build_manifest.product_version == "1.0"
    assert ipsw.restore_version == b"restore-version"
    assert ipsw.system_version == b"system-version"
    assert ipsw.get_development_files() == ["Firmware/devel-file.bin"]


def test_zip_archive_supports_same_ipsw_behavior(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _write_ipsw_layout(source)

    archive_path = tmp_path / "sample.ipsw"
    with ZipFile(archive_path, "w") as archive:
        for file_path in sorted(path for path in source.rglob("*") if path.is_file()):
            archive.write(file_path, arcname=file_path.relative_to(source).as_posix())

    with ZipFile(archive_path) as archive:
        ipsw = IPSW(ZipArchive(archive))

        assert ipsw.build_manifest.product_build_version == "1A1"
        assert ipsw.restore_version == b"restore-version"
        assert ipsw.get_development_files() == ["Firmware/devel-file.bin"]


def test_directory_extractall_copies_requested_members(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    _write_ipsw_layout(source)
    archive = DirectoryArchive(source)

    output = tmp_path / "output"
    members = [member for member in archive.filelist if member.filename.startswith("Firmware")]
    archive.extractall(output, members)

    assert (output / "Firmware" / "devel-file.bin").read_bytes() == b"dev"
    assert not (output / "Release" / "normal-file.bin").exists()


def _cpio_header(ino: int, mode: int, namesize: int, filesize: int) -> bytes:
    return f"070707000000{ino:06o}{mode:06o}000000000000000001000000{0:011o}{namesize:06o}{filesize:011o}".encode()


def test_bootability_builds_odc_cpio_archive(tmp_path: Path) -> None:
    archive_path = tmp_path / "sample.ipsw"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("BuildManifest.plist", _build_manifest())
        for name, mode, data in (
            ("BootabilityBundle/Restore/Bootability/payload.bin", 0o100644, b"hello"),
            ("BootabilityBundle/Restore/Bootability/empty", 0o100600, b""),
            ("BootabilityBundle/Restore/Firmware/Bootability.dmg.trustcache", 0o100644, b"trust"),
            ("Firmware/unrelated.bin", 0o100644, b"ignored"),
        ):
            info = ZipInfo(name)
            info.external_attr = mode << 16
            archive.writestr(info, data)

    with ZipFile(archive_path) as archive:
        bootability = IPSW(ZipArchive(archive)).bootability

    assert bootability == (
        _cpio_header(1, 0o100644, 12, 5)
        + b"payload.bin\0hello"
        + _cpio_header(2, 0o100600, 6, 0)
        + b"empty\0"
        + _cpio_header(3, 0o100644, 23, 5)
        + b"Bootability.trustcache\0trust"
        + _cpio_header(0, 0, 11, 0)
        + b"TRAILER!!!\0"
    )
