import click

DEBUG = True


def error(message):
    __log("error", "red", message)


def warn(message):
    __log("warning", "yellow", message)


def info(message):
    __log("info", None, message)


def dbg(message):
    if DEBUG:
        __log("debug", "cyan", message)


def __log(level, color, message):
    click.secho(f"[{level}] ", nl=False, err=True, fg=color, bold=True)
    click.secho(message, err=True, fg=color)
