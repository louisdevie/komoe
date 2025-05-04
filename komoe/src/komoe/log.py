import warnings

import click


class KomoeLogStyleWarning(UserWarning):
    ...


class Log:
    DEBUG = True

    @classmethod
    def error(cls, message):
        cls.__log("error", "red", message)

    @classmethod
    def warn(cls, message):
        cls.__log("warning", "yellow", message)

    @classmethod
    def info(cls, message):
        cls.__log("info", None, message)

    @classmethod
    def dbg(cls, message):
        if cls.DEBUG:
            cls.__log("debug", "cyan", message)

    @classmethod
    def __log(cls, level: str, color: str | None, message: str):
        if cls.DEBUG:
            if len(message.strip()) == 0:
                warnings.warn("Empty message", KomoeLogStyleWarning)
            elif len(message.rstrip()) < len(message):
                warnings.warn("Trailing spaces in message", KomoeLogStyleWarning)
            elif message[0].islower():
                warnings.warn(
                    "Message starts with a lowercase letter", KomoeLogStyleWarning
                )

        click.secho(f"[{level}] ", nl=False, err=True, fg=color, bold=True)
        click.secho(message, err=True, fg=color)
