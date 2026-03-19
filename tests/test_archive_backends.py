import plistlib
from pathlib import Path
from zipfile import ZipFile

from ipsw_parser.archive import DirectoryArchive, ZipArchive
from ipsw_parser.ipsw import IPSW


def _build_manifest() -> bytes:
    return plistlib.dumps({
        "SupportedProductTypes": ["iPhone1,1"],
        "ProductVersion": "1.0",
        "ProductBuildVersion": "1A1",
        "BuildIdentities": [],
    })


def _write_ipsw_layout(root: Path, manifest_name: str = "BuildManifest.plist", manifest: Optional[bytes] = None) -> None:
    (root / manifest_name).write_bytes(manifest or _build_manifest())
    (root / "RestoreVersion.plist").write_bytes(b"restore-version")
    (root / "SystemVersion.plist").write_bytes(b"system-version")
    firmware = root / "Firmware"
    firmware.mkdir(exist_ok=True)
    (firmware / "devel-file.bin").write_bytes(b"dev")
    release = root / "Release"
    release.mkdir(exist_ok=True)
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


def test_directory_archive_accepts_explicit_build_manifest_name(tmp_path: Path) -> None:
    _write_ipsw_layout(tmp_path, manifest_name="BuildManifest_A.plist", manifest=_build_manifest())
    _write_ipsw_layout(
        tmp_path,
        manifest_name="BuildManifest_B.plist",
        manifest=plistlib.dumps({
            "SupportedProductTypes": ["iPhone2,1"],
            "ProductVersion": "2.0",
            "ProductBuildVersion": "2B2",
            "BuildIdentities": [],
        }),
    )

    ipsw = IPSW(DirectoryArchive(tmp_path), build_manifest_name="BuildManifest_B.plist")

    assert ipsw.build_manifest.product_version == "2.0"
    assert ipsw.build_manifest.product_build_version == "2B2"
    assert ipsw.build_manifest.supported_product_types == ["iPhone2,1"]


def test_create_from_path_accepts_explicit_build_manifest_name(tmp_path: Path) -> None:
    _write_ipsw_layout(tmp_path, manifest_name="BuildManifest_A.plist", manifest=_build_manifest())
    _write_ipsw_layout(
        tmp_path,
        manifest_name="BuildManifest_B.plist",
        manifest=plistlib.dumps({
            "SupportedProductTypes": ["iPhone2,1"],
            "ProductVersion": "2.0",
            "ProductBuildVersion": "2B2",
            "BuildIdentities": [],
        }),
    )

    ipsw = IPSW.create_from_path(str(tmp_path), build_manifest_name="BuildManifest_B.plist")

    assert ipsw.build_manifest.product_version == "2.0"
    assert ipsw.build_manifest.product_build_version == "2B2"
    assert ipsw.build_manifest.supported_product_types == ["iPhone2,1"]


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
