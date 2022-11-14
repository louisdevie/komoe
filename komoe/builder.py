import click
import importlib
import os
import shutil
import sys
import jinja2
import jinja2td
import json
from pathlib import Path
from functools import partial

from . import log
from .plugin import PluginScheduler
from .snapshot import Snapshot, Diff
from .markdown import Markdown
from .utils import file_status, file_status_done, cleartree
from .doctree import DocumentTree
from .relationships import Relationships


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
        self.__templates = Relationships()
        self.__doctree = DocumentTree()
        self.__postprocess = []

        self.__md = Markdown()

        self.__j2 = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir)),
            extensions=[jinja2td.Introspection],
        )

        self.__postprocessors = {"docpath": self.__document_path_postprocess}

        self.__plugin_packages = {}

    @property
    def base_dir(self):
        return self.__base_dir

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
    def snapshot_dirs(self):
        return (s["path"] for s in self.__snapshots.values())

    @property
    def markdown(self):
        return self.__md

    def build(self):
        if self.__options["fresh"]:
            PluginScheduler.reset()
        else:
            PluginScheduler.reload()

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
        self.__postprocess_pages()
        self.__copy_static_files()

        PluginScheduler.build_ended()

        self.__dump_cache_data()

        PluginScheduler.cleanup()

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
                # load installed package
                self.__plugin_packages[plugin["package"]] = name
                already_imported = sys.modules.get(plugin["package"])

                try:
                    if already_imported is None:
                        importlib.import_module(plugin["package"])

                    elif self.__options["fresh"]:
                        importlib.reload(already_imported)

                except Exception as e:
                    log.error(f"can't load plugin “{name}”: {e}")
                    raise click.ClickException("failed to load plugins")

            elif "script" in plugin:
                # load module from file path
                script_path = Path(plugin["script"])
                if not script_path.is_absolute():
                    script_path = self.__base_dir / script_path

                script_module = name + "_komoe_plugin"

                if PluginScheduler.add_script(script_module):
                    spec = importlib.util.spec_from_file_location(
                        script_module, script_path
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
                self.__templates = Relationships.from_dict(json.load(f))

        # load document tree
        doctree_path = self.cache_dir / "doctree"
        if doctree_path.is_file():
            with open(doctree_path, "rt", encoding="utf8") as f:
                self.__doctree = DocumentTree.from_dict(json.load(f))

    def __dump_cache_data(self):
        if not self.cache_dir.exists():
            self.cache_dir.mkdir()

        # dump snapshots
        for name in self.__snapshots:
            snapshot_path = self.cache_dir / ("snapshot_" + name)
            with open(snapshot_path, "wt", encoding="utf8") as f:
                f.write(self.__snapshots[name]["current"].dump())

        # dump page-template relationships
        with open(self.cache_dir / "relationships", "wt", encoding="utf8") as f:
            json.dump(self.__templates.to_dict(), f)

        # dump document tree
        with open(self.cache_dir / "doctree", "wt", encoding="utf8") as f:
            json.dump(self.__doctree.to_dict(), f)

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
                    need_refresh += self.__templates.get_documents(file)
            for file in same:
                if file in need_refresh:
                    modified.append(file)

        env_info = ", ".join(
            ([f"{len(created)} added"] if created else [])
            + ([f"{len(modified)} modified"] if modified else [])
            + ([f"{len(removed)} removed"] if removed else [])
        )
        if env_info:
            log.info(f"Document environment: {env_info}")
        else:
            log.info("Document environment: no changes")
            return

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
            dest,
        )

    def __render_page(self, file, modified):
        src_path, dst_path, dst = self.__page_location(file)

        file_status(dst, modified)

        depth = len(Path(file).parts) - 1
        rel_root = "/".join([".."] * depth) if depth else "."

        with open(src_path, "rt", encoding="utf8") as f:
            md = f.read()

        content = self.__md.render(md)

        template_path = str(
            self.__find_template_file(file).relative_to(self.templates_dir)
        )

        title = self.__md.document_title
        if "title" in self.__md.metadata:
            title = " — ".join(self.__md.metadata["title"])

        if modified == Diff.MODIFIED:
            self.__doctree.edit_document(Path(dst), title)
        else:
            self.__doctree.add_document(Path(dst), title)

        rendering_context = {
            "root": rel_root,
            "path": dst,
        }

        shared = {
            "title": title,
            "absolute": partial(self.__root_path, rendering_context),
            "static": partial(self.__static_path, rendering_context),
            "document_path": partial(self.__document_path_marker, rendering_context),
        }

        tpl = self.__j2.get_template(template_path)
        content_tpl = self.__j2.from_string(content)

        self.__j2.dependencies.watch()

        html = tpl.render(content=content_tpl.render(**shared), **shared)

        self.__templates.update(
            file,
            template_path,
            self.__j2.dependencies.used_last_watch(),
        )

        os.makedirs(dst_path.parent, exist_ok=True)

        with open(dst_path, "wt+", encoding="utf8") as f:
            f.write(html)

        file_status_done()

    def __remove_page(self, file):
        _, path, dst = self.__page_location(file)

        file_status(dst, Diff.DELETED)

        for template, sources in self.__templates.items():
            if str(file) in sources:
                self.__templates[template].remove(str(file))

        self.__doctree.remove_document(Path(dst))

        try:
            os.remove(self.output_dir / path)
            click.echo("done")
        except FileNotFoundError:
            print()
            log.warn(f"Failed to remove {path}: file is already gone")

        file_status_done()

    def __postprocess_pages(self):
        for doc in self.__postprocess:
            try:
                with open(self.output_dir / doc, "rt", encoding="utf8") as f:
                    content = f.read()

                position = 0
                new_content = str()
                failed = []
                while (start := content.find("<!--KOMOE:", position)) != -1:
                    func_end = content.find("-->", start)
                    end = func_end + 3  # include the -->
                    func_start = start + 10  # ignore the <!--KOMOE:

                    new_content += content[position:start]

                    try:
                        op = json.loads(content[func_start:func_end])
                        result = self.__postprocessors.get(op.pop("op"))(
                            path=Path(doc), **op
                        )
                        new_content += result

                    except Exception as e:
                        failed.append(e)

                    position = end

                if failed:
                    log.warn(
                        f"Failed to postprocess one or more markers in file {doc}:\n   "
                        + ", ".join(str(e) for e in failed)
                    )

                new_content += content[position:]

                with open(self.output_dir / doc, "wt", encoding="utf8") as f:
                    f.write(new_content)

            except Exception as e:
                log.warn(f"Failed to postprocess file {doc}:\n   {e}")

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
            log.info(f"Static environment: {env_info}")
        else:
            log.info("Static environment: no changes")
            return

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
            log.warn(f"Failed to remove {file}: file is already gone")

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

    def __root_path(self, ctx, path):
        if not path.startswith("/"):
            path = "/" + path

        return repr(ctx.get("root") + path)

    def __static_path(self, ctx, path):
        if not path.startswith("/"):
            path = "/" + path

        return repr(ctx.get("root") + "/_static" + path)

    def __document_path_marker(self, ctx, sep=" / ", maxdepth=0, include=True):
        self.__postprocess.append(ctx.get("path"))

        func = {"op": "docpath", "sep": sep, "maxdepth": maxdepth, "include": include}

        return f"<!--KOMOE:{json.dumps(func)}-->"

    def __document_path_postprocess(self, path, sep, maxdepth, include):
        if path.stem == "index":
            if len(path.parent.parts) == 0:  # root document
                return ""
            else:
                *parts, leaf = path.parent.parts
                offset = 1
        else:
            parts = path.parent.parts
            leaf = path.stem
            offset = 0

        rel = [
            "/".join([".."] * d) if d else "."
            for d in range(len(parts) + offset, offset - 1, -1)
        ]

        parent = self.__doctree.root
        nodes = [(f' href="{rel.pop(0)}"' if parent.is_document else "", parent.title)]

        for part in parts:
            child = parent.get_child(part)

            if child is None:
                raise ValueError(f"can't find document node in {path}")

            nodes.append(
                (f' href="{rel.pop(0)}"' if child.is_document else "", child.title)
            )
            parent = child

        leaf_node = parent.get_child(leaf)

        if leaf_node is None:
            raise ValueError(f"can't find document node in {path}")

        nodes.append(("", leaf_node.title))

        if not include:
            nodes = nodes[:-1]

        if maxdepth > 0:
            if len(nodes) > maxdepth:
                nodes = [("", "...")] + nodes[-maxdepth:]

        return sep.join(f"<a {n[0]}>{n[1]}</a>" for n in nodes)
