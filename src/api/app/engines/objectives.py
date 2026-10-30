"""Objectives engine: decides which quest objectives one message fulfils.

The AI only reports which objective ids it thinks a message fulfils; this module decides what
counts. It is a pure function over values (no database, no AI), like the Story Engine, so every
rule can be tested directly. services/dialogue.py stores the result in quest_progress.objectives_met.

Rules:
- Only ids that belong to this quest count. Unknown ids, including ids of other quests, are ignored
  and handed back so the caller can log them.
- Only a message the NPC understood (communication_success) can fulfil an objective. Grammar
  mistakes never block one: a learner is judged on being understood, not on being perfect.
- An objective that is met stays met. Nothing here ever removes one.
"""

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class ObjectiveOutcome:
    # Every met objective id of the quest after this message, in the quest's own order
    met: tuple[str, ...]
    # Ids met by this message for the first time
    newly_met: tuple[str, ...]
    # Quest objective ids still open, in the quest's own order
    remaining: tuple[str, ...]
    # Reported ids that are not objectives of this quest (for logging, never stored)
    unknown: tuple[str, ...]


def apply_objectives(
    quest_objective_ids: Iterable[str],
    already_met: Iterable[str],
    reported: Iterable[str],
    communication_success: bool,
) -> ObjectiveOutcome:
    """Merge the objectives an AI reply reports into what the player has already met."""
    quest_ids = tuple(quest_objective_ids)
    valid = set(quest_ids)
    reported_ids = tuple(dict.fromkeys(reported))

    unknown = tuple(item for item in reported_ids if item not in valid)
    before = {item for item in already_met if item in valid}
    fulfilled = {item for item in reported_ids if item in valid} if communication_success else set()

    after = before | fulfilled
    return ObjectiveOutcome(
        met=tuple(item for item in quest_ids if item in after),
        newly_met=tuple(item for item in quest_ids if item in fulfilled and item not in before),
        remaining=tuple(item for item in quest_ids if item not in after),
        unknown=unknown,
    )
