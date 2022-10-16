import click
import tomli

from . import log
from .version import Version


def _require(cfg, *path):
    for key in path:
        if key in cfg:
            cfg = cfg[key]
        else:
            log.error(f"{'.'.join(path)} is missing from configuration file")
            raise click.ClickException("invalid configuration file")
    return cfg


def _default(cfg, default, *path):
    for key in path:
        if key in cfg:
            cfg = cfg[key]
        else:
            return default
    return cfg


class ProjectConfig:
    def __init__(self, cfg):
        self.__minimum_required_version = Version.parse(_require(cfg, "komoe_require"))

        self.__source_dir = _require(cfg, "build", "source")
        self.__templates_dir = _require(cfg, "build", "templates")
        self.__static_dir = _require(cfg, "build", "static")
        self.__output_dir = _require(cfg, "build", "output")

        self.__project_infos = _default(cfg, {}, "project")
        self.__plugins = _default(cfg, {}, "plugin")

    @classmethod
    def from_file(cls, path):
        try:
            with open(path, "rb") as f:
                toml_dict = tomli.load(f)
        except tomli.TOMLDecodeError as e:
            log.error(f"error reading configuration file: {e}")
            raise click.ClickException("invalid configuration file")

        return cls(toml_dict)

    @property
    def minimum_required_version(self):
        return self.__minimum_required_version

    @property
    def source_directory(self):
        return self.__source_dir

    @property
    def templates_directory(self):
        return self.__templates_dir

    @property
    def static_directory(self):
        return self.__static_dir

    @property
    def output_directory(self):
        return self.__output_dir

    @property
    def project(self):
        return self.__project_infos

    @property
    def plugins(self):
        return self.__plugins
