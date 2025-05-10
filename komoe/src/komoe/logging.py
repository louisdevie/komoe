import logging.config
import os
import warnings
from logging import Handler, LoggerAdapter
from typing import Optional

import click

ROOT = "komoe"
PLUGIN_MODULE = "plugin"
RESERVED_MODULES = [
    "plugin",
    "logging",
]


class Logging:
    __development = False
    __color = False

    @classmethod
    def init(cls, development: bool, color: bool | None):
        cls.__development = development or bool(os.getenv("KOMOE_DEV"))
        level = logging.DEBUG if cls.__development else logging.INFO

        cls.__color = color if color is not None else not bool(os.getenv("NO_COLOR"))

        # set up a root 'komoe' logger
        logger = logging.getLogger(ROOT)
        logger.setLevel(level)

        click_handler = ClickHandler()
        click_handler.setLevel(logging.DEBUG)

        logger.addHandler(click_handler)

    @classmethod
    @property
    def development(cls) -> bool:
        return cls.__development

    @classmethod
    @property
    def color(cls) -> bool:
        return cls.__color

    @classmethod
    def get_logger(cls, module: str):
        module_parts = module.split(".")
        if len(module_parts) == 0 or module_parts[0] != ROOT:
            raise ValueError(f"Can't create a komoe logger for module '{module}'")

        komoe_module = module_parts[-1]
        if cls.__development and not komoe_module in RESERVED_MODULES:
            log.warning(
                f"Internal module {komoe_module} ({module}) should be added to the RESERVED_MODULES list"
            )

        return LoggerAdapter(logging.getLogger(module), {"komoe_module": komoe_module})

    @classmethod
    def get_logger_for_plugin(cls, plugin_name: str):
        if plugin_name in RESERVED_MODULES:
            plugin_name = plugin_name + "_plugin"

        module = ".".join((ROOT, PLUGIN_MODULE, plugin_name))
        return LoggerAdapter(logging.getLogger(module), {"komoe_module": plugin_name})


class ExtendedLogRecord(logging.LogRecord):
    komoe_module: str


def remove_decorations(message: str) -> str:
    ascii_only = ""
    trim = False
    for char in message:
        if char.isascii():
            if not trim or not char.isspace():
                ascii_only += char
                trim = False
        else:
            trim = True
    return ascii_only


def echo(message: str, err: bool = False, **style):
    if Logging.color:
        click.secho(message, err=err, **style)
    else:
        click.echo(remove_decorations(message), err=err, color=False)


def check_record(record: ExtendedLogRecord):
    location = f"\n   at {record.pathname}:{record.lineno}"
    if len(record.msg.strip()) == 0:
        log.warning("Empty message" + location)
    elif len(record.msg.rstrip()) < len(record.msg):
        log.warning("Trailing spaces in message" + location)
    elif record.msg[0].islower():
        log.warning("Message starts with a lowercase letter" + location)


class ClickHandler(Handler):
    def emit(self, record: ExtendedLogRecord):
        level_name = record.levelname.lower()

        if record.levelno >= logging.ERROR:
            color = "bright_red"
            stderr = True
        elif record.levelno >= logging.WARNING:
            color = "yellow"
            stderr = True
        elif record.levelno >= logging.INFO:
            color = None
            stderr = False
        else:
            color = "bright_black"
            stderr = False

        echo(
            f"[{level_name}] {record.komoe_module}: {record.msg}",
            err=stderr,
            fg=color,
        )

        if Logging.development:
            check_record(record)


log = Logging.get_logger(__name__)
