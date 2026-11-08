"""Noidea24 fork (beta): which agent plays an adventure.

Original is upstream's agent, unchanged. Revised reworks how Gold, Silver and Crystal prepare and
fight: it trains before the Elite Four, spends the cheapest item that does the job, and learns from
losses, training toward a trainer it has lost to twice instead of walking back for the same result.
Red, Blue and Yellow play the same with either choice for now.
"""
CHOICES = frozenset({'original', 'revised'})


def name():
    from . import config
    value = getattr(config, 'AGENT', 'original') or 'original'
    return value if value in CHOICES else 'original'


def revised():
    return name() == 'revised'


def validate(values):
    result = dict(values)
    value = result.get('agent', 'original')
    if not isinstance(value, str) or value not in CHOICES:
        raise ValueError('Unknown agent')
    # Original is stored as absent, so releases without the setting still open the adventure.
    if value == 'original':
        result.pop('agent', None)
    return result
