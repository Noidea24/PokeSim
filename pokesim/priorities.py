"""Noidea24 fork (beta): what the bot prefers once the story and upkeep are taken care of.

The arbiter ranks goals by tier, then by value for the time they take. Story and upkeep always come
first, since badges, HMs and healing open everything else. A priorities profile reorders the four
tiers below them and scales the curiosity chance, the small chance to wander, explore or chat that
Red, Blue and Yellow use. Balanced is the original order and the default.
"""
from .planning.arbiter import Tier

ORDERS = {
    'balanced': (Tier.PROGRESS, Tier.RACE, Tier.UPGRADE, Tier.FILLER),
    # New entries first, as in the original, then better copies ahead of the marathon.
    'collector': (Tier.PROGRESS, Tier.UPGRADE, Tier.RACE, Tier.FILLER),
    # Training, level 100s and perfect copies ahead of new entries.
    'trainer': (Tier.UPGRADE, Tier.PROGRESS, Tier.RACE, Tier.FILLER),
    # New entries, then exploring and other filler ahead of the marathon and upgrades.
    'explorer': (Tier.PROGRESS, Tier.FILLER, Tier.RACE, Tier.UPGRADE),
}
CURIOSITY = {'balanced': 1.0, 'collector': 0.5, 'trainer': 0.5, 'explorer': 2.5}
CHOICES = frozenset(ORDERS)
_RANKS = {}


def profile():
    from . import config
    name = getattr(config, 'PRIORITIES', 'balanced') or 'balanced'
    return name if name in ORDERS else 'balanced'


def rank(tier):
    """Where ``tier`` sorts under the current profile. Story and upkeep keep their places."""
    name = profile()
    ranks = _RANKS.get(name)
    if ranks is None:
        ranks = _RANKS[name] = {Tier.STORY: 0, Tier.UPKEEP: 1,
                                **{tier: 2 + i for i, tier in enumerate(ORDERS[name])}}
    return ranks.get(tier, tier)


def curiosity(chance):
    """The curiosity chance scaled by the current profile, never above one in two."""
    return min(0.5, chance * CURIOSITY[profile()])


def validate(values):
    result = dict(values)
    name = result.get('priorities', 'balanced')
    if not isinstance(name, str) or name not in CHOICES:
        raise ValueError('Unknown priorities')
    # Balanced is stored as absent, so releases without the setting still open the adventure.
    if name == 'balanced':
        result.pop('priorities', None)
    return result
