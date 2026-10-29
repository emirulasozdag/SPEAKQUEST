import pytest

from app.content.schema import load_content
from app.content.seed import seed_content
from tests.test_player_profile import login_headers

LOCATIONS_URL = "/api/locations"


@pytest.fixture
def headers(client) -> dict[str, str]:
    return login_headers(client, "deniz@example.com")


@pytest.fixture
def seeded(db_session):
    seed_content(db_session)


def test_both_endpoints_require_a_token(client, seeded):
    assert client.get(LOCATIONS_URL).status_code == 401
    assert client.get(f"{LOCATIONS_URL}/1").status_code == 401


def test_the_map_lists_every_place_in_order_with_its_characters(client, headers, seeded):
    response = client.get(LOCATIONS_URL, headers=headers)

    assert response.status_code == 200
    places = response.json()
    assert [place["slug"] for place in places] == ["apartment", "cafe", "office"]
    assert [place["sort_order"] for place in places] == sorted(place["sort_order"] for place in places)
    by_slug = {place["slug"]: place for place in places}
    assert [npc["slug"] for npc in by_slug["office"]["npcs"]] == ["olivia"]
    assert by_slug["office"]["npcs"][0]["name"] == "Olivia"
    assert by_slug["office"]["npcs"][0]["role"]


def test_each_quest_carries_its_story_data_and_the_players_status(client, headers, seeded):
    places = client.get(LOCATIONS_URL, headers=headers).json()
    quests = {quest["slug"]: quest for place in places for quest in place["quests"]}

    assert set(quests) == {q.slug for q in load_content().quests}
    interview = quests["the_job_interview"]
    assert interview["title"] == "The Job Interview"
    assert interview["npc_slug"] == "olivia"
    assert interview["chapter"] == 2
    assert interview["summary"]
    assert interview in next(place for place in places if place["slug"] == "office")["quests"]


def test_a_new_player_can_start_only_the_starting_quest(client, headers, seeded):
    places = client.get(LOCATIONS_URL, headers=headers).json()
    statuses = {quest["slug"]: quest["status"] for place in places for quest in place["quests"]}

    assert statuses.pop("meet_your_neighbor") == "available"
    assert set(statuses.values()) == {"locked"}


def test_quests_of_a_place_are_ordered_by_chapter(client, headers, seeded):
    for place in client.get(LOCATIONS_URL, headers=headers).json():
        chapters = [quest["chapter"] for quest in place["quests"]]
        assert chapters == sorted(chapters)


def test_a_single_place_has_the_same_shape_as_in_the_list(client, headers, seeded):
    places = client.get(LOCATIONS_URL, headers=headers).json()

    for place in places:
        response = client.get(f"{LOCATIONS_URL}/{place['id']}", headers=headers)
        assert response.status_code == 200
        assert response.json() == place


def test_an_unknown_place_returns_404(client, headers, seeded):
    response = client.get(f"{LOCATIONS_URL}/9999", headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Location not found."


def test_a_non_numeric_id_is_a_validation_error_not_a_crash(client, headers, seeded):
    assert client.get(f"{LOCATIONS_URL}/cafe", headers=headers).status_code == 422


def test_prompt_only_character_data_is_never_returned(client, headers, seeded):
    raw = client.get(LOCATIONS_URL, headers=headers).text
    npcs = load_content().npcs

    for npc in npcs:
        assert npc.personality not in raw
        assert npc.speaking_style not in raw
        for fact in npc.knows:
            assert fact not in raw
    for forbidden in ("personality", "speaking_style", "knows", "npc_opening", "rewards", "prerequisites"):
        assert f'"{forbidden}"' not in raw


def test_before_the_content_is_seeded_the_map_is_simply_empty(client, headers):
    assert client.get(LOCATIONS_URL, headers=headers).json() == []
