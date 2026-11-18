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


def test_content_loads_with_the_whole_city():
    content = load_content()

    assert {location.slug for location in content.locations} == {"cafe", "apartment", "office", "market"}
    assert {npc.slug for npc in content.npcs} == {"mia", "alex", "olivia", "rosa"}
    assert len(content.quests) == 8
    assert [ending.slug for ending in content.endings] == [
        "heart_of_the_neighbourhood",
        "home_at_last",
        "a_place_in_the_city",
        "new_in_town",
    ]


def test_every_place_has_a_character_and_a_quest():
    content = load_content()

    for location in content.locations:
        assert any(npc.location == location.slug for npc in content.npcs), location.slug
        assert any(quest.location == location.slug for quest in content.quests), location.slug


@pytest.mark.parametrize("path", QUEST_FILES, ids=[path.stem for path in QUEST_FILES])
def test_each_quest_file_passes_the_schema(path):
    template = QuestTemplate.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert template.slug == path.stem, "the file name must match the quest slug"


def test_every_skill_category_is_practised_by_some_quest():
    practised = {skill for quest in load_content().quests for skill in quest.target_skills}

    assert practised == set(SkillCategory)


def test_three_decisions_unlock_different_quests():
    content = load_content()
    unlocked_by = {quest.slug: set(quest.prerequisites.flags) for quest in content.quests}

    assert unlocked_by["the_flat_viewing"] == {"helped_alex"}
    assert unlocked_by["the_missing_backpack"] == {"watched_mia_bag"}
    assert unlocked_by["the_river_festival"] == {"joined_festival_team"}


def test_the_other_decisions_lead_to_different_endings():
    endings = {ending.slug: set(ending.conditions.flags) for ending in load_content().endings}

    assert "helped_late_customer" in endings["a_place_in_the_city"]
    assert {"invited_neighbours", "helped_late_customer"} <= endings["heart_of_the_neighbourhood"]
    assert "invited_neighbours" not in endings["home_at_last"]


def test_the_best_ending_needs_everything_the_others_need():
    """Endings are checked in order, so an earlier ending must never be easier to reach than a later
    one with the same theme; otherwise the later one would be hidden behind it."""
    heart, home, career, _fallback = load_content().endings

    for later in (home, career):
        assert set(later.conditions.quests_completed) <= set(heart.conditions.quests_completed)
        assert set(later.conditions.flags) <= set(heart.conditions.flags)
        for npc, needed in later.conditions.min_trust.items():
            assert heart.conditions.min_trust[npc] >= needed


def test_every_quest_is_needed_for_the_best_ending():
    content = load_content()
    heart = content.endings[0]
    needed = set(heart.conditions.quests_completed)
    # A quest is needed if the best ending names it, or a needed quest requires it first
    changed = True
    while changed:
        before = len(needed)
        for quest in content.quests:
            if quest.slug in needed:
                needed |= set(quest.prerequisites.quests_completed)
        changed = len(needed) != before

    assert needed == {quest.slug for quest in content.quests}


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
        (lambda c: quest(c, "the_job_interview").pop("locked_summary"), "needs a locked_summary"),
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
        "no-locked-summary",
    ],
)
def test_broken_content_is_rejected(raw_content, break_content, message):
    break_content(raw_content)

    with pytest.raises(ValidationError, match=message):
        Content.model_validate(raw_content)


def test_story_events_are_known_only_in_their_own_quest():
    """#64: an NPC's own knows go into every quest with that NPC, so a story event that happens in
    one quest belongs in that quest's npc_knows, or the NPC talks about it before it happens."""
    content = load_content()
    npcs = {npc.slug: npc for npc in content.npcs}
    backpack = next(q for q in content.quests if q.slug == "the_missing_backpack")
    flat = next(q for q in content.quests if q.slug == "the_flat_viewing")

    assert not any("backpack" in fact for fact in npcs["mia"].knows)
    assert any("backpack" in fact for fact in backpack.npc_knows)
    assert not any("4B" in fact for fact in npcs["alex"].knows)
    assert any("4B" in fact for fact in flat.npc_knows)
    market_walk = next(q for q in content.quests if q.slug == "a_walk_to_the_market")
    festival = next(q for q in content.quests if q.slug == "the_river_festival")
    first_day = next(q for q in content.quests if q.slug == "first_day_at_work")

    # Rosa only mentions the festival once the player has met her at the market
    assert not any("Festival" in fact for fact in npcs["rosa"].knows)
    assert any("Festival" in fact for fact in market_walk.npc_knows)
    # The empty table that leads to the last decision belongs to the festival itself
    assert any("empty table" in fact for fact in festival.npc_knows)
    # Olivia knows the player got the job only after the interview
    assert not any("got the" in fact for fact in npcs["olivia"].knows)
    assert any("got the" in fact for fact in first_day.npc_knows)


def test_new_story_actions_can_raise_trust():
    from app.engines.story import TRUST_RAISING_ACTIONS

    for slug in ("a_walk_to_the_market", "the_river_festival", "first_day_at_work"):
        quest_actions = set(next(q for q in load_content().quests if q.slug == slug).allowed_story_actions)
        own_actions = quest_actions - {"continue", "npc_pleased", "npc_confused"}
        assert own_actions and own_actions <= TRUST_RAISING_ACTIONS, slug
