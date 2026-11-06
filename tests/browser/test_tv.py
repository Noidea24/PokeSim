"""The TV view lays out running adventures from /api/v1/stats without overflowing."""
import json
import time
from pathlib import Path

import pytest

from pokesim.app.manager import Manager, create_app
from pokesim.dashboard import card
from conftest import serve

FRAME = Path(__file__).parents[2] / 'pokesim' / 'web' / 'static' / 'favicon.svg'
GAMES = ['red', 'blue', 'yellow', 'gold', 'silver', 'crystal']


def png(shade):
    import io
    from PIL import Image
    out = io.BytesIO()
    Image.new('RGB', (160, 144), (shade, 120, 60)).save(out, 'PNG')
    return out.getvalue()


def feed(ids):
    return b''.join(f'{aid} {len(data)}\n'.encode() + data for aid, data in ((aid, png(30 * i)) for i, aid in enumerate(ids)))


def add(manager, aid, version, badges, state='running', paused=False):
    game = {'player_name': 'ASH', 'badges': list(range(badges)), 'owned': 10 * badges, 'seen': 20,
            'hall_of_fame_count': 0, 'money': 1, 'playtime': '1:00:00', 'playtime_seconds': 3600,
            'map_name': 'Pallet Town', 'party': [{'dex': 25, 'name': 'PIKACHU', 'nick': 'SPARKY', 'level': 5}]}
    summary = {'stats': card(game), 'last_response': time.time(), 'paused': paused}
    with manager.registry.db:
        manager.registry.db.execute(
            'INSERT INTO adventures (id, campaign_id, name, rom_id, version, settings, desired_state, state, '
            'generation, summary, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (aid, aid, aid.title(), 'rom', version, json.dumps({'speed': 4}), state, state, 'g', json.dumps(summary), 0))


@pytest.mark.parametrize('width,height', [(1920, 1080), (800, 480), (390, 844)])
def test_tv_grid_fits_the_screen(page, tmp_path, monkeypatch, width, height):
    from playwright.sync_api import expect
    def factory(url):
        manager = Manager(tmp_path / 'library', url)
        monkeypatch.setattr(manager, 'start', lambda: None)
        add(manager, 'red', 'red', 3)
        add(manager, 'crystal', 'crystal', 11, paused=True)
        add(manager, 'blue', 'blue', 1)
        add(manager, 'gone', 'yellow', 8, state='stopped')
        return create_app(manager)
    with serve(factory) as url:
        page.route('**/frame.jpg*', lambda route: route.fulfill(body=png(90), content_type='image/png'))
        page.route('**/sprites/**', lambda route: route.fulfill(path=str(FRAME), content_type='image/svg+xml'))
        page.set_viewport_size({'width': width, 'height': height})
        page.goto(url + '/tv?stream=0')
        expect(page.locator('.tv-tile')).to_have_count(3)
        expect(page.locator('.tv-screen img.ready')).to_have_count(3)
        expect(page.locator('#tv-totals')).to_contain_text('3 running')
        expect(page.locator('.tv-tile').nth(1).locator('.tv-state')).to_have_text('PAUSED')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.evaluate('''() => [...document.querySelectorAll('.tv-tile')].every(tile => {
            const box = tile.getBoundingClientRect()
            return box.right <= innerWidth + 1 && box.bottom <= innerHeight + 1
        })''')
        page.goto(url + '/tv?stream=0&all=1&ids=gone,red')
        expect(page.locator('.tv-tile')).to_have_count(2)
        expect(page.locator('.tv-tile').first.locator('.tv-state')).to_have_text('STOPPED')


def test_six_live_games_share_one_connection_and_sprites_still_load(page, tmp_path, monkeypatch):
    from playwright.sync_api import expect
    def factory(url):
        manager = Manager(tmp_path / 'library', url)
        monkeypatch.setattr(manager, 'start', lambda: None)
        for aid in GAMES:
            add(manager, aid, aid, 1)
        return create_app(manager)
    requests = []
    with serve(factory) as url:
        def fulfil_feed(route):
            requests.append(route.request.url)
            route.fulfill(body=feed(GAMES), content_type='application/x-pokesim-frames')
        page.route('**/api/v1/tv/stream*', fulfil_feed)
        page.route('**/sprites/**', lambda route: route.fulfill(path=str(FRAME), content_type='image/svg+xml'))
        page.route('**/stream', lambda route: route.abort())      # no per-tile streams any more
        page.route('**/frame.jpg*', lambda route: route.abort())
        page.set_viewport_size({'width': 1280, 'height': 900})
        page.goto(url + '/tv?fps=30')
        expect(page.locator('.tv-tile')).to_have_count(6)
        expect(page.locator('.tv-screen img.ready')).to_have_count(6)
        page.wait_for_function("[...document.querySelectorAll('.tv-party img')].length === 6 && "
                               "[...document.querySelectorAll('.tv-party img')].every(i => i.complete && i.naturalWidth > 0)")
        from urllib.parse import parse_qs, urlsplit
        query = parse_qs(urlsplit(requests[0]).query)
        assert len(requests) == 1 and set(query['ids'][0].split(',')) == set(GAMES) and query['fps'] == ['30']
        drawn = page.evaluate("""() => [...document.querySelectorAll('.tv-screen img')].map(img => {
            const c = document.createElement('canvas'); c.width = 160; c.height = 144
            const ctx = c.getContext('2d'); ctx.drawImage(img, 0, 0)
            return [...ctx.getImageData(80, 72, 1, 1).data].slice(0, 3).join(',')
        })""")
        order = page.evaluate("[...document.querySelectorAll('.tv-tile')].map(t => new URL(t.href).pathname.split('/')[2])")
        assert {aid: drawn[i] for i, aid in enumerate(order)} == {aid: f'{30 * i},120,60' for i, aid in enumerate(GAMES)}


def test_without_fps_the_feed_leaves_the_rate_to_the_server(page, tmp_path, monkeypatch):
    """No ?fps= must not ask the server for a rate at all (it once asked for 1)."""
    def factory(url):
        manager = Manager(tmp_path / 'library', url)
        monkeypatch.setattr(manager, 'start', lambda: None)
        add(manager, 'red', 'red', 1)
        return create_app(manager)
    requests = []
    with serve(factory) as url:
        page.route('**/api/v1/tv/stream*', lambda route: (requests.append(route.request.url),
                   route.fulfill(body=feed(['red']), content_type='application/x-pokesim-frames')))
        page.route('**/sprites/**', lambda route: route.fulfill(path=str(FRAME), content_type='image/svg+xml'))
        from playwright.sync_api import expect
        page.goto(url + '/tv')
        expect(page.locator('.tv-screen img.ready')).to_have_count(1)
        assert requests and 'fps=' not in requests[0]
