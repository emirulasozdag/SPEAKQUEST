"""Story Engine (dynamic story).

Planned responsibilities: track location, chapter and story flags, apply player decisions,
update NPC trust scores, check quest unlock conditions and decide which ending is reached.
The AI may suggest a story action; this engine decides whether it is allowed.

So far this module holds the one rule everything else asks: is_unlocked(). Quests and endings
both describe what they need as Conditions, and every unlock decision goes through this function,
so adding flags and trust (#13, #17) changes the data fed into it, not its callers.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.content.schema import Conditions


@dataclass(frozen=True)
class StoryProgress:
    """What is known about one player when deciding what is unlocked for them."""

    completed_quests: frozenset[str] = frozenset()
    # Flags are set by decisions the player made (#17); empty until the Story Engine stores them
    flags: frozenset[str] = frozenset()
    # NPC trust 0-100 by NPC slug; a missing NPC counts as 0 (#13 fills this from the database)
    trust: Mapping[str, int] = field(default_factory=dict)


def is_unlocked(conditions: Conditions, progress: StoryProgress) -> bool:
    """True when every listed condition holds. No conditions means always unlocked."""
    return (
        all(slug in progress.completed_quests for slug in conditions.quests_completed)
        and all(flag in progress.flags for flag in conditions.flags)
        and all(progress.trust.get(npc, 0) >= minimum for npc, minimum in conditions.min_trust.items())
    )
