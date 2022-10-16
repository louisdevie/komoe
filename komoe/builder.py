import click
import importlib

from . import log
from .plugin import PluginScheduler
from .snapshot import Snapshot


class Builder:
    def __init__(self, config, base_dir):
        self.__base_dir = base_dir
        self.__cache_dir = base_dir / ".cache"
        self.__output_dir = base_dir / config.output_directory
        self.__source_dir = base_dir / config.source_directory
        self.__html_dir = base_dir / config.templates_directory
        self.__static_dir = base_dir / config.static_directory

        self.__config = config

        self.__snapshots = {
            "source": {"path": self.__source_dir},
            "templates": {"path": self.__html_dir},
            "static": {"path": self.__static_dir},
        }

    def build(self):
        PluginScheduler.context = self
        PluginScheduler.config = {
            plugin: self.__config.plugins[plugin].get("config", {})
            for plugin in self.__config.plugins
        }

        self.__load_plugins()
        self.__load_cache_data()
        self.__scan_directories()

        print(self.current_snapshot("source").diff(self.old_snapshot("source")))
        print(self.current_snapshot("templates").diff(self.old_snapshot("templates")))
        print(self.current_snapshot("static").diff(self.old_snapshot("static")))

        PluginScheduler.build_started()
        log.info("Build started ...")

        self.__render_pages()
        self.__copy_static_files()

        PluginScheduler.build_ended()

        self.__dump_cache_data()

    def add_directory(self, name, path):
        self.__snapshots[name] = {"path": self.__base_dir / path}

    def current_snapshot(self, name):
        return self.__snapshots[name]["current"]

    def old_snapshot(self, name):
        return self.__snapshots[name].get("old", Snapshot({}))

    def __load_plugins(self):
        for name, plugin in self.__config.plugins.items():
            if "script" in plugin:
                script_path = self.__base_dir / plugin["script"]

                spec = importlib.util.spec_from_file_location(
                    name + "_komoe_plugin", script_path
                )
                module = importlib.util.module_from_spec(spec)

                try:
                    spec.loader.exec_module(module)
                except FileNotFoundError as e:
                    log.error(f"can't load plugin “{name}”: {e}")
                    raise click.ClickException("failed to load plugins")

            else:
                log.warn(f"plugin “{name}” is declared but has no script")

    def __load_cache_data(self):
        for name in self.__snapshots:
            snapshot_path = self.__cache_dir / ("snapshot_" + name)
            if snapshot_path.is_file():
                with open(snapshot_path, "rt", encoding="utf8") as f:
                    self.__snapshots[name]["old"] = Snapshot.load(f.read())

    def __dump_cache_data(self):
        if not self.__cache_dir.exists():
            self.__cache_dir.mkdir()

        for name in self.__snapshots:
            snapshot_path = self.__cache_dir / ("snapshot_" + name)
            with open(snapshot_path, "wt+", encoding="utf8") as f:
                f.write(self.__snapshots[name]["current"].dump())

    def __scan_directories(self):
        for name in self.__snapshots:
            self.__snapshots[name]["current"] = Snapshot.scan(
                self.__snapshots[name]["path"]
            )

    def __render_pages(self):
        pass

    def __copy_static_files(self):
        log.info("Copying static files ...")
