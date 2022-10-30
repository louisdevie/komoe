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
from .utils import file_status, file_status_done, cleartree


class Builder:
    def __init__(self, config, base_dir, **options):
        self.__config = config
        self.__options = options

        self.__base_dir = base_dir

        self.__snapshots = {
            "source": {"path": self.source_dir},
            "templates": {"path": self.templates_dir},
            "static": {"path": self.static_dir},
        }
        self.__templates = {}

        self.__md = Markdown()
        self.__j2 = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir))
        )

        self.__plugin_packages = {}

    @property
    def cache_dir(self):
        return self.__base_dir / ".cache"

    @property
    def output_dir(self):
        return self.__base_dir / self.__config.output_directory

    @property
    def static_output_dir(self):
        return self.output_dir / "_static"

    @property
    def source_dir(self):
        return self.__base_dir / self.__config.source_directory

    @property
    def templates_dir(self):
        return self.__base_dir / self.__config.templates_directory

    @property
    def static_dir(self):
        return self.__base_dir / self.__config.static_directory

    @property
    def markdown(self):
        return self.__md

    def build(self):
        PluginScheduler.set_context(self)

        self.__load_plugins()

        PluginScheduler.set_config(
            {
                plugin: self.__config.plugins[plugin].get("config", {})
                for plugin in self.__config.plugins
            }
        )
        PluginScheduler.setup()

        self.__md.init()

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

    def snapshot_register(self, name, path):
        self.__snapshots[name] = {"path": self.__base_dir / path}

    def snapshot_current(self, name):
        return self.__snapshots[name]["current"]

    def snapshot_old(self, name):
        return self.__snapshots[name].get("old", Snapshot({}))

    def snapshot_diff(self, name):
        return self.snapshot_current(name).diff(self.snapshot_old(name))

    def get_package_alias(self, pkg, default=None):
        return self.__plugin_packages.get(pkg, default)

    def __load_plugins(self):
        for name, plugin in self.__config.plugins.items():
            if "package" in plugin:
                # loading installed package
                self.__plugin_packages[plugin["package"]] = name
                try:
                    importlib.import_module(plugin["package"])
                except Exception as e:
                    log.error(f"can't load plugin “{name}”: {e}")
                    raise click.ClickException("failed to load plugins")

            elif "script" in plugin:
                # loading module from file path
                script_path = Path(plugin["script"])
                if not script_path.is_absolute():
                    script_path = self.__base_dir / script_path

                spec = importlib.util.spec_from_file_location(
                    name + "_komoe_plugin", script_path
                )
                module = importlib.util.module_from_spec(spec)

                try:
                    spec.loader.exec_module(module)
                except Exception as e:
                    log.error(f"can't load plugin “{name}”: {e}")
                    raise click.ClickException("failed to load plugins")

            else:
                log.warn(f"plugin “{name}” is declared but has no package/script")

    def __load_cache_data(self):
        # loading previous snapshots
        for name in self.__snapshots:
            snapshot_path = self.cache_dir / ("snapshot_" + name)
            if snapshot_path.is_file():
                with open(snapshot_path, "rt", encoding="utf8") as f:
                    self.__snapshots[name]["old"] = Snapshot.load(f.read())

        # load previous page-template relationships
        relationships_path = self.cache_dir / "relationships"
        if relationships_path.is_file():
            with open(relationships_path, "rt", encoding="utf8") as f:
                self.__templates = json.load(f)

    def __dump_cache_data(self):
        if not self.cache_dir.exists():
            self.cache_dir.mkdir()

        # dump snapshots
        for name in self.__snapshots:
            snapshot_path = self.cache_dir / ("snapshot_" + name)
            with open(snapshot_path, "wt+", encoding="utf8") as f:
                f.write(self.__snapshots[name]["current"].dump())

        # dump page-template relationships
        with open(self.cache_dir / "relationships", "wt+", encoding="utf8") as f:
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
            if diff == Diff.CREATED:
                created.append(file)
            elif diff == Diff.DELETED:
                removed.append(file)
            elif diff == Diff.MODIFIED:
                modified.append(file)
            elif diff == Diff.SAME:
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
            log.info("Document environment updated: no changes")
            return

        click.echo("Rendering pages:")

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
            self.source_dir / file,
            self.output_dir / dest,
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
            self.__find_template_file(file).relative_to(self.templates_dir)
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

        file_status_done()

    def __remove_page(self, file):
        file_status(file, Diff.DELETED)

        _, path = self.__page_location(file)

        for template, sources in self.__templates.items():
            if str(file) in sources:
                self.__templates[template].remove(str(file))

        try:
            os.remove(self.output_dir / path)
            click.echo("done")
        except FileNotFoundError:
            print()
            log.warn(f"Failed to remove {path}: file not found")

        file_status_done()

    def __copy_static_files(self):
        created = list()
        modified = list()
        removed = list()

        for file, diff in self.snapshot_diff("static").items():
            if diff == Diff.CREATED:
                created.append(file)
            elif diff == Diff.DELETED:
                removed.append(file)
            elif diff == Diff.MODIFIED:
                modified.append(file)

        env_info = ", ".join(
            ([f"{len(created)} added"] if created else [])
            + ([f"{len(modified)} modified"] if modified else [])
            + ([f"{len(removed)} removed"] if removed else [])
        )
        if env_info:
            log.info(f"Static environment updated: {env_info}")
        else:
            log.info("Static environment updated: no changes")
            return

        click.echo("Copying static files:")

        for file in created:
            self.__copy_static_file(file, Diff.CREATED)

        for file in modified:
            self.__copy_static_file(file, Diff.MODIFIED)

        for file in removed:
            self.__remove_static_file(file)

    def __copy_static_file(self, file, modified):
        file_status(file, modified)

        dest = self.static_output_dir / file

        os.makedirs(dest.parent, exist_ok=True)
        shutil.copy(self.static_dir / file, dest)

        file_status_done()

    def __remove_static_file(self, file):
        file_status(file, Diff.DELETED)

        try:
            os.remove(self.static_output_dir / file)
            file_status_done()
        except FileNotFoundError:
            print()
            log.warn(f"Failed to remove {file}: file not found")

    def __find_template_file(self, file):
        directory, name = os.path.split(self.__md.template)
        directory = self.templates_dir / directory

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
        if self.output_dir.is_dir():
            cleartree(self.output_dir)
