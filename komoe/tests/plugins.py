import sys
import unittest.mock
from pathlib import Path
from unittest import TestCase

from komoe.config import PluginConfig, ConfigValue, KomoeConfig
from komoe.paths import ProjectPaths
from test_plugins.plugin_class import mock_class
from test_plugins.plugin_functions import mock_module

from komoe.plugin import Plugins, PluginContext


class PluginsTest(TestCase):
    def test_load_plugins(self):
        config_dict = {
            "komoe_require": "==0.5",
            "project": {"title": "Tests"},
            "plugins": {
                "test_module": {"custom_setting": 6},
                "test_class": {"custom_setting": 6},
                "test_script": {"script": "test_script_plugin.py", "custom_setting": 6},
            },
        }
        config = KomoeConfig(ConfigValue("test$", config_dict))

        plugins = Plugins()
        events = plugins.set_context(
            {
                "markdown": None,
                "paths": ProjectPaths(Path.cwd(), config),
            }
        )
        plugins.load_plugins(config.plugins, False)

        mocks = [
            mock_module,
            mock_class,
            sys.modules["test_script_komoe_plugin"].mock_script,
        ]

        for mock in mocks:
            mock.setup.assert_not_called()

        events["setup"].notify()

        for mock in mocks:
            self.assertEqual(1, mock.setup.call_count)
            self.assertIsInstance(mock.setup.call_args[0][0], PluginContext)
            self.assertEqual({"custom_setting": 6}, mock.setup.call_args[0][1])
