import click
import os
from pathlib import Path

from . import template, __version__
from .config import ProjectConfig
from .builder import Builder, ProjectPaths
from . import log
from .file_watcher import FileWatcher
from .server import Server


@click.group()
@click.version_option(version=__version__, prog_name="YourAppName", message="%(prog)s version %(version)s")
def main():
    pass


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
    """Creates a new project

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
@click.option("--fresh", is_flag=True, help="Regenerates all content")
def build(project_file, project_dir, fresh):
    """Build a project

    If no project is specified, the project in the current directory will be built.
    """

    if project_file is not None:
        config_path = project_file

    elif (project_dir is not None) and "komoe.toml" in (f.name for f in project_dir.iterdir()):
        config_path = project_dir / "komoe.toml"

    elif "komoe.toml" in (f.name for f in Path.cwd().iterdir()):
        config_path = Path.cwd() / "komoe.toml"

    else:
        raise click.ClickException("project file not found")

    config = load_config(config_path)

    paths = ProjectPaths(config_path.parent, config)
    builder = Builder(config, paths)
    builder.build(fresh)

    click.echo("\n✨️ All done ! ✨️")


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

    if project_file is not None:
        config_path = project_file

    elif (project_dir is not None) and (
            "komoe.toml" in f.name for f in project_dir.iterdir()
    ):
        config_path = project_dir / "komoe.toml"

    elif "komoe.toml" in (f.name for f in Path.cwd().iterdir()):
        config_path = Path.cwd() / "komoe.toml"

    else:
        raise click.ClickException("project file not found")

    config = load_config(config_path)

    paths = ProjectPaths(config_path.parent, config)

    file_watcher = FileWatcher(config, paths)
    file_watcher.initial_build()

    with Server('127.0.0.1', 5050, paths).serve_threaded():
        file_watcher.watch_and_rebuild()


def load_config(path):
    config = ProjectConfig.from_file(path)

    if config.minimum_required_version > __version__:
        raise click.ClickException(
            f"The project requires at least Komoe v{config.minimum_required_version}"
        )

    return config
