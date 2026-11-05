"""Read-only dashboard numbers: the card the worker reports and the library's /api/v1/stats."""
from fastapi.testclient import TestClient
import pytest

from pokesim.app.manager import Manager, create_app
from pokesim.dashboard import card, library_stats
from pokesim.web.app import status_summary


def game(**extra):
    return {'player_name': 'RED', 'badges': ['BOULDER', 'CASCADE'], 'owned': 40, 'seen': 70,
            'hall_of_fame_count': 0, 'money': 3000, 'playtime': '5:01:02', 'playtime_seconds': 18062,
            'map_name': 'Cerulean City', 'items': [{'id': 1}], 'dex_owned': list(range(40)),
            'party': [{'name': 'PIKACHU', 'nick': 'SPARKY', 'level': 22, 'dex': 25, 'hp': 50, 'moves': [84]}] * 7,
            **extra}


def test_card_keeps_only_dashboard_numbers():
    numbers = card(game())
    assert numbers['badges'] == 2 and numbers['owned'] == 40 and numbers['seen'] == 70
    assert numbers['location'] == 'Cerulean City' and numbers['player'] == 'RED'
    assert len(numbers['party']) == 6
    assert numbers['party'][0] == {'species': 'PIKACHU', 'nick': 'SPARKY', 'level': 22, 'dex': 25, 'shiny': False}
    assert 'items' not in numbers and 'dex_owned' not in numbers
    assert card(None) is None


def test_summary_carries_the_card():
    summary = status_summary({'paused': False, 'game': game(), 'strategy': {'x': 1}})
    assert summary['stats']['owned'] == 40
    assert 'strategy' not in summary and set(summary['game']) == {'map_name', 'playtime'}
    assert status_summary({'paused': True, 'game': None})['stats'] is None


def row(aid, version, state='running', stats=None, **summary):
    return {'id': aid, 'name': aid.title(), 'version': version, 'state': state, 'archived': False,
            'settings': {'speed': 4}, 'summary': {'stats': stats, 'last_response': 1.0, **summary}}


def test_library_totals_and_generation_limits():
    rows = [row('red', 'red', stats=card(game())),
            row('gold', 'gold', state='stopped', stats=card(game(badges=list('ABCDEFGHIJ'), owned=100))),
            row('new', 'blue', stats=None),
            {**row('old', 'red', stats=card(game())), 'archived': True}]
    stats = library_stats(rows, 'http://pokesim.lan')
    assert stats['adventures'] == 3 and stats['running'] == 2
    assert stats['badges'] == 12 and stats['owned'] == 140
    red, gold, new = stats['list']
    assert (red['badge_total'], red['dex_total'], red['generation']) == (8, 151, 1)
    assert (gold['badge_total'], gold['dex_total'], gold['state']) == (16, 251, 'stopped')
    assert new['badges'] is None and new['party'] == []
    assert red['url'] == 'http://pokesim.lan/games/red/' and red['speed'] == 4


@pytest.mark.parametrize('summary,state', [({'paused': True}, 'paused'), ({'manual_mode': True}, 'manual'),
                                           ({'trading': True}, 'trading'), ({}, 'running')])
def test_state_names(summary, state):
    assert library_stats([row('a', 'red', **summary)])['list'][0]['state'] == state


def test_stats_routes_are_read_only_and_host_checked(tmp_path, monkeypatch):
    manager = Manager(tmp_path, 'http://testserver')
    monkeypatch.setattr(manager, 'start', lambda: None)
    with TestClient(create_app(manager)) as client:
        body = client.get('/api/v1/stats').json()
        assert body['adventures'] == 0 and body['list'] == []
        assert client.get('/api/v1/stats/nothere').status_code == 404
        assert client.get('/api/v1/stats', headers={'Host': 'evil.example'}).status_code == 403
        assert client.post('/api/v1/stats').status_code in (403, 405)


def test_tv_page_is_served_with_its_assets(tmp_path, monkeypatch):
    manager = Manager(tmp_path, 'http://testserver')
    monkeypatch.setattr(manager, 'start', lambda: None)
    with TestClient(create_app(manager)) as client:
        page = client.get('/tv')
        assert page.status_code == 200 and '/static/tv.js' in page.text and '${' not in page.text
        assert client.get('/static/tv.js').status_code == 200
        assert client.get('/static/tv.css').status_code == 200
        assert 'href="/tv"' in client.get('/').text
