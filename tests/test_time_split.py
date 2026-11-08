"""Noidea24 fork: the five-minute log line that says where a game's time went."""
from pokesim.time_split import TimeSplit


def test_the_split_reports_each_part_once_a_period_has_passed():
    now = [0.0]
    lines = []
    split = TimeSplit(period=10, clock=lambda: now[0], sink=lines.append)
    for _ in range(100):
        split.decided(0.04)            # 4 s deciding in 100 decisions
    split.add('emulating', 3)
    for _ in range(50):
        split.drew(0.02)               # 1 s of live view
    split.add('sleeping', 1.5)
    now[0] = 5
    assert split.report() is None and not lines
    now[0] = 10
    line = split.report()
    assert line == lines[0]
    assert 'deciding 40% (100 decisions, 40.0 ms each)' in line
    assert 'emulating 30%' in line and 'live view 10% (50 frames)' in line
    assert 'sleeping 15%' in line and 'other 5%' in line


def test_each_period_starts_from_zero():
    now = [0.0]
    split = TimeSplit(period=1, clock=lambda: now[0], sink=lambda line: None)
    split.decided(0.5)
    now[0] = 1
    split.report()
    now[0] = 2
    assert 'deciding 0% (0 decisions, 0.0 ms each)' in split.report()
