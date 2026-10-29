"""Checks the story content files: the real content must load, and broken content must be rejected."""

import copy
import json

import pytest
from pydantic import ValidationError

from app.content.schema import CONTENT_DIR, Content, QuestTemplate, load_content, read_content_files
from app.engines.categories import SkillCategory

QUEST_FILES = sorted((CONTENT_DIR / "quests").glob("*.json"))


@pytest.fixture
def raw_content() -> dict:
    return copy.deepcopy(read_content_files())


def quest(raw_content: dict, slug: str) -> dict:
    return next(item for item in raw_content["quests"] if item["slug"] == slug)


def test_content_loads_with_the_mvp_world():
    content = load_content()

    assert {location.slug for location in content.locations} == {"cafe", "apartment", "office"}
    assert {npc.slug for npc in content.npcs} == {"mia", "alex", "olivia"}
    assert len(content.quests) == 5
    assert len(content.endings) == 2


@pytest.mark.parametrize("path", QUEST_FILES, ids=[path.stem for path in QUEST_FILES])
def test_each_quest_file_passes_the_schema(path):
    template = QuestTemplate.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert template.slug == path.stem, "the file name must match the quest slug"


def test_every_skill_category_is_practised_by_some_quest():
    practised = {skill for quest in load_content().quests for skill in quest.target_skills}

    assert practised == set(SkillCategory)


def test_two_decisions_unlock_different_quests():
    content = load_content()
    unlocked_by = {quest.slug: set(quest.prerequisites.flags) for quest in content.quests}

    assert unlocked_by["the_flat_viewing"] == {"helped_alex"}
    assert unlocked_by["the_missing_backpack"] == {"watched_mia_bag"}


@pytest.mark.parametrize(
    ("break_content", "message"),
    [
        (lambda c: quest(c, "the_job_interview").update(npc="sam"), "unknown 'sam'"),
        (lambda c: quest(c, "the_job_interview").update(location="harbour"), "unknown 'harbour'"),
        (lambda c: quest(c, "the_job_interview").update(npc="mia"), "does not live at"),
        (lambda c: quest(c, "the_job_interview").update(target_skills=["future_tense"]), "target_skills"),
        (lambda c: quest(c, "the_job_interview").update(target_skills=[]), "target_skills"),
        (lambda c: quest(c, "the_job_interview").update(min_level="B1", max_level="A2"), "min_level"),
        (lambda c: quest(c, "the_job_interview").update(objectve=[]), "objectve"),
        (lambda c: quest(c, "the_job_interview").pop("objectives"), "objectives"),
        (lambda c: quest(c, "the_job_interview").update(slug="the_flat_viewing"), "duplicate quest"),
        (
            # The Missing Backpack already requires Morning at the Café, so this closes a loop
            lambda c: quest(c, "morning_at_the_cafe")["prerequisites"].update(
                quests_completed=["the_missing_backpack"]
            ),
            "cycle",
        ),
        (
            lambda c: quest(c, "the_job_interview")["prerequisites"].update(quests_completed=["a_lost_quest"]),
            "unknown 'a_lost_quest'",
        ),
        (lambda c: quest(c, "the_job_interview").update(prerequisites={}), "exactly one quest"),
        (
            lambda c: quest(c, "the_job_interview")["prerequisites"].update(flags=["won_the_lottery"]),
            "no decision ever sets",
        ),
        (
            lambda c: quest(c, "meet_your_neighbor")["decision_points"][0]["options"][1].update(
                effects={"flags": ["was_too_tired"]}
            ),
            "never used",
        ),
        (
            lambda c: quest(c, "the_flat_viewing")["prerequisites"].update(min_trust={"alex": 90}),
            "can never be reached",
        ),
        (lambda c: c["endings"].reverse(), "last ending must have no conditions"),
    ],
    ids=[
        "unknown-npc",
        "unknown-location",
        "npc-at-wrong-location",
        "unknown-category",
        "no-category",
        "level-range",
        "misspelled-field",
        "missing-field",
        "duplicate-slug",
        "prerequisite-cycle",
        "unknown-prerequisite",
        "two-start-quests",
        "flag-never-set",
        "flag-never-used",
        "unreachable-trust",
        "no-fallback-ending",
    ],
)
def test_broken_content_is_rejected(raw_content, break_content, message):
    break_content(raw_content)

    with pytest.raises(ValidationError, match=message):
        Content.model_validate(raw_content)
