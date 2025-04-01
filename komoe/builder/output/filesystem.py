from pathlib import Path

from .base import BuilderOutput
from .. import ProjectPaths


class FileSystemOutput(BuilderOutput):
    __output_dir: Path

    def __init__(self, paths: ProjectPaths):
        self.__output_dir = paths.output_dir