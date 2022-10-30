"""Interface to the markdown library."""

import markdown
from abc import ABC, abstractmethod

from . import log


class Markdown:
    """Wrappper around `markdown.Markdown`."""

    def __init__(self):
        self.__md = None

        self.__template = None
        self.__title = ""

        self.__default_extensions = [
            "attr_list",
            "fenced_code",
            "footnotes",
            "tables",
            "admonition",
            "meta",
            "sane_lists",
            "smarty",
            "toc",
        ]
        self.__additional_extensions = []
        self.__extensions_config = {}

    def init(self):
        """Initialises the internal `markdown.Markdown` class."""

        extensions = (
            [_MarkdownExtension()]
            + self.__default_extensions
            + [
                ext.instanciate(self.__extensions_config)
                for ext in self.__additional_extensions
            ]
        )
        print(extensions)
        print(self.__extensions_config)
        self.__md = markdown.Markdown(
            extensions=extensions,
            extension_configs=self.__extensions_config,
        )
        self.__md.komoe = self

    def render(self, text: str) -> str:
        """Convert Markdown to HTML.

        Parameters
          text: the markdown inputt.

        Returns
          the HTML output.
        """

        if self.__md is None:
            raise RuntimeError("Markdown renderer not initialised yet")

        self.__md.reset()
        return self.__md.convert(text)

    def disable_default_extension(self, name: str):
        """Disables a default extension.

        Parameters
          name: the name of the extension to disable. May be one of "attr_list",
                "fenced_code", "footnotes", "tables", "admonition", "meta",
                "sane_lists", "smarty" or "toc". For more information, see the
                documentation at https://python-markdown.github.io/extensions/.
        """

        self.__default_extensions.remove(name)

    def add_extension(self, extension, config_name=None, **config):
        if isinstance(extension, str):
            if config_name is not None:
                log.warn(
                    f"`config_name` can only be used with class extensions (extension {extension})"
                )
            self.__additional_extensions.append(
                _BasicMarkdownPluginExtension(extension)
            )
            self.configure_extension(extension, **config)

        elif issubclass(extension, markdown.Extension):
            self.__additional_extensions.append(
                _ClassMarkdownPluginExtension(extension, config, config_name)
            )

        elif isinstance(extension, markdown.Extension):
            if config_name is not None:
                log.warn(
                    f"`config_name` can only be used with class extensions (extension {extension})"
                )
            if config:
                log.warn(
                    f"an instance extension cannot be re-configured (extension {type(extension)})"
                )
            self.__additional_extensions.append(
                _BasicMarkdownPluginExtension(extension)
            )

        else:
            raise TypeError(
                "`extension` must be a string, a class derived from"
                "`markdown.Extension` or an instance of it"
            )

    def configure_extension(self, name, **config):
        if name in self.__extensions_config:
            self.__extensions_config[name].update(config)
        else:
            self.__extensions_config[name] = config

    @property
    def template(self):
        return self.__template

    @template.setter
    def template(self, value):
        self.__template = value

    @property
    def document_title(self):
        return self.__title

    @document_title.setter
    def document_title(self, value):
        self.__title = value

    @property
    def metadata(self):
        return self.__md.Meta


class _PluginMarkdownExtension(ABC):
    @abstractmethod
    def instanciate(self, config):
        ...


class _BasicMarkdownPluginExtension(_PluginMarkdownExtension):
    def __init__(self, name_or_instance):
        self.__obj = name_or_instance

    def instanciate(self, config):
        return self.__obj


class _ClassMarkdownPluginExtension(_PluginMarkdownExtension):
    def __init__(self, ext, config, name):
        self.__base_config = config
        self.__class = ext
        self.__name = name

    def instanciate(self, config):
        cfg = dict()
        if self.__name is not None:
            if self.__name in config:
                cfg.update(config[self.__name])
        cfg.update(self.__base_config)
        return self.__class(**cfg)


class _MarkdownExtension(markdown.Extension):
    def extendMarkdown(self, md):
        self.__md = md
        self.__md.registerExtension(self)

        self.__md.preprocessors.register(
            _TemplatePreprocessor(self.__md),
            "komoe.preprocessor.template",
            200,
        )
        self.__md.treeprocessors.register(
            _TitleTreeprocessor(self.__md), "komoe.treeprocessor.title", 200
        )

    def reset(self):
        self.__md.template = None
        self.__md.document_title = ""


class _TemplatePreprocessor(markdown.preprocessors.Preprocessor):
    def run(self, lines):
        new_lines = lines.copy()

        while not new_lines[0].strip():
            new_lines.pop(0)

        if new_lines[0].startswith("@"):
            self.md.komoe.template = new_lines[0][1:]
            new_lines.pop(0)

        return new_lines

    def reset(self):
        self.md.komoe.template = None


class _TitleTreeprocessor(markdown.treeprocessors.Treeprocessor):
    def run(self, root):
        h1 = root.find("h1")
        self.md.komoe.document_title = h1.text if h1 else ""
