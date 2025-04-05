from pathlib import Path

from ..config import ProjectConfig


class ProjectPaths:
    __base_dir: Path
    __config: ProjectConfig

    def __init__(self, base_dir: Path, config: ProjectConfig):
        self.__base_dir = base_dir
        self.__config = config

    @property
    def base_dir(self) -> Path:
        return self.__base_dir

    @property
    def cache_dir(self) -> Path:
        return self.__base_dir / ".cache"

    @property
    def output_dir(self) -> Path:
        return self.__base_dir / self.__config.output_directory

    @property
    def assets_output_dir(self) -> Path:
        return self.output_dir / "assets"

    @property
    def source_dir(self) -> Path:
        return self.__base_dir / self.__config.source_directory

    @property
    def templates_dir(self) -> Path:
        return self.__base_dir / self.__config.templates_directory

    @property
    def assets_dir(self) -> Path:
        return self.__base_dir / self.__config.assets_directory

    @property
    def cached_relationships(self) -> Path:
        return self.cache_dir / "relationships"

    @property
    def cached_doctree(self) -> Path:
        return self.cache_dir / "doctree"

    def cached_snapshot(self, name: str) -> Path:
        return self.cache_dir / (name + '.snap')
