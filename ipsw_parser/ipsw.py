import logging
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import IO, Annotated, Optional
from zipfile import ZipFile

from bytestruct import BinaryStruct, Bytes, Const
from remotezip2 import RemoteZip  # pyright: ignore[reportMissingTypeStubs]

from ipsw_parser.archive import Archive, ArchiveEntry, DirectoryArchive, ZipArchive
from ipsw_parser.build_manifest import BuildManifest
from ipsw_parser.dsc import create_device_support_layout
from ipsw_parser.firmware import Firmware

logger = logging.getLogger(__name__)


@dataclass
class CpioOdcHeader(BinaryStruct):
    """A POSIX.1 portable ("odc") cpio header: every field is zero-padded octal ASCII."""

    c_magic: Annotated[bytes, Bytes(6), Const(b"070707")] = field(default=b"070707", init=False)
    c_dev: Annotated[bytes, Bytes(6)]
    c_ino: Annotated[bytes, Bytes(6)]
    c_mode: Annotated[bytes, Bytes(6)]
    c_uid: Annotated[bytes, Bytes(6)]
    c_gid: Annotated[bytes, Bytes(6)]
    c_nlink: Annotated[bytes, Bytes(6)]
    c_rdev: Annotated[bytes, Bytes(6)]
    c_mtime: Annotated[bytes, Bytes(11)]
    c_namesize: Annotated[bytes, Bytes(6)]
    c_filesize: Annotated[bytes, Bytes(11)]


def _build_cpio_odc_header(ino: int, mode: int, nlink: int, namesize: int, filesize: int = 0) -> bytes:
    """Build an odc cpio header; device, owner, rdev and mtime are always zero."""
    zero6 = b"0" * 6
    return CpioOdcHeader(
        c_dev=zero6,
        c_ino=f"{ino:06o}".encode(),
        c_mode=f"{mode:06o}".encode(),
        c_uid=zero6,
        c_gid=zero6,
        c_nlink=f"{nlink:06o}".encode(),
        c_rdev=zero6,
        c_mtime=b"0" * 11,
        c_namesize=f"{namesize:06o}".encode(),
        c_filesize=f"{filesize:011o}".encode(),
    ).build()


class IPSW:
    """High-level interface for reading and extracting IPSW contents."""

    @classmethod
    def create_from_path(cls, value: str) -> "IPSW":
        """Create an ``IPSW`` from a local path, extracted directory, or URL."""
        if value.startswith("http://") or value.startswith("https://"):
            return cls(ZipArchive(RemoteZip(value)))

        path = Path(value).expanduser()
        if path.is_dir():
            return cls(DirectoryArchive(path))

        return cls(ZipArchive(ZipFile(path)))

    def __init__(self, archive: Archive):
        """Create an IPSW wrapper around an archive backend."""
        self.archive = archive
        self._logger = logging.getLogger(__file__)
        self.build_manifest = BuildManifest(
            self,
            self.archive.read(
                next(f for f in self.archive.namelist() if f.startswith("BuildManifest") and f.endswith(".plist"))
            ),
        )

    @cached_property
    def restore_version(self) -> bytes:
        """Return the raw ``RestoreVersion.plist`` payload."""
        return self.read("RestoreVersion.plist")

    @cached_property
    def system_version(self) -> bytes:
        """Return the raw ``SystemVersion.plist`` payload."""
        return self.read("SystemVersion.plist")

    @cached_property
    def filelist(self) -> Sequence[ArchiveEntry]:
        """Return archive members for the IPSW."""
        return self.archive.filelist

    @contextmanager
    def open_path(self, path: str) -> Generator[IO[bytes], None, None]:
        """Open an IPSW member and close it automatically on exit."""
        file = self.archive.open(path)
        try:
            yield file
        finally:
            file.close()

    @property
    def bootability(self) -> bytes:
        """Build a cpio archive containing bootability bundle payloads."""
        result = b""
        prefix = "BootabilityBundle/Restore/Bootability/"
        inode = 1
        nlink = 1

        for e in self.filelist:
            if e.filename == "BootabilityBundle/Restore/Firmware/Bootability.dmg.trustcache":
                subpath = "Bootability.trustcache"
            elif not e.filename.startswith(prefix):
                continue
            else:
                subpath = e.filename[len(prefix) :]

            self._logger.debug(f"BootabilityBundle: adding {subpath}")

            filename = subpath
            filename = f"{filename}\0".encode()
            mode = e.external_attr >> 16
            result += _build_cpio_odc_header(inode, mode, nlink, len(filename), e.file_size)
            inode += 1
            result += filename
            if not e.file_size:
                continue

            with self.open_path(e.filename) as f:
                result += f.read()

        filename = b"TRAILER!!!\0"
        inode = 0
        mode = 0
        result += _build_cpio_odc_header(inode, mode, nlink, len(filename)) + filename
        return result

    def read(self, path: str) -> bytes:
        """Read an IPSW member into memory."""
        return self.archive.read(path)

    def get_global_manifest(self, macos_variant: str, device_class: str) -> bytes:
        """Return the restore manifest for a macOS variant and device class."""
        manifest_path = f"Firmware/Manifests/restore/{macos_variant}/apticket.{device_class}.im4m"
        return self.read(manifest_path)

    def get_firmware(self, firmware_path: str) -> Firmware:
        """Return a firmware helper rooted at ``firmware_path``."""
        return Firmware(firmware_path, self)

    def get_development_files(self) -> list[str]:
        """Return archive entries associated with development builds."""
        result: list[str] = []
        for entry in self.archive.namelist():
            for release in ("devel", "kasan", "research"):
                if release in entry.lower():
                    result.append(entry)
        return result

    def create_device_support(self, pem_db: Optional[str] = None) -> None:
        """Create an Xcode DeviceSupport directory for this IPSW."""
        device_support_path = Path("~/Library/Developer/Xcode/iOS DeviceSupport").expanduser()
        device_support_path /= (
            f"{self.build_manifest.supported_product_types[0]} "
            f"{self.build_manifest.product_version} ({self.build_manifest.product_build_version})"
        )
        build_identity = self.build_manifest.build_identities[0]
        symbols_path = device_support_path / "Symbols"
        build_identity.extract_dsc(symbols_path, pem_db=pem_db, split=False)
        create_device_support_layout(
            self.build_manifest.supported_product_types[0],
            self.build_manifest.product_version,
            self.build_manifest.product_build_version,
            symbols_path,
        )
