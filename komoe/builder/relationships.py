from jinja2td import Template


class Relationships:
    __rel: dict[str, list[str]]

    def __init__(self):
        self.__rel = {}

    @classmethod
    def from_dict(cls, data):
        rel = cls()
        rel.__rel = data
        return rel

    def to_dict(self):
        return self.__rel

    def update(self, source: str, base_template: str, other_templates: list[Template]):
        all_templates = [base_template] + [t.name for t in other_templates]

        for old_template, dependents in self.__rel.items():
            if old_template in all_templates:
                all_templates.remove(old_template)
                if source not in dependents:
                    dependents.append(source)
            else:
                if source in dependents:
                    dependents.remove(source)

        for new_template in all_templates:
            self.__rel[new_template] = [source]

    def remove(self, source: str):
        for template, dependents in self.__rel.items():
            if source in dependents:
                dependents.remove(source)

    def get_documents(self, template):
        return self.__rel.get(template, [])
