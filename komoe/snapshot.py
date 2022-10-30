from pathlib import Path
from enum import Enum, auto


class Diff(Enum):
    CREATED = auto()
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
    def __init__(self, files):
        self.__files = files

    @classmethod
    def scan(cls, root, ignore_hidden=True, ignore_patterns=[]):
        if not isinstance(root, Path):
            root = Path(root)

        if not root.is_dir():
            raise ValueError("root must be an existing directory")

        return cls(_scan(root, root, ignore_hidden, ignore_patterns))

    @classmethod
    def load(cls, text):
        data = {}
        for entry in text.split("\n"):
            if len(entry) == 0:
                continue
            path, time = entry.rsplit(":", 1)
            time = int(time)
            data[path] = time
        return cls(data)

    def dump(self):
        text = str()
        for path, time in self.__files.items():
            text += f"{path}:{time}\n"
        return text

    def diff(self, old):
        diff_dict = {}

        for entry in set(self.__files) | set(old.__files):
            if entry in self.__files:
                if entry in old.__files:
                    if self.__files[entry] == old.__files[entry]:
                        diff_dict[entry] = Diff.SAME
                    else:
                        diff_dict[entry] = Diff.MODIFIED
                else:
                    diff_dict[entry] = Diff.CREATED
            else:
                diff_dict[entry] = Diff.DELETED

        return diff_dict
