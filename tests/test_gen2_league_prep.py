"""Noidea24 fork, revised agent: Crystal picks and raises a team before each leader and the League."""
from types import SimpleNamespace

import pytest

from pokesim import config
from pokesim.gen2 import league_prep, team_prep

NORMAL, FLYING, FIRE, WATER, ELECTRIC, ICE, DRAGON = 0, 2, 20, 21, 23, 25, 26
SPECIES = {
    155: {'types': [FIRE], 'stats': [39, 52, 43, 65, 60, 50]},           # fire starter
    130: {'types': [WATER, FLYING], 'stats': [95, 125, 79, 81, 65, 100]},
    25: {'types': [ELECTRIC], 'stats': [35, 55, 30, 90, 50, 40]},
    87: {'types': [WATER, ICE], 'stats': [90, 70, 80, 70, 70, 95]},
    16: {'types': [NORMAL, FLYING], 'stats': [40, 45, 40, 56, 35, 35]},
    149: {'types': [DRAGON, FLYING], 'stats': [91, 134, 95, 80, 100, 100]},
    241: {'types': [NORMAL], 'stats': [95, 80, 105, 100, 40, 70]},
}
MOVES = {
    1: {'power': 90, 'type': FIRE, 'accuracy': 100},
    2: {'power': 95, 'type': WATER, 'accuracy': 100},
    3: {'power': 90, 'type': ELECTRIC, 'accuracy': 100},
    4: {'power': 95, 'type': ICE, 'accuracy': 100},
    5: {'power': 0, 'type': NORMAL, 'accuracy': 100},        # Flash: no damage
    6: {'power': 40, 'type': NORMAL, 'accuracy': 100},
}
MATCHUPS = {(ICE, DRAGON): 2, (ICE, FLYING): 2, (ELECTRIC, WATER): 2, (ELECTRIC, FLYING): 2,
            (FIRE, WATER): 0.5, (WATER, FIRE): 2, (DRAGON, DRAGON): 2, (FIRE, FIRE): 0.5,
            (WATER, WATER): 0.5, (ELECTRIC, DRAGON): 0.5, (ICE, WATER): 0.5, (ICE, ICE): 0.5}
DATA = SimpleNamespace(species=SPECIES, moves=MOVES, matchups=MATCHUPS,
                       map_ids={'ROUTE_26': 1, 'ROUTE_35': 2})
LANCE = ((149, 47), (149, 47), (149, 50))


def mon(species, level, moves, tid=1, dvs=(1, 1, 1, 1), egg=False):
    return SimpleNamespace(species=species, level=level, moves=list(moves), experience=level ** 3,
                           trainer_id=tid, dvs=dvs, egg=egg, hp=10, max_hp=10, box=None, held_item=0)


@pytest.fixture(autouse=True)
def profile(monkeypatch):
    monkeypatch.setattr(config, 'BATTLE_PROFILE', 'balanced')
    monkeypatch.setattr(config, 'TRAINING_PATIENCE', 0)
    monkeypatch.delenv('RANDOMIZER', raising=False)


def test_the_strongest_leads_and_an_ice_type_covers_lance():
    starter = mon(155, 55, [1], dvs=(9, 9, 9, 9))
    dewgong = mon(87, 20, [4], dvs=(2, 2, 2, 2))
    team = team_prep.choose(DATA, [starter, mon(16, 7, [5, 6]), dewgong, mon(241, 22, [6])], LANCE, 'league')
    assert team[0] is starter and team[1] is dewgong


def test_pokemon_with_no_damaging_move_and_eggs_are_left_out():
    starter = mon(155, 55, [1])
    team = team_prep.choose(DATA, [starter, mon(16, 30, [5]), mon(87, 30, [4], egg=True)], LANCE)
    assert team == [starter]


def test_near_ties_differ_between_runs_and_hold_within_one():
    picks = set()
    for tid in range(1, 40):
        party = [mon(155, 55, [1], tid=tid, dvs=(9, 9, 9, 9)),
                 mon(87, 30, [4], tid=tid, dvs=(2, 2, 2, 2)), mon(87, 30, [4], tid=tid, dvs=(3, 3, 3, 3))]
        first = team_prep.choose(DATA, party, LANCE, 'league')[1].dvs
        assert team_prep.choose(DATA, party, LANCE, 'league')[1].dvs == first
        picks.add(first)
    assert len(picks) == 2


def test_a_pokemon_raised_before_is_kept_over_a_slightly_better_newcomer(monkeypatch):
    monkeypatch.setattr(team_prep, 'TEAM_SIZE', 2)
    monkeypatch.setattr(team_prep, 'CLOSE', 1.0)      # no random near-tie for this check
    starter = mon(155, 55, [1], dvs=(9, 9, 9, 9))
    pikachu = mon(25, 30, [3], dvs=(4, 4, 4, 4))      # same-type bonus: a little better
    gyarados = mon(130, 30, [3], dvs=(5, 5, 5, 5))
    roster = ((130, 40),)
    assert team_prep.choose(DATA, [starter, pikachu, gyarados], roster)[1] is pikachu
    raised = [[gyarados.trainer_id, list(gyarados.dvs)]]
    assert team_prep.choose(DATA, [starter, pikachu, gyarados], roster, 'x', raised)[1] is gyarados


def test_gym_levels_follow_the_leaders_best_and_the_style():
    assert team_prep.levels('plain', None, 10) == (25, 15)      # Whitney's Miltank is level 20
    assert team_prep.levels('plain', None, 5) == (22, 12)
    assert team_prep.levels('plain', None, 15) == (27, 17)
    assert team_prep.levels('plain', {'count': 3, 'level': 20}, 10) == (31, 21)


def test_league_levels_match_league_preparation():
    assert team_prep.levels('league', None, 10) == (50, 40) == league_prep.targets()
    assert team_prep.levels('league', {'count': 3, 'level': 50}, 10) == (56, 46)


def test_randomized_trainers_use_only_what_losses_saw():
    assert team_prep.levels('plain', None, 10, randomized=True) is None
    assert team_prep.levels('plain', {'count': 1, 'level': 24}, 10, randomized=True) == (29, 19)


def test_partners_train_first_the_furthest_behind_first_then_the_strongest():
    starter = mon(155, 45, [1], dvs=(9, 9, 9, 9))
    dewgong, pikachu = mon(87, 22, [4], dvs=(2, 2, 2, 2)), mon(25, 12, [3], dvs=(4, 4, 4, 4))
    snap = SimpleNamespace(party=[starter, dewgong, pikachu])
    assert team_prep.wanted(DATA, snap, 'league', (50, 40), LANCE) == (pikachu, 40)
    pikachu.level = 40
    assert team_prep.wanted(DATA, snap, 'league', (50, 40), LANCE) == (dewgong, 40)
    dewgong.level = 40
    assert team_prep.wanted(DATA, snap, 'league', (50, 40), LANCE) == (starter, 50)
    starter.level = 50
    assert team_prep.wanted(DATA, snap, 'league', (50, 40), LANCE) is None


class Policy:
    def __init__(self, league=False):
        self.collection = {}
        self.league = league
        self.data = DATA

    def in_league(self, snapshot):
        return self.league


def snapshot(*party, fame=0):
    return SimpleNamespace(party=list(party), frame=0, hall_of_fame_count=fame)


def test_goal_starts_a_project_on_the_gyms_route_and_remembers_the_trainee(monkeypatch):
    calls = []
    monkeypatch.setattr(team_prep, 'train', lambda policy, s, mem, Goal: calls.append(dict(policy.collection['training'])) or 'goal')
    policy = Policy()
    partner = mon(87, 8, [4], dvs=(2, 2, 2, 2))
    assert team_prep.goal(policy, snapshot(mon(241, 24, [6], dvs=(9, 9, 9, 9)), partner), None, object, 'plain') == 'goal'
    assert calls[0]['level_goal'] == 15 and calls[0]['map'] == 'ROUTE_35' and calls[0]['team'] == 'plain'
    assert policy.collection['team_raised'] == [[partner.trainer_id, list(partner.dvs)]]


def test_goal_clears_its_project_once_ready_and_never_runs_in_the_league():
    policy = Policy()
    policy.collection['training'] = {'team': 'plain', 'identity': [1, [1, 1, 1, 1]]}
    assert team_prep.goal(policy, snapshot(mon(241, 25, [6]), mon(87, 15, [4], dvs=(2, 2, 2, 2))), None, object, 'plain') is None
    assert policy.collection['training'] is None
    assert team_prep.goal(Policy(league=True), snapshot(mon(155, 30, [1]), mon(87, 5, [4])), None, object, 'league') is None
    assert team_prep.goal(Policy(), snapshot(mon(155, 30, [1]), mon(87, 5, [4]), fame=1), None, object, 'league') is None


def test_every_gym_has_a_roster_and_a_route():
    assert set(team_prep.ROSTERS) == set(team_prep.ROUTES)
    assert team_prep.GYMS == {'hive', 'plain', 'fog', 'storm', 'mineral', 'glacier', 'clair'}



def test_a_share_code_with_random_trainers_is_recognised(monkeypatch):
    from pokecore.randomizer import Options, encode_share_code
    assert not team_prep.randomized_trainers()
    monkeypatch.setenv('RANDOMIZER', encode_share_code('crystal', 7, Options(wild=True, starters=False, trainers=False)))
    assert not team_prep.randomized_trainers()
    monkeypatch.setenv('RANDOMIZER', encode_share_code('crystal', 7, Options(wild=False, starters=False, trainers=True)))
    assert team_prep.randomized_trainers()
