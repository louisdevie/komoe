from . import log


class Node:
    def __init__(self, title, is_document):
        self.__title = title
        self.__is_document = is_document
        self.__children = {}

    @property
    def title(self):
        return self.__title

    @property
    def is_document(self):
        return self.__is_document

    @property
    def children(self):
        return self.__children.values()

    def _add_child(self, docid, node):
        self.__children[docid] = node

    def _found(self, title):
        if title:  # ignore None and empty strings
            self.__title = title
        self.__is_document = True

    def _remove_child(self, docid):
        del self.__children[docid]

    def _lost(self, title):
        self.__title = title
        self.__is_document = False

    def _to_dict(self):
        return {
            "title": self.__title,
            "is_document": self.__is_document,
            "children": {
                docid: child._to_dict() for docid, child in self.__children.items()
            },
        }

    @classmethod
    def _from_dict(cls, d, default_title="Home"):
        node = cls(d["title"], d["is_document"])
        node.__children = {
            docid: Node._from_dict(child) for docid, child in d["children"].items()
        }
        return node

    def get_child(self, docid):
        return self.__children.get(docid)


class DocumentTree:
    def __init__(self):
        self.__root = Node("Home", False)

    @property
    def root(self):
        return self.__root

    def to_dict(self):
        return self.root._to_dict()

    @classmethod
    def from_dict(cls, d):
        doctree = cls()

        try:
            doctree.__root = Node._from_dict(d)
            return doctree
        except Exception as e:
            log.warn(f"Failed to load the document tree: {e}")

        return doctree

    def add_document(self, path, title):
        if path.stem == "index":
            if len(path.parent.parts) == 0:  # root document
                if self.root.is_document:
                    log.warn(f"File {path} overwritten")
                else:
                    self.root._found(title)
                return
            else:
                *parent, stem = path.parent.parts
        else:
            parent = path.parent.parts
            stem = path.stem

        parent_node = self.__ensure_path_exists(self.root, parent)

        already_exists = parent_node.get_child(stem)

        if already_exists is None:
            new_node = Node(title, True)
            parent_node._add_child(stem, new_node)

        else:
            if already_exists.is_document:
                log.warn(f"File {path} overwritten")
            else:
                already_exists._found(title)

    def edit_document(self, path, title):
        if path.stem == "index":
            if len(path.parent.parts) == 0:  # root document
                self.root._found(title)
                return
            else:
                parts = path.parent.parts
        else:
            parts = path.parent.parts + (path.stem,)

        node = self.__get_node(self.root, parts)

        if node is None:
            self.add_document(path, title)

        else:
            node._found(title)

    def remove_document(self, path):
        if path.stem == "index":
            if len(path.parent.parts) == 0:  # root document
                self.root._lost("Home")
                return
            else:
                *parent, stem = path.parent.parts
        else:
            parent = path.parent.parts
            stem = path.stem

        parent_node = self.__get_node(self.root, parent)

        if parent_node is None:
            return

        target_node = self.parent_node.get_child(stem)

        if target_node is None:
            return

        if len(target_node.children) == 0:
            parent_node._remove_child(stem)
        else:
            target_node._lost(stem.title())

    def __get_node(self, base, path):
        if len(path) == 0:
            return base

        child = base.get_child(path[0])

        if child is None:
            return None

        return self.__get_node(child, path[1:])

    def __ensure_path_exists(self, base, path):
        if len(path) == 0:
            return base

        child = base.get_child(path[0])

        if child is None:
            child = Node(path[0].title(), False)
            base._add_child(path[0], child)

        return self.__ensure_path_exists(child, path[1:])
