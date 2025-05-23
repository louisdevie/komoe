from unittest.mock import Mock

import komoe.plugin

mock_module = Mock()


@komoe.plugin.setup
def setup(ctx, cfg):
    mock_module.setup(ctx, cfg)


@komoe.plugin.cleanup
def cleanup(ctx, cfg):
    mock_module.cleanup(ctx, cfg)


@komoe.plugin.compilation_start
def compilation_start(ctx, cfg):
    mock_module.compilation_start(ctx, cfg)


@komoe.plugin.compilation_end
def compilation_end(ctx, cfg):
    mock_module.compilation_end(ctx, cfg)


@komoe.plugin.on("my_custom_event")
def my_custom_event(ctx, cfg):
    mock_module.my_custom_event(ctx, cfg)
