"""Noidea24 fork, revised agent: train for the Johto League before challenging the Elite Four.

The original walks into Will as soon as the eighth badge is won, whatever the team's levels. A
journey fought mostly by the starter reaches the League with one strong Pokémon and HM carriers
in the single digits, so once the starter faints the battle is lost, and the run went back to Will
again and again. Now a team of three is raised before each attempt: the strongest Pokémon and two
partners picked to cover the Elite Four and Lance (see team_prep.py), on Route 26 just outside the
League gate.

The battle profile sets the levels through its level margin: Balanced trains the partners to 40
and the strongest to 50, Bold to 35 and 45, Careful to 45 and 55. With training patience (Bold),
time spent training alternates with attempts, as before a gym. Every lost attempt after the first
adds three levels to both (see losses.py).
"""


def targets(bump=0):
    """The strongest and partner levels. ``bump`` adds the levels lost attempts asked for."""
    from ..caution import margin
    return min(100, 40 + margin() + bump), min(100, 30 + margin() + bump)


def goal(policy, snapshot, mem, Goal):
    """A training goal before the next League attempt, or None to challenge now."""
    from .team_prep import goal as team_goal
    return team_goal(policy, snapshot, mem, Goal, 'league')
