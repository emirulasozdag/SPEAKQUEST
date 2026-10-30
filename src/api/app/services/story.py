"""Loading and storing one player's story state for the Story Engine (engines/story.py).

The engine works on StoryProgress values; this module turns story_states, npc_relationships and
quest_progress rows into one and writes the engine's result back. Functions that change the
state do not commit: they run inside the caller's transaction (quest completion, the dialogue
flow in #12), so a failure there leaves the story untouched.
"""

from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.engines.story import QuestRules, StoryActionOutcome, StoryProgress, apply_story_action, apply_trust_changes
from app.models.content import Npc, QuestTemplate
from app.models.quest_progress import QuestProgress, QuestProgressStatus
from app.models.story import NpcRelationship, StoryState


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


def apply_suggested_action(db: Session, user_id: int, quest: QuestTemplate, action: str) -> StoryActionOutcome:
    """Let the Story Engine accept or refuse the AI's suggested action and store what it changed.

    For the dialogue flow (#12). Does not commit.
    """
    rules = QuestRules(npc=quest.npc.slug, allowed_story_actions=frozenset(quest.allowed_story_actions))
    outcome = apply_story_action(StoryProgress(trust=load_trust(db, user_id)), rules, action)
    if outcome.trust_change:
        _store_trust(db, user_id, {rules.npc: outcome.progress.trust[rules.npc]})
    return outcome


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
