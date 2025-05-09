"""A static site generator"""


def __version__():
    from importlib.metadata import version
    from packaging.version import Version

    return Version(version("komoe"))


__version__ = __version__()
