"""Noidea24 fork: Crystal trains a second battler and the starter before the Elite Four."""
from types import SimpleNamespace

import pytest

from pokesim import config
from pokesim.gen2 import league_prep


def mon(level, species=1, egg=False, tid=1, dvs=(1, 1, 1, 1)):
    return SimpleNamespace(level=level, experience=level ** 3, species=species, egg=egg, trainer_id=tid,
                           dvs=dvs, box=None, held_item=0)


@pytest.fixture(autouse=True)
def profile(monkeypatch):
    monkeypatch.setattr(config, 'BATTLE_PROFILE', 'balanced')
    monkeypatch.setattr(config, 'TRAINING_PATIENCE', 0)


def snapshot(*party, frame=0):
    return SimpleNamespace(party=list(party), frame=frame)


def test_the_reported_team_trains_its_best_partner_first():
    starter, partner = mon(48, dvs=(9, 9, 9, 9)), mon(22, dvs=(2, 2, 2, 2))
    chosen, level = league_prep.wanted(snapshot(starter, mon(2), mon(7), mon(13), partner))
    assert chosen is partner and level == 40


def test_the_starter_trains_once_the_partner_is_ready():
    starter = mon(45, dvs=(9, 9, 9, 9))
    chosen, level = league_prep.wanted(snapshot(starter, mon(41), mon(3)))
    assert chosen is starter and level == 50


def test_a_ready_team_challenges():
    assert league_prep.wanted(snapshot(mon(50), mon(40), mon(5))) is None


def test_eggs_are_never_chosen():
    starter = mon(55)
    assert league_prep.wanted(snapshot(starter, mon(5, egg=True))) is None


def test_profiles_set_the_levels(monkeypatch):
    monkeypatch.setattr(config, 'BATTLE_PROFILE', 'bold')
    assert league_prep.targets() == (45, 35)
    monkeypatch.setattr(config, 'BATTLE_PROFILE', 'careful')
    assert league_prep.targets() == (55, 45)


def test_choice_ignores_party_order():
    a, b, c = mon(30, dvs=(1, 2, 3, 4)), mon(30, dvs=(4, 3, 2, 1)), mon(50)
    first = league_prep.wanted(snapshot(c, a, b))[0]
    assert league_prep.wanted(snapshot(b, c, a))[0] is first


class Policy:
    def __init__(self, league=False):
        self.collection = {}
        self.league = league

    def in_league(self, snapshot):
        return self.league


def test_goal_starts_a_route_26_project(monkeypatch):
    calls = []
    monkeypatch.setattr(league_prep, 'train', lambda policy, snap, mem, Goal: calls.append(dict(policy.collection['training'])) or 'goal')
    policy = Policy()
    partner = mon(22, dvs=(2, 2, 2, 2))
    assert league_prep.goal(policy, snapshot(mon(48, dvs=(9, 9, 9, 9)), partner), None, object) == 'goal'
    project = calls[0]
    assert project['level_goal'] == 40 and project['league'] and project['map'] == 'ROUTE_26'
    assert project['identity'] == [partner.trainer_id, list(partner.dvs)]


def test_goal_clears_its_project_when_ready(monkeypatch):
    policy = Policy()
    policy.collection['training'] = {'league': True, 'identity': [1, [1, 1, 1, 1]]}
    assert league_prep.goal(policy, snapshot(mon(50), mon(40)), None, object) is None
    assert policy.collection['training'] is None


def test_other_training_is_left_alone_when_ready():
    policy = Policy()
    policy.collection['training'] = {'identity': [1, [1, 1, 1, 1]], 'level_goal': 30}
    league_prep.goal(policy, snapshot(mon(50), mon(40)), None, object)
    assert policy.collection['training'] == {'identity': [1, [1, 1, 1, 1]], 'level_goal': 30}


def test_no_training_inside_the_league():
    assert league_prep.goal(Policy(league=True), snapshot(mon(48), mon(2)), None, object) is None
