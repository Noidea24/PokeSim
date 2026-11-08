"""Noidea24 fork, revised agent: learn from losing to a trainer.

The original never changes anything after a loss. It heals and walks back to the same trainer with
the same team, and only the watchdog's reloads ever break the loop. The revised agent counts each
whiteout against the story step it was working on. After a second loss to the same step it trains
first: the strongest Pokémon to three levels above the best Pokémon it saw that trainer use, and the
next strongest to five below that, with three more levels for every further loss. Training happens
on a route the story has already opened for the current badge count. In the League, every loss after
the first raises League preparation's levels by three instead.

Records are kept in the adventure, so a restart keeps them, and a reload to an older save keeps the
newer count, since what was learned happened all the same. A step's record is dropped once the story
moves to another step, and the League's once the Hall of Fame is reached.
"""
from .training import identity, journey as train

LEAGUE = 'league'
# Training grass by Johto badge count, each reachable once the story has that many badges, chosen
# close to where the next challenge stands. Falkner already has his own training before the first badge.
ROUTES = {1: 'ROUTE_33', 2: 'ROUTE_35', 3: 'ROUTE_37', 4: 'ROUTE_39', 5: 'ROUTE_42', 6: 'ROUTE_43',
          7: 'ROUTE_44', 8: 'ROUTE_26'}
STEP = 3          # levels added for each loss after the first
LEAD_ABOVE = 3    # the strongest trains to this many levels above the trainer's best Pokémon
PARTNER_BELOW = 5  # the next strongest to this many below it


def records(policy):
    return policy.collection.setdefault('losses', {})


def observe(policy, snapshot):
    """Count a whiteout in a trainer battle against the story step under way."""
    battle = getattr(policy, 'loss_battle', None)
    if snapshot.in_battle == 2:
        key = LEAGUE if policy.in_league(snapshot) else getattr(policy, 'journey_key', None)
        if battle is None:
            battle = policy.loss_battle = {'key': key, 'level': 0, 'lost': False}
        battle['level'] = max(battle['level'], int(getattr(snapshot, 'enemy_level', 0) or 0))
        mons = [mon for mon in snapshot.party if not mon.egg]
        if battle['key'] and not battle['lost'] and mons and all(mon.hp == 0 for mon in mons):
            battle['lost'] = True
            entry = records(policy).setdefault(battle['key'], {'count': 0, 'level': 0})
            entry['count'] += 1
            entry['level'] = max(entry['level'], battle['level'])
    elif not snapshot.in_battle:
        policy.loss_battle = None


def carry(policy, lessons):
    """Keep the larger count and level of each record across a reload to an older save."""
    from ..agent import revised
    if not revised():
        return
    state = records(policy)
    for key, entry in lessons.items():
        mine = state.setdefault(key, {'count': 0, 'level': 0})
        mine['count'] = max(mine['count'], entry.get('count', 0))
        mine['level'] = max(mine['level'], entry.get('level', 0))


def forget(policy, snapshot, journey_key):
    """Drop records the story has moved past."""
    state = records(policy)
    for key in list(state):
        if key == LEAGUE and not snapshot.hall_of_fame_count:
            continue
        if key != journey_key:
            del state[key]


def league_bump(policy):
    """Levels League preparation adds for its losses after the first."""
    entry = records(policy).get(LEAGUE)
    return STEP * max(0, entry['count'] - 1) if entry else 0


def targets(entry):
    extra = STEP * (entry['count'] - 1)
    return min(100, entry['level'] + LEAD_ABOVE + extra), min(100, entry['level'] - PARTNER_BELOW + extra)


def goal(policy, snapshot, mem, Goal, journey_key):
    """A training goal after two losses to the step under way, or None to try again now."""
    from ..caution import keep_training
    from .team_prep import strength

    def team(snapshot):
        mons = sorted((mon for mon in snapshot.party if not mon.egg), key=strength, reverse=True)
        return (mons[0] if mons else None), (mons[1] if len(mons) > 1 else None)
    state = policy.collection
    project = state.get('training')
    entry = records(policy).get(journey_key)
    where = ROUTES.get(bin(snapshot.badges & 0xFF).count('1'))
    need = None
    if (entry and entry['count'] >= 2 and entry['level'] and where in policy.data.map_ids
            and not snapshot.hall_of_fame_count and not policy.in_league(snapshot)):
        lead_target, partner_target = targets(entry)
        lead, partner = team(snapshot)
        if partner is not None and partner.level < partner_target:
            need = partner, partner_target
        elif lead is not None and lead.level < lead_target:
            need = lead, lead_target
    if need is None or not keep_training(f'loss_{journey_key}', snapshot.frame):
        if project and project.get('loss'):
            state['training'] = None
        return None
    mon, level = need
    key = identity(mon)
    if not (project and project.get('loss') == journey_key and project['identity'] == key
            and project.get('level_goal') == level):
        state['training'] = {'identity': key, 'target': mon.species, 'item': None, 'species': mon.species,
                             'terminal': True, 'level_goal': level, 'loss': journey_key, 'map': where}
    return train(policy, snapshot, mem, Goal)
