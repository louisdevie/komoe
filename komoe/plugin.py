"""Interface to the Komoe build process for plugins."""

import click

from . import log
from .snapshot import Diff
from .utils import file_status, file_status_done, proxy
from .markdown import Markdown

__all__ = [
    "before_build",
    "after_build",
    "before_plugin",
    "after_plugin",
    "setup",
    "Diff",
    "file_status",
    "file_status_done",
]


class _ModuleEvents:
    def __init__(self):
        self.__on_start = list()
        self.__on_end = list()

    def register(self, event, action):
        if event == "start":
            self.__on_start.append(action)
        elif event == "end":
            self.__on_end.append(action)
        else:
            raise ValueError(f"invalid event “{event}”")

    def on(self, event):
        if event == "start":
            return iter(self.__on_start)
        elif event == "end":
            return iter(self.__on_end)
        else:
            raise ValueError(f"invalid event “{event}”")


class _Action:
    def __init__(self, callback):
        self.__callback = callback
        self.__called = False
        self.__module = None

    def __bool__(self):
        return self.__called

    def __call__(self, context, config):
        if self.__called:
            raise RuntimeError("Action object called twice")
        else:
            self.__called = True
            return self.__callback(context, config)

    @property
    def module(self):
        return self.__module

    @module.setter
    def module(self, value):
        self.__module = value


class _ModuleActions:
    def __init__(self, name):
        self.__actions = list()
        self.__name = name

    def add(self, action):
        action.module = self
        self.__actions.append(action)

    @property
    def started(self):
        return any(self.__actions)

    @property
    def ended(self):
        return all(self.__actions)

    @property
    def name(self):
        return self.__name


class PluginScheduler:
    __setup = []
    __cleanup = []
    __events = {"build!": _ModuleEvents()}
    __actions = {}

    __context = None
    __config = None

    @classmethod
    def events(cls, module):
        if module not in cls.__events:
            cls.__events[module] = _ModuleEvents()
        return cls.__events[module]

    @classmethod
    def actions(cls, module):
        if module not in cls.__actions:
            cls.__actions[module] = _ModuleActions(module)

        return cls.__actions[module]

    @classmethod
    def subscribe(cls, module, event, callback):
        plugin_name = cls.__context.get_package_alias(
            callback.__module__,
            callback.__module__.replace("_komoe_plugin", ""),
        )
        action_name = callback.__name__

        if plugin_name == module:
            log.error(
                f"a plugin can't subscribe to itself ({plugin_name}.{action_name})"
            )
            raise click.ClickException("failed to load plugins")

        action = _Action(callback)

        events = cls.events(module)
        events.register(event, action)

        actions = cls.actions(plugin_name)
        actions.add(action)

        cls.events(plugin_name)

    @classmethod
    def register_setup(cls, callback):
        plugin_name = cls.__context.get_package_alias(
            callback.__module__,
            callback.__module__.replace("_komoe_plugin", ""),
        )

        cls.__setup.append((plugin_name, callback))

    @classmethod
    def register_cleanup(cls, callback):
        plugin_name = cls.__context.get_package_alias(
            callback.__module__,
            callback.__module__.replace("_komoe_plugin", ""),
        )

        cls.__cleanup.append((plugin_name, callback))

    @classmethod
    def build_started(cls):
        cls.notify("build!", "start")

    @classmethod
    def build_ended(cls):
        cls.notify("build!", "end")

    @classmethod
    def set_context(cls, context):
        cls.__context = context

    @classmethod
    def set_config(cls, config):
        cls.__config = config

    @classmethod
    def notify(cls, module, event):
        for action in cls.__events[module].on(event):
            if not action.module.started:
                cls.notify(action.module.name, "start")

            action(
                BuilderProxy(cls.__context, action.module.name),
                cls.__config.get(action.module.name, {}),
            )

            if action.module.ended:
                cls.notify(action.module.name, "end")

    @classmethod
    def setup(cls):
        for module, callback in cls.__setup:
            callback(
                BuilderProxy(cls.__context, module),
                cls.__config.get(module, {}),
            )

    @classmethod
    def cleanup(cls):
        for module, callback in cls.__cleanup:
            callback(
                BuilderProxy(cls.__context, module),
                cls.__config.get(module, {}),
            )


class LogProxy:
    def __init__(self, ctx):
        self.__context = ctx

    @property
    def context(self):
        return self.__context

    @proxy(log.error)
    def error(self, message):
        log.error(f"{self.context}: {message}")

    @proxy(log.warn)
    def warn(self, message):
        log.warn(f"{self.context}: {message}")

    @proxy(log.warn)
    def info(self, message):
        log.info(f"{self.context}: {message}")


class MarkdownProxy:
    def __init__(self, markdown):
        self.__md = markdown

    @proxy(Markdown.disable_default_extension)
    def disable_default_extension(self, name):
        self.__md.disable_default_extension(name)

    @proxy(Markdown.disable_default_extension)
    def add_extension(self, extension, config_name=None, **config):
        self.__md.add_extension(extension, config_name, **config)

    @proxy(Markdown.disable_default_extension)
    def configure_extension(self, name, **config):
        self.__md.configure_extension(name, **config)


class BuilderProxy:
    def __init__(self, builder, log_ctx):
        self.__builder = builder
        self.__log = LogProxy(log_ctx)
        self.__md = MarkdownProxy(self.__builder.markdown)

    @property
    def log(self):
        return self.__log

    @property
    def echo(self):
        return click.echo

    def fatal(self, message=None):
        raise click.ClickException(
            f"plugin {self.__log.context} aborted the build"
            + ("" if message is None else ": " + message)
        )

    def snapshot_register(self, name, path):
        return self.__builder.snapshot_register(name, path)

    def snapshot_current(self, name):
        return self.__builder.snapshot_current(name)

    def snapshot_old(self, name):
        return self.__builder.snapshot_old(name)

    def snapshot_diff(self, name):
        return self.__builder.snapshot_diff(name)

    @property
    def markdown(self):
        return self.__md

    @property
    def cache_dir(self):
        return self.__builder.cache_dir

    @property
    def output_dir(self):
        return self.__builder.output_dir

    @property
    def static_output_dir(self):
        return self.__builder.static_output_dir

    @property
    def source_dir(self):
        return self.__builder.source_dir

    @property
    def templates_dir(self):
        return self.__builder.templates_dir

    @property
    def static_dir(self):
        return self.__builder.static_dir


def setup(func):
    PluginScheduler.register_setup(func)


def cleanup(func):
    PluginScheduler.register_cleanup(func)


def before_build(func):
    PluginScheduler.subscribe("build!", "start", func)


def after_build(func):
    PluginScheduler.subscribe("build!", "end", func)


def before_plugin(plugin_name):
    def deco(func):
        PluginScheduler.subscribe(plugin_name, "start", func)

    return deco


def after_plugin(plugin_name):
    def deco(func):
        PluginScheduler.subscribe(plugin_name, "end", func)

    return deco
