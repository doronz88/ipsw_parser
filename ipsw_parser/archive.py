import shutil
import stat
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import BinaryIO, Protocol, Union
from zipfile import ZipFile, ZipInfo


@dataclass(frozen=True)
class ArchiveMember:
    filename: str
    file_size: int
    external_attr: int


class Archive(Protocol):
    @property
    def filelist(self) -> list[ArchiveMember]: ...

    def namelist(self) -> list[str]: ...

    def open(self, path: str) -> BinaryIO: ...

    def read(self, path: str) -> bytes: ...

    def extractall(self, path: Path, members: Iterable[Union[ArchiveMember, ZipInfo, str]]) -> None: ...


class ZipArchive:
    def __init__(self, archive: ZipFile):
        self._archive = archive

    @property
    def filelist(self) -> list[ZipInfo]:
        return self._archive.filelist

    def namelist(self) -> list[str]:
        return self._archive.namelist()

    def open(self, path: str) -> BinaryIO:
        return self._archive.open(path)

    def read(self, path: str) -> bytes:
        return self._archive.read(path)

    def extractall(self, path: Path, members: Iterable[Union[ArchiveMember, ZipInfo, str]]) -> None:
        self._archive.extractall(path=path, members=members)


class DirectoryArchive:
    def __init__(self, root: Path):
        self._root = root

    @cached_property
    def filelist(self) -> list[ArchiveMember]:
        result = []
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
        return [member.filename for member in self.filelist]

    def open(self, path: str) -> BinaryIO:
        return (self._root / path).open("rb")

    def read(self, path: str) -> bytes:
        return (self._root / path).read_bytes()

    def extractall(self, path: Path, members: Iterable[Union[ArchiveMember, ZipInfo, str]]) -> None:
        for member in members:
            filename = member if isinstance(member, str) else member.filename
            source = self._root / filename
            destination = path / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
