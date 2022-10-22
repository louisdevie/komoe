import markdown


class Markdown:
    def __init__(self):
        self.__md = markdown.Markdown(
            extensions=[
                MarkdownExtension(),
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
        )
        self.__md.komoe = self

        self.__template = None
        self.__title = ""

    def render(self, text):
        self.__md.reset()
        return self.__md.convert(text)

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


class MarkdownExtension(markdown.Extension):
    def extendMarkdown(self, md):
        self.__md = md
        self.__md.registerExtension(self)

        self.__md.preprocessors.register(
            TemplatePreprocessor(self.__md),
            "komoe.preprocessor.template",
            200,
        )
        self.__md.treeprocessors.register(
            TitleTreeprocessor(self.__md), "komoe.treeprocessor.title", 200
        )

    def reset(self):
        self.__md.template = None
        self.__md.document_title = ""


class TemplatePreprocessor(markdown.preprocessors.Preprocessor):
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


class TitleTreeprocessor(markdown.treeprocessors.Treeprocessor):
    def run(self, root):
        self.md.komoe.document_title = root.find("h1").text
