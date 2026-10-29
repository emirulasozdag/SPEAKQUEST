"""Story content: locations, NPCs, quest templates and endings.

The content lives in JSON files next to this module (see docs/story-bible.md for the format).
load_content() reads and checks all of them, so the seed command and the tests share one
definition of valid content. Content files are written by the team, never by the AI.
"""

import json
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.engines.categories import SkillCategory
from app.models.player import EnglishLevel

CONTENT_DIR = Path(__file__).resolve().parent

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$", max_length=60)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Trust = Annotated[int, Field(ge=0, le=100)]
TrustChange = Annotated[int, Field(ge=-100, le=100)]


class _ContentModel(BaseModel):
    # A misspelled field name in a content file is an error, not something to ignore
    model_config = ConfigDict(extra="forbid", frozen=True)


class Location(_ContentModel):
    slug: Slug
    name: Text
    description: Text
    sort_order: int


class Npc(_ContentModel):
    slug: Slug
    location: Slug
    name: Text
    role: Text
    personality: Text
    speaking_style: Text
    knows: list[Text] = []


class Conditions(_ContentModel):
    """Used for quest prerequisites and ending conditions; every listed condition must hold."""

    quests_completed: list[Slug] = []
    flags: list[Slug] = []
    min_trust: dict[Slug, Trust] = {}

    def is_empty(self) -> bool:
        return not (self.quests_completed or self.flags or self.min_trust)


class Effects(_ContentModel):
    flags: list[Slug] = []
    trust: dict[Slug, TrustChange] = {}


class Rewards(_ContentModel):
    xp: int = Field(ge=0)
    trust: dict[Slug, TrustChange] = {}


class Objective(_ContentModel):
    id: Slug
    description: Text


class DecisionOption(_ContentModel):
    id: Slug
    label: Text
    effects: Effects = Effects()


class DecisionPoint(_ContentModel):
    id: Slug
    prompt: Text
    options: list[DecisionOption] = Field(min_length=2)

    @model_validator(mode="after")
    def option_ids_are_unique(self) -> "DecisionPoint":
        _require_unique([option.id for option in self.options], f"option in decision {self.id!r}")
        return self


class QuestTemplate(_ContentModel):
    slug: Slug
    title: Text
    chapter: int = Field(ge=1)
    location: Slug
    npc: Slug
    target_skills: list[SkillCategory] = Field(min_length=1)
    min_level: EnglishLevel
    max_level: EnglishLevel
    summary: Text
    npc_opening: Text
    objectives: list[Objective] = Field(min_length=1)
    prerequisites: Conditions = Conditions()
    rewards: Rewards
    allowed_story_actions: list[Slug] = Field(min_length=1)
    decision_points: list[DecisionPoint] = []

    @model_validator(mode="after")
    def check_quest(self) -> "QuestTemplate":
        levels = list(EnglishLevel)
        if levels.index(self.min_level) > levels.index(self.max_level):
            raise ValueError(f"quest {self.slug!r}: min_level is above max_level")
        _require_unique([objective.id for objective in self.objectives], f"objective in quest {self.slug!r}")
        _require_unique([point.id for point in self.decision_points], f"decision in quest {self.slug!r}")
        return self


class Ending(_ContentModel):
    slug: Slug
    title: Text
    summary: Text
    conditions: Conditions = Conditions()


class Content(_ContentModel):
    """All content together, so references between files can be checked."""

    locations: list[Location]
    npcs: list[Npc]
    quests: list[QuestTemplate]
    # Checked in order; the first ending whose conditions hold is the one the player reaches
    endings: list[Ending] = Field(min_length=2)

    @model_validator(mode="after")
    def check_references(self) -> "Content":
        location_slugs = _require_unique([location.slug for location in self.locations], "location")
        npc_slugs = _require_unique([npc.slug for npc in self.npcs], "NPC")
        quest_slugs = _require_unique([quest.slug for quest in self.quests], "quest")
        _require_unique([ending.slug for ending in self.endings], "ending")
        npc_location = {npc.slug: npc.location for npc in self.npcs}

        for npc in self.npcs:
            _require_known(npc.location, location_slugs, f"NPC {npc.slug!r} location")

        for quest in self.quests:
            where = f"quest {quest.slug!r}"
            _require_known(quest.location, location_slugs, f"{where} location")
            _require_known(quest.npc, npc_slugs, f"{where} NPC")
            if npc_location[quest.npc] != quest.location:
                raise ValueError(f"{where}: NPC {quest.npc!r} does not live at {quest.location!r}")
            self._check_conditions(quest.prerequisites, quest_slugs, npc_slugs, f"{where} prerequisites")
            for npc in quest.rewards.trust:
                _require_known(npc, npc_slugs, f"{where} reward trust")
            for point in quest.decision_points:
                for option in point.options:
                    for npc in option.effects.trust:
                        _require_known(npc, npc_slugs, f"{where} decision {point.id!r} trust")

        for ending in self.endings:
            self._check_conditions(ending.conditions, quest_slugs, npc_slugs, f"ending {ending.slug!r}")

        self._check_start_quest()
        self._check_no_prerequisite_cycles()
        self._check_flags()
        self._check_trust_is_reachable()
        self._check_endings()
        return self

    def _check_conditions(self, conditions: Conditions, quests: set, npcs: set, where: str) -> None:
        for quest in conditions.quests_completed:
            _require_known(quest, quests, f"{where} quest")
        for npc in conditions.min_trust:
            _require_known(npc, npcs, f"{where} trust")

    def _check_start_quest(self) -> None:
        starts = [quest.slug for quest in self.quests if quest.prerequisites.is_empty()]
        if len(starts) != 1:
            raise ValueError(f"exactly one quest must have no prerequisites, found {starts}")

    def _check_no_prerequisite_cycles(self) -> None:
        needs = {quest.slug: quest.prerequisites.quests_completed for quest in self.quests}
        finished: set[str] = set()

        def visit(slug: str, path: list[str]) -> None:
            if slug in path:
                raise ValueError(f"quest prerequisites form a cycle: {' -> '.join([*path, slug])}")
            if slug in finished:
                return
            for required in needs[slug]:
                visit(required, [*path, slug])
            finished.add(slug)

        for slug in needs:
            visit(slug, [])

    def _check_flags(self) -> None:
        """Every flag a condition needs must be set by some decision, and every flag a decision
        sets must matter somewhere; otherwise content is either unreachable or dead."""
        set_by_decisions = {
            flag
            for quest in self.quests
            for point in quest.decision_points
            for option in point.options
            for flag in option.effects.flags
        }
        conditions = [quest.prerequisites for quest in self.quests] + [e.conditions for e in self.endings]
        required = {flag for condition in conditions for flag in condition.flags}
        if missing := sorted(required - set_by_decisions):
            raise ValueError(f"flags no decision ever sets: {missing}")
        if unused := sorted(set_by_decisions - required):
            raise ValueError(f"flags set by decisions but never used: {unused}")

    def _check_trust_is_reachable(self) -> None:
        """A trust threshold is reachable only if the possible trust gains add up to it."""
        best_trust: dict[str, int] = {}
        for quest in self.quests:
            for npc, change in quest.rewards.trust.items():
                best_trust[npc] = best_trust.get(npc, 0) + max(change, 0)
            for point in quest.decision_points:
                for npc in {npc for option in point.options for npc in option.effects.trust}:
                    gain = max(option.effects.trust.get(npc, 0) for option in point.options)
                    best_trust[npc] = best_trust.get(npc, 0) + max(gain, 0)

        conditions = [(f"quest {q.slug!r}", q.prerequisites) for q in self.quests]
        conditions += [(f"ending {e.slug!r}", e.conditions) for e in self.endings]
        for where, condition in conditions:
            for npc, needed in condition.min_trust.items():
                if best_trust.get(npc, 0) < needed:
                    raise ValueError(f"{where} needs trust {needed} with {npc!r}, which can never be reached")

    def _check_endings(self) -> None:
        *specific, fallback = self.endings
        if not fallback.conditions.is_empty():
            raise ValueError("the last ending must have no conditions, so every player reaches an ending")
        if any(ending.conditions.is_empty() for ending in specific):
            raise ValueError("only the last ending may have no conditions")


def _require_unique(values: list[str], kind: str) -> set[str]:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise ValueError(f"duplicate {kind} ids: {duplicates}")
    return set(values)


def _require_known(value: str, known: set[str], where: str) -> None:
    if value not in known:
        raise ValueError(f"{where} refers to unknown {value!r}")


def read_content_files(content_dir: Path = CONTENT_DIR) -> dict:
    """Read the raw JSON content; quests come from one file each in quests/."""

    def read(path: Path):
        return json.loads(path.read_text(encoding="utf-8"))

    return {
        "locations": read(content_dir / "locations.json"),
        "npcs": read(content_dir / "npcs.json"),
        "quests": [read(path) for path in sorted((content_dir / "quests").glob("*.json"))],
        "endings": read(content_dir / "endings.json"),
    }


def load_content(content_dir: Path = CONTENT_DIR) -> Content:
    """Read and validate all content. Raises pydantic.ValidationError when something is wrong."""
    return Content.model_validate(read_content_files(content_dir))
