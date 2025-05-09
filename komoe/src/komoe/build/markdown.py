"""Interface to the markdown library."""
from typing import Optional

import markdown
import markdown.preprocessors
import markdown.treeprocessors
from abc import ABC, abstractmethod


class KomoeExtendedMarkdown(markdown.Markdown):
    __title: Optional[str]
    __template: Optional[str]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__title = None
        self.__template = None

    @property
    def template(self) -> Optional[str]:
        return self.__template

    @template.setter
    def template(self, value: str):
        self.__template = value

    @property
    def document_title(self) -> Optional[str]:
        return self.__title

    @document_title.setter
    def document_title(self, value: str):
        self.__title = value


class Markdown:
    """Wrapper around ``markdown.Markdown``."""

    __md: Optional[KomoeExtendedMarkdown]

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

        self.__md = KomoeExtendedMarkdown(
            extensions=extensions,
            extension_configs=self.__extensions_config,
        )

    def render(self, text: str) -> str:
        """
        Convert Markdown to HTML.

        :param text: the markdown input.

        :returns: the HTML output.
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
                Log.warn(
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
                Log.warn(
                    f"`config_name` can only be used with class extensions (extension {extension})"
                )
            if config:
                Log.warn(
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
    def template(self) -> Optional[str]:
        return self.__md.template if self.__md is not None else None

    @property
    def document_title(self) -> Optional[str]:
        return self.__md.document_title if self.__md is not None else None

    @property
    def metadata(self) -> dict[str, list[str]]:
        if self.__md is not None and hasattr(self.__md, "Meta"):
            return self.__md.Meta
        else:
            return dict()


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
    md: KomoeExtendedMarkdown

    def run(self, lines):
        new_lines = lines.copy()

        while new_lines[0].strip() == "":
            new_lines.pop(0)

        if new_lines[0].startswith("@"):
            self.md.template = new_lines[0][1:].strip()
            new_lines.pop(0)

        return new_lines

    def reset(self):
        self.md.template = None


class _TitleTreeprocessor(markdown.treeprocessors.Treeprocessor):
    md: KomoeExtendedMarkdown

    def run(self, root):
        h1 = root.find("h1")
        self.md.document_title = h1.text if h1 is not None else ""
