import click

from . import log

__all__ = ["before_build", "after_build", "before_plugin", "after_plugin", "log"]


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
    __events = {"build!": _ModuleEvents()}
    __actions = {}

    context = None
    config = None

    @classmethod
    def events(cls, module):
        if not module in cls.__events:
            cls.__events[module] = _ModuleEvents()
        return cls.__events[module]

    @classmethod
    def actions(cls, module):
        if not module in cls.__actions:
            cls.__actions[module] = _ModuleActions(module)

        return cls.__actions[module]

    @classmethod
    def subscribe(cls, module, event, callback):
        plugin_name = callback.__module__.removesuffix("_komoe_plugin")
        action_name = callback.__name__

        if plugin_name == module:
            log.error(
                f"a plugin can't subscribe to itself ({plugin_name}.{callback.__name__})"
            )
            raise click.ClickException("failed to load plugins")

        action = _Action(callback)

        events = cls.events(module)
        events.register(event, action)

        actions = cls.actions(plugin_name)
        actions.add(action)

        cls.events(plugin_name)

    @classmethod
    def build_started(cls):
        cls.notify("build!", "start")

    @classmethod
    def build_ended(cls):
        cls.notify("build!", "end")

    @classmethod
    def notify(cls, module, event):
        for action in cls.__events[module].on(event):
            if not action.module.started:
                cls.notify(action.module.name, "start")

            action(cls.context, cls.config.get(action.module.name, {}))

            if action.module.ended:
                cls.notify(action.module.name, "end")


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
