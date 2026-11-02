"""Story state in the database: created with the character, moved by quests, read by the API."""

import pytest
from sqlalchemy import func, select

from app.content.seed import seed_content
from app.engines.story import ACTION_TRUST_STEP, TRUST_MAX
from app.models.content import Npc, QuestTemplate
from app.models.story import NpcRelationship, StoryState
from app.models.user import User
from app.services import story as story_service
from tests.test_player_profile import VALID_PROFILE, login_headers
from tests.test_quest_complete import meet_objectives, progress_of, quest_by_slug

STATE_URL = "/api/story/state"
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


def user_id_of(db_session, email: str = EMAIL) -> int:
    return db_session.scalar(select(User.id).where(User.email == email))


def play(client, headers, db_session, slug: str) -> None:
    """Start a quest, meet its objectives and complete it."""
    quest = quest_by_slug(db_session, slug)
    assert client.post(f"/api/quests/{quest.id}/start", headers=headers).status_code == 201
    meet_objectives(db_session, EMAIL, quest)
    assert client.post(f"/api/quests/{quest.id}/complete", headers=headers).status_code == 200


def set_flags(db_session, *flags: str) -> None:
    """What a decision (#17) will do."""
    state = db_session.scalar(select(StoryState).where(StoryState.user_id == user_id_of(db_session)))
    state.flags = list(flags)
    db_session.commit()


def trust_by_slug(body: dict) -> dict[str, int]:
    return {npc["slug"]: npc["trust"] for npc in body["npcs"]}


# --- starting state --------------------------------------------------------------------------


def test_story_state_requires_a_token(client):
    assert client.get(STATE_URL).status_code == 401


def test_without_a_character_there_is_no_story_yet(client):
    headers = login_headers(client, "ece@example.com")

    response = client.get(STATE_URL, headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Create your character first."


def test_a_new_character_starts_in_chapter_one_with_no_flags_and_no_trust(client, headers, db_session):
    response = client.get(STATE_URL, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["chapter"] == 1
    assert body["current_location"] is None
    assert body["flags"] == []
    assert body["ending"] is None
    npc_slugs = list(db_session.scalars(select(Npc.slug).order_by(Npc.id)))
    assert [npc["slug"] for npc in body["npcs"]] == npc_slugs
    assert set(trust_by_slug(body).values()) == {0}
    assert all(npc["name"] for npc in body["npcs"])


def test_the_story_state_is_created_once_and_editing_the_character_keeps_it(client, headers, db_session):
    set_flags(db_session, "helped_alex")

    assert client.put("/api/player/profile", json={**VALID_PROFILE, "avatar": 1}, headers=headers).status_code == 200

    assert db_session.scalar(select(func.count()).select_from(StoryState)) == 1
    assert client.get(STATE_URL, headers=headers).json()["flags"] == ["helped_alex"]


def test_the_api_never_returns_npc_secrets(client, headers):
    npc = client.get(STATE_URL, headers=headers).json()["npcs"][0]

    assert set(npc) == {"slug", "name", "trust"}


# --- quests move the story -------------------------------------------------------------------


def test_starting_a_quest_moves_the_player_to_its_place(client, headers, db_session):
    quest = quest_by_slug(db_session, STARTER)
    client.post(f"/api/quests/{quest.id}/start", headers=headers)

    location = client.get(STATE_URL, headers=headers).json()["current_location"]

    assert location == {"slug": quest.location.slug, "name": quest.location.name}


def test_completing_a_quest_gives_its_trust_reward_and_moves_to_the_next_chapter(client, headers, db_session):
    play(client, headers, db_session, STARTER)

    body = client.get(STATE_URL, headers=headers).json()

    reward = quest_by_slug(db_session, STARTER).rewards["trust"]
    assert reward
    for npc, change in reward.items():
        assert trust_by_slug(body)[npc] == change
    assert body["chapter"] == 2


def test_a_trust_reward_is_paid_only_once(client, headers, db_session):
    play(client, headers, db_session, STARTER)
    quest = quest_by_slug(db_session, STARTER)

    assert client.post(f"/api/quests/{quest.id}/complete", headers=headers).status_code == 409

    assert trust_by_slug(client.get(STATE_URL, headers=headers).json())["alex"] == quest.rewards["trust"]["alex"]


def test_a_trust_reward_is_capped_at_one_hundred(client, headers, db_session):
    alex = db_session.scalar(select(Npc).where(Npc.slug == "alex"))
    db_session.add(NpcRelationship(user_id=user_id_of(db_session), npc_id=alex.id, trust=TRUST_MAX - 1))
    db_session.commit()

    play(client, headers, db_session, STARTER)

    assert trust_by_slug(client.get(STATE_URL, headers=headers).json())["alex"] == TRUST_MAX


def test_a_refused_completion_changes_no_trust_and_no_chapter(client, headers, db_session):
    quest = quest_by_slug(db_session, STARTER)
    client.post(f"/api/quests/{quest.id}/start", headers=headers)

    assert client.post(f"/api/quests/{quest.id}/complete", headers=headers).status_code == 409

    body = client.get(STATE_URL, headers=headers).json()
    assert set(trust_by_slug(body).values()) == {0}
    assert body["chapter"] == 1


def test_the_chapter_follows_the_earliest_quest_still_open(client, headers, db_session):
    play(client, headers, db_session, STARTER)
    set_flags(db_session, "watched_mia_bag")
    play(client, headers, db_session, "morning_at_the_cafe")

    # The Job Interview (chapter 2) is still open, so the player stays in chapter 2
    assert client.get(STATE_URL, headers=headers).json()["chapter"] == 2

    play(client, headers, db_session, "the_job_interview")

    # Only The Missing Backpack (chapter 3) is left
    assert client.get(STATE_URL, headers=headers).json()["chapter"] == 3


# --- unlocking uses the stored flags and trust -----------------------------------------------


def test_a_stored_flag_unlocks_the_quest_that_needs_it(client, headers, db_session):
    play(client, headers, db_session, STARTER)
    statuses = {q["slug"]: q["status"] for q in client.get("/api/quests", headers=headers).json()}
    assert statuses["the_flat_viewing"] == "locked"

    set_flags(db_session, "helped_alex")

    statuses = {q["slug"]: q["status"] for q in client.get("/api/quests", headers=headers).json()}
    assert statuses["the_flat_viewing"] == "available"


def test_stored_trust_reaches_the_unlock_rule(client, headers, db_session):
    alex = db_session.scalar(select(Npc).where(Npc.slug == "alex"))
    db_session.add(NpcRelationship(user_id=user_id_of(db_session), npc_id=alex.id, trust=42))
    set_flags(db_session, "helped_alex")

    progress = story_service.load_story_progress(db_session, user_id_of(db_session))

    assert progress.trust == {"alex": 42}
    assert progress.flags == {"helped_alex"}


def test_one_players_story_never_shows_up_for_another(client, headers, db_session):
    play(client, headers, db_session, STARTER)
    set_flags(db_session, "helped_alex")
    other = login_headers(client, "ece@example.com")
    client.put("/api/player/profile", json=VALID_PROFILE, headers=other)

    body = client.get(STATE_URL, headers=other).json()

    assert body["flags"] == []
    assert set(trust_by_slug(body).values()) == {0}
    assert body["chapter"] == 1


# --- AI-suggested actions (used by the dialogue flow, #12) -----------------------------------


def starter_template(db_session) -> QuestTemplate:
    return db_session.scalar(select(QuestTemplate).where(QuestTemplate.slug == STARTER))


def test_an_allowed_pleasing_action_stores_a_small_trust_gain(client, headers, db_session):
    starter = starter_template(db_session)
    assert client.post(f"/api/quests/{starter.id}/start", headers=headers).status_code == 201
    progress = progress_of(db_session, EMAIL, starter)
    outcome = story_service.apply_suggested_action(db_session, user_id_of(db_session), starter, "npc_pleased", progress)
    db_session.commit()

    assert outcome.accepted is True
    assert trust_by_slug(client.get(STATE_URL, headers=headers).json())["alex"] == ACTION_TRUST_STEP


def test_an_action_the_quest_does_not_allow_stores_nothing(client, headers, db_session):
    starter = starter_template(db_session)
    assert client.post(f"/api/quests/{starter.id}/start", headers=headers).status_code == 201
    progress = progress_of(db_session, EMAIL, starter)
    outcome = story_service.apply_suggested_action(db_session, user_id_of(db_session), starter, "clue_found", progress)
    db_session.commit()

    assert outcome.accepted is False
    assert db_session.scalar(select(func.count()).select_from(NpcRelationship)) == 0


def test_deleting_the_account_removes_the_story(client, headers, db_session):
    play(client, headers, db_session, STARTER)

    response = client.request("DELETE", "/api/auth/me", json={"password": "secret-pass"}, headers=headers)

    assert response.status_code == 204
    assert db_session.scalar(select(func.count()).select_from(StoryState)) == 0
    assert db_session.scalar(select(func.count()).select_from(NpcRelationship)) == 0
