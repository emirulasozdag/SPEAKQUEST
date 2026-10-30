"""Quest endpoints: list, active, start. Completing a quest is tested in test_quest_complete.py."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.content.seed import seed_content
from app.models.quest_progress import QuestProgress
from app.models.content import QuestTemplate
from app.models.user import User
from app.services import quests as quest_service
from tests.test_player_profile import VALID_PROFILE, login_headers

QUESTS_URL = "/api/quests"
STARTER = "meet_your_neighbor"


@pytest.fixture(autouse=True)
def seeded(db_session):
    seed_content(db_session)


@pytest.fixture
def headers(client) -> dict[str, str]:
    return login_headers(client, "deniz@example.com")


def quests_by_slug(client, headers) -> dict[str, dict]:
    response = client.get(QUESTS_URL, headers=headers)
    assert response.status_code == 200
    return {quest["slug"]: quest for quest in response.json()}


def start(client, headers, slug: str):
    return client.post(f"{QUESTS_URL}/{quests_by_slug(client, headers)[slug]['id']}/start", headers=headers)


def complete_in_db(db_session, email: str, slug: str) -> None:
    """Write a finished quest row directly, to set up story state without playing the quest."""
    user = db_session.scalar(select(User).where(User.email == email))
    quest = db_session.scalar(select(QuestTemplate).where(QuestTemplate.slug == slug))
    db_session.add(
        QuestProgress(
            user_id=user.id,
            quest_template_id=quest.id,
            status="completed",
            xp_awarded=quest.rewards["xp"],
            completed_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()


def test_every_quest_endpoint_requires_a_token(client):
    assert client.get(QUESTS_URL).status_code == 401
    assert client.get(f"{QUESTS_URL}/active").status_code == 401
    assert client.post(f"{QUESTS_URL}/1/start").status_code == 401


# --- list ----------------------------------------------------------------------------------


def test_a_new_player_sees_all_quests_and_can_start_only_the_first(client, headers):
    response = client.get(QUESTS_URL, headers=headers)

    assert response.status_code == 200
    quests = response.json()
    assert len(quests) == 5
    assert [q["chapter"] for q in quests] == sorted(q["chapter"] for q in quests)
    statuses = {q["slug"]: q["status"] for q in quests}
    assert statuses.pop(STARTER) == "available"
    assert set(statuses.values()) == {"locked"}


def test_a_listed_quest_shows_what_the_journal_needs_and_nothing_secret(client, headers):
    response = client.get(QUESTS_URL, headers=headers)

    interview = next(q for q in response.json() if q["slug"] == "the_job_interview")
    assert interview["title"] == "The Job Interview"
    assert interview["location_slug"] == "office" and interview["npc_slug"] == "olivia"
    assert interview["target_skills"] == ["past_simple"]
    assert interview["reward_xp"] == 100
    assert interview["started_at"] is None and interview["completed_at"] is None
    for secret in ("npc_opening", "prerequisites", "decision_points", "allowed_story_actions", "trust"):
        assert secret not in response.text


# --- active --------------------------------------------------------------------------------


def test_without_a_started_quest_there_is_no_active_quest(client, headers):
    response = client.get(f"{QUESTS_URL}/active", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "You have no active quest."


# --- start ---------------------------------------------------------------------------------


def test_starting_the_first_quest_makes_it_the_active_one(client, headers):
    response = start(client, headers, STARTER)

    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == STARTER and body["status"] == "active"
    assert body["started_at"] is not None and body["completed_at"] is None
    assert [o["id"] for o in body["objectives"]]
    assert all(o["met"] is False for o in body["objectives"])  # only the backend can mark objectives
    assert client.get(f"{QUESTS_URL}/active", headers=headers).json() == body
    assert quests_by_slug(client, headers)[STARTER]["status"] == "active"


def test_starting_a_quest_needs_no_character_and_gives_no_xp(client, headers):
    assert start(client, headers, STARTER).status_code == 201

    assert client.put("/api/player/profile", json=VALID_PROFILE, headers=headers).status_code == 201
    profile = client.get("/api/player/profile", headers=headers).json()
    assert (profile["xp"], profile["level"]) == (0, 1)


def test_the_same_quest_cannot_be_started_twice(client, headers):
    start(client, headers, STARTER)

    response = start(client, headers, STARTER)

    assert response.status_code == 409
    assert response.json()["detail"] == "This quest is already active."


def test_a_locked_quest_is_refused_and_nothing_is_started(client, headers):
    response = start(client, headers, "the_job_interview")

    assert response.status_code == 409
    assert "locked" in response.json()["detail"]
    assert client.get(f"{QUESTS_URL}/active", headers=headers).status_code == 404
    assert quests_by_slug(client, headers)["the_job_interview"]["status"] == "locked"


def test_a_quest_that_needs_a_decision_stays_locked_even_after_its_quest_prerequisites(client, headers, db_session):
    complete_in_db(db_session, "deniz@example.com", STARTER)
    # the_flat_viewing also needs the helped_alex flag, which a player decision (#17) will set
    assert start(client, headers, "the_flat_viewing").status_code == 409


def test_unknown_quest_is_404_and_a_non_number_is_422(client, headers):
    assert client.post(f"{QUESTS_URL}/9999/start", headers=headers).status_code == 404
    assert client.post(f"{QUESTS_URL}/9999/start", headers=headers).json()["detail"] == "Quest not found."
    assert client.post(f"{QUESTS_URL}/the_job_interview/start", headers=headers).status_code == 422


def test_finishing_the_first_quest_opens_the_next_ones(client, headers, db_session):
    complete_in_db(db_session, "deniz@example.com", STARTER)

    statuses = {slug: q["status"] for slug, q in quests_by_slug(client, headers).items()}

    assert statuses[STARTER] == "completed"
    assert statuses["morning_at_the_cafe"] == "available"
    assert statuses["the_job_interview"] == "available"
    assert statuses["the_flat_viewing"] == "locked"
    assert statuses["the_missing_backpack"] == "locked"


def test_only_one_quest_can_be_active_at_a_time(client, headers, db_session):
    complete_in_db(db_session, "deniz@example.com", STARTER)
    assert start(client, headers, "the_job_interview").status_code == 201

    response = start(client, headers, "morning_at_the_cafe")

    assert response.status_code == 409
    assert response.json()["detail"] == "Finish your active quest before starting another one."
    assert client.get(f"{QUESTS_URL}/active", headers=headers).json()["slug"] == "the_job_interview"


def test_a_completed_quest_cannot_be_started_again(client, headers, db_session):
    complete_in_db(db_session, "deniz@example.com", STARTER)

    response = start(client, headers, STARTER)

    assert response.status_code == 409
    assert response.json()["detail"] == "You have already completed this quest."


# --- players do not see each other ----------------------------------------------------------


def test_one_players_progress_never_shows_up_for_another(client, headers, db_session):
    other = login_headers(client, "mert@example.com")
    complete_in_db(db_session, "deniz@example.com", STARTER)
    start(client, headers, "the_job_interview")

    mine = quests_by_slug(client, headers)
    theirs = quests_by_slug(client, other)

    assert mine[STARTER]["status"] == "completed" and mine["the_job_interview"]["status"] == "active"
    assert theirs[STARTER]["status"] == "available"
    assert {q["status"] for slug, q in theirs.items() if slug != STARTER} == {"locked"}
    assert client.get(f"{QUESTS_URL}/active", headers=other).status_code == 404


def test_two_players_can_have_an_active_quest_each(client, headers):
    other = login_headers(client, "mert@example.com")

    assert start(client, headers, STARTER).status_code == 201
    assert start(client, other, STARTER).status_code == 201


def test_a_player_cannot_start_anything_for_someone_else(client, headers, db_session):
    other = login_headers(client, "mert@example.com")
    start(client, other, STARTER)

    # There is no user id anywhere in the request: the token alone decides whose progress changes
    assert client.get(f"{QUESTS_URL}/active", headers=headers).status_code == 404
    rows = db_session.scalars(select(QuestProgress)).all()
    assert len(rows) == 1
    assert rows[0].user_id == db_session.scalar(select(User.id).where(User.email == "mert@example.com"))


# --- the database enforces the rules even when two requests race -----------------------------


def test_the_database_refuses_a_second_active_quest_for_the_same_player(db_session, client, headers):
    complete_in_db(db_session, "deniz@example.com", STARTER)
    user_id = db_session.scalar(select(User.id).where(User.email == "deniz@example.com"))
    quest_ids = db_session.scalars(
        select(QuestTemplate.id).where(QuestTemplate.slug.in_(["the_job_interview", "morning_at_the_cafe"]))
    ).all()

    db_session.add(QuestProgress(user_id=user_id, quest_template_id=quest_ids[0], status="active"))
    db_session.commit()
    db_session.add(QuestProgress(user_id=user_id, quest_template_id=quest_ids[1], status="active"))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_a_player_may_have_many_completed_quests_and_one_active(db_session, client, headers):
    complete_in_db(db_session, "deniz@example.com", STARTER)
    complete_in_db(db_session, "deniz@example.com", "morning_at_the_cafe")

    assert start(client, headers, "the_job_interview").status_code == 201


def test_losing_a_race_between_two_start_requests_is_a_clean_409(client, headers, db_session, monkeypatch):
    complete_in_db(db_session, "deniz@example.com", STARTER)
    assert start(client, headers, "the_job_interview").status_code == 201
    # Pretend the other request had not been committed yet when this one checked for an active quest
    monkeypatch.setattr(quest_service, "get_active_quest", lambda db, user_id: None)

    response = start(client, headers, "morning_at_the_cafe")

    assert response.status_code == 409
    assert response.json()["detail"] == "Finish your active quest before starting another one."
    assert len(db_session.scalars(select(QuestProgress).where(QuestProgress.status == "active")).all()) == 1
