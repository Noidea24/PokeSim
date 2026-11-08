"""Noidea24 fork, revised agent: pick and raise a team for the next gym leader or the League.

The original fights the whole journey with its strongest Pokémon and trains on purpose only before
Falkner, so its other Pokémon stay where they were caught. Once the strongest faints, the rest cannot
win. Before each gym from Bugsy on, and before the League, the revised agent now:

1. Picks a team of three from the party it already has: the strongest Pokémon, plus two that cover
   the leader's team well. It never goes looking for particular Pokémon, so each run's team grows from
   its own starter and catches. Each Pokémon is scored against each of the leader's Pokémon by its best damaging move
   (power, type effectiveness, same-type bonus, accuracy, and its attack against their defense, from
   base stats so level does not decide it) and by how hard the leader's types hit it back. Coverage
   counts the best teammate for each opponent, so a second Pokémon that beats what the first cannot is
   worth more than another of the same kind. Pokémon raised for an earlier leader count a quarter
   more, so the team carries on through the run instead of starting over at each gym. Among
   candidates within 15% of the best, the pick is random, seeded by the run's trainer ID and the
   leader, so it stays the same within a run and differs between runs.
2. Trains the two partners first, the furthest behind first, holding the Exp. Share so the strongest
   keeps gaining beside them, then the strongest.

Levels, with ``m`` the battle style's level margin (10 on Balanced, 5 on Bold, 15 on Careful):

- A gym: the strongest to the leader's best level plus m/2, the partners to five below that level,
  moved by half of (m - 10). Whitney's Miltank is level 20, so on Balanced 25 and 15.
- The League: the strongest to 40 + m and the partners to 30 + m, as League preparation did for two.
- After two losses to the same leader or in the League, three more levels for every further loss.

Training happens on a route beside the gym's city (losses.py has the League's). The leaders' teams are
the cartridges' own, written out below because PokeSim's Gen II game data does not carry trainer
parties. A run with randomized trainers skips the roster and trains to the levels its losses saw.
"""
import random
import zlib

from .training import identity, journey as train

TEAM_SIZE = 3
LOYALTY = 1.25      # weight for a Pokémon already raised for an earlier leader
CLOSE = 0.85        # candidates within this share of the best are picked between at random
# Each leader's team as (national Pokédex number, level), from pokecrystal's trainer parties. Gold and
# Silver use the same Pokémon at these levels or within a level or two.
ROSTERS = {
    'hive': ((11, 14), (14, 14), (123, 16)),
    'plain': ((35, 18), (241, 20)),
    'fog': ((92, 21), (93, 21), (94, 25), (93, 23)),
    'storm': ((57, 27), (62, 30)),
    'mineral': ((81, 30), (81, 30), (208, 35)),
    'glacier': ((86, 27), (87, 29), (221, 31)),
    'clair': ((148, 37), (148, 37), (148, 37), (230, 40)),
    'league': ((178, 40), (124, 41), (103, 41), (80, 41), (178, 42),        # Will
               (168, 40), (49, 41), (205, 43), (89, 42), (169, 44),         # Koga
               (237, 42), (106, 42), (107, 42), (95, 43), (68, 46),         # Bruno
               (197, 42), (45, 42), (198, 44), (94, 45), (229, 47),         # Karen
               (130, 44), (149, 47), (149, 47), (142, 46), (6, 46), (149, 50)),  # Lance
}
# Grass beside each leader's city that the story has opened by the time the leader is next. Cianwood
# has none, so Chuck's partners train on Route 39 by Olivine; Clair's on Route 44 by Mahogany, which
# Fly reaches without crossing Ice Path again.
ROUTES = {'hive': 'ROUTE_33', 'plain': 'ROUTE_35', 'fog': 'ROUTE_37', 'storm': 'ROUTE_39',
          'mineral': 'ROUTE_39', 'glacier': 'ROUTE_43', 'clair': 'ROUTE_44', 'league': 'ROUTE_26'}
GYMS = frozenset(ROUTES) - {'league'}


def strength(mon):
    return mon.level, mon.experience, mon.trainer_id, tuple(mon.dvs)


def offense(data, mon, foe):
    """The best damage ``mon`` deals ``foe`` per turn, relative, from base stats and its moves."""
    mine, theirs = data.species.get(mon.species, {}), data.species.get(foe, {})
    stats, guard = mine.get('stats', [50] * 6), theirs.get('stats', [50] * 6)
    best = 0
    for mid in mon.moves:
        move = data.moves.get(mid, {}) if mid else {}
        power = move.get('power', 0)
        if not power:
            continue
        kind = move['type']
        factor = 1
        for target in set(theirs.get('types', [])):
            factor *= data.matchups.get((kind, target), 1)
        stab = 1.5 if kind in mine.get('types', []) else 1
        physical = kind < 20
        attack, defense = stats[1 if physical else 4], guard[2 if physical else 5]
        best = max(best, power * factor * stab * move.get('accuracy', 100) / 100 * attack / max(1, defense))
    return best


def resilience(data, mon, foe):
    """Up to 2 for a Pokémon the foe's types barely touch, down to 0.5 for one they hit hard."""
    mine, theirs = data.species.get(mon.species, {}), data.species.get(foe, {})
    factors = []
    for kind in set(theirs.get('types', [])):
        factor = 1
        for target in set(mine.get('types', [])):
            factor *= data.matchups.get((kind, target), 1)
        factors.append(factor)
    return 1 / max(0.5, max(factors, default=1))


def matchup(data, mon, foe):
    return offense(data, mon, foe) * resilience(data, mon, foe)


def choose(data, party, roster, boss='', raised=()):
    """The strongest Pokémon, then teammates that cover ``roster`` well.

    ``raised`` holds the identities of Pokémon trained for earlier leaders, which count a quarter more.
    Near ties are broken at random, seeded by the run's trainer ID and ``boss``.
    """
    mons = [mon for mon in party if not mon.egg]
    if not mons:
        return []
    anchor = max(mons, key=strength)
    team = [anchor]
    fighters = sorted((mon for mon in mons if mon is not anchor and any(
        data.moves.get(mid, {}).get('power', 0) for mid in mon.moves if mid)), key=strength)
    loyal = {tuple(map(tuple_or_value, key)) for key in raised}
    weight = {id(mon): LOYALTY if tuple(map(tuple_or_value, identity(mon))) in loyal else 1 for mon in mons}
    scores = {id(mon): [matchup(data, mon, foe) * level * weight[id(mon)] for foe, level in roster] for mon in mons}
    chance = random.Random(zlib.crc32(f'{anchor.trainer_id}:{boss}'.encode()))

    def coverage(members):
        return sum(max(scores[id(mon)][i] for mon in members) for i in range(len(roster)))

    while len(team) < TEAM_SIZE and fighters:
        values = {id(mon): coverage(team + [mon]) for mon in fighters}
        best = max(values.values())
        close = [mon for mon in fighters if values[id(mon)] >= best * CLOSE]
        pick = chance.choice(close)
        team.append(pick)
        fighters.remove(pick)
    return team


def tuple_or_value(value):
    return tuple(value) if isinstance(value, list) else value


def levels(boss, entry, margin, randomized=False):
    """(strongest, partners) target levels for ``boss`` given its loss record ``entry``, or None."""
    count = entry['count'] if entry else 0
    bump = 3 * max(0, count - 1)
    if boss == 'league':
        return min(100, 40 + margin + bump), min(100, 30 + margin + bump)
    seen = entry['level'] if entry else 0
    best = seen if randomized else max([level for _, level in ROSTERS[boss]] + [seen])
    if not best:
        return None
    return (min(100, best + margin // 2 + bump),
            max(2, min(100, best - 5 + (margin - 10) // 2 + bump)))


def wanted(data, snapshot, boss, targets, roster, raised=()):
    """The team member to train and the level it needs, or None when the team is ready."""
    team = choose(data, snapshot.party, roster, boss, raised) if roster else []
    if not team:
        return None
    lead, partners = targets
    behind = sorted((mon for mon in team[1:] if mon.level < partners), key=lambda mon: (mon.level, strength(mon)))
    if behind:
        return behind[0], partners
    if team[0].level < lead:
        return team[0], lead
    return None


def randomized_trainers():
    """Whether this run's share code randomizes trainer parties, so the written rosters are wrong."""
    import os
    from ..randomized import ENV
    code = os.environ.get(ENV, '')
    if not code:
        return False
    from pokecore.randomizer import decode_share_code
    try:
        return bool(decode_share_code(code)[2].trainers)
    except ValueError:
        return True


def goal(policy, snapshot, mem, Goal, boss):
    """A training goal before the gym leader or League ``boss``, or None to challenge now."""
    from ..caution import keep_training, margin
    from .losses import LEAGUE, records
    state = policy.collection
    project = state.get('training')
    need = None
    where = ROUTES.get(boss)
    if (where in policy.data.map_ids and not snapshot.hall_of_fame_count
            and not policy.in_league(snapshot)):
        entry = records(policy).get(LEAGUE if boss == 'league' else boss)
        randomized = randomized_trainers()
        targets = levels(boss, entry, margin(), randomized)
        roster = ROSTERS[boss]
        if randomized:
            roster = tuple((mon.species, 0) for mon in snapshot.party if not mon.egg)[:1] or roster
        if targets:
            need = wanted(policy.data, snapshot, boss, targets, roster, state.get('team_raised', ()))
    if need is None or not keep_training(f'team_{boss}', snapshot.frame):
        if project and project.get('team'):
            state['training'] = None
        return None
    mon, level = need
    key = identity(mon)
    raised = state.setdefault('team_raised', [])
    if key not in raised:
        raised.append(key)
        del raised[:-12]
    if not (project and project.get('team') == boss and project['identity'] == key
            and project.get('level_goal') == level):
        state['training'] = {'identity': key, 'target': mon.species, 'item': None, 'species': mon.species,
                             'terminal': True, 'level_goal': level, 'team': boss, 'map': where}
    return train(policy, snapshot, mem, Goal)
