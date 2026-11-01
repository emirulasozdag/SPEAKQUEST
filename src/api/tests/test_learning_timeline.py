"""Progress over time: each skill's score at the end of every day the player practised."""

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, update

from app.engines.categories import SkillCategory
from app.engines.learning import TIMELINE_MAX_DAYS, Observation, score_timeline, skill_score
from app.models.learning import SkillObservation
from tests.test_dialogue_message import headers, interview  # noqa: F401
from tests.test_learning_api import LEARNING, right, seeded, skills_by_category, talk, wrong  # noqa: F401
from tests.test_player_profile import VALID_PROFILE, login_headers

PS, QF = SkillCategory.PAST_SIMPLE, SkillCategory.QUESTION_FORMATION


def at(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 12, day, hour, tzinfo=timezone.utc)


def obs(category: SkillCategory, correct: bool, when: datetime | None, message_id: int = 1) -> Observation:
    return Observation(category, correct, message_id, when)


# --- score_timeline (pure) -------------------------------------------------------------------


def test_no_practice_means_no_points():
    assert score_timeline([]) == []


def test_one_point_per_day_with_the_score_at_the_end_of_that_day():
    points = score_timeline(
        [obs(PS, False, at(1, 9)), obs(PS, False, at(1, 18)), obs(PS, True, at(3)), obs(QF, True, at(3))]
    )

    assert [point.day for point in points] == [date(2026, 12, 1), date(2026, 12, 3)]
    assert points[0].scores[PS] == skill_score([False, False])
    assert points[1].scores[PS] == skill_score([False, False, True])
    assert points[0].scores[QF] is None
    assert points[1].scores[QF] == skill_score([True])


def test_the_last_point_matches_the_current_score():
    items = [obs(PS, i % 3 != 0, at(1 + i)) for i in range(8)]

    assert score_timeline(items)[-1].scores[PS] == skill_score([item.correct for item in items])


def test_only_the_most_recent_days_are_kept():
    start = at(1)
    items = [obs(PS, True, start + timedelta(days=i)) for i in range(TIMELINE_MAX_DAYS + 5)]

    points = score_timeline(items)

    assert len(points) == TIMELINE_MAX_DAYS
    assert points[0].day == (start + timedelta(days=5)).date()
    # Older days still count towards the score, they are only not drawn
    assert points[-1].scores[PS] == skill_score([True] * (TIMELINE_MAX_DAYS + 5))


def test_observations_without_a_time_are_left_out_and_naive_times_count_as_utc():
    points = score_timeline([obs(PS, True, None), obs(PS, False, datetime(2026, 12, 2, 23, 30))])

    assert [point.day for point in points] == [date(2026, 12, 2)]
    assert points[0].scores[PS] == skill_score([False])


# --- GET /api/learning/timeline ----------------------------------------------------------------


def test_timeline_requires_a_token(client):
    assert client.get(f"{LEARNING}/timeline").status_code == 401


def test_a_new_player_has_an_empty_timeline(client, headers):  # noqa: F811
    assert client.get(f"{LEARNING}/timeline", headers=headers).json() == {"points": []}


def test_the_timeline_follows_the_conversation_day_by_day(client, headers, interview, db_session):  # noqa: F811
    talk(client, headers, wrong("past_simple"), wrong("past_simple"))
    # Move the first two results to yesterday, as if they were written then
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.execute(update(SkillObservation).values(created_at=yesterday))
    db_session.commit()
    talk(client, headers, right("past_simple"))

    points = client.get(f"{LEARNING}/timeline", headers=headers).json()["points"]

    assert len(points) == 2
    first, last = ({s["category"]: s["score"] for s in point["scores"]} for point in points)
    assert first["past_simple"] == skill_score([False, False])
    assert last["past_simple"] == skills_by_category(client, headers)["past_simple"]["score"]
    assert first["prepositions"] is None


def test_the_timeline_never_includes_another_players_practice(client, headers, interview, db_session):  # noqa: F811
    talk(client, headers, wrong("past_simple"))
    other = login_headers(client, "other@example.com")
    client.put("/api/player/profile", json=VALID_PROFILE, headers=other)

    assert client.get(f"{LEARNING}/timeline", headers=other).json() == {"points": []}
    assert db_session.scalar(select(SkillObservation.id)) is not None
