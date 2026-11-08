"""Noidea24 fork, revised agent: team preparation checked against generated Gold, Silver and Crystal data."""
import os
from types import SimpleNamespace

import pytest

from pokesim.gen2 import losses, team_prep
from pokesim.gen2.data import GameData


@pytest.fixture(scope='module', params=['gold', 'silver', 'crystal'])
def data(request):
    directory = os.environ.get('GEN2_DATA_DIR')
    if not directory:
        pytest.skip('Set GEN2_DATA_DIR to generated local game data')
    return GameData.load(directory, request.param)


def test_rosters_name_the_leaders_pokemon(data):
    names = {boss: [data.species[species]['name'] for species, _ in roster] for boss, roster in team_prep.ROSTERS.items()}
    assert names['plain'] == ['Clefairy', 'Miltank']
    assert names['clair'][-1] == 'Kingdra'
    assert names['league'][-6:] == ['Gyarados', 'Dragonite', 'Dragonite', 'Aerodactyl', 'Charizard', 'Dragonite']
    assert all(data.species[species]['types'] for roster in team_prep.ROSTERS.values() for species, _ in roster)


def test_every_training_route_exists_and_has_grass(data):
    for route in set(team_prep.ROUTES.values()) | set(losses.ROUTES.values()):
        mid = data.map_ids[route]
        assert any(row['map'] == mid and row['method'] == 'grass' for row in data.encounters), route


def mon(data, species, level, moves, dvs):
    ids = {move['name']: mid for mid, move in data.moves.items()}
    return SimpleNamespace(species=species, level=level, moves=[ids[name] for name in moves], experience=level ** 3,
                           trainer_id=4321, dvs=dvs, egg=False)


def test_an_ice_type_joins_the_team_for_the_league_and_the_hm_carrier_does_not(data):
    typhlosion = mon(data, 157, 55, ['Flamethrower', 'Strength'], (9, 9, 9, 9))
    gyarados = mon(data, 130, 45, ['Waterfall', 'Bite', 'Surf'], (8, 8, 8, 8))
    lapras = mon(data, 131, 20, ['Ice Beam', 'Surf'], (7, 7, 7, 7))
    pidgey = mon(data, 16, 7, ['Fly'], (6, 6, 6, 6))
    team = team_prep.choose(data, [typhlosion, gyarados, lapras, pidgey], team_prep.ROSTERS['league'], 'league')
    assert team[0] is typhlosion and lapras in team and pidgey not in team
