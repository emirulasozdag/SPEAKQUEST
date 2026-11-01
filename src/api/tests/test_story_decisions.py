"""Story decisions: made once per started quest, applied by the Story Engine, and unlocking quests."""

import pytest
from sqlalchemy import func, select

from app.content.schema import Effects, Ending, load_content
from app.content.seed import seed_content
from app.engines.story import StoryProgress, apply_decision, choose_ending
from app.models.story import StoryDecision
from app.services import story as story_service
from tests.test_player_profile import VALID_PROFILE, login_headers
from tests.test_story_state import EMAIL, play, quest_by_slug, user_id_of

DECISION_URL = "/api/story/decision"
ENDINGS = load_content().endings


@pytest.fixture(autouse=True)
def seeded(db_session):
    seed_content(db_session)


@pytest.fixture
def headers(client) -> dict[str, str]:
    headers = login_headers(client, EMAIL)
    assert client.put("/api/player/profile", json=VALID_PROFILE, headers=headers).status_code == 201
    return headers


def start(client, headers, db_session, slug: str) -> int:
    quest = quest_by_slug(db_session, slug)
    assert client.post(f"/api/quests/{quest.id}/start", headers=headers).status_code == 201
    return quest.id


def decide(client, headers, quest_id: int, decision_id: str, option_id: str):
    payload = {"quest_id": quest_id, "decision_id": decision_id, "option_id": option_id}
    return client.post(DECISION_URL, json=payload, headers=headers)


def statuses(client, headers) -> dict[str, str]:
    return {quest["slug"]: quest["status"] for quest in client.get("/api/quests", headers=headers).json()}


def trust_of(client, headers, npc: str) -> int:
    npcs = client.get("/api/story/state", headers=headers).json()["npcs"]
    return next(item["trust"] for item in npcs if item["slug"] == npc)


# --- Story Engine: pure functions ------------------------------------------------------------


def test_a_decision_adds_its_flags_and_trust():
    before = StoryProgress(flags=frozenset({"old_flag"}), trust={"alex": 5})

    after = apply_decision(before, Effects(flags=["helped_alex"], trust={"alex": 15}))

    assert after.flags == {"old_flag", "helped_alex"}
    assert after.trust == {"alex": 20}
    assert before.flags == {"old_flag"} and before.trust == {"alex": 5}


def test_a_decision_without_effects_changes_nothing():
    before = StoryProgress(flags=frozenset({"a"}), trust={"mia": 10})

    assert apply_decision(before, Effects()) == before


def test_trust_from_a_decision_stays_within_limits():
    after = apply_decision(StoryProgress(trust={"alex": 95}), Effects(trust={"alex": 15}))

    assert after.trust["alex"] == 100


def test_the_best_ending_needs_every_condition():
    progress = StoryProgress(
        completed_quests=frozenset({"the_flat_viewing", "the_missing_backpack"}),
        flags=frozenset({"helped_alex", "watched_mia_bag"}),
        trust={"alex": 30, "mia": 35},
    )

    assert choose_ending(ENDINGS, progress).slug == "home_at_last"
    assert choose_ending(ENDINGS, StoryProgress(**{**progress.__dict__, "trust": {"alex": 29, "mia": 35}})).slug == (
        "new_in_town"
    )


def test_every_player_reaches_an_ending():
    assert choose_ending(ENDINGS, StoryProgress()).slug == "new_in_town"


def test_endings_are_checked_in_content_order():
    first = Ending(slug="first", title="First", summary="Comes first.")
    second = Ending(slug="second", title="Second", summary="Also matches.")

    assert choose_ending([first, second], StoryProgress()).slug == "first"


# --- POST /api/story/decision ----------------------------------------------------------------


def test_decisions_require_a_token(client):
    assert client.post(DECISION_URL, json={"quest_id": 1, "decision_id": "x", "option_id": "y"}).status_code == 401
    assert client.get("/api/story/decisions/1").status_code == 401


def test_helping_alex_sets_the_flag_raises_trust_and_unlocks_the_flat_viewing(client, headers, db_session):
    play(client, headers, db_session, "meet_your_neighbor")
    assert statuses(client, headers)["the_flat_viewing"] == "locked"
    alex_before = trust_of(client, headers, "alex")

    response = decide(client, headers, quest_by_slug(db_session, "meet_your_neighbor").id, "help_alex_move", "help")

    assert response.status_code == 201
    body = response.json()
    assert "helped_alex" in body["flags"]
    assert body["npcs"] == [{"slug": "alex", "name": "Alex", "trust": alex_before + 15}]
    assert [quest["slug"] for quest in body["unlocked_quests"]] == ["the_flat_viewing"]
    assert statuses(client, headers)["the_flat_viewing"] == "available"
    assert trust_of(client, headers, "alex") == alex_before + 15


def test_saying_no_keeps_the_flat_viewing_locked(client, headers, db_session):
    play(client, headers, db_session, "meet_your_neighbor")

    response = decide(client, headers, quest_by_slug(db_session, "meet_your_neighbor").id, "help_alex_move", "not_now")

    assert response.status_code == 201
    assert response.json()["flags"] == []
    assert response.json()["unlocked_quests"] == []
    assert statuses(client, headers)["the_flat_viewing"] == "locked"


def test_watching_mias_bag_unlocks_a_different_quest(client, headers, db_session):
    play(client, headers, db_session, "meet_your_neighbor")
    play(client, headers, db_session, "morning_at_the_cafe")
    assert statuses(client, headers)["the_missing_backpack"] == "locked"

    response = decide(client, headers, quest_by_slug(db_session, "morning_at_the_cafe").id, "watch_mia_bag", "watch")

    assert [quest["slug"] for quest in response.json()["unlocked_quests"]] == ["the_missing_backpack"]
    # The other branch stays closed: each quest depends on its own decision
    assert statuses(client, headers)["the_flat_viewing"] == "locked"


def test_a_decision_can_be_made_while_the_quest_is_active(client, headers, db_session):
    quest_id = start(client, headers, db_session, "meet_your_neighbor")

    assert decide(client, headers, quest_id, "help_alex_move", "help").status_code == 201


def test_a_decision_is_made_only_once(client, headers, db_session):
    quest_id = start(client, headers, db_session, "meet_your_neighbor")
    assert decide(client, headers, quest_id, "help_alex_move", "not_now").status_code == 201

    response = decide(client, headers, quest_id, "help_alex_move", "help")

    assert response.status_code == 409
    assert response.json()["detail"] == "You already made this decision."
    assert "helped_alex" not in client.get("/api/story/state", headers=headers).json()["flags"]
    assert db_session.scalar(select(func.count()).select_from(StoryDecision)) == 1


def test_a_quest_that_is_not_started_has_no_decisions_yet(client, headers, db_session):
    quest_id = quest_by_slug(db_session, "meet_your_neighbor").id

    assert decide(client, headers, quest_id, "help_alex_move", "help").status_code == 409
    assert client.get(f"/api/story/decisions/{quest_id}", headers=headers).status_code == 409


@pytest.mark.parametrize(
    ("decision_id", "option_id"),
    [("help_alex_move", "steal_the_box"), ("watch_mia_bag", "watch"), ("made_up", "help")],
    ids=["unknown-option", "decision-of-another-quest", "unknown-decision"],
)
def test_an_invalid_decision_is_refused_and_changes_nothing(client, headers, db_session, decision_id, option_id):
    quest_id = start(client, headers, db_session, "meet_your_neighbor")

    response = decide(client, headers, quest_id, decision_id, option_id)

    assert response.status_code == 400
    assert client.get("/api/story/state", headers=headers).json()["flags"] == []
    assert db_session.scalar(select(func.count()).select_from(StoryDecision)) == 0


def test_an_unknown_quest_is_not_found(client, headers):
    assert decide(client, headers, 9999, "help_alex_move", "help").status_code == 404


def test_extra_fields_are_rejected(client, headers, db_session):
    quest_id = start(client, headers, db_session, "meet_your_neighbor")
    payload = {"quest_id": quest_id, "decision_id": "help_alex_move", "option_id": "help", "trust": 100}

    assert client.post(DECISION_URL, json=payload, headers=headers).status_code == 422


def test_one_players_decision_does_not_change_another_player(client, headers, db_session):
    quest_id = start(client, headers, db_session, "meet_your_neighbor")
    other = login_headers(client, "other@example.com")
    client.put("/api/player/profile", json=VALID_PROFILE, headers=other)

    decide(client, headers, quest_id, "help_alex_move", "help")

    assert client.get("/api/story/state", headers=other).json()["flags"] == []
    assert decide(client, other, quest_id, "help_alex_move", "help").status_code == 409


# --- GET /api/story/decisions/{quest_id} -----------------------------------------------------


def test_listing_shows_the_options_without_their_effects(client, headers, db_session):
    quest_id = start(client, headers, db_session, "meet_your_neighbor")

    body = client.get(f"/api/story/decisions/{quest_id}", headers=headers).json()

    assert [item["id"] for item in body] == ["help_alex_move"]
    assert body[0]["chosen"] is None
    assert [option["id"] for option in body[0]["options"]] == ["help", "not_now"]
    assert all(set(option) == {"id", "label"} for option in body[0]["options"])


def test_listing_shows_what_was_chosen(client, headers, db_session):
    quest_id = start(client, headers, db_session, "meet_your_neighbor")
    decide(client, headers, quest_id, "help_alex_move", "help")

    body = client.get(f"/api/story/decisions/{quest_id}", headers=headers).json()

    assert body[0]["chosen"] == "help"


# --- ending ----------------------------------------------------------------------------------


def test_a_new_player_is_heading_for_the_open_ending(client, headers, db_session):
    assert story_service.ending_for(db_session, user_id_of(db_session)).slug == "new_in_town"
