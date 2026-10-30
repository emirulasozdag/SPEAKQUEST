"""XP and level rules, checked at every boundary."""

import pytest

from app.content.schema import load_content
from app.engines.progression import (
    LEVEL_THRESHOLDS,
    MAX_LEVEL,
    add_xp,
    level_for_xp,
    progress_in_level,
    xp_for_level,
)


def test_thresholds_start_at_zero_and_strictly_increase():
    assert LEVEL_THRESHOLDS[0] == 0
    assert all(a < b for a, b in zip(LEVEL_THRESHOLDS, LEVEL_THRESHOLDS[1:]))
    assert MAX_LEVEL == len(LEVEL_THRESHOLDS)


@pytest.mark.parametrize(
    ("xp", "level"),
    [
        (0, 1), (49, 1),
        (50, 2), (119, 2),
        (120, 3), (219, 3),
        (220, 4), (349, 4),
        (350, 5), (499, 5),
        (500, 6),
        (501, 6), (1_000_000, 6),  # capped at the maximum level
    ],
)
def test_level_changes_exactly_at_each_threshold(xp, level):
    assert level_for_xp(xp) == level


def test_xp_for_level_is_the_inverse_of_level_for_xp():
    for level in range(1, MAX_LEVEL + 1):
        assert level_for_xp(xp_for_level(level)) == level
        if level > 1:
            assert level_for_xp(xp_for_level(level) - 1) == level - 1


@pytest.mark.parametrize("level", [0, -1, MAX_LEVEL + 1])
def test_xp_for_an_impossible_level_is_an_error(level):
    with pytest.raises(ValueError):
        xp_for_level(level)


def test_level_never_goes_down_and_stays_in_range_as_xp_grows():
    levels = [level_for_xp(xp) for xp in range(0, 800)]

    assert levels == sorted(levels)
    assert min(levels) == 1 and max(levels) == MAX_LEVEL


def test_adding_xp_reports_the_new_total_level_and_gain():
    gain = add_xp(0, 50)

    assert (gain.xp, gain.level, gain.gained, gain.previous_level) == (50, 2, 50, 1)
    assert gain.leveled_up


@pytest.mark.parametrize(
    ("current", "amount", "leveled_up"),
    [(0, 49, False), (49, 1, True), (50, 0, False), (110, 80, True), (190, 29, False), (190, 30, True)],
)
def test_leveled_up_is_true_only_when_a_threshold_is_crossed(current, amount, leveled_up):
    assert add_xp(current, amount).leveled_up is leveled_up


def test_a_big_reward_can_skip_several_levels():
    gain = add_xp(0, 500)

    assert (gain.previous_level, gain.level) == (1, 6)
    assert gain.leveled_up


def test_adding_zero_changes_nothing():
    gain = add_xp(123, 0)

    assert (gain.xp, gain.level, gain.leveled_up) == (123, 3, False)


def test_xp_cannot_be_taken_away_or_start_negative():
    with pytest.raises(ValueError):
        add_xp(100, -1)
    with pytest.raises(ValueError):
        add_xp(-1, 10)
    with pytest.raises(ValueError):
        level_for_xp(-1)


@pytest.mark.parametrize("bad", [True, False, 1.5, "50", None])
def test_only_whole_numbers_count_as_xp(bad):
    with pytest.raises(TypeError):
        add_xp(0, bad)
    with pytest.raises(TypeError):
        add_xp(bad, 0)
    with pytest.raises(TypeError):
        level_for_xp(bad)


@pytest.mark.parametrize(
    ("xp", "level", "into", "needed"),
    [(0, 1, 0, 50), (49, 1, 49, 50), (50, 2, 0, 70), (75, 2, 25, 70), (499, 5, 149, 150), (500, 6, 0, None), (650, 6, 150, None)],
)
def test_progress_inside_the_current_level(xp, level, into, needed):
    progress = progress_in_level(xp)

    assert (progress.level, progress.xp_into_level, progress.xp_needed_for_next) == (level, into, needed)


def test_finishing_the_mvp_quests_gives_a_meaningful_progression():
    quests = load_content().quests
    starter = next(q for q in quests if q.prerequisites.is_empty())

    assert all(q.rewards.xp > 0 for q in quests)
    assert level_for_xp(starter.rewards.xp) >= 2  # the very first quest already feels rewarding
    assert level_for_xp(sum(q.rewards.xp for q in quests)) >= 4  # the whole story is worth several levels
