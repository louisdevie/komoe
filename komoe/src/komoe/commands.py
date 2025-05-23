from email.policy import default
from typing import Optional

import click
import os
from pathlib import Path

from . import template, __version__
from .build.builder import Builder
from .config import KomoeConfig, Caching
from .devtools import Devtools
from .logging import Logging, echo
from .paths import ProjectPaths


@click.group()
@click.version_option(
    version=str(__version__),
    prog_name="Komoe",
    message="%(prog)s version %(version)s",
)
@click.option("--debug", is_flag=True, help="Enable debug logging to the console.")
@click.option(
    "--color/--no-color",
    default=None,
    help="Enable or disable colored output and non-ascii decorations. If no flag "
    "is passed, color will be enabled unless the NO_COLOR environment variable "
    "is set.",
)
def main(debug: bool, color: bool | None):
    Logging.init(debug, color)


def load_config(path):
    config = KomoeConfig.from_file(path)

    if not config.minimum_required_version.contains(__version__):
        raise click.ClickException(
            f"The project requires Komoe {config.minimum_required_version}"
        )

    return config


@main.command()
@click.argument(
    "path",
    default=".",
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--project-name", "-N", prompt=True, required=True, help="The name of the project"
)
def new(path, project_name):
    """
    Creates a new project

    If PATH isn't specified, the current directory is used.
    """

    if path.exists():
        entries = [
            entry for entry in path.iterdir() if not entry.name.startswith(".git")
        ]
        if len(entries) != 0:
            path_repr = str(path)
            if path_repr == ".":
                path_repr = "the current directory"
            raise click.ClickException(f"{path_repr} isn't empty")
    else:
        os.makedirs(path)

    template.create_new_project(path, project_name)


@main.command()
@click.argument(
    "project",
    default=".",
    type=click.Path(path_type=Path),
)
@click.option(
    "--clean/--dirty",
    help="A clean build (the default) will clear the output directory before "
    "rebuilding the project. A dirty build will keep the files from previous "
    "builds.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(file_okay=False, path_type=Path),
    default="www",
    help='The directory where the site is built. "site" is used by default.',
)
@click.option(
    "--strict",
    is_flag=True,
    help="Treat warnings as errors and make the build fail if any error occurs.",
)
@click.option(
    "--cache",
    "caching",
    flag_value=Caching.USE_CACHE,
    default=True,
    help="Use cached data from the previous builds and also store the results of "
    "this build in the cache. This is the default option.",
)
@click.option(
    "--no-cache",
    "caching",
    flag_value=Caching.NO_CACHE,
    help="Do not cache anything and destroy any data that was cached previously.",
)
@click.option(
    "--ignore-cache",
    "caching",
    flag_value=Caching.IGNORE_CACHE,
    help="Do not use or modify the cached data.",
)
@click.option(
    "--cache-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=".cache",
    help='The directory where cache data is stored. The default is ".cache".',
)
def build(
    project: Path,
    **options,
):
    """Build a project

    The PROJECT may be a project directory or a configuration file. If PROJECT
    is not specified, the project in the current directory will be built.
    """

    config_path = None

    if project.is_file():
        config_path = project
    elif project.is_dir():
        project_file = project / "komoe.toml"
        if project_file.is_file():
            config_path = project_file

    if config_path is None:
        raise click.ClickException(f"No project found in '{project}'")

    config = load_config(config_path)
    config.use_cli_args(options)

    paths = ProjectPaths(config_path.parent, config)
    builder = Builder(config, paths)

    echo("\n✨️ All done ! ✨️")


@main.command()
@click.option(
    "--project-file",
    "-p",
    type=click.Path(dir_okay=False, exists=True, path_type=Path),
    help="Build a specific project file (overrides --project-dir)",
)
@click.option(
    "--project-dir",
    "-P",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    help="Build the project in that directory",
)
def serve(project_file, project_dir):
    """Serve a preview of a project locally

    The website automatically refreshes when a file is modified.
    If no project is specified, the project in the current directory will be built.
    """
    if not Devtools.are_available:
        raise click.ClickException(
            "The komoe-devtools package must be installed in order to use this command."
        )

    if project_file is not None:
        config_path = project_file

    elif (project_dir is not None) and "komoe.toml" in (
        f.name for f in project_dir.iterdir()
    ):
        config_path = project_dir / "komoe.toml"

    elif "komoe.toml" in (f.name for f in Path.cwd().iterdir()):
        config_path = Path.cwd() / "komoe.toml"

    else:
        raise click.ClickException("project file not found")

    config = load_config(config_path)

    paths = ProjectPaths(config_path.parent, config)

    # file_watcher = FileWatcher(config, paths)
    # file_watcher.initial_build()

    # with Server('127.0.0.1', 5050, paths).serve_threaded():
    #     file_watcher.watch_and_rebuild()
