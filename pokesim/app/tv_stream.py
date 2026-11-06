"""One live feed carrying every TV view game, so the browser keeps connections free.

Browsers open about six connections to one server. Six games streamed one per tile use all of
them, and party sprites and stats then never load. Here the Library reads each game's own
``/stream`` on the server side and sends the newest frame of each down a single response.

Each frame on the wire is a header line, ``<adventure id> <byte length>\\n``, followed by that
many bytes of PNG. A game that stops, or fails to connect, simply sends no more frames.
"""
import asyncio
import logging
import re

import httpx

log = logging.getLogger(__name__)
LENGTH = re.compile(rb'content-length:\s*(\d+)', re.I)
MAX_FRAME = 1 << 20


async def child_frames(client, child, aid, latest, changed, viewer_header):
    """Keep ``latest[aid]`` set to the newest frame from one game's multipart stream."""
    url = httpx.URL(child.url).copy_with(path='/stream')
    headers = {'Authorization': 'Bearer ' + child.token, viewer_header: '1'}
    try:
        async with client.stream('GET', url, headers=headers, timeout=httpx.Timeout(10, read=None)) as response:
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


async def combined(client, children, fps, viewer_header, closing):
    """Yield framed PNGs for every game in ``children`` ({aid: child}) at up to ``fps``."""
    latest, sent, changed = {}, {}, asyncio.Event()
    tasks = [asyncio.create_task(child_frames(client, child, aid, latest, changed, viewer_header))
             for aid, child in children.items()]
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
                    await asyncio.wait_for(changed.wait(), timeout=5)
                except asyncio.TimeoutError:
                    yield b''       # a keep-alive so a dropped viewer is noticed
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
