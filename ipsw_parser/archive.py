import shutil
import stat
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import IO, Protocol, Union
from zipfile import ZipFile, ZipInfo


@dataclass(frozen=True)
class ArchiveMember:
    """Metadata describing a single archive entry."""

    filename: str
    file_size: int
    external_attr: int


class ArchiveEntry(Protocol):
    """Metadata of an archive member: an ``ArchiveMember`` or a ``zipfile.ZipInfo``."""

    @property
    def filename(self) -> str: ...

    @property
    def file_size(self) -> int: ...

    @property
    def external_attr(self) -> int: ...


class Archive(Protocol):
    """Protocol implemented by supported IPSW archive backends."""

    @property
    def filelist(self) -> Sequence[ArchiveEntry]:
        """Return archive members with metadata."""
        ...

    def namelist(self) -> list[str]:
        """Return archive member names."""
        ...

    def open(self, path: str) -> IO[bytes]:
        """Open an archive member for binary reading."""
        ...

    def read(self, path: str) -> bytes:
        """Read an archive member into memory."""
        ...

    def extractall(self, path: Path, members: Iterable[Union[ArchiveEntry, str]]) -> None:
        """Extract the selected archive members into ``path``."""
        ...


class ZipArchive:
    """Archive adapter backed by ``zipfile.ZipFile``."""

    def __init__(self, archive: ZipFile):
        """Wrap an existing ZIP archive object."""
        self._archive = archive

    @property
    def filelist(self) -> list[ZipInfo]:
        """Return ZIP member metadata."""
        return self._archive.filelist

    def namelist(self) -> list[str]:
        """Return ZIP member names."""
        return self._archive.namelist()

    def open(self, path: str) -> IO[bytes]:
        """Open a ZIP member for binary reading."""
        return self._archive.open(path)

    def read(self, path: str) -> bytes:
        """Read a ZIP member into memory."""
        return self._archive.read(path)

    def extractall(self, path: Path, members: Iterable[Union[ArchiveEntry, str]]) -> None:
        """Extract the selected ZIP members into ``path``."""
        self._archive.extractall(
            path=path, members=[member if isinstance(member, str) else member.filename for member in members]
        )


class DirectoryArchive:
    """Archive adapter that exposes a directory tree like an IPSW archive."""

    def __init__(self, root: Path):
        """Wrap an extracted IPSW directory."""
        self._root = root

    @property
    def filelist(self) -> list[ArchiveMember]:
        """Return filesystem entries as archive-style metadata."""
        return self._members

    @cached_property
    def _members(self) -> list[ArchiveMember]:
        result: list[ArchiveMember] = []
        for file_path in sorted(path for path in self._root.rglob("*") if path.is_file()):
            file_stat = file_path.stat()
            relative_path = file_path.relative_to(self._root).as_posix()
            mode = stat.S_IFREG | stat.S_IMODE(file_stat.st_mode)
            result.append(
                ArchiveMember(
                    filename=relative_path,
                    file_size=file_stat.st_size,
                    external_attr=mode << 16,
                )
            )
        return result

    def namelist(self) -> list[str]:
        """Return relative file paths under the archive root."""
        return [member.filename for member in self.filelist]

    def open(self, path: str) -> IO[bytes]:
        """Open a file relative to the archive root."""
        return (self._root / path).open("rb")

    def read(self, path: str) -> bytes:
        """Read a file relative to the archive root."""
        return (self._root / path).read_bytes()

    def extractall(self, path: Path, members: Iterable[Union[ArchiveEntry, str]]) -> None:
        """Copy the selected members into ``path``."""
        for member in members:
            filename = member if isinstance(member, str) else member.filename
            source = self._root / filename
            destination = path / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
