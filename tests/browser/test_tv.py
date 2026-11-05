"""The TV view lays out running adventures from /api/v1/stats without overflowing."""
import json
import time
from pathlib import Path

import pytest

from pokesim.app.manager import Manager, create_app
from pokesim.dashboard import card
from conftest import serve

FRAME = Path(__file__).parents[2] / 'pokesim' / 'web' / 'static' / 'favicon.svg'


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
        page.route('**/frame.jpg*', lambda route: route.fulfill(path=str(FRAME), content_type='image/svg+xml'))
        page.route('**/sprites/**', lambda route: route.fulfill(path=str(FRAME), content_type='image/svg+xml'))
        page.set_viewport_size({'width': width, 'height': height})
        page.goto(url + '/tv?stream=0')
        expect(page.locator('.tv-tile')).to_have_count(3)
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
