"""Noidea24 fork: Crystal spends the cheapest item that does the job."""
from pokesim.gen2.remedies import curing, healing

POISON, SLEEP, PARALYSIS = 8, 2, 64


def test_light_damage_uses_a_potion_first():
    assert healing(15)[:3] == ('POTION', 'SUPER_POTION', 'HYPER_POTION')


def test_full_restore_comes_after_every_covering_potion():
    order = healing(120)
    assert order.index('HYPER_POTION') < order.index('MAX_POTION') < order.index('FULL_RESTORE')
    assert 'POTION' not in order[:order.index('FULL_RESTORE')]


def test_heavy_damage_with_no_covering_potion_tries_the_big_heals_then_the_biggest_partial():
    assert healing(250) == ('MAX_POTION', 'FULL_RESTORE', 'HYPER_POTION', 'SUPER_POTION', 'POTION')


def test_damage_and_status_in_battle_takes_one_full_restore_turn():
    assert healing(100, status=True, in_battle=True)[0] == 'FULL_RESTORE'


def test_damage_and_status_outside_battle_still_saves_the_full_restore():
    assert healing(30, status=True)[0] == 'SUPER_POTION'


def test_poison_alone_uses_an_antidote_never_a_full_restore_outside_battle():
    assert curing(POISON) == ('ANTIDOTE', 'FULL_HEAL')


def test_status_in_battle_falls_back_to_a_full_restore_last():
    assert curing(PARALYSIS, in_battle=True) == ('PARLYZ_HEAL', 'FULL_HEAL', 'FULL_RESTORE')
    assert curing(SLEEP, in_battle=True)[0] == 'AWAKENING'


def test_every_order_lists_each_item_once():
    for missing in (1, 20, 21, 50, 51, 200, 201, 999):
        for status in (False, True):
            for battle in (False, True):
                order = healing(missing, status=status, in_battle=battle)
                assert len(order) == len(set(order)) == 5


def test_revised_tops_up_under_60_percent_between_league_battles(monkeypatch):
    from pokesim import config
    from pokesim.gen2.remedies import heal_below
    monkeypatch.setattr(config, 'AGENT', 'original')
    assert heal_below() == 0.8
    monkeypatch.setattr(config, 'AGENT', 'revised')
    assert heal_below() == 0.6
    assert not 30 < 50 * heal_below()      # the reported 30 of 50 HP keeps its potion


def test_revised_restocks_cheapest_first():
    from pokesim.gen2.ledger import POTIONS, REVISED_POTIONS
    assert set(POTIONS) == set(REVISED_POTIONS)
    assert REVISED_POTIONS[0] == 'HYPER_POTION' and POTIONS[0] == 'FULL_RESTORE'
