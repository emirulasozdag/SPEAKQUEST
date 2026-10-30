"""Story Engine (dynamic story).

Tracks chapter, flags and NPC trust, decides which story actions the AI may trigger and checks
quest unlock conditions. Everything in this module is a pure function over StoryProgress (values
in, new values out), so it can be tested without a database; services/story.py loads and stores it.

The AI may suggest a story action; apply_story_action() decides whether it is allowed and what
it changes. Quests and endings both describe what they need as Conditions, and every unlock
decision goes through is_unlocked().
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace

from app.content.schema import Conditions
# Re-exported so callers of the Story Engine find the trust bounds here
from app.engines.trust import TRUST_MAX, TRUST_MIN, clamp_trust

# Story actions that make the quest's NPC like the player a little more. Every other allowed action
# (continue, npc_confused, interview_concern) only colours the conversation and changes nothing:
# a language learner is never punished in the story for being misunderstood.
TRUST_RAISING_ACTIONS = frozenset({"npc_pleased", "order_taken", "viewing_positive", "interview_positive", "clue_found"})
# The most trust one AI-suggested action can add. Decisions (+15) and quest rewards (+5/+10) are
# what move the story; a pleased NPC is only a small bonus on top.
ACTION_TRUST_STEP = 2


@dataclass(frozen=True)
class StoryProgress:
    """What is known about one player when deciding what is unlocked for them."""

    completed_quests: frozenset[str] = frozenset()
    # Flags are set by decisions the player made (#17)
    flags: frozenset[str] = frozenset()
    # NPC trust 0-100 by NPC slug; a missing NPC counts as 0
    trust: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class QuestRules:
    """The parts of a quest template the Story Engine needs."""

    npc: str
    allowed_story_actions: frozenset[str]


@dataclass(frozen=True)
class StoryActionOutcome:
    action: str
    # False when the quest template does not allow this action; nothing changes then
    accepted: bool
    progress: StoryProgress
    # Trust actually added to the quest's NPC, after clamping (0 when nothing changed)
    trust_change: int = 0


def is_unlocked(conditions: Conditions, progress: StoryProgress) -> bool:
    """True when every listed condition holds. No conditions means always unlocked."""
    return (
        all(slug in progress.completed_quests for slug in conditions.quests_completed)
        and all(flag in progress.flags for flag in conditions.flags)
        and all(progress.trust.get(npc, 0) >= minimum for npc, minimum in conditions.min_trust.items())
    )


def apply_story_action(progress: StoryProgress, quest: QuestRules, action: str) -> StoryActionOutcome:
    """Apply an AI-suggested story action if the quest allows it.

    An action that is not in the quest's allowed_story_actions is refused and changes nothing,
    whatever the AI claims. An allowed action changes at most the quest NPC's trust, by at most
    ACTION_TRUST_STEP, and never beyond TRUST_MAX.
    """
    if action not in quest.allowed_story_actions:
        return StoryActionOutcome(action=action, accepted=False, progress=progress)
    if action not in TRUST_RAISING_ACTIONS:
        return StoryActionOutcome(action=action, accepted=True, progress=progress)

    updated = apply_trust_changes(progress, {quest.npc: ACTION_TRUST_STEP})
    change = updated.trust.get(quest.npc, 0) - progress.trust.get(quest.npc, 0)
    return StoryActionOutcome(action=action, accepted=True, progress=updated, trust_change=change)


def apply_trust_changes(progress: StoryProgress, changes: Mapping[str, int]) -> StoryProgress:
    """Add trust changes (from quest rewards or decisions), keeping every value within 0-100."""
    if not changes:
        return progress
    trust = dict(progress.trust)
    for npc, change in changes.items():
        trust[npc] = clamp_trust(trust.get(npc, 0) + change)
    return replace(progress, trust=trust)


def current_chapter(open_quest_chapters: Iterable[int], completed_quest_chapters: Iterable[int]) -> int:
    """The chapter the player is in: the earliest chapter that still has a quest to play.

    Open quests are the available and active ones. When none are left, the player stays in the
    last chapter they finished; a new player is in chapter 1.
    """
    open_chapters = list(open_quest_chapters)
    if open_chapters:
        return min(open_chapters)
    return max(completed_quest_chapters, default=1)
