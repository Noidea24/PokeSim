"""Noidea24 fork: trade preparation limits follow game speed when TRADE_PREPARE_SECONDS is set."""
from types import SimpleNamespace

import pytest

from pokesim import config
from pokesim.trade.timing import scaled_seconds


@pytest.mark.parametrize('base,speeds,expected', [
    (0, [4], 900),              # unset: the original limit, whatever the speed
    (600, [1], 600),
    (600, [4], 150),
    (600, [16], 60),            # never under a minute
    (600, [4, 1], 600),         # the slower game sets the limit
    (600, [0], 60),             # unlimited counts as 16x
    (3600, [2], 1800),
])
def test_scaled_seconds(base, speeds, expected):
    assert scaled_seconds(base, speeds, 900) == expected


@pytest.mark.parametrize('module', ['pokesim.runtime.preparation', 'pokesim.gen2.preparation'])
def test_each_game_walks_for_its_own_scaled_time(module, monkeypatch):
    import importlib
    travel = importlib.import_module(module).travel_seconds
    monkeypatch.setattr(config, 'TRADE_PREPARE_SECONDS', 0)
    assert travel(SimpleNamespace(speed=8)) == 1800
    monkeypatch.setattr(config, 'TRADE_PREPARE_SECONDS', 600)
    assert travel(SimpleNamespace(speed=4)) == 150
    assert travel(SimpleNamespace(speed=1)) == 600


def test_the_library_gives_up_on_the_slower_game_scaled_time(tmp_path, monkeypatch):
    from pokesim.app.manager import Manager
    manager = Manager(tmp_path, 'http://testserver')
    coordinator = manager.coordinator
    speeds = {'a': 4, 'b': 8}
    monkeypatch.setattr(coordinator.registry, 'adventure', lambda aid: {'settings': {'speed': speeds[aid]}})
    row = {'plan': {'participants': ['a', 'b']}}
    monkeypatch.setattr(config, 'TRADE_PREPARE_SECONDS', 0)
    assert coordinator._prepare_seconds(row) == 900
    monkeypatch.setattr(config, 'TRADE_PREPARE_SECONDS', 600)
    assert coordinator._prepare_seconds(row) == 150


def test_setting_is_validated(monkeypatch):
    monkeypatch.setattr(config, 'TRADE_PREPARE_SECONDS', -1)
    with pytest.raises(ValueError, match='TRADE_PREPARE_SECONDS'):
        config.validate()
