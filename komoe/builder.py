import click
import importlib
import os, shutil
import jinja2
import json
from pathlib import Path

from . import log
from .plugin import PluginScheduler
from .snapshot import Snapshot, Diff
from .markdown import Markdown
from .utils import file_status, cleartree


class Builder:
    def __init__(self, config, base_dir, **options):
        self.__config = config
        self.__options = options

        self.__base_dir = base_dir
        self.__cache_dir = self.__base_dir / ".cache"
        self.__output_dir = self.__base_dir / self.__config.output_directory
        self.__source_dir = self.__base_dir / self.__config.source_directory
        self.__templates_dir = self.__base_dir / self.__config.templates_directory
        self.__static_dir = self.__base_dir / self.__config.static_directory

        self.__snapshots = {
            "source": {"path": self.__source_dir},
            "templates": {"path": self.__templates_dir},
            "static": {"path": self.__static_dir},
        }
        self.__templates = {}

        self.__md = Markdown()
        self.__j2 = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.__templates_dir))
        )

    def build(self):
        PluginScheduler.context = self
        PluginScheduler.config = {
            plugin: self.__config.plugins[plugin].get("config", {})
            for plugin in self.__config.plugins
        }

        self.__load_plugins()
        self.__scan_directories()

        if self.__options["fresh"]:
            self.__clear_output_directory()
        else:
            self.__load_cache_data()

        PluginScheduler.build_started()
        click.echo("Build started ...")

        self.__render_pages()
        self.__copy_static_files()

        PluginScheduler.build_ended()

        self.__dump_cache_data()

    def add_directory(self, name, path):
        self.__snapshots[name] = {"path": self.__base_dir / path}

    def snapshot_current(self, name):
        return self.__snapshots[name]["current"]

    def snapshot_old(self, name):
        return self.__snapshots[name].get("old", Snapshot({}))

    def snapshot_diff(self, name):
        return self.snapshot_current(name).diff(self.snapshot_old(name))

    def __load_plugins(self):
        for name, plugin in self.__config.plugins.items():
            if "script" in plugin:
                # loading module from file path
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
        # loading previous snapshots
        for name in self.__snapshots:
            snapshot_path = self.__cache_dir / ("snapshot_" + name)
            if snapshot_path.is_file():
                with open(snapshot_path, "rt", encoding="utf8") as f:
                    self.__snapshots[name]["old"] = Snapshot.load(f.read())

        # load previous page-template relationships
        with open(self.__cache_dir / "relationships", "rt", encoding="utf8") as f:
            self.__templates = json.load(f)

    def __dump_cache_data(self):
        if not self.__cache_dir.exists():
            self.__cache_dir.mkdir()

        # dump snapshots
        for name in self.__snapshots:
            snapshot_path = self.__cache_dir / ("snapshot_" + name)
            with open(snapshot_path, "wt+", encoding="utf8") as f:
                f.write(self.__snapshots[name]["current"].dump())

        # dump page-template relationships
        with open(self.__cache_dir / "relationships", "wt+", encoding="utf8") as f:
            json.dump(self.__templates, f)

    def __scan_directories(self):
        for name in self.__snapshots:
            self.__snapshots[name]["current"] = Snapshot.scan(
                self.__snapshots[name]["path"]
            )

    def __render_pages(self):
        created = list()
        modified = list()
        removed = list()
        same = list()

        for file, diff in self.snapshot_diff("source").items():
            match diff:
                case Diff.CREATED:
                    created.append(file)
                case Diff.DELETED:
                    removed.append(file)
                case Diff.MODIFIED:
                    modified.append(file)
                case Diff.SAME:
                    same.append(file)

        if same:
            need_refresh = list()
            for file, diff in self.snapshot_diff("templates").items():
                if diff == Diff.MODIFIED:
                    need_refresh += self.__templates.get(file, [])
            for file in same:
                if file in need_refresh:
                    modified.append(file)

        env_info = ", ".join(
            ([f"{len(created)} added"] if created else [])
            + ([f"{len(modified)} modified"] if modified else [])
            + ([f"{len(removed)} removed"] if removed else [])
        )
        if env_info:
            log.info(f"Document environment updated: {env_info}")
        else:
            log.info(f"Document environment updated: no changes")
            return

        click.echo("Rendering pages ...")

        for file in created:
            self.__render_page(file, Diff.CREATED)

        for file in modified:
            self.__render_page(file, Diff.MODIFIED)

        for file in removed:
            self.__remove_page(file)

    def __page_location(self, file):
        base, _ = os.path.splitext(file)
        dest = base + ".html"

        return (
            self.__source_dir / file,
            self.__output_dir / dest,
        )

    def __render_page(self, file, modified):
        file_status(file, modified)

        src_path, dst_path = self.__page_location(file)

        depth = len(Path(file).parts) - 1
        rel_root = "/".join([".."] * depth) if depth else "."

        with open(src_path, "rt", encoding="utf8") as f:
            md = f.read()

        content = self.__md.render(md)

        template_path = str(
            self.__find_template_file().relative_to(self.__templates_dir)
        )

        same_template = False
        for old_template, sources in self.__templates.items():
            if file in sources:
                if template_path == old_template:
                    same_template = True
                else:
                    sources.remove(file)
                break
        if not same_template:
            if template_path in self.__templates:
                self.__templates[template_path].append(str(file))
            else:
                self.__templates[template_path] = [str(file)]

        tpl = self.__j2.get_template(template_path)

        title = self.__md.document_title
        if "title" in self.__md.metadata:
            title = self.__md.metadata["title"][0]

        shared = {
            "TITLE": title,
            "ROOT": rel_root,
            "STATIC": rel_root + "/_static",
        }

        content_tpl = self.__j2.from_string(content)
        html = tpl.render(CONTENT=content_tpl.render(**shared), **shared)

        os.makedirs(dst_path.parent, exist_ok=True)

        with open(dst_path, "wt+", encoding="utf8") as f:
            f.write(html)

        click.echo("done")

    def __remove_page(self, file):
        file_status(file, Diff.REMOVED)

        _, path = self.__page_location(file)

        self.__templates_remove_source(file)

        try:
            os.remove(self.__output_dir / path)
            click.echo("done")
        except FileNotFoundError:
            print()
            log.warn(f"Failed to remove {path}: file not found")

    def __copy_static_files(self):
        created = list()
        modified = list()
        removed = list()

        for file, diff in self.snapshot_diff("static").items():
            match diff:
                case Diff.CREATED:
                    created.append(file)
                case Diff.DELETED:
                    removed.append(file)
                case Diff.MODIFIED:
                    modified.append(file)

        env_info = ", ".join(
            ([f"{len(created)} added"] if created else [])
            + ([f"{len(modified)} modified"] if modified else [])
            + ([f"{len(removed)} removed"] if removed else [])
        )
        if env_info:
            log.info(f"Static environment updated: {env_info}")
        else:
            log.info(f"Static environment updated: no changes")
            return

        click.echo("Copying static files ...")

        for file in created:
            self.__copy_static_file(file, Diff.CREATED)

        for file in modified:
            self.__copy_static_file(file, Diff.MODIFIED)

        for file in removed:
            self.__remove_static_file(file)

    def __copy_static_file(self, file, modified):
        file_status(file, modified)

        dest = self.__output_dir / "_static" / file

        os.makedirs(dest.parent, exist_ok=True)
        shutil.copy(self.__static_dir / file, dest)

        click.echo("done")

    def __remove_static_file(self, file):
        file_status(file, Diff.REMOVED)

        try:
            os.remove(self.__output_dir / "_static" / file)
            click.echo("done")
        except FileNotFoundError:
            print()
            log.warn(f"Failed to remove {file}: file not found")

    def __find_template_file(self):
        directory, name = os.path.split(self.__md.template)
        directory = self.__templates_dir / directory

        if not directory.is_dir():
            log.error(f"No such template : {self.__md.template}")
            raise click.ClickException(f"failed to render {file}")

        path = None
        for f in directory.iterdir():
            if f.is_file() and f.name.startswith(name + "."):
                path = f
        if path is None:
            log.error(f"No such template : {self.__md.template}")
            raise click.ClickException(f"failed to render {file}")

        return path

    def __clear_output_directory(self):
        cleartree(self.__output_dir)
