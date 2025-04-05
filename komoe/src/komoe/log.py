import click


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
    def __log(cls, level, color, message):
        click.secho(f"[{level}] ", nl=False, err=True, fg=color, bold=True)
        click.secho(message, err=True, fg=color)
