"""Adaptive Quest Engine: picks the next quest for one player, and says why.

The choice is never random. Candidates are the quests whose prerequisites the Story Engine says
are met and that the player has not started yet. Each candidate gets points, every part of which
can be explained to the player:

- skill match: the quest practises the skill the Learning Engine wants next
  (choose_learning_target); while there is too little data about the player, the skills of
  their learning goal from character creation are used instead
- other weak skills the quest also practises
- level fit: the quest is meant for the player's English level
- NPC relationship: an NPC who already trusts the player pulls them back
- recent topics: skills the player has just practised (other than the target) count a little less

Ties go to the earlier chapter, so the story is played in order, and then to content order.
Everything here is a pure function over values; services/quests.py loads them.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from app.content.schema import Conditions
from app.engines.categories import SkillCategory
from app.engines.learning import SkillScore, SkillStatus, TargetReason, choose_learning_target
from app.engines.story import StoryProgress, is_unlocked
from app.models.player import EnglishLevel, LearningGoal

# Below this many skill opportunities in total, the player's learning goal decides the skill
MIN_OBSERVATIONS = 5

TARGET_SKILL_POINTS = 40
OTHER_WEAK_SKILL_POINTS = 10
LEVEL_FIT_POINTS = 10
LEVEL_MISFIT_POINTS = -30
# Trust 0-100 adds 0-10 points
TRUST_POINTS_PER = 10
RECENT_TOPIC_POINTS = -5

# The skills each learning goal from the character form stands for
GOAL_SKILLS: Mapping[LearningGoal, tuple[SkillCategory, ...]] = {
    LearningGoal.EVERYDAY: (SkillCategory.VOCABULARY_USAGE, SkillCategory.PREPOSITIONS),
    LearningGoal.WORK: (SkillCategory.PAST_SIMPLE,),
    LearningGoal.GRAMMAR: (SkillCategory.QUESTION_FORMATION, SkillCategory.PRESENT_SIMPLE),
}
GOAL_LABELS: Mapping[LearningGoal, str] = {
    LearningGoal.EVERYDAY: "everyday conversation",
    LearningGoal.WORK: "job interviews and work",
    LearningGoal.GRAMMAR: "grammar accuracy",
}
SKILL_LABELS: Mapping[SkillCategory, str] = {
    SkillCategory.PRESENT_SIMPLE: "Present Simple",
    SkillCategory.PAST_SIMPLE: "Past Simple",
    SkillCategory.QUESTION_FORMATION: "Question Formation",
    SkillCategory.PREPOSITIONS: "Prepositions",
    SkillCategory.VOCABULARY_USAGE: "Vocabulary Usage",
}
_LEVEL_ORDER = list(EnglishLevel)


@dataclass(frozen=True)
class QuestCandidate:
    """The parts of a quest template the engine needs."""

    slug: str
    title: str
    npc: str
    npc_name: str
    chapter: int
    target_skills: tuple[SkillCategory, ...]
    min_level: EnglishLevel
    max_level: EnglishLevel
    prerequisites: Conditions = field(default_factory=Conditions)


@dataclass(frozen=True)
class PlayerSnapshot:
    """What the engine knows about one player."""

    level: EnglishLevel
    goal: LearningGoal
    # From the Learning Engine, one score per category
    skills: Mapping[SkillCategory, SkillScore]
    story: StoryProgress
    # Quests the player has started or completed: never candidates
    started: frozenset[str] = frozenset()


@dataclass(frozen=True)
class QuestRecommendation:
    slug: str
    title: str
    points: int
    # One or two sentences for the player
    reason: str
    # How the points were made up, by part, for tests and debugging
    breakdown: Mapping[str, int]


def candidates_for(player: PlayerSnapshot, quests: Iterable[QuestCandidate]) -> list[QuestCandidate]:
    """Quests the player could start now: prerequisites met and not started yet."""
    return [
        quest
        for quest in quests
        if quest.slug not in player.started and is_unlocked(quest.prerequisites, player.story)
    ]


def rank_quests(player: PlayerSnapshot, quests: Sequence[QuestCandidate]) -> list[QuestRecommendation]:
    """Every candidate with its points, best first. Deterministic for the same input."""
    focus, focus_reason = _focus(player)
    order = {quest.slug: index for index, quest in enumerate(quests)}
    scored = []
    for quest in candidates_for(player, quests):
        breakdown = _breakdown(player, quest, focus)
        scored.append((quest, breakdown))
    scored.sort(key=lambda item: (-sum(item[1].values()), item[0].chapter, order[item[0].slug]))
    return [
        QuestRecommendation(
            slug=quest.slug,
            title=quest.title,
            points=sum(breakdown.values()),
            reason=_reason(player, quest, focus, focus_reason),
            breakdown=breakdown,
        )
        for quest, breakdown in scored
    ]


def choose_next_quest(player: PlayerSnapshot, quests: Sequence[QuestCandidate]) -> QuestRecommendation | None:
    """The quest to play next, or None when nothing can be started."""
    ranking = rank_quests(player, quests)
    return ranking[0] if ranking else None


def has_enough_data(skills: Mapping[SkillCategory, SkillScore]) -> bool:
    return sum(score.opportunities for score in skills.values()) >= MIN_OBSERVATIONS


def _focus(player: PlayerSnapshot) -> tuple[tuple[SkillCategory, ...], str]:
    """The skills the next quest should practise, and why (a TargetReason value or "goal")."""
    if not has_enough_data(player.skills):
        return GOAL_SKILLS[player.goal], "goal"
    target = choose_learning_target(player.skills, player.level)
    return (target.category,), target.reason.value


def _breakdown(player: PlayerSnapshot, quest: QuestCandidate, focus: tuple[SkillCategory, ...]) -> dict[str, int]:
    skills = set(quest.target_skills)
    weak_others = [
        skill
        for skill in skills - set(focus)
        if (score := player.skills.get(skill)) is not None and (score.status == SkillStatus.WEAK or score.repeated)
    ]
    recent_others = [
        skill
        for skill in skills - set(focus)
        if (score := player.skills.get(skill)) is not None and score.practised_recently
    ]
    fits = _LEVEL_ORDER.index(quest.min_level) <= _LEVEL_ORDER.index(player.level) <= _LEVEL_ORDER.index(
        quest.max_level
    )
    return {
        "skill_match": TARGET_SKILL_POINTS if skills & set(focus) else 0,
        "other_weak_skills": OTHER_WEAK_SKILL_POINTS * len(weak_others),
        "level_fit": LEVEL_FIT_POINTS if fits else LEVEL_MISFIT_POINTS,
        "npc_trust": player.story.trust.get(quest.npc, 0) // TRUST_POINTS_PER,
        "recent_topics": RECENT_TOPIC_POINTS * len(recent_others),
    }


def _reason(player: PlayerSnapshot, quest: QuestCandidate, focus: tuple[SkillCategory, ...], why: str) -> str:
    matched = [skill for skill in quest.target_skills if skill in focus]
    if not matched:
        first = SKILL_LABELS[quest.target_skills[0]]
        sentence = f"It continues your story and practises {first}."
    else:
        skill = SKILL_LABELS[matched[0]]
        sentence = {
            "goal": f"It practises {skill}, which fits your goal: {GOAL_LABELS[player.goal]}.",
            TargetReason.REPEATED_MISTAKE.value: f"It practises {skill}, a mistake you keep making.",
            TargetReason.WEAKEST_SKILL.value: f"It practises {skill}, your weakest skill right now.",
            TargetReason.NOT_PRACTISED.value: f"It practises {skill}, which you have not practised yet.",
            TargetReason.REVIEW.value: f"It reviews {skill}, so your strong skills stay strong.",
        }[why]
    if player.story.trust.get(quest.npc, 0) >= 20:
        sentence += f" {quest.npc_name} already trusts you."
    return sentence
