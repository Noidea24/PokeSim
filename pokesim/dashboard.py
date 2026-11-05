"""Read-only adventure numbers for home dashboards such as Homepage or Home Assistant.

Each game worker already reports its live status to the library every few seconds. ``card``
keeps the few numbers a dashboard tile needs from that status, the supervisor saves them with
the adventure, and ``library_stats`` turns the saved cards into one small JSON document. A
stopped adventure keeps the numbers from its last report.
"""
import time

GEN2_VERSIONS = frozenset({'gold', 'silver', 'crystal'})
PARTY_LIMIT = 6


def card(game):
    """The dashboard numbers from one live game status, or None before the game has a save."""
    if not isinstance(game, dict):
        return None
    badges = game.get('badges')
    party = game.get('party') if isinstance(game.get('party'), list) else []
    return {
        'player': game.get('player_name') or None,
        'badges': len(badges) if isinstance(badges, (list, tuple)) else badges,
        'owned': game.get('owned'), 'seen': game.get('seen'),
        'hall_of_fame': game.get('hall_of_fame_count'), 'money': game.get('money'),
        'playtime': game.get('playtime'), 'playtime_seconds': game.get('playtime_seconds'),
        'location': game.get('map_name'),
        'party': [{'species': mon.get('name'), 'nick': mon.get('nick'), 'level': mon.get('level'),
                   'dex': mon.get('dex'), 'shiny': bool(mon.get('shiny'))}
                  for mon in party[:PARTY_LIMIT] if isinstance(mon, dict)],
    }


def _state(row):
    summary = row.get('summary') or {}
    if row.get('state') != 'running':
        return row.get('state') or 'stopped'
    if summary.get('trading'):
        return 'trading'
    if summary.get('manual_mode'):
        return 'manual'
    if summary.get('paused'):
        return 'paused'
    return 'running'


def adventure_stats(row, public_url=''):
    summary = row.get('summary') or {}
    numbers = summary.get('stats') or {}
    version = row.get('version') or ''
    gen2 = version in GEN2_VERSIONS
    return {
        'id': row['id'], 'name': row.get('name'), 'game': version, 'generation': 2 if gen2 else 1,
        'state': _state(row), 'speed': (row.get('settings') or {}).get('speed', 1),
        'badge_total': 16 if gen2 else 8, 'dex_total': 251 if gen2 else 151,
        'player': None, 'badges': None, 'owned': None, 'seen': None, 'hall_of_fame': None,
        'money': None, 'playtime': None, 'playtime_seconds': None, 'location': None, 'party': [],
        **numbers,
        'reported_at': summary.get('last_response'),
        'url': f"{public_url.rstrip('/')}/games/{row['id']}/",
    }


def library_stats(rows, public_url=''):
    adventures = [adventure_stats(row, public_url) for row in rows if not row.get('archived')]
    total = lambda key: sum(a[key] for a in adventures if isinstance(a[key], (int, float)))
    return {
        'running': sum(a['state'] in {'running', 'paused', 'manual', 'trading'} for a in adventures),
        'adventures': len(adventures),
        'badges': total('badges'), 'owned': total('owned'), 'hall_of_fame': total('hall_of_fame'),
        'playtime_seconds': total('playtime_seconds'),
        'generated_at': time.time(),
        'list': adventures,
    }
