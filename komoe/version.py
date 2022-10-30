import click


class Version:
    def __init__(self, major, minor, patch):
        self.__major = major
        self.__minor = minor
        self.__patch = patch

    @classmethod
    def parse(cls, string):
        try:
            nums = [int(num) for num in string.split(".")]
        except ValueError:
            raise click.ClickException("invalid version format")

        if len(nums) == 1:
            return cls(nums[0], 0, 0)

        elif len(nums) == 2:
            return cls(nums[0], nums[1], 0)

        elif len(nums) == 3:
            return cls(nums[0], nums[1], nums[2])

        else:
            raise click.ClickException("invalid version format")

    @property
    def major(self):
        return self.__major

    @property
    def minor(self):
        return self.__minor

    @property
    def patch(self):
        return self.__patch

    def __eq__(self, other):
        if not isinstance(other, Version):
            return NotImplemented

        return (
            self.__major == other.__major
            and self.__minor == other.__minor
            and self.__patch == other.__patch
        )

    def __lt__(self, other):
        if not isinstance(other, Version):
            return NotImplemented

        if self.__major == other.__major:
            if self.__minor == other.__minor:
                return self.__patch < other.__patch
            else:
                return self.__minor < other.__minor
        else:
            return self.__major < other.__major

    def __le__(self, other):
        if not isinstance(other, Version):
            return NotImplemented

        if self.__major == other.__major:
            if self.__minor == other.__minor:
                return self.__patch <= other.__patch
            else:
                return self.__minor < other.__minor
        else:
            return self.__major < other.__major

    def __repr__(self):
        return f"{type(self).__module__}.{type(self).__qualname__}({self.major}, {self.minor}, {self.patch})"

    def __str__(self):
        if self.patch:
            return f"{self.major}.{self.minor}.{self.patch}"
        else:
            if self.minor:
                return f"{self.major}.{self.minor}"
            else:
                return f"{self.major}"
