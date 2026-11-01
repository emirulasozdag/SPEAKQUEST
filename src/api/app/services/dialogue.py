"""A quest's conversation: stored messages, read back only by the player who wrote them, and one
dialogue turn (player message -> AI analysis -> stored messages, learning records, story).

There is no separate session table: a player's quest_progress row for a quest is that quest's
dialogue session, so every message belongs to exactly one player through it. The NPC's opening
line is stored as the first message when the quest is started (services/quests.start_quest).
"""

import logging
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engines.categories import SkillCategory
from app.engines.learning import DetectedMistake, record_message_analysis
from app.engines.objectives import apply_objectives
from app.engines.story import StoryActionOutcome, StoryProgress
from app.models.content import Npc, QuestTemplate
from app.models.dialogue import PLAYER_MESSAGE_MAX_LENGTH, DialogueMessage, MessageRole
from app.models.learning import LanguageError
from app.models.player import EnglishLevel
from app.models.quest_progress import QuestProgress
from app.services.ai.analysis import analyze_message
from app.services.ai.client import AiClient
from app.services.ai.prompts import (
    MAX_HISTORY_MESSAGES,
    DialogueContext,
    HistoryLine,
    NpcProfile,
    ObjectiveBrief,
    QuestBrief,
)
from app.services.ai.schemas import DialogueAnalysis
from app.services.players import get_profile
from app.services.quests import get_active_quest
from app.services.story import apply_suggested_action, get_story_state, load_story_progress

logger = logging.getLogger("speakquest.dialogue")


class DialogueNotFoundError(Exception):
    """The quest does not exist or this player has never started it."""


class MessageRefusedError(Exception):
    """The message cannot be sent. `reason` is stable, `message` is for the player."""

    def __init__(
        self, reason: Literal["empty", "too_long", "no_active_quest", "no_character"], message: str
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class DialogueTurn:
    """The result of one player message.

    When the AI was unavailable, status is "ai_unavailable", npc_reply is the safe fallback line
    and nothing was stored: the player can simply send the message again.
    """

    status: Literal["ok", "ai_unavailable"]
    quest_id: int
    npc_reply: str
    analysis: DialogueAnalysis | None = None
    player_message: DialogueMessage | None = None
    npc_message: DialogueMessage | None = None
    story: StoryActionOutcome | None = None
    # Every objective of the quest with its state after this message; empty when the AI was unavailable
    objectives: tuple["ObjectiveState", ...] = ()
    newly_met: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObjectiveState:
    id: str
    description: str
    met: bool


def get_history(db: Session, user_id: int, quest_id: int) -> list[DialogueMessage]:
    """The player's messages for one quest, oldest first."""
    progress_id = db.scalar(
        select(QuestProgress.id).where(QuestProgress.user_id == user_id, QuestProgress.quest_template_id == quest_id)
    )
    if progress_id is None:
        raise DialogueNotFoundError
    return _messages_of(db, progress_id)


def get_corrections(db: Session, user_id: int, message_ids: list[int]) -> dict[int, list[LanguageError]]:
    """The mistakes found in the given messages of this player, by message id, oldest first."""
    if not message_ids:
        return {}
    errors = db.scalars(
        select(LanguageError)
        .where(LanguageError.user_id == user_id, LanguageError.message_id.in_(message_ids))
        .order_by(LanguageError.id)
    )
    by_message: dict[int, list[LanguageError]] = {}
    for error in errors:
        by_message.setdefault(error.message_id, []).append(error)
    return by_message


MAX_SUMMARY_EXAMPLES = 3


@dataclass(frozen=True)
class ConversationSummary:
    """What the conversation of one quest showed, from stored data only."""

    messages_sent: int
    # Messages the NPC understood; communication is judged apart from grammar
    understood: int
    mistakes: int
    # The most frequent mistake category; None when there were no mistakes
    top_category: str | None
    # Up to MAX_SUMMARY_EXAMPLES corrections, one per category first (most frequent category first)
    examples: tuple[LanguageError, ...]


def get_summary(db: Session, user_id: int, quest_id: int) -> ConversationSummary:
    """Summarise the player's own conversation for a quest they started."""
    messages = [message for message in get_history(db, user_id, quest_id) if message.role == MessageRole.PLAYER]
    errors = [error for found in get_corrections(db, user_id, [m.id for m in messages]).values() for error in found]
    return summarize(messages, errors)


def summarize(messages: list[DialogueMessage], errors: list[LanguageError]) -> ConversationSummary:
    """Pure aggregation over already loaded player messages and their mistakes."""
    counts = Counter(error.category for error in errors)
    # Most frequent category first; the category name only makes ties deterministic
    ranked = sorted(counts, key=lambda category: (-counts[category], category))
    # Newest mistake first within a category, so the example is what the player did last
    newest = sorted(errors, key=lambda error: -error.id)
    one_each = [next(error for error in newest if error.category == category) for category in ranked]
    rest = [error for error in newest if error not in one_each]
    return ConversationSummary(
        messages_sent=len(messages),
        understood=sum(1 for message in messages if message.communication_success),
        mistakes=len(errors),
        top_category=ranked[0] if ranked else None,
        examples=tuple((one_each + rest)[:MAX_SUMMARY_EXAMPLES]),
    )


def send_message(db: Session, user_id: int, text: str, client: AiClient | None) -> DialogueTurn:
    """Answer one player message in the active quest.

    The AI only analyses and suggests. Everything that changes the game happens here, in one
    transaction, and only after the AI reply was validated: both messages are stored, the Learning
    Engine records the mistakes, and the Story Engine accepts or refuses the suggested action.
    If the AI fails, nothing is stored and nothing changes.
    """
    text = text.strip()
    if not text:
        raise MessageRefusedError("empty", "Write a message first.")
    if len(text) > PLAYER_MESSAGE_MAX_LENGTH:
        raise MessageRefusedError("too_long", f"Keep your message under {PLAYER_MESSAGE_MAX_LENGTH} characters.")
    profile = get_profile(db, user_id)
    if profile is None:
        raise MessageRefusedError("no_character", "Create your character first.")
    active = get_active_quest(db, user_id)
    if active is None:
        raise MessageRefusedError("no_active_quest", "Start a quest before talking to someone.")

    quest, progress = active.quest, active.progress
    context = _dialogue_context(db, user_id, quest, progress, EnglishLevel(profile.english_level))
    result = analyze_message(client, context, text)
    if not result.ok:
        return DialogueTurn(status="ai_unavailable", quest_id=quest.id, npc_reply=result.npc_reply)

    analysis = result.analysis
    player_message = DialogueMessage(
        quest_progress_id=progress.id,
        role=MessageRole.PLAYER,
        text=text,
        communication_success=analysis.communication_success,
    )
    db.add(player_message)
    db.flush()
    record_message_analysis(
        db,
        user_id,
        player_message.id,
        mistakes=[
            DetectedMistake(e.category, e.original, e.corrected, e.explanation) for e in analysis.detected_errors
        ],
        correctly_used=[SkillCategory(c) for c in analysis.correctly_used],
    )
    # Only a suggestion: the Story Engine checks it against the quest's allowed actions
    story = apply_suggested_action(db, user_id, quest, analysis.suggested_story_action)
    outcome = apply_objectives(
        [objective["id"] for objective in quest.objectives],
        progress.objectives_met,
        analysis.objectives_met,
        analysis.communication_success,
    )
    if outcome.unknown:
        # Ids only (capped), never the reply: the AI named objectives this quest does not have
        logger.warning("ai reported unknown objective ids quest=%s ids=%s", quest.slug, list(outcome.unknown[:5]))
    if outcome.newly_met:
        # A new list, so SQLAlchemy sees the JSON column change
        progress.objectives_met = list(outcome.met)
    npc_message = DialogueMessage(quest_progress_id=progress.id, role=MessageRole.NPC, text=analysis.npc_reply)
    db.add(npc_message)
    db.commit()
    return DialogueTurn(
        status="ok",
        quest_id=quest.id,
        npc_reply=analysis.npc_reply,
        analysis=analysis,
        player_message=player_message,
        npc_message=npc_message,
        story=story,
        objectives=tuple(
            ObjectiveState(objective["id"], objective["description"], objective["id"] in outcome.met)
            for objective in quest.objectives
        ),
        newly_met=outcome.newly_met,
    )


def _dialogue_context(
    db: Session, user_id: int, quest: QuestTemplate, progress: QuestProgress, level: EnglishLevel
) -> DialogueContext:
    """Only what the prompt needs: no ids, e-mails or other players ever reach the AI."""
    npc: Npc = quest.npc
    recent = _messages_of(db, progress.id)[-MAX_HISTORY_MESSAGES:]
    return DialogueContext(
        # The quest's own facts are added, so story events reach the NPC only in their own quest
        npc=NpcProfile(npc.name, npc.role, npc.personality, npc.speaking_style, (*npc.knows, *quest.npc_knows)),
        quest=QuestBrief(
            title=quest.title,
            summary=quest.summary,
            objectives=tuple(
                ObjectiveBrief(objective["id"], objective["description"]) for objective in quest.objectives
            ),
            allowed_story_actions=tuple(quest.allowed_story_actions),
        ),
        level=level,
        story_summary=_story_summary(db, user_id, npc),
        history=tuple(HistoryLine(speaker=m.role, text=m.text) for m in recent),
        objectives_met=tuple(progress.objectives_met),
    )


def _story_summary(db: Session, user_id: int, npc: Npc) -> str:
    """A few plain sentences about the story so far, without spoilers of what comes next."""
    state = get_story_state(db, user_id)
    progress: StoryProgress = load_story_progress(db, user_id)
    sentences = [f"Chapter {state.chapter if state else 1}."]
    if progress.completed_quests:
        titles = db.scalars(
            select(QuestTemplate.title)
            .where(QuestTemplate.slug.in_(progress.completed_quests))
            .order_by(QuestTemplate.chapter, QuestTemplate.id)
        )
        sentences.append(f"The player has already done: {', '.join(titles)}.")
    trust = progress.trust.get(npc.slug, 0)
    if trust >= 30:
        sentences.append(f"{npc.name} trusts the player and sees them as a friend.")
    elif trust >= 10:
        sentences.append(f"{npc.name} knows the player a little and likes them.")
    else:
        sentences.append(f"{npc.name} has only just met the player.")
    return " ".join(sentences)


def _messages_of(db: Session, quest_progress_id: int) -> list[DialogueMessage]:
    # Ordered by id, not created_at: two messages saved in the same request share a timestamp
    return list(
        db.scalars(
            select(DialogueMessage)
            .where(DialogueMessage.quest_progress_id == quest_progress_id)
            .order_by(DialogueMessage.id)
        )
    )
