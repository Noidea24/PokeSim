"""Noidea24 fork (beta): priorities reorder the tiers below story and upkeep."""
import pytest

from pokesim import config
from pokesim import priorities
from pokesim.planning import arbiter
from pokesim.planning.arbiter import Candidate, Tier


def candidates():
    return [Candidate('story', Tier.STORY, 0.01, 10_000), Candidate('heal', Tier.UPKEEP, 0.01, 10_000),
            Candidate('new', Tier.PROGRESS, 1.0, 1000), Candidate('race', Tier.RACE, 0.05, 1000),
            Candidate('train', Tier.UPGRADE, 0.5, 1000), Candidate('explore', Tier.FILLER, 0.05, 1000)]


@pytest.mark.parametrize('name,order', [
    ('balanced', ['story', 'heal', 'new', 'race', 'train', 'explore']),
    ('collector', ['story', 'heal', 'new', 'train', 'race', 'explore']),
    ('trainer', ['story', 'heal', 'train', 'new', 'race', 'explore']),
    ('explorer', ['story', 'heal', 'new', 'explore', 'race', 'train']),
])
def test_order(monkeypatch, name, order):
    monkeypatch.setattr(config, 'PRIORITIES', name)
    assert [c.key for c in arbiter.rank(candidates())] == order


def test_story_and_upkeep_always_lead(monkeypatch):
    for name in priorities.CHOICES:
        monkeypatch.setattr(config, 'PRIORITIES', name)
        pool = [c for c in candidates() if c.key != 'story']
        assert arbiter.choose(pool).key == 'heal'


def test_curiosity(monkeypatch):
    monkeypatch.setattr(config, 'PRIORITIES', 'balanced')
    assert priorities.curiosity(0.12) == pytest.approx(0.12)
    monkeypatch.setattr(config, 'PRIORITIES', 'explorer')
    assert priorities.curiosity(0.12) == pytest.approx(0.30)
    monkeypatch.setattr(config, 'PRIORITIES', 'trainer')
    assert priorities.curiosity(0.12) == pytest.approx(0.06)


def test_validation():
    assert priorities.validate({'priorities': 'balanced'}) == {}
    assert priorities.validate({'priorities': 'trainer'}) == {'priorities': 'trainer'}
    with pytest.raises(ValueError):
        priorities.validate({'priorities': 'speedrun'})
    from pokesim.app.manager import Manager
    assert Manager.validate_adventure_settings({'priorities': 'explorer'})['priorities'] == 'explorer'


def test_phone_waits_run_in_the_background_outside_balanced(monkeypatch):
    """Crystal's wait for a trainer's call: Balanced stands by a PC as before, the others keep working."""
    from pokesim.gen2.collection import passive_goal, PHONE_WAIT
    monkeypatch.setattr(config, 'PRIORITIES', 'balanced')
    assert passive_goal(PHONE_WAIT) is False
    assert passive_goal('collection_hatch') is True
    for name in ('collector', 'trainer', 'explorer'):
        monkeypatch.setattr(config, 'PRIORITIES', name)
        assert passive_goal(PHONE_WAIT) is True
        assert passive_goal('collection_phone_gift') is False      # collecting the stone still runs


def test_the_ladder_asks_passive_goal_for_every_rung():
    import inspect
    from pokesim.gen2 import collection
    assert 'passive=passive_goal(goal.key)' in inspect.getsource(collection.Ladder.offer)
