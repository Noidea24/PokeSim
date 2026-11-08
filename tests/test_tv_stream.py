"""The TV view's combined feed: each game's multipart stream merged into one framed response."""
import asyncio
from types import SimpleNamespace

import httpx

from pokesim.app.tv_stream import combined


def part(data):
    return f'--pokesimframe\r\nContent-Type: image/png\r\nContent-Length: {len(data)}\r\n\r\n'.encode() + data + b'\r\n'


def transport(streams):
    """A fake set of game workers. ``streams`` maps host to a list of byte chunks."""
    async def handler(request):
        assert request.url.path == '/stream'
        assert request.headers['authorization'] == 'Bearer secret'
        assert request.headers['x-pokesim-viewer'] == '1'
        chunks = streams.get(request.url.host)
        if chunks is None:
            return httpx.Response(409)

        async def body():
            for chunk in chunks:
                yield chunk
                await asyncio.sleep(0)
        return httpx.Response(200, content=body())
    return httpx.MockTransport(handler)


def parse(raw):
    frames = []
    while raw:
        head, raw = raw.split(b'\n', 1)
        aid, size = head.decode().split(' ')
        frames.append((aid, raw[:int(size)]))
        raw = raw[int(size):]
    return frames


async def collect(streams, children):
    def lookup(aid):
        return children[aid]
    async with httpx.AsyncClient(transport=transport(streams)) as client:
        out = b''
        async for chunk in combined(client, list(children), lookup, 60, 'X-PokeSim-Viewer', lambda: False, retry=None):
            out += chunk
        return parse(out)


def child(host):
    return SimpleNamespace(url=f'http://{host}', token='secret')


def test_frames_from_every_game_arrive_whole_even_when_split_across_chunks():
    one = part(b'\x89PNG-one-a') + part(b'\x89PNG-one-b')
    two = part(b'\x89PNG-two-a' * 50)
    streams = {'a.test': [one[:7], one[7:40], one[40:]], 'b.test': [two[i:i + 13] for i in range(0, len(two), 13)]}
    frames = asyncio.run(collect(streams, {'red': child('a.test'), 'gold': child('b.test')}))
    by_game = {}
    for aid, data in frames:
        by_game.setdefault(aid, []).append(data)
    assert by_game['red'][-1] == b'\x89PNG-one-b'
    assert by_game['gold'] == [b'\x89PNG-two-a' * 50]
    assert all(data.startswith(b'\x89PNG') for _, data in frames)


def test_a_game_that_refuses_or_stops_does_not_break_the_others():
    streams = {'a.test': [part(b'\x89PNG-red')]}
    frames = asyncio.run(collect(streams, {'red': child('a.test'), 'gone': child('missing.test')}))
    assert frames == [('red', b'\x89PNG-red')]


def test_a_game_that_trades_reconnects_at_its_new_worker():
    """A trade ends the game's stream. The feed looks the game up again and carries on."""
    streams = {'old.test': [part(b'\x89PNG-before')], 'new.test': [part(b'\x89PNG-after')]}
    workers = iter([child('old.test'), RuntimeError('trading'), child('new.test')])

    def lookup(aid):
        worker = next(workers, None)
        if worker is None or isinstance(worker, Exception):
            raise RuntimeError('busy')
        return worker

    async def run():
        seen = []
        async with httpx.AsyncClient(transport=transport(streams)) as client:
            async for chunk in combined(client, ['red'], lookup, 60, 'X-PokeSim-Viewer',
                                        lambda: b'after' in b''.join(seen), retry=0.01):
                seen.append(chunk)
        return parse(b''.join(seen))
    frames = asyncio.run(asyncio.wait_for(run(), 10))
    assert frames == [('red', b'\x89PNG-before'), ('red', b'\x89PNG-after')]


def test_oversized_frames_end_that_game_only():
    huge = b'--pokesimframe\r\nContent-Length: 999999999\r\n\r\n'
    streams = {'a.test': [huge], 'b.test': [part(b'\x89PNG-ok')]}
    frames = asyncio.run(collect(streams, {'bad': child('a.test'), 'ok': child('b.test')}))
    assert frames == [('ok', b'\x89PNG-ok')]


def test_library_route_merges_live_worker_streams(tmp_path, monkeypatch):
    """The real /api/v1/tv/stream route against real HTTP servers shaped like game workers."""
    import socket
    import threading
    import time
    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse
    from fastapi.testclient import TestClient
    from pokesim.app.manager import Manager, create_app

    def worker(name):
        app = FastAPI()

        @app.get('/stream')
        async def stream():
            async def gen():
                for i in range(3):
                    yield part(b'\x89PNG-' + f'{name}-{i}'.encode())
                    await asyncio.sleep(0.05)
            return StreamingResponse(gen(), media_type='multipart/x-mixed-replace; boundary=pokesimframe')
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
        threading.Thread(target=server.run, daemon=True).start()
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)
        return server, SimpleNamespace(url=f'http://127.0.0.1:{port}', token='secret')

    import json
    servers = {name: worker(name) for name in ('red', 'gold')}
    manager = Manager(tmp_path, 'http://testserver')
    monkeypatch.setattr(manager, 'start', lambda: None)
    with manager.registry.db:
        for aid in ('red', 'gold', 'stopped'):
            manager.registry.db.execute(
                'INSERT INTO adventures (id, campaign_id, name, rom_id, version, settings, desired_state, state, '
                'generation, summary, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (aid, aid, aid, 'rom', 'red', '{}', 'running', 'running', 'g', json.dumps({}), 0))
    def child(aid):
        if aid not in servers:
            raise RuntimeError('stopped')
        return servers[aid][1]
    monkeypatch.setattr(manager.supervisor, 'child', child)
    try:
        with TestClient(create_app(manager)) as client:
            assert client.get('/api/v1/tv/stream?ids=nothere').status_code == 409
            # Each test game sends three frames, ends its stream and is followed again a second
            # later, so the feed replays them. Slow runners need a few seconds for the first round.
            timer = threading.Timer(4, lambda: setattr(manager, 'closing', True))
            timer.start()
            response = client.get('/api/v1/tv/stream?ids=red,gold,stopped,nothere&fps=60')
            timer.join()
            assert response.status_code == 200
            assert response.headers['content-type'].startswith('application/x-pokesim-frames')
            assert 'content-encoding' not in response.headers
            raw = response.content
            frames = parse(raw)
    finally:
        for server, _ in servers.values():
            server.should_exit = True
    # Every frame reaches the viewer under its own game, and stopped or unknown games send none.
    # Which frame comes last depends on where in a replay the feed closed, so it is not checked.
    seen = {}
    for aid, data in frames:
        seen.setdefault(aid, set()).add(data)
    assert seen == {name: {b'\x89PNG-' + f'{name}-{i}'.encode() for i in range(3)} for name in ('red', 'gold')}


def test_a_quiet_live_stream_ends_without_an_error(tmp_path, monkeypatch, caplog):
    """A paused or trading game sends no frames. The viewer's stream closes, logged as info."""
    AID = 'ab' * 16
    import json
    import logging
    import socket
    import threading
    import time
    import uvicorn
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse
    from fastapi.testclient import TestClient
    from pokesim.app.manager import Manager, create_app

    app = FastAPI()

    @app.get('/stream')
    async def stream():
        async def gen():
            yield part(b'\x89PNG-one')
            await asyncio.sleep(30)
        return StreamingResponse(gen(), media_type='multipart/x-mixed-replace; boundary=pokesimframe')
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=port, log_level='warning'))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    manager = Manager(tmp_path, 'http://testserver')
    monkeypatch.setattr(manager, 'start', lambda: None)
    monkeypatch.setattr(manager.supervisor, 'child', lambda aid: SimpleNamespace(url=f'http://127.0.0.1:{port}', token='t'))
    with manager.registry.db:
        manager.registry.db.execute(
            'INSERT INTO adventures (id, campaign_id, name, rom_id, version, settings, desired_state, state, '
            'generation, summary, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (AID, AID, 'Red', 'rom', 'red', '{}', 'running', 'running', 'g', json.dumps({}), 0))
    try:
        web = create_app(manager)
        with TestClient(web) as client:
            web.state.children = httpx.AsyncClient(timeout=httpx.Timeout(5, read=0.5))
            with caplog.at_level(logging.INFO, logger='pokesim.app.manager'):
                response = client.get(f'/games/{AID}/stream')
            assert response.status_code == 200 and b'\x89PNG-one' in response.content, response.text[:300]
    finally:
        server.should_exit = True
    assert 'went quiet' in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_every_frame_gets_through_when_games_run_at_the_feed_rate():
    """Games publishing at the same rate as the feed, with uneven timing, lose no frames."""
    import random

    def timed(name, count, rate, seed):
        rng = random.Random(seed)

        async def body():
            for i in range(count):
                yield part(f'{name}-{i:03d}'.encode())
                await asyncio.sleep((1 / rate) * rng.uniform(0.7, 1.3))
        return body

    async def handler(request):
        return httpx.Response(200, content=games[request.url.host]())
    names = [f'g{i}' for i in range(6)]
    games = {f'{name}.test': timed(name, 30, 15, i) for i, name in enumerate(names)}

    async def run():
        out = b''
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            async for chunk in combined(client, names, lambda aid: child(f'{aid}.test'), 15,
                                        'X-PokeSim-Viewer', lambda: False, retry=None):
                out += chunk
        return parse(out)
    frames = asyncio.run(asyncio.wait_for(run(), 20))
    for name in names:
        got = [data for aid, data in frames if aid == name]
        assert len(got) >= 29, (name, len(got))      # at most the very last can be cut off
        assert got == sorted(got)


def test_games_follow_stream_fps_unless_they_set_their_own(tmp_path, monkeypatch):
    """STREAM_FPS reached only the Library. A game with no frame rate now uses it, and the
    original's 15 still applies when it is unset."""
    from pokesim import config
    from pokesim.app.manager import Manager
    from pokesim.runtime.settings import SimulationSettings
    manager = Manager(tmp_path, 'http://testserver')
    monkeypatch.setattr(manager.assets, 'rom_path', lambda rom: tmp_path / 'rom.gb')
    plain = {'settings': {'speed': 4}, 'rom_id': 'rom'}
    own = {'settings': {'speed': 4, 'stream_fps': 20}, 'rom_id': 'rom'}
    aid = 'ab' * 16
    monkeypatch.setattr(config, 'STREAM_FPS', 15)
    assert manager.supervisor._settings(aid, plain)['stream_fps'] == 15
    monkeypatch.setattr(config, 'STREAM_FPS', 60)
    assert manager.supervisor._settings(aid, plain)['stream_fps'] == 60
    assert manager.supervisor._settings(aid, own)['stream_fps'] == 20
    assert SimulationSettings.__dataclass_fields__['stream_fps'].default == 15
