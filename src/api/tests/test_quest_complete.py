"""POST /api/quests/{id}/complete: the backend's objectives decide, and XP is paid only once."""

import pytest
from sqlalchemy import select

from app.content.seed import seed_content
from app.engines.progression import level_for_xp
from app.models.content import QuestTemplate
from app.models.player import PlayerProfile
from app.models.quest_progress import QuestProgress
from app.models.user import User
from app.services import quests as quest_service
from tests.test_dialogue_history import add_messages
from tests.test_player_profile import VALID_PROFILE, login_headers

EMAIL = "deniz@example.com"
STARTER = "meet_your_neighbor"


@pytest.fixture(autouse=True)
def seeded(db_session):
    seed_content(db_session)


@pytest.fixture
def headers(client) -> dict[str, str]:
    headers = login_headers(client, EMAIL)
    assert client.put("/api/player/profile", json=VALID_PROFILE, headers=headers).status_code == 201
    return headers


def quest_by_slug(db_session, slug: str) -> QuestTemplate:
    return db_session.scalar(select(QuestTemplate).where(QuestTemplate.slug == slug))


def progress_of(db_session, email: str, quest: QuestTemplate) -> QuestProgress:
    user_id = db_session.scalar(select(User.id).where(User.email == email))
    return db_session.scalar(
        select(QuestProgress).where(QuestProgress.user_id == user_id, QuestProgress.quest_template_id == quest.id)
    )


def profile_of(db_session, email: str) -> PlayerProfile:
    user_id = db_session.scalar(select(User.id).where(User.email == email))
    return db_session.scalar(select(PlayerProfile).where(PlayerProfile.user_id == user_id))


def start(client, headers, quest: QuestTemplate) -> None:
    assert client.post(f"/api/quests/{quest.id}/start", headers=headers).status_code == 201


def meet_objectives(db_session, email: str, quest: QuestTemplate, ids: list[str] | None = None) -> None:
    """What the dialogue checks (#31) will write once the player reaches each objective."""
    progress = progress_of(db_session, email, quest)
    progress.objectives_met = [o["id"] for o in quest.objectives] if ids is None else ids
    db_session.commit()


def complete(client, headers, quest: QuestTemplate):
    return client.post(f"/api/quests/{quest.id}/complete", headers=headers)


def test_completing_requires_a_token(client):
    assert client.post("/api/quests/1/complete").status_code == 401


def test_completing_with_every_objective_met_pays_xp_and_levels_up(client, headers, db_session):
    quest = quest_by_slug(db_session, STARTER)
    start(client, headers, quest)
    meet_objectives(db_session, EMAIL, quest)

    response = complete(client, headers, quest)

    assert response.status_code == 200
    body = response.json()
    reward = quest.rewards["xp"]
    assert body["quest"]["slug"] == STARTER
    assert body["quest"]["status"] == "completed"
    assert body["quest"]["completed_at"] is not None
    assert body["xp_gained"] == reward
    assert body["xp"] == reward
    assert body["level"] == level_for_xp(reward) == 2
    assert body["leveled_up"] is True

    progress = progress_of(db_session, EMAIL, quest)
    assert progress.status == "completed"
    assert progress.xp_awarded == reward
    profile = profile_of(db_session, EMAIL)
    assert (profile.xp, profile.level) == (reward, 2)


def test_the_profile_and_active_quest_reflect_the_completion(client, headers, db_session):
    quest = quest_by_slug(db_session, STARTER)
    start(client, headers, quest)
    meet_objectives(db_session, EMAIL, quest)
    complete(client, headers, quest)

    profile = client.get("/api/player/profile", headers=headers).json()
    assert (profile["xp"], profile["level"]) == (quest.rewards["xp"], 2)
    assert client.get("/api/quests/active", headers=headers).status_code == 404


def test_missing_objectives_refuse_completion_and_change_nothing(client, headers, db_session):
    quest = quest_by_slug(db_session, STARTER)
    start(client, headers, quest)
    first, *rest = [o["id"] for o in quest.objectives]
    meet_objectives(db_session, EMAIL, quest, [first])

    response = complete(client, headers, quest)

    assert rest
    assert response.status_code == 409
    assert response.json()["detail"] == "You have not reached every objective of this quest yet."
    assert progress_of(db_session, EMAIL, quest).status == "active"
    assert profile_of(db_session, EMAIL).xp == 0


def test_a_quest_with_no_objectives_met_cannot_be_completed(client, headers, db_session):
    quest = quest_by_slug(db_session, STARTER)
    start(client, headers, quest)

    assert complete(client, headers, quest).status_code == 409


def test_grammar_mistakes_do_not_block_completion(client, headers, db_session):
    """Communication and grammar are judged apart: a quest whose objectives were met through
    understandable but ungrammatical messages is still completed."""
    quest = quest_by_slug(db_session, STARTER)
    start(client, headers, quest)
    add_messages(
        db_session,
        EMAIL,
        quest,
        ("player", "Hello Alex! My name Deniz, I am come from Izmir.", True),
        ("player", "Every morning I goes to the gym.", True),
    )
    meet_objectives(db_session, EMAIL, quest)

    assert complete(client, headers, quest).status_code == 200


def test_unmet_objectives_block_completion_even_when_every_message_was_understood(client, headers, db_session):
    quest = quest_by_slug(db_session, STARTER)
    start(client, headers, quest)
    add_messages(db_session, EMAIL, quest, ("player", "Hello, nice to meet you!", True))

    assert complete(client, headers, quest).status_code == 409


def test_the_same_quest_cannot_be_completed_or_paid_twice(client, headers, db_session):
    quest = quest_by_slug(db_session, STARTER)
    start(client, headers, quest)
    meet_objectives(db_session, EMAIL, quest)
    assert complete(client, headers, quest).status_code == 200

    response = complete(client, headers, quest)

    assert response.status_code == 409
    assert response.json()["detail"] == "You have already completed this quest."
    assert profile_of(db_session, EMAIL).xp == quest.rewards["xp"]


def test_losing_a_race_between_two_complete_requests_pays_nothing(client, headers, db_session, monkeypatch):
    """Both requests passed the status check; the conditional update lets only one of them pay."""
    quest = quest_by_slug(db_session, STARTER)
    start(client, headers, quest)
    meet_objectives(db_session, EMAIL, quest)
    # The other request already flipped the row to completed between our read and our update
    progress = progress_of(db_session, EMAIL, quest)
    real_get_profile = quest_service.get_profile

    def get_profile_after_the_other_request(db, user_id):
        db.execute(
            QuestProgress.__table__.update().where(QuestProgress.id == progress.id).values(status="completed")
        )
        return real_get_profile(db, user_id)

    monkeypatch.setattr(quest_service, "get_profile", get_profile_after_the_other_request)

    response = complete(client, headers, quest)

    assert response.status_code == 409
    assert profile_of(db_session, EMAIL).xp == 0


def test_a_quest_that_was_never_started_cannot_be_completed(client, headers, db_session):
    response = complete(client, headers, quest_by_slug(db_session, STARTER))

    assert response.status_code == 409
    assert response.json()["detail"] == "Start this quest before completing it."


def test_unknown_quest_is_404_and_a_non_number_is_422(client, headers):
    assert client.post("/api/quests/9999/complete", headers=headers).status_code == 404
    assert client.post("/api/quests/abc/complete", headers=headers).status_code == 422


def test_a_player_without_a_character_cannot_complete(client, db_session):
    headers = login_headers(client, "ece@example.com")
    quest = quest_by_slug(db_session, STARTER)
    start(client, headers, quest)
    meet_objectives(db_session, "ece@example.com", quest)

    response = complete(client, headers, quest)

    assert response.status_code == 409
    assert response.json()["detail"] == "Create your character before completing a quest."


def test_a_player_cannot_complete_someone_elses_quest(client, headers, db_session):
    quest = quest_by_slug(db_session, STARTER)
    start(client, headers, quest)
    meet_objectives(db_session, EMAIL, quest)
    other = login_headers(client, "ece@example.com")
    assert client.put("/api/player/profile", json=VALID_PROFILE, headers=other).status_code == 201

    assert complete(client, other, quest).status_code == 409
    assert progress_of(db_session, EMAIL, quest).status == "active"
    assert profile_of(db_session, "ece@example.com").xp == 0


def test_completing_the_first_quest_unlocks_the_next_ones(client, headers, db_session):
    quest = quest_by_slug(db_session, STARTER)
    start(client, headers, quest)
    meet_objectives(db_session, EMAIL, quest)
    complete(client, headers, quest)

    statuses = {q["slug"]: q["status"] for q in client.get("/api/quests", headers=headers).json()}

    assert statuses[STARTER] == "completed"
    assert "available" in statuses.values()


def test_xp_adds_up_across_quests(client, headers, db_session):
    first = quest_by_slug(db_session, STARTER)
    start(client, headers, first)
    meet_objectives(db_session, EMAIL, first)
    complete(client, headers, first)
    second_slug = next(
        q["slug"] for q in client.get("/api/quests", headers=headers).json() if q["status"] == "available"
    )
    second = quest_by_slug(db_session, second_slug)
    start(client, headers, second)
    meet_objectives(db_session, EMAIL, second)

    body = complete(client, headers, second).json()

    total = first.rewards["xp"] + second.rewards["xp"]
    assert body["xp_gained"] == second.rewards["xp"]
    assert body["xp"] == total
    assert body["level"] == level_for_xp(total)
