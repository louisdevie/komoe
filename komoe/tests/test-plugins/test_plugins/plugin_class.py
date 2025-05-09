from unittest.mock import Mock

from komoe.plugin import KomoePlugin

mock_class = Mock()


class MyPlugin(KomoePlugin):
    def on_setup(self):
        mock_class.setup(self.context, self.config)

    def on_cleanup(self):
        mock_class.cleanup(self.context, self.config)

    def on_compilation_start(self):
        mock_class.compilation_start(self.context, self.config)

    def on_compilation_end(self):
        mock_class.compilation_end(self.context, self.config)

    def on_my_custom_event(self):
        mock_class.my_custom_event(self.context, self.config)
