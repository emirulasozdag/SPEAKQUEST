"""The single unlock rule of the Story Engine, on its own and against the real quests."""

import pytest

from app.content.schema import Conditions, load_content
from app.engines.story import StoryProgress, is_unlocked, unmet_conditions


def progress(completed=(), flags=(), trust=None) -> StoryProgress:
    return StoryProgress(frozenset(completed), frozenset(flags), trust or {})


def test_no_conditions_means_always_unlocked():
    assert is_unlocked(Conditions(), progress())


def test_every_required_quest_must_be_completed():
    needs = Conditions(quests_completed=["a", "b"])

    assert not is_unlocked(needs, progress())
    assert not is_unlocked(needs, progress(completed=["a"]))
    assert is_unlocked(needs, progress(completed=["a", "b"]))
    assert is_unlocked(needs, progress(completed=["a", "b", "c"]))


def test_a_required_flag_must_be_set():
    needs = Conditions(flags=["helped_alex"])

    assert not is_unlocked(needs, progress())
    assert not is_unlocked(needs, progress(flags=["watched_mia_bag"]))
    assert is_unlocked(needs, progress(flags=["helped_alex"]))


@pytest.mark.parametrize(
    ("trust", "unlocked"),
    [({}, False), ({"alex": 29}, False), ({"alex": 30}, True), ({"alex": 100}, True), ({"mia": 80}, False)],
)
def test_trust_must_reach_the_minimum_for_that_npc(trust, unlocked):
    assert is_unlocked(Conditions(min_trust={"alex": 30}), progress(trust=trust)) is unlocked


def test_a_missing_npc_counts_as_zero_trust():
    assert is_unlocked(Conditions(min_trust={"alex": 0}), progress())
    assert not is_unlocked(Conditions(min_trust={"alex": 1}), progress())


def test_all_kinds_of_condition_must_hold_together():
    needs = Conditions(quests_completed=["a"], flags=["f"], min_trust={"alex": 10})

    assert is_unlocked(needs, progress(["a"], ["f"], {"alex": 10}))
    assert not is_unlocked(needs, progress([], ["f"], {"alex": 10}))
    assert not is_unlocked(needs, progress(["a"], [], {"alex": 10}))
    assert not is_unlocked(needs, progress(["a"], ["f"], {"alex": 9}))


def test_unmet_conditions_lists_only_what_is_still_missing():
    needs = Conditions(quests_completed=["a", "b"], flags=["f", "g"], min_trust={"alex": 10, "mia": 30})

    missing = unmet_conditions(needs, progress(["a"], ["g"], {"alex": 10, "mia": 29}))

    assert missing == Conditions(quests_completed=["b"], flags=["f"], min_trust={"mia": 30})
    assert unmet_conditions(needs, progress(["a", "b"], ["f", "g"], {"alex": 10, "mia": 30})).is_empty()


def unlocked_quests(state: StoryProgress) -> set[str]:
    return {q.slug for q in load_content().quests if is_unlocked(q.prerequisites, state)}


def test_a_new_player_can_only_play_the_starting_quest():
    assert unlocked_quests(progress()) == {"meet_your_neighbor"}


def test_finishing_the_starting_quest_opens_the_café_and_the_interview():
    opened = unlocked_quests(progress(completed=["meet_your_neighbor"]))

    assert opened == {"meet_your_neighbor", "morning_at_the_cafe", "the_job_interview"}


def test_quests_that_need_a_decision_stay_locked_until_the_flag_exists():
    done = ["meet_your_neighbor", "morning_at_the_cafe"]

    assert "the_flat_viewing" not in unlocked_quests(progress(completed=done))
    assert "the_missing_backpack" not in unlocked_quests(progress(completed=done))
    assert "the_flat_viewing" in unlocked_quests(progress(completed=done, flags=["helped_alex"]))
    assert "the_missing_backpack" in unlocked_quests(progress(completed=done, flags=["watched_mia_bag"]))
