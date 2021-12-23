from src.lib.music import *


logger = logging.getLogger(__name__)


queue = tj.Component(checks=(guild_c,), hooks=music_h)


# Play


@queue.with_slash_command
@tj.with_str_slash_option("song", "What song? (Could be a title or a youtube link)")
@tj.as_slash_command("play", "Plays a song, or add it to the queue")
async def play_s(
    ctx: tj.abc.SlashContext,
    song: str,
    lvc: lv.Lavalink = tj.injected(type=lv.Lavalink),
) -> None:
    await play_(ctx, song, lvc=lvc)


@queue.with_message_command
@tj.with_greedy_argument("song")  # Set song to be greedy
@tj.with_parser  # Add an argument parser to the command
@tj.as_message_command("play", "p")
async def play_m(
    ctx: tj.abc.MessageContext,
    song: str,
    lvc: lv.Lavalink = tj.injected(type=lv.Lavalink),
) -> None:
    """Play a song, or add it to the queue."""
    await play_(ctx, song, lvc=lvc)


@check(Checks.CATCH_ALL)
async def play_(ctx: tj.abc.Context, song: str, lvc: lv.Lavalink) -> None:
    """Attempts to play the song from youtube."""
    assert ctx.guild_id is not None

    # Check if we are connected to voice
    conn = await lvc.get_guild_gateway_connection_info(ctx.guild_id)

    if not conn:
        # Join the users voice channel if we are not already connected
        try:
            await join__(ctx, None, lvc)
        except NotInVoice:
            return await err_reply(
                ctx,
                content=f"❌ Please join a voice channel first. You can also do `/join channel:` `[🔊 ...]`",
            )

    await check_auth_in_vc(ctx, lvc)

    query = await lvc.auto_search_tracks(song)
    if not (tracks := query.tracks):
        # We didnt find any tracks
        return await err_reply(
            ctx, content=f"❓ No tracks found. Please try changing your wording"
        )

    try:
        # Play the first track in tracks
        # Set the requester, and queue the song
        async with access_queue(ctx, lvc) as q:
            if query.load_type == "PLAYLIST_LOADED":
                players = tuple(
                    lvc.play(ctx.guild_id, t).requester(ctx.author.id).replace(False)
                    for t in tracks
                )
                q.ext(*map(lambda p: p.to_track_queue(), players))
                await def_reply(
                    ctx,
                    content=f"**`≡+`** Added `{len(tracks)} songs` from playlist `{query.playlist_info.name}` to the queue",
                )
                player = players[0]
            else:
                track = tracks[0]
                player = (
                    lvc.play(ctx.guild_id, track)
                    .requester(ctx.author.id)
                    .replace(False)
                )
                q.ext(player.to_track_queue())
                await def_reply(
                    ctx, content=f"**`＋`** Added `{track.info.title}` to the queue"
                )
            if not q.is_stopped:
                await player.start()
    except lv.NoSessionPresent:
        # Occurs if lavalink crashes
        return await err_reply(
            ctx,
            content="⁉️ Something internal went wrong. Please try again in few minutes",
        )


## Remove


remove_g_s = queue.with_slash_command(
    tj.slash_command_group("remove", "Removes tracks from the queue")
)


@queue.with_message_command
@tj.as_message_command_group("remove", "rem", "rm", "rmv", "del", "d", strict=True)
async def remove_g_m(ctx: tj.abc.MessageContext):
    cmd = ctx.command
    assert isinstance(cmd, tj.abc.MessageCommandGroup)
    p = next(iter(ctx.client.prefixes))
    cmd_n = next(iter(cmd.names))
    sub_cmds_n = map(lambda s: next(iter(s.names)), cmd.commands)
    valid_cmds = ", ".join(f"`{p}{cmd_n} {sub_cmd_n} ...`" for sub_cmd_n in sub_cmds_n)
    await err_reply(
        ctx,
        content=f"❌ This is a command group. Use the following instead:\n{valid_cmds}",
    )


# Remove One


@remove_g_s.with_command
@tj.with_str_slash_option("track", "The track by the name/position what?")
@tj.as_slash_command(
    "one", "Removes a track from the queue by queue position or track name"
)
async def remove_one_s(
    ctx: tj.abc.SlashContext,
    track: str,
    lvc: lv.Lavalink = tj.injected(type=lv.Lavalink),
) -> None:
    await remove_one_(ctx, track, lvc=lvc)


@remove_g_m.with_command
@tj.with_greedy_argument("track")
@tj.with_parser
@tj.as_message_command("one", "1", "o", "s")
async def remove_one_m(
    ctx: tj.abc.MessageContext,
    track: str,
    lvc: lv.Lavalink = tj.injected(type=lv.Lavalink),
) -> None:
    await remove_one_(ctx, track, lvc=lvc)


@check(Checks.QUEUE | Checks.CONN)
async def remove_one_(ctx: tj.abc.Context, track: str, lvc: lv.Lavalink):
    assert ctx.guild_id is not None
    async with access_queue(ctx, lvc) as q:

        np = q.now_playing
        if track.isdigit():
            t = int(track)
            if not (1 <= t <= len(q)):
                return await err_reply(
                    ctx,
                    content=f"❌ Invalid position. **The position must be between `1` and `{len(q)}`**",
                )
            i = t - 1
            rm = q[i]
        else:
            rm = max(
                *q,
                key=lambda t: SequenceMatcher(None, t.track.info.title, track).ratio(),
            )
            i = q.index(rm)

    try:
        await check_others_not_in_vc(ctx, lvc)
    except OthersInVoice:
        if rm.requester != ctx.author.id:
            raise PlaybackChangeRefused

    if rm == np:
        await stop__(ctx, lvc)
        await asyncio.sleep(0.15)
        await skip__(ctx, lvc, advance=False)
        # q.is_stopped = False

    async with access_queue(ctx, lvc) as q:
        if i < q.pos:
            q.pos = max(0, q.pos - 1)
        q.sub(rm)

        q.is_stopped = False

        logger.info(f"Removed track '{rm.track.info.title}' in guild {ctx.guild_id}")
        return await reply(
            ctx, content=f"**`ー`** Removed `{rm.track.info.title}` from the queue"
        )


# Remove Bulk


@remove_g_s.with_command
@tj.with_int_slash_option(
    "end",
    "To the track with what position? (If not given, the end of the queue)",
    default=None,
)
@tj.with_int_slash_option("start", "From the track with what position?")
@tj.as_slash_command(
    "bulk", "Removes a track from the queue by queue position or track name"
)
async def remove_bulk_s(
    ctx: tj.abc.SlashContext,
    end: t.Optional[int],
    start: int,
    lvc: lv.Lavalink = tj.injected(type=lv.Lavalink),
) -> None:
    await remove_bulk_(ctx, start, end, lvc=lvc)


@remove_g_m.with_command
@tj.with_argument("end", converters=int, default=None)
@tj.with_argument("start", converters=int)
@tj.with_parser
@tj.as_message_command("bulk", "b", "m", "r")
async def remove_bulk_m(
    ctx: tj.abc.MessageContext,
    end: t.Optional[int],
    start: int,
    lvc: lv.Lavalink = tj.injected(type=lv.Lavalink),
) -> None:
    await remove_bulk_(ctx, end, start, lvc=lvc)


@check(Checks.QUEUE | Checks.CONN | Checks.IN_VC_ALONE)
async def remove_bulk_(
    ctx: tj.abc.Context, start: int, end: t.Optional[int], lvc: lv.Lavalink
):
    assert ctx.guild_id is not None
    async with access_queue(ctx, lvc) as q:
        end = end or len(q)

        if not (1 <= start <= end <= len(q)):
            return await err_reply(
                ctx,
                content=f"❌ Invalid start time or end time\n**Start time must be smaller or equal to end time *AND* both of them has to be in between 1 and the queue length **",
            )

        i_s = start - 1
        i_e = end - 1
        t_n = end - i_s
        rm = q[i_s:end]
        if q.now_playing in rm:
            async with while_stop(ctx, lvc, q):
                pass
            if next_t := None if len(q) <= end else q[end]:
                await lvc.play(ctx.guild_id, next_t.track).start()
        if i_s < q.pos:
            q.pos = i_s + (q.pos - i_e - 1)
        q.sub(*rm)

        logger.info(
            f"""Removed tracks {', '.join(("'%s'" %  t.track.info.title) for t in rm)} in guild {ctx.guild_id}"""
        )
        return await reply(
            ctx,
            content=f"`≡⁻` Removed track position `{start}-{end}` `({t_n} tracks)` from the queue",
        )


# Clear


@queue.with_command
@tj.as_slash_command("clear", "Clears the queue; Equivalent to /remove bulk start:1")
async def clear_s(
    ctx: tj.abc.SlashContext, lvc: lv.Lavalink = tj.injected(type=lv.Lavalink)
):
    await clear_(ctx, lvc=lvc)


@queue.with_command
@tj.as_message_command("clear", "d", "destroy", "clr", "c")
async def clear_m(
    ctx: tj.abc.MessageContext, lvc: lv.Lavalink = tj.injected(type=lv.Lavalink)
):
    await clear_(ctx, lvc=lvc)


@check(Checks.QUEUE | Checks.CONN | Checks.IN_VC_ALONE)
async def clear_(ctx: tj.abc.Context, lvc: lv.Lavalink):
    async with access_queue(ctx, lvc) as q:
        l = len(q)
        async with while_stop(ctx, lvc, q):
            q.clr()
        return await reply(ctx, content=f"💥 Cleared the queue `({l} tracks)`")


# Shuffle


@queue.with_command
@tj.as_slash_command('shuffle', "Shuffles the upcoming tracks")
async def shuffle_s(
    ctx: tj.abc.SlashContext, lvc: lv.Lavalink = tj.injected(type=lv.Lavalink)
):
    await shuffle_(ctx, lvc=lvc)


@queue.with_command
@tj.as_message_command('shuffle', 'sh', 'shuf', 'rand', 'r')
async def shuffle_m(
    ctx: tj.abc.MessageContext, lvc: lv.Lavalink = tj.injected(type=lv.Lavalink)
):
    await shuffle_(ctx, lvc=lvc)


@check(Checks.QUEUE | Checks.CONN | Checks.IN_VC_ALONE)
async def shuffle_(ctx: tj.abc.Context, lvc: lv.Lavalink):
    async with access_queue(ctx, lvc) as q:
        if not q.upcoming:
            return await err_reply(ctx, content=f"❗ This is the end of the queue")
        q.shuffle()

        await reply(
            ctx,
            content=f"🔀 Shuffled the upcoming tracks. `(Track #{q.pos+2}-{len(q)}; {len(q) - q.pos - 1} tracks)`",
        )


# -


@tj.as_loader
def load_component(client: tj.abc.Client) -> None:
    client.add_component(queue.copy())
