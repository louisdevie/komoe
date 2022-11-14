class Relationships:
    def __init__(self):
        self.__rel = {}

    @classmethod
    def from_dict(cls, data):
        rel = cls()
        rel.__rel = data
        return rel

    def to_dict(self):
        return self.__rel

    def update(self, source, base_template, other_templates):
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

    def get_documents(self, template):
        return self.__rel.get(template, [])
