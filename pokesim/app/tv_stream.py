"""One live feed carrying every TV view game, so the browser keeps connections free.

Browsers open about six connections to one server. Six games streamed one per tile use all of
them, and party sprites and stats then never load. Here the Library reads each game's own
``/stream`` on the server side and sends the newest frame of each down a single response.

Each frame on the wire is a header line, ``<adventure id> <byte length>\\n``, followed by that
many bytes of PNG. When a game's stream ends, as it does while two games trade or a game
restarts, the feed looks the game up again and reconnects, so the tile carries on by itself.
"""
import asyncio
import logging
import re

import httpx

log = logging.getLogger(__name__)
LENGTH = re.compile(rb'content-length:\s*(\d+)', re.I)
MAX_FRAME = 1 << 20


async def child_frames(client, child, aid, latest, changed, viewer_header, quiet=10):
    """Copy one game's multipart stream into ``latest[aid]`` until it ends or goes quiet."""
    url = httpx.URL(child.url).copy_with(path='/stream')
    headers = {'Authorization': 'Bearer ' + child.token, viewer_header: '1'}
    try:
        async with client.stream('GET', url, headers=headers, timeout=httpx.Timeout(10, read=quiet)) as response:
            if response.status_code != 200:
                return
            buffer = b''
            async for chunk in response.aiter_raw():
                buffer += chunk
                while True:
                    head_end = buffer.find(b'\r\n\r\n')
                    if head_end < 0:
                        break
                    match = LENGTH.search(buffer[:head_end])
                    if not match:      # a stray boundary or blank line: drop up to the header end
                        buffer = buffer[head_end + 4:]
                        continue
                    size = int(match.group(1))
                    if size > MAX_FRAME:
                        return
                    start = head_end + 4
                    if len(buffer) < start + size:
                        break
                    latest[aid] = buffer[start:start + size]
                    changed.set()
                    buffer = buffer[start + size:]
                if len(buffer) > 2 * MAX_FRAME:
                    return
    except (httpx.HTTPError, OSError):
        log.debug('TV feed for %s ended', aid, exc_info=True)


async def follow(client, lookup, aid, latest, changed, viewer_header, closing, retry):
    """Keep one game's frames coming, reconnecting after trades and restarts.

    ``lookup(aid)`` returns the game's current worker, or raises while it is stopped or busy.
    With ``retry`` set to None it connects once, which the tests use.
    """
    while not closing():
        try:
            child = lookup(aid)
        except (RuntimeError, KeyError, ValueError):
            child = None
        if child is not None:
            await child_frames(client, child, aid, latest, changed, viewer_header)
        if retry is None:
            return
        await asyncio.sleep(retry)


async def combined(client, ids, lookup, fps, viewer_header, closing, retry=1.0):
    """Yield framed PNGs for every game in ``ids`` at up to ``fps``."""
    latest, sent, changed = {}, {}, asyncio.Event()
    tasks = [asyncio.create_task(follow(client, lookup, aid, latest, changed, viewer_header, closing, retry))
             for aid in ids]
    delay = 1 / fps
    try:
        while not closing():
            finished = all(task.done() for task in tasks)
            changed.clear()
            parts = []
            for aid, frame in list(latest.items()):
                if sent.get(aid) is not frame:
                    sent[aid] = frame
                    parts.append(f'{aid} {len(frame)}\n'.encode() + frame)
            if parts:
                yield b''.join(parts)
            if finished:
                break
            await asyncio.sleep(delay)
            if not changed.is_set():
                try:
                    await asyncio.wait_for(changed.wait(), timeout=2)
                except asyncio.TimeoutError:
                    yield b''       # a keep-alive so a dropped viewer is noticed
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
