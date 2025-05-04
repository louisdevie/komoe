from abc import ABC, abstractmethod
from typing import Optional

from komoe.build.artefacts import Artefact


class FilePeek:
    def read_first_bytes(self, size: int) -> bytes:
        raise NotImplementedError()

    def read_first_chars(self, size: int) -> str:
        raise NotImplementedError()

    def read_first_line(self) -> str:
        raise NotImplementedError()


class Loader(ABC):
    @abstractmethod
    def load_file(self, name: str, peek: FilePeek) -> Optional[Artefact]:
        ...


class StaticAssetsLoader:
    ...
