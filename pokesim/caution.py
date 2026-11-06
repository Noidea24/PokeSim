"""Noidea24 fork (beta): battle caution profiles.

Before a gym leader or the League, the original trains until its best partner scores 75 against a
representative opponent or the team is ten levels above the gym. A profile changes those two
numbers and can add training patience: after that much game time spent training for one
challenge, the next stretch of the same length goes to challenging instead, and the two alternate
until the challenge is won. Balanced is the original's behaviour and the default.
"""

# caution: readiness score wanted. margin: levels above the gym. patience: game minutes, 0 = none.
PROFILES = {
    'balanced': {'caution': 75, 'margin': 10, 'patience': 0},
    'bold': {'caution': 55, 'margin': 5, 'patience': 30},
    'careful': {'caution': 85, 'margin': 15, 'patience': 0},
}
CHOICES = frozenset(PROFILES) | {'custom'}
LIMITS = {'gym_caution': (30, 95), 'level_margin': (0, 20), 'training_patience': (0, 600)}
FRAMES_PER_MINUTE = 3600
_STARTS = {}


def current():
    """The caution, level margin and patience the running adventure uses."""
    from . import config
    profile = getattr(config, 'BATTLE_PROFILE', 'balanced') or 'balanced'
    if profile == 'custom':
        return {'caution': int(config.GYM_CAUTION), 'margin': int(config.LEVEL_MARGIN),
                'patience': int(config.TRAINING_PATIENCE)}
    return dict(PROFILES.get(profile, PROFILES['balanced']))


def caution():
    return current()['caution']


def margin():
    return current()['margin']


def keep_training(key, frame):
    """True while training for ``key`` should go on, False during a challenge stretch.

    With no patience set, training always goes on, as in the original. With patience, game time
    spent on ``key`` alternates between training and challenging in stretches of that length.
    """
    minutes = current()['patience']
    if not minutes:
        return True
    if len(_STARTS) > 32:
        _STARTS.clear()
    start = _STARTS.setdefault(key, frame)
    if frame < start:        # an earlier save was loaded
        start = _STARTS[key] = frame
    return (frame - start) // (minutes * FRAMES_PER_MINUTE) % 2 == 0


def validate(values):
    """Check the profile fields of an adventure's settings and drop those left at their defaults."""
    result = dict(values)
    profile = result.get('battle_profile', 'balanced')
    if not isinstance(profile, str) or profile not in CHOICES:
        raise ValueError('Unknown battle_profile')
    for name, (low, high) in LIMITS.items():
        if name in result and (type(result[name]) is not int or not low <= result[name] <= high):
            raise ValueError(f'{name} must be between {low} and {high}')
    if profile == 'custom':
        defaults = PROFILES['balanced']
        result.setdefault('gym_caution', defaults['caution'])
        result.setdefault('level_margin', defaults['margin'])
        result.setdefault('training_patience', defaults['patience'])
    else:
        for name in LIMITS:
            result.pop(name, None)
    # Balanced is stored as absent, so releases without profiles still open the adventure.
    if profile == 'balanced':
        result.pop('battle_profile', None)
    return result
