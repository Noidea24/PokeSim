"""Noidea24 fork: train for the Johto League before challenging the Elite Four.

The original walks into Will as soon as the eighth badge is won, whatever the team's levels. A
journey fought mostly by the starter reaches the League with one strong Pokémon and HM carriers
in the single digits, so once the starter faints the battle is lost, and the run went back to Will
again and again. Now a second battler is raised first, with the Exp. Share so the starter keeps
learning beside it, and then the starter, before each attempt. Training happens on Route 26, just
outside the League gate.

The battle profile sets the levels through its level margin: Balanced trains the partner to 40
and the strongest to 50, Bold to 35 and 45, Careful to 45 and 55. With training patience (Bold),
time spent training alternates with attempts, as before a gym.
"""
from .training import identity, journey as train

MAP = 'ROUTE_26'
LEAD_LEVEL = 40       # plus the profile's level margin
PARTNER_LEVEL = 30    # plus the profile's level margin


def targets():
    from ..caution import margin
    return LEAD_LEVEL + margin(), PARTNER_LEVEL + margin()


def team(snapshot):
    """The strongest party member and the next strongest, chosen the same way whatever the order.

    Party order changes while a partner without an Exp. Share leads, so position never decides.
    """
    order = lambda mon: (mon.level, mon.experience, mon.trainer_id, tuple(mon.dvs))
    mons = sorted((mon for mon in snapshot.party if not mon.egg), key=order, reverse=True)
    return (mons[0] if mons else None), (mons[1] if len(mons) > 1 else None)


def wanted(snapshot):
    """The Pokémon to train and the level it needs, or None when the team is ready."""
    lead_target, partner_target = targets()
    lead, partner = team(snapshot)
    if partner is not None and partner.level < partner_target:
        return partner, partner_target
    if lead is not None and lead.level < lead_target:
        return lead, lead_target
    return None


def goal(policy, snapshot, mem, Goal):
    """A training goal before the next League attempt, or None to challenge now."""
    from ..caution import keep_training
    state = policy.collection
    project = state.get('training')
    if policy.in_league(snapshot):
        return None
    need = wanted(snapshot)
    if need is None or not keep_training('train_league', snapshot.frame):
        if project and project.get('league'):
            state['training'] = None
        return None
    mon, level = need
    key = identity(mon)
    if not (project and project.get('league') and project['identity'] == key
            and project.get('level_goal') == level):
        state['training'] = {'identity': key, 'target': mon.species, 'item': None, 'species': mon.species,
                             'terminal': True, 'level_goal': level, 'league': True, 'map': MAP}
    return train(policy, snapshot, mem, Goal)
