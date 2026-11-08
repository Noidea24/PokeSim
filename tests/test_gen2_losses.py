"""Noidea24 fork, revised agent: Crystal learns from losing to a trainer."""
from types import SimpleNamespace

import pytest

from pokesim import agent, config
from pokesim.gen2 import league_prep, losses


@pytest.fixture(autouse=True)
def profile(monkeypatch):
    monkeypatch.setattr(config, 'BATTLE_PROFILE', 'balanced')
    monkeypatch.setattr(config, 'AGENT', 'revised')


def mon(level, hp=10, dvs=(1, 1, 1, 1), egg=False):
    return SimpleNamespace(level=level, experience=level ** 3, species=1, egg=egg, trainer_id=1, dvs=dvs,
                           hp=hp, max_hp=10, box=None, held_item=0)


class Policy:
    def __init__(self, league=False, routes=('ROUTE_35', 'ROUTE_26')):
        self.collection = {}
        self.league = league
        self.journey_key = 'plain'
        self.data = SimpleNamespace(map_ids={name: i for i, name in enumerate(routes)})

    def in_league(self, snapshot):
        return self.league


def snap(*party, battle=0, enemy=20, badges=0b11, fame=0, frame=0):
    return SimpleNamespace(party=list(party), in_battle=battle, enemy_level=enemy, badges=badges,
                           hall_of_fame_count=fame, frame=frame)


def lose(policy, enemy=20):
    losses.observe(policy, snap(mon(24), mon(7), battle=2, enemy=enemy - 2))
    losses.observe(policy, snap(mon(24), mon(7), battle=2, enemy=enemy))
    losses.observe(policy, snap(mon(24, hp=0), mon(7, hp=0), battle=2, enemy=enemy))
    losses.observe(policy, snap(mon(24, hp=0), mon(7, hp=0), battle=2, enemy=enemy))   # same faint, counted once
    losses.observe(policy, snap(mon(24), mon(7)))


def test_a_whiteout_counts_once_with_the_trainers_best_level():
    policy = Policy()
    lose(policy)
    assert losses.records(policy) == {'plain': {'count': 1, 'level': 20}}


def test_a_won_battle_counts_nothing():
    policy = Policy()
    losses.observe(policy, snap(mon(24), mon(7), battle=2))
    losses.observe(policy, snap(mon(24), mon(7)))
    assert losses.records(policy) == {}


def test_wild_battles_are_not_losses_to_a_trainer():
    policy = Policy()
    losses.observe(policy, snap(mon(24, hp=0), battle=1))
    assert losses.records(policy) == {}


def test_one_loss_tries_again(monkeypatch):
    policy = Policy()
    lose(policy)
    assert losses.goal(policy, snap(mon(24), mon(7)), None, object, 'plain') is None


def test_two_losses_train_the_partner_then_the_strongest(monkeypatch):
    calls = []
    monkeypatch.setattr(losses, 'train', lambda policy, s, mem, Goal: calls.append(dict(policy.collection['training'])) or 'goal')
    policy = Policy()
    lose(policy)
    lose(policy)
    partner = mon(7, dvs=(2, 2, 2, 2))
    assert losses.goal(policy, snap(mon(24, dvs=(9, 9, 9, 9)), partner), None, object, 'plain') == 'goal'
    assert calls[-1]['level_goal'] == 20 - 5 + 3 and calls[-1]['map'] == 'ROUTE_35' and calls[-1]['loss'] == 'plain'
    assert losses.goal(policy, snap(mon(24, dvs=(9, 9, 9, 9)), mon(18, dvs=(2, 2, 2, 2))), None, object, 'plain') == 'goal'
    assert calls[-1]['level_goal'] == 20 + 3 + 3


def test_ready_team_tries_again_and_clears_its_project():
    policy = Policy()
    lose(policy)
    lose(policy)
    policy.collection['training'] = {'loss': 'plain', 'identity': [1, [1, 1, 1, 1]]}
    assert losses.goal(policy, snap(mon(26), mon(18)), None, object, 'plain') is None
    assert policy.collection['training'] is None


def test_no_route_open_means_no_training():
    policy = Policy(routes=())
    lose(policy)
    lose(policy)
    assert losses.goal(policy, snap(mon(24), mon(7)), None, object, 'plain') is None


def test_moving_on_forgets_the_old_step_but_not_the_league():
    policy = Policy()
    lose(policy)
    losses.records(policy)['league'] = {'count': 2, 'level': 50}
    losses.forget(policy, snap(), 'fog')
    assert losses.records(policy) == {'league': {'count': 2, 'level': 50}}
    losses.forget(policy, snap(fame=1), 'fog')
    assert losses.records(policy) == {}


def test_league_losses_raise_league_preparation():
    policy = Policy(league=True)
    lose(policy, enemy=50)
    assert losses.league_bump(policy) == 0
    lose(policy, enemy=50)
    lose(policy, enemy=50)
    assert losses.records(policy)['league']['count'] == 3 and losses.league_bump(policy) == 6
    assert league_prep.targets(losses.league_bump(policy)) == (56, 46)


def test_agent_setting():
    assert agent.revised()
    assert agent.validate({'agent': 'original'}) == {}
    assert agent.validate({'agent': 'revised'}) == {'agent': 'revised'}
    with pytest.raises(ValueError):
        agent.validate({'agent': 'smart'})


def test_original_is_the_default(monkeypatch):
    monkeypatch.setattr(config, 'AGENT', 'nonsense')
    assert agent.name() == 'original' and not agent.revised()


def test_the_reported_league_pattern_raises_training_after_each_lost_attempt():
    """Win, win, win, loss, then win x3 loss, win x4 loss, win x2 loss: four lost attempts."""
    policy = Policy(league=True)
    bumps = []
    for wins in (3, 3, 4, 2):
        for _ in range(wins):
            losses.observe(policy, snap(mon(48), mon(30), battle=2, enemy=44))
            losses.observe(policy, snap(mon(48), mon(30)))
        lose(policy, enemy=47)
        bumps.append(losses.league_bump(policy))
    assert bumps == [0, 3, 6, 9]
    assert league_prep.targets(bumps[-1]) == (59, 49)


def test_a_reload_to_an_older_save_keeps_what_was_learned():
    policy = Policy(league=True)
    lose(policy, enemy=47)
    lose(policy, enemy=47)
    older = {'league': {'count': 1, 'level': 40}}
    lessons = losses.records(policy)
    policy.collection = {'losses': dict(older)}
    losses.carry(policy, lessons)
    assert losses.records(policy)['league'] == {'count': 2, 'level': 47}


def test_the_original_agent_keeps_nothing_across_reloads(monkeypatch):
    monkeypatch.setattr(config, 'AGENT', 'original')
    policy = Policy()
    losses.carry(policy, {'plain': {'count': 2, 'level': 20}})
    assert losses.records(policy) == {}
