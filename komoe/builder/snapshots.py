from os import PathLike
from pathlib import Path
from enum import Enum, auto
from typing import Optional, Type

import click

from komoe import log
from komoe.builder.paths import ProjectPaths
from komoe.utils import Internal


class Diff(Enum):
    ADDED = auto()
    MODIFIED = auto()
    SAME = auto()
    DELETED = auto()


def _scan(root, path, ignore_hidden, ignore_patterns):
    files = {}

    for e in path.iterdir():
        if ignore_hidden and e.name.startswith("."):
            continue

        ignore = False
        for pattern in ignore_patterns:
            if e.match(pattern):
                ignore = True
        if ignore:
            continue

        if e.is_file():
            files[str(e.relative_to(root))] = int(e.stat().st_mtime)

        elif e.is_dir():
            files.update(_scan(root, e, ignore_hidden, ignore_patterns))

    return files


class Snapshot:
    __files: dict[str, int]

    def __init__(self, files: dict[str, int]):
        self.__files = files

    @classmethod
    def scan(cls, root: PathLike, ignore_hidden=True, ignore_patterns=None) -> 'Snapshot':
        if ignore_patterns is None:
            ignore_patterns = []
        if not isinstance(root, Path):
            root = Path(root)

        if not root.is_dir():
            raise ValueError("root must be an existing directory")

        return cls(_scan(root, root, ignore_hidden, ignore_patterns))

    @classmethod
    def load(cls, text: str) -> 'Snapshot':
        data = {}
        for entry in text.split("\n"):
            if len(entry) == 0:
                continue
            path, time = entry.rsplit(":", 1)
            time = int(time)
            data[path] = time
        return cls(data)

    def dump(self) -> str:
        text = str()
        for path, time in self.__files.items():
            text += f"{path}:{time}\n"
        return text

    def diff(self, old: 'Snapshot') -> dict[str, Diff]:
        diff_dict = {}

        deleted = set(old.__files)
        for entry in self.__files.keys():
            if entry in old.__files:
                deleted.remove(entry)
                if self.__files[entry] == old.__files[entry]:
                    diff_dict[entry] = Diff.SAME
                else:
                    diff_dict[entry] = Diff.MODIFIED
            else:
                diff_dict[entry] = Diff.ADDED
        for entry in deleted:
            diff_dict[entry] = Diff.DELETED

        return diff_dict


class SnapshotRegistry:
    class __Entry:
        __scan_path: Path
        __cache_path: Path
        __current: Optional[Snapshot]
        __old: Optional[Snapshot]
        __is_internal: bool

        def __init__(self, scan_path: Path, cache_path: Path, is_internal: bool):
            self.__scan_path = scan_path
            self.__cache_path = cache_path
            self.__is_internal = is_internal

        @property
        def current(self) -> Snapshot:
            if self.__current is None:
                raise RuntimeError('attempt to access snapshots before they were loaded')
            else:
                return self.__current

        @property
        def old(self) -> Snapshot:
            if self.__old is None:
                return Snapshot({})
            else:
                return self.__old

        @property
        def is_internal(self) -> bool:
            return self.__is_internal

        @property
        def scan_path(self) -> Path:
            return self.__scan_path

        def load(self):
            if self.__cache_path.is_file():
                with open(self.__cache_path, "rt", encoding="utf8") as f:
                    self.__old = Snapshot.load(f.read())

        def scan(self):
            self.__current = Snapshot.scan(self.__scan_path)

        def dump(self):
            with open(self.__cache_path, "wt", encoding="utf8") as f:
                f.write(self.__current.dump())

    __paths: ProjectPaths
    __snapshots: dict[str, __Entry]

    def __init__(self, paths: ProjectPaths):
        self.__paths = paths
        self.__snapshots = {
            'source': SnapshotRegistry.__Entry(paths.source_dir, paths.cached_snapshot("source"), True),
            'static': SnapshotRegistry.__Entry(paths.static_dir, paths.cached_snapshot("static"), True),
            'templates': SnapshotRegistry.__Entry(paths.templates_dir, paths.cached_snapshot("templates"), True)
        }

    @property
    def tracked_dirs(self) -> list[Path]:
        return [entry.scan_path for entry in self.__snapshots.values()]

    def register(self, name, path):
        if name in self.__snapshots:
            if self.__snapshots[name].is_internal:
                log.error(f"'{name}' is a reserved snapshot entry")
            else:
                log.error(f"The snapshot '{name}' is already registered")
            raise click.ClickException("failed to register snapshot")

        self.__snapshots[name] = SnapshotRegistry.__Entry(
            self.__paths.base_dir / path,
            self.__paths.cached_snapshot(name),
            False
        )

    def current(self, name) -> Snapshot:
        return self.__snapshots[name].current

    def old(self, name) -> Snapshot:
        return self.__snapshots[name].old

    def diff(self, name: str) -> dict[str, Diff]:
        return self.current(name).diff(self.old(name))

    def load_all(self):
        for entry in self.__snapshots.values():
            entry.load()

    def scan_all(self):
        for entry in self.__snapshots.values():
            entry.scan()

    def dump_all(self):
        for entry in self.__snapshots.values():
            entry.dump()
