from abc import ABC, abstractmethod
from collections.abc import Mapping, Callable
from os import PathLike
from types import NotImplementedType
from typing import TypeVar, Any, Generic, Optional, Type

import click
import tomli
from packaging.specifiers import SpecifierSet, InvalidSpecifier

from .log import Log

X = TypeVar("X")


class ConfigValue:
    def __init__(self, key: str, value: Any):
        self.__key = key
        self.__value = value

    def unwrap(self, expected_type: type[X]) -> X:
        if isinstance(self.__value, expected_type):
            return self.__value
        else:
            Log.error(
                f"expected {self.__key} to be of type <{expected_type}>, got <{type(self.__value)}> instead"
            )
            raise click.ClickException("invalid configuration file")

    def unwrap_as(self, converter: Callable[[str, Any], X | NotImplementedType]) -> X:
        converted_value = converter(self.__key, self.__value)
        if converted_value is NotImplemented:
            return self.__value
        else:
            raise click.ClickException("invalid configuration file")

    def get(self, item: str, default: object = None) -> "ConfigValue":
        item_value = None
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
        return nested_property


def specifier_set(key: str, value: Any) -> SpecifierSet:
    spec = None
    if isinstance(value, str):
        try:
            spec = SpecifierSet(value)
        except InvalidSpecifier:
            pass

    if spec is None:
        Log.error(f"{key} must be a valid type specifier")
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

        plugins = cfg.get("plugins", {}).unwrap(dict)
        self.__plugins = {
            str(key): PluginConfig(config) for key, config in plugins.items()
        }

    @classmethod
    def from_file(cls, path: PathLike) -> "KomoeConfig":
        try:
            with open(path, "rb") as f:
                toml_dict = tomli.load(f)
        except tomli.TOMLDecodeError as e:
            Log.error(f"error reading configuration file: {e}")
            raise click.ClickException("invalid configuration file")

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
    def __init__(self, cfg: ConfigValue):
        self.__title = cfg.require("title").unwrap(str)

    @property
    def title(self) -> str:
        return self.__title


class PluginConfig:
    def __init__(self, cfg: ConfigValue):
        ...
