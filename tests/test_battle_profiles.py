"""Noidea24 fork (beta): battle caution profiles."""
import pytest

from pokesim import caution as profiles
from pokesim import config


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    profiles._STARTS.clear()
    monkeypatch.setattr(config, 'BATTLE_PROFILE', 'balanced')


def use(monkeypatch, profile, **custom):
    monkeypatch.setattr(config, 'BATTLE_PROFILE', profile)
    for name, value in custom.items():
        monkeypatch.setattr(config, name.upper(), value)


def test_balanced_is_the_original():
    assert profiles.current() == {'caution': 75, 'margin': 10, 'patience': 0}
    assert all(profiles.keep_training('train_marsh', frame) for frame in (0, 10 ** 6, 10 ** 9))


@pytest.mark.parametrize('profile,caution,margin', [('bold', 55, 5), ('careful', 85, 15)])
def test_presets(monkeypatch, profile, caution, margin):
    use(monkeypatch, profile)
    assert (profiles.caution(), profiles.margin()) == (caution, margin)


def test_custom_uses_its_numbers(monkeypatch):
    use(monkeypatch, 'custom', gym_caution=40, level_margin=2, training_patience=10)
    assert profiles.current() == {'caution': 40, 'margin': 2, 'patience': 10}


def test_patience_alternates_training_and_challenging(monkeypatch):
    use(monkeypatch, 'bold')        # 30 game minutes
    span = 30 * 3600
    assert profiles.keep_training('train_marsh', 1000)
    assert profiles.keep_training('train_marsh', 1000 + span - 1)
    assert not profiles.keep_training('train_marsh', 1000 + span)
    assert profiles.keep_training('train_marsh', 1000 + 2 * span)
    assert profiles.keep_training('train_soul', 1000 + span)     # each challenge has its own clock
    assert profiles.keep_training('train_marsh', 5)              # an earlier save restarts the clock


def test_validation_stores_only_what_differs():
    assert profiles.validate({'battle_profile': 'balanced', 'gym_caution': 50}) == {}
    assert profiles.validate({'battle_profile': 'bold', 'level_margin': 3}) == {'battle_profile': 'bold'}
    assert profiles.validate({'battle_profile': 'custom', 'gym_caution': 50}) == {
        'battle_profile': 'custom', 'gym_caution': 50, 'level_margin': 10, 'training_patience': 0}
    for bad in ({'battle_profile': 'reckless'}, {'battle_profile': 'custom', 'gym_caution': 10},
                {'battle_profile': 'custom', 'training_patience': 'long'}):
        with pytest.raises(ValueError):
            profiles.validate(bad)


def test_adventure_settings_accept_profiles():
    from pokesim.app.manager import Manager
    assert Manager.validate_adventure_settings({'battle_profile': 'careful'})['battle_profile'] == 'careful'
    assert 'battle_profile' not in Manager.validate_adventure_settings({'battle_profile': 'balanced'})
    with pytest.raises(ValueError):
        Manager.validate_adventure_settings({'battle_profile': 'nope'})


def test_simulation_settings_carry_the_profile(tmp_path):
    from pokesim.runtime.settings import SimulationSettings
    rom = tmp_path / 'rom.gb'
    rom.write_bytes(b'\0' * 32)
    base = dict(rom_path=str(rom), data_dir=str(tmp_path), game_data_dir=str(tmp_path))
    assert SimulationSettings(**base).battle_profile == 'balanced'
    assert SimulationSettings(**base, battle_profile='custom', gym_caution=60).gym_caution == 60
    for bad in ({'battle_profile': 'wild'}, {'gym_caution': 5}, {'training_patience': 9999}):
        with pytest.raises(ValueError):
            SimulationSettings(**base, **bad)


def test_gym_gate_follows_the_profile(monkeypatch):
    """A weak matchup before Sabrina (gym level 40 in Red): Balanced trains to 50, Bold to 45."""
    from pokesim.policies.progression import gym_goal
    from test_events import snap
    from test_strategy import mon
    party = (mon(level=47),)
    state = dict(badges=31, party=party, map=1)
    assert gym_goal(snap(**state), 32).title == 'Prepare for Sabrina'
    use(monkeypatch, 'bold')
    assert gym_goal(snap(**state), 32).title == 'Challenge Sabrina'
    use(monkeypatch, 'careful')
    assert gym_goal(snap(**dict(state, party=(mon(level=52),))), 32).title == 'Prepare for Sabrina'


def test_patience_lets_a_stuck_team_try_the_gym(monkeypatch):
    from pokesim.policies.progression import gym_goal
    from test_events import snap
    from test_strategy import mon
    use(monkeypatch, 'custom', gym_caution=95, level_margin=20, training_patience=10)
    state = dict(badges=31, party=(mon(level=47),), map=1)
    assert gym_goal(snap(frame=0, **state), 32).title == 'Prepare for Sabrina'
    assert gym_goal(snap(frame=10 * 3600, **state), 32).title == 'Challenge Sabrina'
    assert gym_goal(snap(frame=20 * 3600, **state), 32).title == 'Prepare for Sabrina'
