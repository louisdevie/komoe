from unittest.mock import Mock

import komoe.plugin

mock_script = Mock()


@komoe.plugin.setup
def setup(ctx, cfg):
    mock_script.setup(ctx, cfg)


@komoe.plugin.cleanup
def cleanup(ctx, cfg):
    mock_script.cleanup(ctx, cfg)


@komoe.plugin.compilation_start
def compilation_start(ctx, cfg):
    mock_script.compilation_start(ctx, cfg)


@komoe.plugin.compilation_end
def compilation_end(ctx, cfg):
    mock_script.compilation_end(ctx, cfg)


@komoe.plugin.on("my_custom_event")
def my_custom_event(ctx, cfg):
    mock_script.my_custom_event(ctx, cfg)
