from pathlib import Path

from .config import KomoeConfig


class ProjectPaths:
    __base_dir: Path
    __config: KomoeConfig

    def __init__(self, base_dir: Path, config: KomoeConfig):
        self.__base_dir = base_dir
        self.__config = config

    @property
    def base_dir(self) -> Path:
        return self.__base_dir

    @property
    def cache_dir(self) -> Path:
        return self.__base_dir / self.__config.cache_dir

    @property
    def output_dir(self) -> Path:
        return self.__base_dir / self.__config.output_dir

    @property
    def assets_output_dir(self) -> Path:
        return self.output_dir / "assets"

    @property
    def source_dir(self) -> Path:
        return self.__base_dir / "content"

    @property
    def templates_dir(self) -> Path:
        return self.__base_dir / "templates"

    @property
    def assets_dir(self) -> Path:
        return self.__base_dir / "assets"

    @property
    def cached_relationships(self) -> Path:
        return self.cache_dir / "relationships"

    @property
    def cached_doctree(self) -> Path:
        return self.cache_dir / "doctree"

    def cached_snapshot(self, name: str) -> Path:
        return self.cache_dir / (name + ".snap")
