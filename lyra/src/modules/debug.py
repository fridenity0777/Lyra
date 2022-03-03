import pathlib as pl
import src.lib.consts as c

from src.lib.utils import *


debug = tj.Component(name='debug', strict=True)


modules = {p.stem: p for p in pl.Path('.').glob('./src/modules/*.py')}
choices = tuple(modules)


@tj.with_str_slash_option('module', "The module to target.", choices=choices)
@tj.as_slash_command('reload', "Reloads a module.", default_permission=False)
#
@tj.with_argument('module')
@tj.as_message_command('reload', 'rl')
async def reload_module(
    ctx: tj.abc.Context,
    module: str,
    client: tj.Client = tj.inject(type=tj.Client),
):
    """Reload a module in tanjun"""
    if ctx.author.id not in c.DEVS:
        await err_reply(ctx, content="🚫⚙️ Reserved for bot's developers only")
        return
    mod = modules[module]
    try:
        client.reload_modules(mod)
    except ValueError:
        client.load_modules(mod)

    await reply(ctx, content=f"⚙️♻️ Reloaded `{mod.stem}`")


@tj.with_str_slash_option("module", "The module to target.", choices=choices)
@tj.as_slash_command("unload", "Removes a module.")
#
@tj.with_argument('module')
@tj.as_message_command('unload', 'ul')
async def unload_module(
    ctx: tj.abc.Context,
    module: str,
    client: tj.Client = tj.inject(type=tj.Client),
):
    """Unload a module in tanjun"""
    if ctx.author.id not in c.DEVS:
        await err_reply(ctx, content="🚫⚙️ Reserved for bot's developers only")
        return
    mod = modules[module]
    try:
        client.unload_modules(mod)
    except ValueError:
        await err_reply(ctx, content=f"❗ Couldn't unload `{mod.stem}`")
        return

    await reply(ctx, content=f"⚙️📤 Unloaded `{mod.stem}`")


@tj.with_str_slash_option("module", "The module to reload.", choices=choices)
@tj.as_slash_command("load", "Loads a module.")
#
@tj.with_argument('module')
@tj.as_message_command('load', 'lo')
async def load_module(
    ctx: tj.abc.Context,
    module: str,
    client: tj.Client = tj.inject(type=tj.Client),
):
    """Load a module in tanjun"""
    if ctx.author.id not in c.DEVS:
        await err_reply(ctx, content="🚫⚙️ Reserved for bot's developers only")
        return
    mod = modules[module]
    try:
        client.load_modules(mod)
    except ValueError:
        await err_reply(ctx, content=f"❗ Couldn't load `{mod.stem}`")
        return

    await reply(ctx, content=f"⚙️📥 Loaded `{mod.stem}`")


# @tj.as_message_menu("test")
# @with_message_menu_template
# async def test(
#     ctx: tj.abc.MenuContext,
#     msg: hk.Message,
#     lvc: lv.Lavalink = tj.inject(type=lv.Lavalink),
# ) -> None:
#     print(msg.app)
#     await reply(ctx, content=lvc)


# @tj.as_message_command('test')
# async def test2(
#     ctx: tj.abc.MenuContext,
#     lvc: lv.Lavalink = tj.inject(type=lv.Lavalink),
# ) -> None:
#     await reply(ctx, content=lvc)

# -


loader = debug.load_from_scope().make_loader()
