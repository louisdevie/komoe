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
    __initialised = False
    __development = False

    @classmethod
    def __init_once(cls):
        if cls.__initialised:
            return
        cls.__initialised = True

        cls.__development = bool(os.getenv("KOMOE_DEV"))
        level = logging.DEBUG if cls.__development else logging.INFO

        # set up a root 'komoe' logger
        logger = logging.getLogger(ROOT)
        logger.setLevel(level)

        click_handler = ClickHandler(cls.__development)
        click_handler.setLevel(logging.DEBUG)

        logger.addHandler(click_handler)

    @classmethod
    def get_logger(cls, module: str):
        cls.__init_once()

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
        cls.__init_once()

        if plugin_name in RESERVED_MODULES:
            plugin_name = plugin_name + "_plugin"

        module = ".".join((ROOT, PLUGIN_MODULE, plugin_name))
        return LoggerAdapter(logging.getLogger(module), {"komoe_module": plugin_name})


class ExtendedLogRecord(logging.LogRecord):
    komoe_module: str


def check_record(record: ExtendedLogRecord):
    location = f"\n   at {record.pathname}:{record.lineno}"
    if len(record.msg.strip()) == 0:
        log.warning("Empty message" + location)
    elif len(record.msg.rstrip()) < len(record.msg):
        log.warning("Trailing spaces in message" + location)
    elif record.msg[0].islower():
        log.warning("Message starts with a lowercase letter" + location)


class ClickHandler(Handler):
    __development: bool

    def __init__(self, development):
        super().__init__()
        self.__development = development

    def emit(self, record: ExtendedLogRecord):
        level_name = record.levelname.lower()

        if record.levelno >= logging.ERROR:
            color = "red"
        elif record.levelno >= logging.WARNING:
            color = "yellow"
        elif record.levelno >= logging.INFO:
            color = None
        else:
            color = "bright_black"

        click.secho(
            f"[{level_name}] {record.komoe_module}: {record.msg}",
            err=True,
            fg=color,
            bold=True,
        )

        if self.__development:
            check_record(record)


log = Logging.get_logger(__name__)
