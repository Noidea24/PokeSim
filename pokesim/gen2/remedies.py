"""Noidea24 fork, revised agent: pick the cheapest item that does the job, and keep Full Restores for when it counts.

The original reached for a Full Restore first whenever a Pokémon was hurt or had a status, so a
Potion's worth of damage or a poisoning at nearly full health spent one. By the League the bag was
out of them and later poisonings got Potions too late. Now:

- Damage: the smallest potion that heals all of it, then a Max Potion, then a Full Restore, and only
  when nothing heals all of it, the biggest potion left.
- A status alone: its own cure, then Full Heal. A Full Restore only in battle, where a status left
  alone can cost the fight. Outside battle a Pokémon Center cures it, and in Gold, Silver and Crystal
  poison stops at 1 HP outside battle.
- Damage and a status together in battle: a Full Restore first, since it fixes both in one turn.
"""

HEALS = (('POTION', 20), ('SUPER_POTION', 50), ('HYPER_POTION', 200))


def cure(status):
    return ('ANTIDOTE' if status & 8 else 'AWAKENING' if status & 7 else 'PARLYZ_HEAL' if status & 64
            else 'BURN_HEAL' if status & 16 else 'ICE_HEAL')


def healing(missing, *, status=False, in_battle=False):
    """Healing item names in the order to try them for ``missing`` HP."""
    covering = [name for name, amount in HEALS if amount >= missing]
    partial = [name for name, amount in reversed(HEALS) if amount < missing]
    order = covering + ['MAX_POTION', 'FULL_RESTORE'] + partial
    if status and in_battle:
        order.remove('FULL_RESTORE')
        order.insert(0, 'FULL_RESTORE')
    return tuple(order)


def curing(status, *, in_battle=False):
    """Status cure names in the order to try them."""
    return (cure(status), 'FULL_HEAL') + (('FULL_RESTORE',) if in_battle else ())
