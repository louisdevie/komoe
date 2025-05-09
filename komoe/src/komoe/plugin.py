"""Interface to the Komoe build process for plugins."""
import importlib.util
import sys
from importlib.metadata import entry_points
from logging import Logger
from pathlib import Path
from types import ModuleType
from typing import Optional, Mapping, Any, Callable, final, TypeAlias, TypeVar, Dict

import click
from click import ClickException

from .build.markdown import Markdown
from .config import PluginConfig
from .logging import Logging
from .utils import proxy

__all__ = [
    "KomoePlugin",
    "PluginContext",
    "MarkdownProxy",
    "setup",
    "compilation_start",
    "compilation_end",
    "cleanup",
    "on",
]

log = Logging.get_logger(__name__)


class KomoePlugin:
    """
    The base class for komoe plugins.
    """

    __name: str
    __context: "PluginContext"
    __config: Mapping

    def __init__(self, name: str, context: "PluginContext", config: Mapping):
        self.__name = name
        self.__context = context
        self.__config = config

    def on_build_event(self, event: str):
        handler_name = f"on_{event}"
        try:
            getattr(self, handler_name)()
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
    def context(self) -> "PluginContext":
        return self.__context

    @property
    def log(self) -> Logger:
        return self.__context.log

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


StandalonePluginFunction: TypeAlias = Callable[["PluginContext", Mapping], Any]
"""
A function that can be registered as a plugin event handler using a decorator
like :deco:`setup`.
"""


@final
class KomoePluginModule(KomoePlugin):
    """A plugin loaded from a module."""

    __handlers: dict[str, StandalonePluginFunction]

    def __init__(self, name: str, context: "PluginContext", config: Mapping):
        super().__init__(name, context, config)

        self.__handlers = {}

    def attach(self, event: str, handler: StandalonePluginFunction):
        if event in self.__handlers:
            log.error(
                f"Another handler for '{event}' is already defined in plugin '{self.name}'."
            )
            raise RuntimeError("cannot define multiple handlers for the same event")
        self.__handlers[event] = handler
        log.debug(f"Handler attached to plugin module '{self.name}'")

    def on_build_event(self, event: str):
        handler = self.__handlers.get(event)
        if handler is not None:
            try:
                handler(self.context, self.config)
            except Exception as e:
                self.log.exception("a", exc_info=e)
                raise ClickException(
                    f"an unexpected error occurred when calling handler "
                    f"'{handler.__name__}' of plugin '{self.name}'"
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
        """Set up events to be triggered by the komoe build process."""
        event_sources = dict()
        for event_name in ("setup", "cleanup", "compilation_start", "compilation_end"):
            if event_name in self.__events:
                raise ValueError(f"'{event_name}' has already been reserved.")
            else:
                self.__events[event_name] = self.__INTERNAL_MARKER
                event_sources[event_name] = EventSource(self, event_name)
        return event_sources

    def create_event(self, plugin: KomoePlugin, event_name: str) -> EventSource:
        """Set up an event to be triggered by a plugin."""
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
        """Triggers all registered observers with the given event."""
        for observer in self.__observers:
            observer.on_build_event(event)


@final
class Plugins:
    __instance: Optional["Plugins"] = None

    def __new__(cls) -> "Plugins":
        if cls.__instance is None:
            cls.__instance = super(Plugins, cls).__new__(cls)
            cls.__instance.__init_once()
        return cls.__instance

    __plugins: dict[str, KomoePlugin]
    __standalone_functions: list[tuple[StandalonePluginFunction, str]]
    __context: Mapping[str, Any] | None
    __config: Mapping[str, PluginConfig] | None

    def __init_once(self):
        self.__plugins = {}
        self.__standalone_functions = []
        self.__context = None
        self.__config = None

    def __require_context_for(self, plugin_name: str) -> "PluginContext":
        if self.__context is None:
            raise RuntimeError(f"Attempt to access context before initialisation")
        return PluginContext(plugin_name, self.__context)

    def __get_config_for(self, plugin_name: str) -> Mapping:
        if self.__config is None:
            raise RuntimeError("Attempt to access plugin config before initialisation")
        config = self.__config.get(plugin_name)
        return None if config is None else config.extras

    def __add_plugin(self, plugin: KomoePlugin):
        if plugin.name in self.__plugins:
            raise RuntimeError(
                f"Attempt to register plugin '{plugin.name}' multiple times"
            )
        self.__plugins[plugin.name] = plugin
        self.__context["observable"].register(plugin)

    def __add_plugin_module(self, plugin_name: str, module_name: str):
        """
        Register a plugin module.

        :param plugin_name: The name of the plugin.
        :param module_name: The name of the python module. The standalone
           functions that belong to this module will be attached to the plugin.
        """
        log.debug(f"Adding module '{module_name}' as plugin '{plugin_name}'")

        plugin = KomoePluginModule(
            plugin_name,
            self.__require_context_for(plugin_name),
            self.__get_config_for(plugin_name),
        )

        for handler, event in self.__standalone_functions:
            if getattr(handler, "__module__", None) == module_name:
                log.debug(f"Found a standalone handler for '{event}'")
                plugin.attach(event, handler)

        self.__add_plugin(plugin)

    def __add_plugin_class(self, plugin_name: str, cls: type[KomoePlugin]):
        """
        Register a plugin class.

        :param plugin_name: The name of the plugin.
        :param cls: The plugin class derived from ``KomoePlugin``.
        """
        log.debug(f"Adding class '{cls.__name__}' as plugin '{plugin_name}'")

        plugin = cls(
            plugin_name,
            self.__require_context_for(plugin_name),
            self.__get_config_for(plugin_name),
        )

        self.__add_plugin(plugin)

    def __discover_plugins(self):
        """Automatically load plugins using setuptools entry points."""
        log.debug("Searching for 'komoe_plugins' entry points")

        for entry_point in entry_points(group="komoe_plugins"):
            log.debug(f"Found plugin '{entry_point.name}'")
            plugin = entry_point.load()
            if isinstance(plugin, ModuleType):
                self.__add_plugin_module(entry_point.name, entry_point.module)
            elif type(plugin) is type and issubclass(plugin, KomoePlugin):
                self.__add_plugin_class(entry_point.name, plugin)
            else:
                dist = entry_point.dist
                origin = " declared by " + dist.name if dist is not None else ""
                log.warning(
                    f"Entry point '{entry_point.name}'{origin} is not a valid plugin"
                )

    def __load_scripts(self):
        """Load script plugins declared in the config file."""
        log.debug("Loading scripts")
        for name, plugin in self.__config.items():
            if plugin.script is not None:
                log.debug(f"Found plugin '{name}'")

                # load module from file path
                script_path = Path(plugin.script)
                if not script_path.is_absolute():
                    script_path = self.__context["paths"].base_dir / script_path

                script_module = name + "_komoe_plugin"
                already_imported = sys.modules.get(script_module)

                if already_imported is None:
                    log.debug(f"Loading script '{script_path}' as '{script_module}'")

                    spec = importlib.util.spec_from_file_location(
                        script_module, script_path
                    )
                    if spec is None or spec.loader is None:
                        log.error(
                            f"failed to load plugin '{name}': unable to load {script_path} as a module"
                        )
                        raise click.ClickException("failed to load plugins")

                    module = importlib.util.module_from_spec(spec)
                    sys.modules[script_module] = module
                    spec.loader.exec_module(module)

                self.__add_plugin_module(name, script_module)

    def load_plugins(self, config: Mapping[str, PluginConfig], reload_modules: bool):
        """Loads all available plugins."""
        log.debug("Loading plugins")
        self.__config = config

        self.__discover_plugins()
        self.__load_scripts()

    def register_standalone_function(self, func: StandalonePluginFunction, event: str):
        self.__standalone_functions.append((func, event))

    def set_context(self, context: Mapping[str, Any]) -> Mapping[str, EventSource]:
        """
        Set up the build context and initialise a new observable.

        :param context: Data passed from the builder to the plugins. The mapping
           is expected to have a 'markdown' and a 'paths' entry.

        :return: The internal events like ``setup`` and ``cleanup``.
        """
        if self.__context is not None:
            raise RuntimeError("A build context has already been defined")

        observable = ObservableBuild()
        self.__context = {**context, "observable": observable}
        return observable.setup_internal_events()


class MarkdownProxy:
    __md: Markdown

    def __init__(self, markdown: Markdown):
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


class PluginContext:
    __plugin_name: str
    __md: MarkdownProxy
    __log: Logger

    def __init__(self, plugin_name: str, context: Mapping[str, Any]):
        self.__plugin_name = plugin_name
        self.__log = Logging.get_logger_for_plugin(plugin_name)
        self.__md = MarkdownProxy(context["markdown"])

    @property
    def log(self):
        return self.__log

    @property
    def echo(self):
        return click.echo

    def abort(self, message=None):
        raise click.ClickException(
            f"plugin {self.__plugin_name} aborted the build"
            + ("" if message is None else ": " + message)
        )


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
