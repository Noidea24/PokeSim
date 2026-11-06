"""Noidea24 fork: trade preparation limits that follow game speed.

TRADE_PREPARE_SECONDS is the time two games get to reach the Cable Club, measured in game time at
1x speed. A game at 4x walks four times as far each real second, so it gets a quarter of the real
time. The slowest game in the trade sets the limit, an unlimited-speed game counts as 16x, and no
limit drops under a minute, which leaves room for menus and the trade itself.
"""

FLOOR_SECONDS = 60
UNLIMITED_SPEED = 16


def scaled_seconds(base, speeds, original):
    """Real seconds for ``base`` seconds of 1x game time, or ``original`` when ``base`` is 0."""
    if not base:
        return original
    rates = [UNLIMITED_SPEED if not speed or speed <= 0 else float(speed) for speed in speeds] or [1.0]
    return max(FLOOR_SECONDS, base / min(rates))
