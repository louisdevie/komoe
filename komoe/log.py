import click

DEBUG = False


def error(message):
    __log("ERROR", "red", message)


def warn(message):
    __log("WARNING", "yellow", message)


def info(message):
    __log("INFO", None, message)


def dbg(message):
    if DEBUG:
        __log("DEBUG", "cyan", message)


def __log(level, color, message):
    click.secho(f"[{level}] ", nl=False, err=True, fg=color, bold=True)
    click.secho(message, err=True, fg=color)
