import traceback
from pathlib import Path

import click
import watchfiles

from komoe.builder import Builder, ProjectPaths
from komoe.config import ProjectConfig
from komoe.log import Log


class FileWatcher:
    __paths: ProjectPaths
    __builder: Builder

    def __init__(self, config: ProjectConfig, paths: ProjectPaths):
        self.__paths = paths
        self.__builder = Builder(config, self.__paths)

    def initial_build(self):
        self.__builder.build(True)


    def watch_and_rebuild(self):
        while True:
            try:
                for changes in watchfiles.watch(self.__paths.base_dir):
                    self.__files_changed(changes)

            except KeyboardInterrupt:
                print()  # add a newline after the ^C in the console
                Log.info("Stopping preview server")
                break

            except Exception as e:
                click.secho(
                    "".join(traceback.format_tb(e.__traceback__)), nl=False, dim=True
                )
                Log.error(f"{type(e).__name__}: {e}")

    def __files_changed(self, changes: set[tuple[watchfiles.Change, str]]):
        need_rebuild = False
        need_refresh = False

        for _, file in changes:
            path = Path(file)

            if not self.__file_is_ignored(path):
                # source files
                if any(
                        path.is_relative_to(src_dir)
                        for src_dir in self.__builder.snapshot_dirs
                ):
                    need_rebuild = True

                # project file and plugins
                elif path.name == "komoe.toml" or path.suffix == ".py":
                    need_rebuild = True
                    need_refresh = True

        if need_rebuild:
            print()
            if need_refresh:
                Log.info("The project file or a plugin changed, doing a clean build")
            self.__builder.build(need_refresh)

    def __file_is_ignored(self, file: Path) -> bool:
        return file.is_relative_to(self.__paths.output_dir) or file.is_relative_to(self.__paths.cache_dir)
