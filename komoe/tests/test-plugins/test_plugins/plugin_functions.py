import komoe.plugin


@komoe.plugin.setup
def my_setup(ctx, cfg):
    ...


@komoe.plugin.cleanup
def my_cleanup(ctx, cfg):
    ...


@komoe.plugin.compilation_start
def my_compilation_start(ctx, cfg):
    ...


@komoe.plugin.compilation_end
def my_compilation_end(ctx, cfg):
    ...


@komoe.plugin.on("my_custom_event")
def my_compilation_end(ctx, cfg):
    ...
