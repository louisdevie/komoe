import click
import os
from pathlib import Path
import traceback

import watchfiles

from . import template, __version__
from .config import ProjectConfig
from .builder import Builder
from . import log


@click.group()
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
@click.option("--watch", is_flag=True, help="Rebuild as files change")
def build(project_file, project_dir, fresh, watch):
    """Build a project

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

    builder = Builder(config, config_path.parent, fresh=fresh)
    builder.build()

    if watch:
        while True:
            try:
                click.echo("Waiting for a file to change ...")
                for changes in watchfiles.watch(config_path.parent):
                    need_rebuild = False
                    force_fresh = False
                    for _, file in changes:
                        path = Path(file)

                        if (not path.is_relative_to(builder.output_dir)) and (
                            not path.is_relative_to(builder.cache_dir)
                        ):
                            # source files
                            if any(
                                path.is_relative_to(srcdir)
                                for srcdir in builder.snapshot_dirs
                            ):
                                need_rebuild = True

                            # project file and plugins
                            elif path.name == "komoe.toml" or path.suffix == ".py":
                                need_rebuild = True
                                force_fresh = True

                    if need_rebuild:
                        if force_fresh:
                            log.info("The project file or a plugin changed")

                        builder = Builder(
                            config, config_path.parent, fresh=fresh or force_fresh
                        )
                        builder.build()

                        click.echo("Waiting for a file to change ...")

            except KeyboardInterrupt:
                click.echo("\nWatch stoppped")
                break

            except Exception as e:
                click.secho(
                    "".join(traceback.format_tb(e.__traceback__)), nl=False, dim=True
                )
                log.error(f"{type(e).__name__}: {e}")

    else:
        click.echo("✨ All done ! ✨")


def load_config(path):
    config = ProjectConfig.from_file(path)

    if config.minimum_required_version > __version__:
        raise click.ClickException(
            f"The project requires at least Komoe v{config.minimum_required_version}"
        )

    return config
