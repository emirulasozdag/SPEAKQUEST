"""Loading and storing one player's story state for the Story Engine (engines/story.py).

The engine works on StoryProgress values; this module turns story_states, npc_relationships and
quest_progress rows into one and writes the engine's result back. Functions that change the
state do not commit: they run inside the caller's transaction (quest completion, the dialogue
flow in #12), so a failure there leaves the story untouched.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.content.schema import DecisionPoint, Ending, load_content
from app.engines.story import (
    QuestRules,
    StoryActionOutcome,
    StoryProgress,
    apply_decision,
    apply_story_action,
    apply_trust_changes,
    choose_ending,
)
from app.models.content import Npc, QuestTemplate
from app.models.quest_progress import QuestProgress, QuestProgressStatus
from app.models.story import NpcRelationship, StoryDecision, StoryState


def new_story_state(user_id: int) -> StoryState:
    """The starting state of a new character: chapter 1, no flags, no trust yet."""
    return StoryState(user_id=user_id, chapter=1, flags=[])


def get_story_state(db: Session, user_id: int) -> StoryState | None:
    return db.scalar(
        select(StoryState).where(StoryState.user_id == user_id).options(selectinload(StoryState.current_location))
    )


def load_trust(db: Session, user_id: int) -> dict[str, int]:
    """Trust by NPC slug. NPCs without a row are left out and count as 0."""
    rows = db.execute(
        select(Npc.slug, NpcRelationship.trust)
        .join(NpcRelationship, NpcRelationship.npc_id == Npc.id)
        .where(NpcRelationship.user_id == user_id)
    )
    return dict(rows.tuples().all())


def load_story_progress(db: Session, user_id: int) -> StoryProgress:
    """Everything the Story Engine needs about this player: completed quests, flags and trust."""
    completed = db.scalars(
        select(QuestTemplate.slug)
        .join(QuestProgress, QuestProgress.quest_template_id == QuestTemplate.id)
        .where(QuestProgress.user_id == user_id, QuestProgress.status == QuestProgressStatus.COMPLETED)
    )
    state = get_story_state(db, user_id)
    return StoryProgress(
        completed_quests=frozenset(completed),
        flags=frozenset(state.flags) if state else frozenset(),
        trust=load_trust(db, user_id),
    )


def add_trust(db: Session, user_id: int, changes: Mapping[str, int]) -> dict[str, int]:
    """Apply trust changes by NPC slug through the Story Engine (clamped to 0-100) and store them.

    Returns the new trust of every changed NPC. Does not commit.
    """
    before = load_trust(db, user_id)
    after = apply_trust_changes(StoryProgress(trust=before), changes).trust
    _store_trust(db, user_id, {npc: after[npc] for npc in changes})
    return {npc: after[npc] for npc in changes}


def apply_suggested_action(
    db: Session, user_id: int, quest: QuestTemplate, action: str, progress: QuestProgress
) -> StoryActionOutcome:
    """Let the Story Engine accept or refuse the AI's suggested action and store what it changed.

    progress is the quest's own row: it counts the trust the conversation has added so far, so the
    per-quest cap holds however many messages the player sends. For the dialogue flow (#12).
    Does not commit.
    """
    rules = QuestRules(npc=quest.npc.slug, allowed_story_actions=frozenset(quest.allowed_story_actions))
    outcome = apply_story_action(
        StoryProgress(trust=load_trust(db, user_id)), rules, action, gained_in_quest=progress.story_trust_gained
    )
    if outcome.trust_change:
        _store_trust(db, user_id, {rules.npc: outcome.progress.trust[rules.npc]})
        progress.story_trust_gained += outcome.trust_change
    return outcome


def open_decision_ids(db: Session, user_id: int, quest: QuestTemplate) -> list[str]:
    """The quest's decision points the player has not made yet, in template order."""
    made = set(
        db.scalars(
            select(StoryDecision.decision_key).where(
                StoryDecision.user_id == user_id, StoryDecision.quest_template_id == quest.id
            )
        )
    )
    return [point["id"] for point in quest.decision_points if point["id"] not in made]


def list_relationships(db: Session, user_id: int) -> list[tuple[Npc, int]]:
    """Every NPC with this player's trust, in content order; NPCs without a row have trust 0."""
    trust = load_trust(db, user_id)
    return [(npc, trust.get(npc.slug, 0)) for npc in db.scalars(select(Npc).order_by(Npc.id))]


def _store_trust(db: Session, user_id: int, trust: Mapping[str, int]) -> None:
    npc_ids = dict(db.execute(select(Npc.slug, Npc.id).where(Npc.slug.in_(trust))).tuples().all())
    rows = {
        row.npc_id: row
        for row in db.scalars(select(NpcRelationship).where(NpcRelationship.user_id == user_id))
    }
    for slug, value in trust.items():
        npc_id = npc_ids[slug]
        if npc_id in rows:
            rows[npc_id].trust = value
        else:
            db.add(NpcRelationship(user_id=user_id, npc_id=npc_id, trust=value))
    db.flush()


class DecisionRefusedError(Exception):
    """Why a decision cannot be made. reason: not_found, not_started, invalid or already_made."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class QuestDecision:
    point: DecisionPoint
    # The option the player chose, or None while the decision is still open
    chosen: str | None


@dataclass(frozen=True)
class DecisionResult:
    flags: frozenset[str]
    # New trust of every NPC the decision changed, by NPC slug
    trust: dict[str, int]


def list_decisions(db: Session, user_id: int, quest_id: int) -> list[QuestDecision]:
    """The quest's decision points and what the player chose so far. The quest must be started."""
    quest = _load_started_quest(db, user_id, quest_id)
    chosen = dict(
        db.execute(
            select(StoryDecision.decision_key, StoryDecision.choice).where(
                StoryDecision.user_id == user_id, StoryDecision.quest_template_id == quest.id
            )
        ).tuples().all()
    )
    return [QuestDecision(point, chosen.get(point.id)) for point in _decision_points(quest)]


def make_decision(db: Session, user_id: int, quest_id: int, decision_id: str, option_id: str) -> DecisionResult:
    """Record a decision once and apply its flags and trust through the Story Engine. Commits."""
    quest = _load_started_quest(db, user_id, quest_id)
    point = next((p for p in _decision_points(quest) if p.id == decision_id), None)
    option = next((o for o in point.options if o.id == option_id), None) if point else None
    if option is None:
        raise DecisionRefusedError("invalid", "This quest has no such decision or option.")
    state = get_story_state(db, user_id)
    if state is None:
        raise DecisionRefusedError("not_started", "Create your character first.")
    if state.ending is not None:
        raise DecisionRefusedError("story_ended", "Your story has ended. Reset your progress to play again.")
    if _decision_exists(db, user_id, quest.id, decision_id):
        raise _already_made()

    before = StoryProgress(flags=frozenset(state.flags), trust=load_trust(db, user_id))
    after = apply_decision(before, option.effects)
    db.add(StoryDecision(user_id=user_id, quest_template_id=quest.id, decision_key=decision_id, choice=option_id))
    # A new list, so SQLAlchemy sees the JSON column change
    state.flags = sorted(after.flags)
    changed = {npc: after.trust[npc] for npc in option.effects.trust}
    try:
        _store_trust(db, user_id, changed)
        db.commit()
    except IntegrityError:
        # The same decision sent twice at once: the unique constraint lets only one through
        db.rollback()
        raise _already_made() from None
    return DecisionResult(flags=after.flags, trust=changed)


@dataclass(frozen=True)
class MadeDecision:
    quest: QuestTemplate
    point: DecisionPoint
    # The label of the option the player chose
    choice: str


def made_decisions(db: Session, user_id: int) -> list[MadeDecision]:
    """Every decision the player made, in the order they made them; for the ending screen."""
    rows = db.execute(
        select(StoryDecision, QuestTemplate)
        .join(QuestTemplate, QuestTemplate.id == StoryDecision.quest_template_id)
        .where(StoryDecision.user_id == user_id)
        .order_by(StoryDecision.id)
    ).tuples()
    made = []
    for decision, quest in rows:
        point = next((p for p in _decision_points(quest) if p.id == decision.decision_key), None)
        option = next((o for o in point.options if o.id == decision.choice), None) if point else None
        # A decision whose point was later removed from the content is left out
        if option is not None:
            made.append(MadeDecision(quest, point, option.label))
    return made


@cache
def content_endings() -> tuple[Ending, ...]:
    """Endings come straight from endings.json; they are not stored in the database."""
    return tuple(load_content().endings)


def reached_ending(db: Session, user_id: int) -> Ending | None:
    """The ending stored when the player's story closed, or None while it goes on."""
    state = get_story_state(db, user_id)
    if state is None or state.ending is None:
        return None
    return next((ending for ending in content_endings() if ending.slug == state.ending), None)


def ending_for(db: Session, user_id: int) -> Ending:
    """The ending this player's story leads to now, decided by the Story Engine's choose_ending()."""
    return choose_ending(content_endings(), load_story_progress(db, user_id))


def _load_started_quest(db: Session, user_id: int, quest_id: int) -> QuestTemplate:
    quest = db.get(QuestTemplate, quest_id)
    if quest is None:
        raise DecisionRefusedError("not_found", "Quest not found.")
    started = db.scalar(
        select(QuestProgress.id).where(QuestProgress.user_id == user_id, QuestProgress.quest_template_id == quest.id)
    )
    if started is None:
        raise DecisionRefusedError("not_started", "Start this quest before making its decisions.")
    return quest


def _decision_points(quest: QuestTemplate) -> list[DecisionPoint]:
    return [DecisionPoint.model_validate(point) for point in quest.decision_points]


def _decision_exists(db: Session, user_id: int, quest_id: int, decision_id: str) -> bool:
    return (
        db.scalar(
            select(StoryDecision.id).where(
                StoryDecision.user_id == user_id,
                StoryDecision.quest_template_id == quest_id,
                StoryDecision.decision_key == decision_id,
            )
        )
        is not None
    )


def _already_made() -> DecisionRefusedError:
    return DecisionRefusedError("already_made", "You already made this decision.")
