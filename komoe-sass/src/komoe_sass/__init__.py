from komoe.plugin import *

import os, pathlib


@setup
def setup(ctx, cfg):
    if "path" not in cfg:
        ctx.log.error("No Sass path set.")
        ctx.fatal()

    path = cfg["path"]

    cfg["path"] = ctx.base_dir / path

    if not cfg["path"].is_dir():
        ctx.log.error(f"The directory ‘{cfg['path']}’ doesn't exist.")
        ctx.fatal()

    ctx.snapshot_register("sass", path)


@after_build
def build_sass(ctx, cfg):
    diff = ctx.snapshot_diff("sass")

    if any(d != Diff.SAME for d in diff.values()):
        ctx.echo("Building CSS:")

        for file, diff in diff.items():
            file_status(file, diff)

            if diff == Diff.CREATED or diff == Diff.MODIFIED:
                compile_stylesheet(ctx, cfg, file)

            elif diff == Diff.DELETED:
                remove_stylesheet(ctx, file)

            file_status_done()


def compile_stylesheet(ctx, cfg, file):
    src = cfg["path"] / file
    dst = (ctx.static_output_dir / file).with_suffix(".css")

    os.makedirs(dst.parent, exist_ok=True)
    status = os.system(
        cfg.get("command", "sass {input} {output}").format(input=src, output=dst)
    )

    if status != 0:
        ctx.log.error(f"Failed to build {file}")
        ctx.fatal()


def remove_stylesheet(ctx, file):
    dst = ctx.static_output_dir / file

    try:
        os.remove(dst)
    except FileNotFoundError as e:
        ctx.log.warn(f"Can't delete {file}: {e}")
