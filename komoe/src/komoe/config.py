from collections.abc import Mapping, Callable
from os import PathLike
from types import NotImplementedType
from typing import TypeVar, Any

import click
import tomli
from click import ClickException
from packaging.specifiers import SpecifierSet, InvalidSpecifier

from komoe.logging import Logging
from komoe.utils import pretty_type

log = Logging.get_logger(__name__)


X = TypeVar("X")


class InvalidConfigException(ClickException):
    def __init__(self):
        super().__init__("invalid configuration file")


class ConfigValue:
    MISSING = object()

    def __init__(self, key: str, value: Any):
        self.__key = key
        self.__value = value

    def __raise_if_missing(self):
        if self.__value is ConfigValue.MISSING:
            log.error(f"A value for {self.__key} is required")
            raise InvalidConfigException()

    def unwrap(self, expected_type: type[X]) -> X:
        if isinstance(self.__value, expected_type):
            return self.__value
        else:
            log.error(
                f"expected {self.__key} to be of type {pretty_type(expected_type)}, got {pretty_type(self.__value)} instead"
            )
            raise InvalidConfigException()

    def unwrap_as(self, converter: Callable[[str, Any], X | NotImplementedType]) -> X:
        converted_value = converter(self.__key, self.__value)
        if converted_value is NotImplemented:
            raise InvalidConfigException()
        else:
            return converted_value

    def get(self, item: str, default: object = MISSING) -> "ConfigValue":
        item_value = default
        if hasattr(self.__value, "__getitem__"):
            try:
                item_value = self.__value[item]
            except (KeyError, IndexError, TypeError):
                pass
        return ConfigValue(self.__key + "." + item, item_value)

    def require(self, path: str) -> "ConfigValue":
        nested_property = self
        for item in path.split("."):
            nested_property = nested_property.get(item)
            nested_property.__raise_if_missing()
        return nested_property


def specifier_set(key: str, value: Any) -> SpecifierSet:
    spec = None
    if isinstance(value, str):
        try:
            spec = SpecifierSet(value)
        except InvalidSpecifier:
            pass

    if spec is None:
        log.error(f"{key} must be a valid version specifier")
        return NotImplemented
    else:
        return spec


class KomoeConfig:
    __minimum_required_version: SpecifierSet
    __project: "ProjectConfig"
    __plugins: dict[str, "PluginConfig"]

    def __init__(self, cfg: ConfigValue):
        self.__minimum_required_version = cfg.require("komoe_require").unwrap_as(
            specifier_set
        )

        self.__project = ProjectConfig(cfg.get("project"))

        plugins = cfg.get("plugins", {})
        self.__plugins = {
            str(key): PluginConfig(plugins.get(key)) for key in plugins.unwrap(dict)
        }

    @classmethod
    def from_file(cls, path: PathLike) -> "KomoeConfig":
        log.debug(f"Reading configuration from '{path}'")
        try:
            with open(path, "rb") as f:
                toml_dict = tomli.load(f)
        except tomli.TOMLDecodeError as e:
            log.error(f"error reading configuration file: {e}")
            raise InvalidConfigException()

        return cls(ConfigValue("$", toml_dict))

    @property
    def minimum_required_version(self) -> SpecifierSet:
        return self.__minimum_required_version

    @property
    def project(self) -> "ProjectConfig":
        return self.__project

    @property
    def plugins(self) -> Mapping[str, "PluginConfig"]:
        return self.__plugins


class ProjectConfig:
    __title: str

    def __init__(self, cfg: ConfigValue):
        self.__title = cfg.require("title").unwrap(str)

    @property
    def title(self) -> str:
        return self.__title


class PluginConfig:
    __script: str | None
    __extras: dict[str, Any]

    def __init__(self, cfg: ConfigValue):
        config_dict = cfg.unwrap(dict)
        self.__script = config_dict.pop("script", None)
        self.__extras = config_dict

    @property
    def script(self) -> str | None:
        return self.__script

    @property
    def extras(self) -> Mapping:
        return self.__extras
