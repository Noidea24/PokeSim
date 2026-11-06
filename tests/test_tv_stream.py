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
    async with httpx.AsyncClient(transport=transport(streams)) as client:
        out = b''
        async for chunk in combined(client, children, 60, 'X-PokeSim-Viewer', lambda: False):
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

    servers = {name: worker(name) for name in ('red', 'gold')}
    manager = Manager(tmp_path, 'http://testserver')
    monkeypatch.setattr(manager, 'start', lambda: None)
    def child(aid):
        if aid not in servers:
            raise RuntimeError('stopped')
        return servers[aid][1]
    monkeypatch.setattr(manager.supervisor, 'child', child)
    try:
        with TestClient(create_app(manager)) as client:
            response = client.get('/api/v1/tv/stream?ids=red,gold,stopped&fps=60')
            assert response.status_code == 200
            assert response.headers['content-type'].startswith('application/x-pokesim-frames')
            assert 'content-encoding' not in response.headers
            frames = parse(response.content)
    finally:
        for server, _ in servers.values():
            server.should_exit = True
    last = {aid: data for aid, data in frames}
    assert last == {'red': b'\x89PNG-red-2', 'gold': b'\x89PNG-gold-2'}
