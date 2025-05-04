from unittest import TestCase

from komoe.plugin import Plugins


class PluginsTest(TestCase):
    def test_load_plugins(self):
        Plugins().load_plugins({}, False)
