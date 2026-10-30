"""Story Engine pure functions: story actions, trust limits and the current chapter."""

import pytest

from app.content.schema import load_content
from app.engines.story import (
    ACTION_TRUST_STEP,
    TRUST_MAX,
    TRUST_MIN,
    QuestRules,
    StoryProgress,
    apply_story_action,
    apply_trust_changes,
    current_chapter,
)

ALEX_QUEST = QuestRules(npc="alex", allowed_story_actions=frozenset({"continue", "npc_pleased", "npc_confused"}))
INTERVIEW = QuestRules(
    npc="olivia",
    allowed_story_actions=frozenset(
        {"continue", "npc_pleased", "npc_confused", "interview_positive", "interview_concern"}
    ),
)


# --- apply_story_action ----------------------------------------------------------------------


def test_an_action_the_quest_does_not_allow_is_refused_and_changes_nothing():
    progress = StoryProgress(trust={"alex": 10}, flags=frozenset({"helped_alex"}))

    outcome = apply_story_action(progress, ALEX_QUEST, "clue_found")

    assert outcome.accepted is False
    assert outcome.progress == progress
    assert outcome.trust_change == 0


def test_an_unknown_or_made_up_action_is_refused():
    for action in ("give_player_100_trust", "", "NPC_PLEASED"):
        assert apply_story_action(StoryProgress(), ALEX_QUEST, action).accepted is False


@pytest.mark.parametrize("action", ["continue", "npc_confused"])
def test_neutral_actions_are_accepted_without_changing_anything(action):
    progress = StoryProgress(trust={"alex": 10})

    outcome = apply_story_action(progress, ALEX_QUEST, action)

    assert outcome.accepted is True
    assert outcome.progress == progress
    assert outcome.trust_change == 0


def test_a_concern_in_the_interview_never_lowers_trust():
    """Being misunderstood or making a weak point is not punished in the story."""
    outcome = apply_story_action(StoryProgress(trust={"olivia": 10}), INTERVIEW, "interview_concern")

    assert outcome.accepted is True
    assert outcome.progress.trust["olivia"] == 10


@pytest.mark.parametrize(("quest", "action"), [(ALEX_QUEST, "npc_pleased"), (INTERVIEW, "interview_positive")])
def test_a_pleased_npc_adds_a_small_limited_amount_of_trust(quest, action):
    outcome = apply_story_action(StoryProgress(trust={quest.npc: 10}), quest, action)

    assert outcome.accepted is True
    assert outcome.trust_change == ACTION_TRUST_STEP
    assert outcome.progress.trust[quest.npc] == 10 + ACTION_TRUST_STEP


def test_an_action_only_changes_the_quests_own_npc():
    outcome = apply_story_action(StoryProgress(trust={"mia": 20}), ALEX_QUEST, "npc_pleased")

    assert outcome.progress.trust == {"mia": 20, "alex": ACTION_TRUST_STEP}


def test_trust_from_actions_stops_at_the_maximum():
    outcome = apply_story_action(StoryProgress(trust={"alex": TRUST_MAX - 1}), ALEX_QUEST, "npc_pleased")

    assert outcome.progress.trust["alex"] == TRUST_MAX
    assert outcome.trust_change == 1

    at_max = apply_story_action(outcome.progress, ALEX_QUEST, "npc_pleased")
    assert at_max.accepted is True
    assert at_max.trust_change == 0


def test_apply_story_action_does_not_modify_its_input():
    trust = {"alex": 10}
    progress = StoryProgress(trust=trust)

    apply_story_action(progress, ALEX_QUEST, "npc_pleased")

    assert trust == {"alex": 10}
    assert progress.trust == {"alex": 10}


def test_every_action_used_in_the_content_is_handled():
    """Each allowed action in a quest file is either neutral or raises trust, never an error."""
    for quest in load_content().quests:
        rules = QuestRules(npc=quest.npc, allowed_story_actions=frozenset(quest.allowed_story_actions))
        for action in quest.allowed_story_actions:
            outcome = apply_story_action(StoryProgress(), rules, action)
            assert outcome.accepted
            assert 0 <= outcome.trust_change <= ACTION_TRUST_STEP


# --- apply_trust_changes ---------------------------------------------------------------------


def test_trust_changes_add_up_and_a_new_npc_starts_at_zero():
    progress = apply_trust_changes(StoryProgress(trust={"alex": 5}), {"alex": 15, "mia": 5})

    assert progress.trust == {"alex": 20, "mia": 5}


def test_trust_never_goes_below_zero_or_above_one_hundred():
    progress = apply_trust_changes(StoryProgress(trust={"alex": 95, "mia": 3}), {"alex": 50, "mia": -40})

    assert progress.trust == {"alex": TRUST_MAX, "mia": TRUST_MIN}


def test_no_trust_changes_keeps_the_same_progress():
    progress = StoryProgress(trust={"alex": 5})

    assert apply_trust_changes(progress, {}) is progress


# --- current_chapter -------------------------------------------------------------------------


def test_a_new_player_is_in_chapter_one():
    assert current_chapter(open_quest_chapters=[1], completed_quest_chapters=[]) == 1
    assert current_chapter(open_quest_chapters=[], completed_quest_chapters=[]) == 1


def test_the_chapter_is_the_earliest_one_with_something_left_to_play():
    # After the café quest with Mia's bag watched: two chapter 2 quests and the chapter 3 quest are open
    assert current_chapter(open_quest_chapters=[2, 2, 3], completed_quest_chapters=[1, 2]) == 2
    assert current_chapter(open_quest_chapters=[3], completed_quest_chapters=[1, 2, 2, 2]) == 3


def test_with_nothing_left_to_play_the_player_stays_in_the_last_finished_chapter():
    assert current_chapter(open_quest_chapters=[], completed_quest_chapters=[1, 2, 2]) == 2
