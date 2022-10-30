import os, shutil, pathlib
import click

from .snapshot import Diff


def file_status(filename, diff):
    if diff == Diff.CREATED:
        tag = " + "
    elif diff == Diff.MODIFIED:
        tag = " ~ "
    elif diff == Diff.SAME:
        tag = " = "
    elif diff == Diff.DELETED:
        tag = " - "

    click.secho(tag, nl=False, bold=True)
    click.echo(f"{filename} … ", nl=False)


def file_status_done():
    click.echo("\x1b[2D✓")


def cleartree(path):
    if not isinstance(path, pathlib.Path):
        path = pathlib.Path(path)

    for item in path.iterdir():
        if item.is_file():
            os.remove(item)
        elif item.is_dir():
            shutil.rmtree(item)


def proxy(back):
    def deco(front):
        front.__doc__ = back.__doc__
        return front

    return deco
