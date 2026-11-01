"""Learning Engine read side (#16): skill scores, repeated mistakes and the learning target.

Scenario tests over pure functions: a player is built message by message the way the dialogue
flow stores observations, without a database or an AI.
"""

import itertools

import pytest

from app.engines.categories import SkillCategory
from app.engines.learning import (
    LEVEL_ORDER,
    PRIOR_SCORE,
    RECENT_PRACTICE_MESSAGES,
    REPEAT_MIN_MISTAKES,
    REPEAT_WINDOW_MESSAGES,
    STRONG_FROM,
    WEAK_BELOW,
    Observation,
    SkillStatus,
    TargetReason,
    choose_learning_target,
    most_improved_skill,
    rank_learning_targets,
    skill_score,
    skill_scores,
)
from app.models.player import EnglishLevel

PAST = SkillCategory.PAST_SIMPLE
PRESENT = SkillCategory.PRESENT_SIMPLE
PREPS = SkillCategory.PREPOSITIONS


class Player:
    """A player's history, message by message."""

    def __init__(self) -> None:
        self.observations: list[Observation] = []
        self.message_ids: list[int] = []
        self._ids = itertools.count(1)

    def says(self, *results: tuple[SkillCategory, bool]) -> "Player":
        """One message; each (category, correct) pair is one skill opportunity in it."""
        message_id = next(self._ids)
        self.message_ids.append(message_id)
        self.observations.extend(Observation(category, correct, message_id) for category, correct in results)
        return self

    def scores(self):
        return skill_scores(self.observations, list(reversed(self.message_ids)))


# --- scenario: a new player ------------------------------------------------------------------


def test_a_new_player_starts_every_skill_at_the_prior_and_not_practised():
    scores = Player().scores()

    assert list(scores) == list(SkillCategory)
    assert {s.score for s in scores.values()} == {PRIOR_SCORE}
    assert {s.status for s in scores.values()} == {SkillStatus.NOT_PRACTISED}
    assert not any(s.repeated for s in scores.values())
    assert {s.last_practiced_at for s in scores.values()} == {None}


@pytest.mark.parametrize(("level", "first"), [(EnglishLevel.A2, PRESENT), (EnglishLevel.B1, PAST)])
def test_a_new_player_starts_with_the_first_skill_of_their_level(level, first):
    target = choose_learning_target(Player().scores(), level)

    assert target.category == first
    assert target.reason == TargetReason.NOT_PRACTISED


# --- scenario: a single mistake --------------------------------------------------------------


def test_one_mistake_lowers_the_score_without_crashing_it():
    score = Player().says((PAST, False)).scores()[PAST]

    assert 25 < score.score < PRIOR_SCORE  # a single message never decides a skill
    assert (score.opportunities, score.error_count, score.correct_count) == (1, 1, 0)
    assert score.status == SkillStatus.WEAK
    assert not score.repeated


def test_one_correct_use_raises_the_score():
    score = Player().says((PAST, True)).scores()[PAST]

    assert PRIOR_SCORE < score.score < STRONG_FROM


def test_other_skills_are_not_touched_by_a_message_about_one_skill():
    scores = Player().says((PAST, False)).scores()

    assert scores[PRESENT].score == PRIOR_SCORE
    assert scores[PRESENT].status == SkillStatus.NOT_PRACTISED


# --- scenario: improvement -------------------------------------------------------------------


def test_recent_messages_weigh_more_than_older_ones():
    improving = skill_score([False] * 5 + [True] * 5)
    declining = skill_score([True] * 5 + [False] * 5)

    assert improving > PRIOR_SCORE > declining
    assert improving + declining == 100  # the same results, only the order differs


def test_a_score_rises_step_by_step_as_the_player_gets_it_right():
    scores = [skill_score([False] * 3 + [True] * n) for n in range(8)]

    assert scores == sorted(scores)
    assert len(set(scores)) == len(scores)
    assert scores[0] < WEAK_BELOW <= scores[-1]


def test_with_enough_practice_the_score_reaches_the_ends_of_the_scale():
    assert skill_score([True] * 40) == 100
    assert skill_score([False] * 40) == 0


def test_an_improving_player_loses_a_repeated_mistake_and_the_target_moves_on():
    player = Player()
    for _ in range(REPEAT_MIN_MISTAKES):
        player.says((PAST, False))
    assert choose_learning_target(player.scores(), EnglishLevel.B1).reason == TargetReason.REPEATED_MISTAKE

    for _ in range(REPEAT_WINDOW_MESSAGES):
        player.says((PAST, True))

    item = player.scores()[PAST]
    assert not item.repeated
    assert item.status == SkillStatus.STRONG
    assert choose_learning_target(player.scores(), EnglishLevel.B1).category != PAST


@pytest.mark.parametrize(
    ("results", "status"),
    [
        ([True] * 5, SkillStatus.STRONG),
        ([True, False], SkillStatus.WEAK),
        ([True, True, False, True], SkillStatus.DEVELOPING),
    ],
)
def test_status_bands(results, status):
    player = Player()
    for correct in results:
        player.says((PAST, correct))

    item = player.scores()[PAST]
    assert item.status == status
    assert (item.score >= STRONG_FROM) == (status == SkillStatus.STRONG)


# --- scenario: repeated mistakes -------------------------------------------------------------


def test_three_mistakes_in_the_last_ten_messages_are_a_repeated_mistake():
    player = Player()
    for _ in range(REPEAT_MIN_MISTAKES):
        player.says((PAST, False)).says()

    item = player.scores()[PAST]
    assert item.recent_mistakes == REPEAT_MIN_MISTAKES
    assert item.repeated


def test_two_mistakes_are_not_yet_repeated():
    assert not Player().says((PAST, False)).says((PAST, False)).scores()[PAST].repeated


def test_mistakes_older_than_the_last_ten_messages_do_not_count_as_repeated():
    player = Player()
    for _ in range(REPEAT_MIN_MISTAKES):
        player.says((PAST, False))
    for _ in range(REPEAT_WINDOW_MESSAGES):
        player.says((PRESENT, True))

    item = player.scores()[PAST]
    assert item.recent_mistakes == 0
    assert not item.repeated
    assert item.error_count == REPEAT_MIN_MISTAKES  # the history itself is kept


def test_messages_without_any_skill_still_fill_the_window():
    player = Player()
    for _ in range(REPEAT_MIN_MISTAKES):
        player.says((PAST, False))
    for _ in range(REPEAT_WINDOW_MESSAGES - 1):
        player.says()  # small talk: no skill touched

    assert player.scores()[PAST].recent_mistakes == 1  # only the newest mistake is still inside


def test_a_message_counts_once_however_many_observations_of_a_category_it_has():
    player = Player().says((PAST, False), (PAST, False), (PAST, False))

    assert player.scores()[PAST].recent_mistakes == 1


def test_a_repeated_mistake_is_the_target_even_when_another_skill_is_weaker():
    player = Player()
    for _ in range(5):
        player.says((PREPS, False))  # prepositions: very weak, but long ago
    for _ in range(REPEAT_WINDOW_MESSAGES):
        player.says((PRESENT, True))
    for _ in range(REPEAT_MIN_MISTAKES):
        player.says((PAST, True)).says((PAST, False))

    scores = player.scores()
    assert scores[PREPS].score < scores[PAST].score
    target = choose_learning_target(scores, EnglishLevel.A2)
    assert (target.category, target.reason) == (PAST, TargetReason.REPEATED_MISTAKE)


def test_of_two_repeated_mistakes_the_one_with_more_recent_mistakes_comes_first():
    player = Player()
    for _ in range(REPEAT_MIN_MISTAKES):
        player.says((PREPS, False))
    for _ in range(REPEAT_MIN_MISTAKES + 1):
        player.says((PRESENT, False))

    ranking = rank_learning_targets(player.scores(), EnglishLevel.B1)
    assert [t.category for t in ranking[:2]] == [PRESENT, PREPS]


# --- learning target -------------------------------------------------------------------------


def test_every_level_order_contains_every_category_once():
    assert set(LEVEL_ORDER) == set(EnglishLevel)
    for order in LEVEL_ORDER.values():
        assert sorted(order) == sorted(SkillCategory)


def test_the_weakest_practised_skill_beats_an_unpractised_one():
    player = Player().says((PREPS, False)).says((PREPS, False))
    for _ in range(RECENT_PRACTICE_MESSAGES):
        player.says((PRESENT, True))  # prepositions are no longer "just practised"

    target = choose_learning_target(player.scores(), EnglishLevel.B1)

    assert (target.category, target.reason) == (PREPS, TargetReason.WEAKEST_SKILL)


def test_a_slightly_weak_skill_practised_just_now_gives_way_to_another_skill():
    # Just below the start after a mistake a moment ago: the recent-practice penalty lifts it
    # above an untouched skill, so the next quest brings variety
    player = Player().says((PAST, True)).says((PAST, False))

    target = choose_learning_target(player.scores(), EnglishLevel.B1)

    assert target.category != PAST
    assert target.reason == TargetReason.NOT_PRACTISED


def test_a_clearly_weak_skill_stays_the_target_even_right_after_practice():
    player = Player()
    for _ in range(4):
        for _ in range(REPEAT_WINDOW_MESSAGES):
            player.says()
        player.says((PAST, False))  # mistakes spread out, so they never become "repeated"

    scores = player.scores()
    assert not scores[PAST].repeated
    assert scores[PAST].practised_recently
    assert choose_learning_target(scores, EnglishLevel.A2).category == PAST


def test_when_everything_is_strong_the_target_is_a_review():
    player = Player()
    for _ in range(6):
        player.says(*[(category, True) for category in SkillCategory])
    for _ in range(RECENT_PRACTICE_MESSAGES):
        player.says()

    target = choose_learning_target(player.scores(), EnglishLevel.A2)

    assert target.reason == TargetReason.REVIEW
    assert target.category == LEVEL_ORDER[EnglishLevel.A2][0]  # equal scores: the level order decides


def test_the_ranking_lists_every_skill_once_and_is_deterministic():
    player = Player().says((PAST, False), (PRESENT, True)).says((PREPS, True))

    first = rank_learning_targets(player.scores(), EnglishLevel.B1)

    assert first == rank_learning_targets(player.scores(), EnglishLevel.B1)
    assert sorted(t.category for t in first) == sorted(SkillCategory)


def test_level_changes_the_order_of_otherwise_equal_skills():
    scores = Player().scores()

    assert [t.category for t in rank_learning_targets(scores, EnglishLevel.A2)] == list(LEVEL_ORDER[EnglishLevel.A2])
    assert [t.category for t in rank_learning_targets(scores, EnglishLevel.B1)] == list(LEVEL_ORDER[EnglishLevel.B1])


# --- most improved skill (ending screen) -----------------------------------------------------


def test_the_most_improved_skill_is_the_one_furthest_above_the_start():
    scores = Player().says((PAST, True)).says((PREPS, True), (PAST, True)).says((PRESENT, False)).scores()

    improved = most_improved_skill(scores)

    assert improved.category == PAST and improved.score > scores[PREPS].score > PRIOR_SCORE


def test_no_skill_improved_without_practice_or_only_mistakes():
    assert most_improved_skill(Player().scores()) is None
    assert most_improved_skill(Player().says((PAST, False)).says((PRESENT, False)).scores()) is None
