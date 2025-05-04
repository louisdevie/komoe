"""Interface to the Komoe build process for plugins."""

from importlib.metadata import entry_points
from types import ModuleType
from typing import Optional, Mapping, Any, Callable, final, TypeAlias, TypeVar, Dict

import click
from click import ClickException

from .build.markdown import Markdown
from .config import PluginConfig
from .log import Log
from .utils import proxy

__all__ = [
    "KomoePlugin",
    "BuilderProxy",
    "MarkdownProxy",
    "LogProxy",
    "setup",
    "compilation_start",
    "compilation_end",
    "cleanup",
    "on",
]


class KomoePlugin:
    """
    The base class for komoe plugins.
    """

    __name: str
    __context: "BuilderProxy"
    __config: Mapping

    def __init__(self, name: str, context: "BuilderProxy", config: Mapping):
        self.__name = name
        self.__context = context
        self.__config = config

    def on_build_event(self, event: str):
        handler_name = f"on_{event}"
        try:
            getattr(self, handler_name)(self.__context, self.__config)
        except AttributeError:
            pass
        except TypeError as e:
            raise ClickException(
                f"an unexpected error occurred when calling handler "
                f"'{handler_name}' of plugin '{self.__name}'"
            )

    @property
    def name(self) -> str:
        return self.__name

    @property
    def context(self) -> "BuilderProxy":
        return self.__context

    @property
    def config(self) -> Mapping:
        return self.__config

    def on_setup(self):
        """
        This method will be called only once during the very first setup phase.
        You can use it to add file loaders, Markdown extensions, etc.
        """

    def on_compilation_start(self):
        """
        This method will be called each time a compilation starts. At this
        point, all plugins and komoe internals (e.g. the Markdown processor)
        are configured.
        """

    def on_compilation_end(self):
        """
        This method will be called each time a compilation ends. At this point,
        all the output files are written.
        """

    def on_cleanup(self):
        """
        This method will be called only once after a build is done, or when the
        development server shuts down.
        """


StandalonePluginFunction: TypeAlias = Callable[["BuilderProxy", Mapping], Any]
"""
A function that can be registered as a plugin event handler using a decorator
like @setup.
"""


@final
class KomoePluginModule(KomoePlugin):
    """A plugin loaded from a module."""

    __handlers: dict[str, StandalonePluginFunction]

    def __init__(self, name: str, context: "BuilderProxy", config: Mapping):
        super().__init__(name, context, config)

        self.__handlers = {}

    def attach(self, event: str, handler: StandalonePluginFunction):
        if event in self.__handlers:
            Log.error(
                f"Another handler for '{event}' is already defined in plugin '{self.name}'."
            )
            raise RuntimeError("cannot define multiple handlers for the same event")
        self.__handlers[event] = handler
        Log.dbg(f"Handler attached to plugin module '{self.name}'")

    def on_build_event(self, event: str):
        handler = self.__handlers.get(event)
        if handler is not None:
            try:
                handler(self.__context, self.__config)
            except TypeError as e:
                raise ClickException(
                    f"an unexpected error occurred when calling handler "
                    f"'{handler.__name__}' of plugin '{self.__name}'"
                )


@final
class EventSource:
    """Object that emits an event from an observable."""

    __observable: "ObservableBuild"
    __event_name: str

    def __init__(self, notify: "ObservableBuild", event_name: str):
        self.__observable = notify
        self.__event_name = event_name

    @property
    def event_name(self) -> str:
        return self.__event_name

    def notify(self):
        self.__observable.notify(self.__event_name)


@final
class ObservableBuild:
    """An observable that notifies plugins when build events occur."""

    __INTERNAL_MARKER = "!"

    __events: dict[str, str]
    __observers: list[KomoePlugin]

    def __init__(self):
        self.__events = dict()
        self.__observers = list()

    def register(self, observer: KomoePlugin):
        """Add a plugin to be notified."""
        self.__observers.append(observer)

    def setup_internal_events(self) -> Mapping[str, EventSource]:
        event_sources = dict()
        for event_name in ("setup", "cleanup", "compilation_start", "compilation_end"):
            if event_name in self.__events:
                raise ValueError(f"'{event_name}' has already been reserved.")
            else:
                self.__events[event_name] = self.__INTERNAL_MARKER
                event_sources[event_name] = EventSource(self, event_name)
        return event_sources

    def create_event(self, plugin: KomoePlugin, event_name: str) -> EventSource:
        already_registered_by = self.__events.get(event_name)
        if already_registered_by is None:
            self.__events[event_name] = plugin.name
            return EventSource(self, event_name)
        else:
            if already_registered_by == self.__INTERNAL_MARKER:
                raise ValueError(f"'{event_name}' is a reserved event name.")
            else:
                raise ValueError(
                    f"Event '{event_name}' was already registered by plugin '{already_registered_by}'"
                )

    def notify(self, event: str):
        """"""
        for observer in self.__observers:
            observer.on_build_event(event)


@final
class Plugins:
    __instance: Optional["Plugins"] = None

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super(Plugins, cls).__new__(cls)
            cls.__instance.__init_once()
        return cls.__instance

    __plugins: dict[str, KomoePlugin]
    __standalone_functions: list[tuple[StandalonePluginFunction, str]]
    __context: Optional["BuilderProxy"]
    __config = Optional[Mapping]

    def __init_once(self):
        self.__plugins = {}
        self.__standalone_functions = []
        self.__context = None
        self.__config = None

    def __require_context(self) -> "BuilderProxy":
        return self.__context

    def __get_config_for(self, plugin_name: str) -> Mapping:
        if self.__config is None:
            raise RuntimeError("")
        return self.__config.get(plugin_name)

    def __add_plugin_script(self, module_name):
        if module_name in self.__scripts:
            Log.dbg("script {module_name} is already loaded")
            return False
        else:
            self.__scripts.append(module_name)
            return True

    def __add_plugin_module(self, plugin_name: str, module_name: str):
        Log.dbg(f"Adding module '{module_name}' for plugin '{plugin_name}'")
        plugin = KomoePluginModule(
            plugin_name, self.__require_context(), self.__get_config_for(plugin_name)
        )
        for handler, event in self.__standalone_functions:
            if hasattr(handler, "__module__") and handler.__module__ == module_name:
                Log.dbg(f"Found a standalone handler for '{event}'")
                plugin.attach(event, handler)

    def __discover_plugins(self):
        Log.dbg("Searching for 'komoe_plugins' entry points")
        for entry_point in entry_points(group="komoe_plugins"):
            Log.dbg(f"Found plugin '{entry_point.name}'")
            plugin = entry_point.load()
            if isinstance(plugin, ModuleType):
                self.__add_plugin_module(entry_point.name, entry_point.module)

    def load_plugins(self, config: Mapping[str, PluginConfig], reload_modules: bool):
        Log.dbg("Loading plugins")
        self.__discover_plugins()
        """
        for name, plugin in config.items():
            plugin.is_explicit_package:
                # load installed package
                self.__plugin_packages[plugin["package"]] = name
                already_imported = sys.modules.get(plugin["package"])

                try:
                    if already_imported is None:
                        importlib.import_module(plugin["package"])

                    elif fresh:
                        importlib.reload(already_imported)

                except Exception as e:
                    Log.error(f"can't load plugin “{name}”: {e}")
                    raise click.ClickException("failed to load plugins")

            elif "script" in plugin:
                # load module from file path
                script_path = Path(plugin["script"])
                if not script_path.is_absolute():
                    script_path = self.__paths.base_dir / script_path

                script_module = name + "_komoe_plugin"

                if PluginScheduler().add_script(script_module):
                    spec = importlib.util.spec_from_file_location(
                        script_module, script_path
                    )
                    if spec is None or spec.loader is None:
                        Log.error(
                            f"can't load plugin “{name}”: unable to load {script_path} as a module"
                        )
                        raise click.ClickException("failed to load plugins")

                    module = importlib.util.module_from_spec(spec)

                    try:
                        spec.loader.exec_module(module)
                    except Exception as e:
                        Log.error(f"can't load plugin “{name}”: {e}")
                        raise click.ClickException("failed to load plugins")

            else:
                Log.warn(f"plugin “{name}” is declared but has no package/script")"""

    def register_standalone_function(self, func: StandalonePluginFunction, event: str):
        self.__standalone_functions.append((func, event))

    # def events(self, module):
    #     if module not in self.__events:
    #         self.__events[module] = _ModuleEvents()
    #     return self.__events[module]
    #
    # def actions(self, module):
    #     if module not in self.__actions:
    #         self.__actions[module] = _ModuleActions(module)
    #
    #     return self.__actions[module]
    #
    # def subscribe(self, module, event, callback):
    #     plugin_name = self.__context.get_package_alias(
    #         callback.__module__,
    #         callback.__module__.replace("_komoe_plugin", ""),
    #     )
    #     action_name = callback.__name__
    #
    #     if plugin_name == module:
    #         Log.error(
    #             f"a plugin can't subscribe to itself ({plugin_name}.{action_name})"
    #         )
    #         raise click.ClickException("failed to load plugins")
    #
    #     action = _Action(callback)
    #
    #     events = self.events(module)
    #     events.register(event, action)
    #
    #     actions = self.actions(plugin_name)
    #     actions.add(action)
    #
    #     self.events(plugin_name)
    #
    # def register_setup(self, callback):
    #     plugin_name = self.__context.get_package_alias(
    #         callback.__module__,
    #         callback.__module__.replace("_komoe_plugin", ""),
    #     )
    #
    #     self.__setup.append((plugin_name, callback))
    #
    # def register_cleanup(self, callback):
    #     plugin_name = self.__context.get_package_alias(
    #         callback.__module__,
    #         callback.__module__.replace("_komoe_plugin", ""),
    #     )
    #
    #     self.__cleanup.append((plugin_name, callback))
    #
    # def build_started(self):
    #     self.notify(Internal.Build, "start")
    #
    # def build_ended(self):
    #     self.notify(Internal.Build, "end")
    #
    # def set_context(self, context):
    #     self.__context = context
    #
    # def set_config(self, config):
    #     self.__config = config
    #
    # def notify(self, module, event):
    #     for action in self.events(module).on(event):
    #         if not action.module.started:
    #             self.notify(action.module.name, "start")
    #
    #         action(
    #             BuilderProxy(self.__context, action.module.name),
    #             self.__config.get(action.module.name, {}),
    #         )
    #
    #         if action.module.ended:
    #             self.notify(action.module.name, "end")
    #
    # def setup(self):
    #     for module, callback in self.__setup:
    #         callback(
    #             BuilderProxy(self.__context, module),
    #             self.__config.get(module, {}),
    #         )
    #
    # def cleanup(self):
    #     for module, callback in self.__cleanup:
    #         callback(
    #             BuilderProxy(self.__context, module),
    #             self.__config.get(module, {}),
    #         )
    #
    # def reload(self):
    #     for module_actions in self.__actions.values():
    #         module_actions.reload()
    #
    # def reset(self):
    #     self.__setup.clear()
    #     self.__cleanup.clear()
    #     self.__events.clear()
    #     self.__actions.clear()
    #     self.__scripts.clear()
    #
    #     self.__context = None
    #     self.__config = None
    #
    #     self.__events[Internal.Build] = _ModuleEvents()


class LogProxy:
    def __init__(self, ctx):
        self.__context = ctx

    @property
    def context(self):
        return self.__context

    @proxy(Log.error)
    def error(self, message):
        Log.error(f"{self.context}: {message}")

    @proxy(Log.warn)
    def warn(self, message):
        Log.warn(f"{self.context}: {message}")

    @proxy(Log.warn)
    def info(self, message):
        Log.info(f"{self.context}: {message}")


class MarkdownProxy:
    def __init__(self, markdown):
        self.__md = markdown

    @proxy(Markdown.disable_default_extension)
    def disable_default_extension(self, name):
        self.__md.disable_default_extension(name)

    @proxy(Markdown.add_extension)
    def add_extension(self, extension, config_name=None, **config):
        self.__md.add_extension(extension, config_name, **config)

    @proxy(Markdown.configure_extension)
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
    def base_dir(self):
        return self.__builder.base_dir

    @property
    def cache_dir(self):
        return self.__builder.cache_dir

    @property
    def output_dir(self):
        return self.__builder.output_dir

    @property
    def assets_output_dir(self):
        return self.__builder.assets_output_dir

    @property
    def source_dir(self):
        return self.__builder.source_dir

    @property
    def templates_dir(self):
        return self.__builder.templates_dir

    @property
    def assets_dir(self):
        return self.__builder.assets_dir


_TFunc = TypeVar("_TFunc", bound=StandalonePluginFunction)


def setup(func: _TFunc) -> _TFunc:
    """
    Register a function to be called only once during the very first setup
    phase. You can use it to add file loaders, markdown extensions, etc.
    """
    Plugins().register_standalone_function(func, "setup")
    return func


def compilation_start(func: _TFunc) -> _TFunc:
    """
    Register a function to be called each time a compilation starts. At this
    point, all plugins and komoe internals (e.g. the Markdown processor) are
    configured.
    """
    Plugins().register_standalone_function(func, "compilation_start")
    return func


def compilation_end(func: _TFunc) -> _TFunc:
    """
    Register a function to be called each time a compilation ends. At this
    point, all the output files are written.
    """
    Plugins().register_standalone_function(func, "compilation_end")
    return func


def cleanup(func: _TFunc) -> _TFunc:
    """
    Register a function to be called only once after a build is done, or when
    the development server shuts down.
    """
    Plugins().register_standalone_function(func, "cleanup")
    return func


def on(event_name: str) -> Callable[[_TFunc], _TFunc]:
    """
    Register a function to be called each time the specified event is emitted.
    """

    def _deco(func):
        Plugins().register_standalone_function(func, event_name)
        return func

    return _deco
