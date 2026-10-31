"""GET /api/learning/errors, /skills and /recommendations (#16): real data from the dialogue flow,
only ever the logged-in player's own."""

import pytest

from app.content.seed import seed_content
from app.engines.learning import PRIOR_SCORE, REPEAT_MIN_MISTAKES
from tests.ai_fakes import reply_json
from tests.test_dialogue_message import headers, interview, send, use_ai  # noqa: F401
from tests.test_player_profile import VALID_PROFILE, login_headers

LEARNING = "/api/learning"


@pytest.fixture(autouse=True)
def seeded(db_session):
    seed_content(db_session)


def mistake(category: str, original: str = "I go there", corrected: str = "I went there") -> dict:
    return {"category": category, "original": original, "corrected": corrected, "explanation": "Kısa açıklama."}


def wrong(category: str, **kwargs) -> str:
    return reply_json(detected_errors=[mistake(category, **kwargs)], correctly_used=[])


def right(*categories: str) -> str:
    return reply_json(detected_errors=[], correctly_used=list(categories))


def talk(client, headers, *replies: str) -> None:  # noqa: F811
    use_ai(*replies)
    for index in range(len(replies)):
        assert send(client, headers, f"Message number {index}.").json()["status"] == "ok"


def skills_by_category(client, headers) -> dict[str, dict]:  # noqa: F811
    body = client.get(f"{LEARNING}/skills", headers=headers).json()
    return {item["category"]: item for item in body["skills"]}


@pytest.mark.parametrize("path", ["/errors", "/skills", "/recommendations"])
def test_every_learning_endpoint_requires_a_token(client, path):
    assert client.get(f"{LEARNING}{path}").status_code == 401


# --- /skills ---------------------------------------------------------------------------------


def test_a_new_player_has_every_skill_at_the_start_and_nothing_repeated(client, headers):  # noqa: F811
    response = client.get(f"{LEARNING}/skills", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert [s["category"] for s in body["skills"]] == [
        "present_simple",
        "past_simple",
        "question_formation",
        "prepositions",
        "vocabulary_usage",
    ]
    states = {(s["score"], s["status"], s["opportunities"]) for s in body["skills"]}
    assert states == {(PRIOR_SCORE, "not_practised", 0)}
    assert body["repeated_mistakes"] == []


def test_mistakes_and_correct_uses_from_the_conversation_change_the_scores(client, headers, interview):  # noqa: F811
    talk(client, headers, wrong("past_simple"), right("present_simple"))

    skills = skills_by_category(client, headers)

    assert skills["past_simple"]["score"] < PRIOR_SCORE
    assert (skills["past_simple"]["error_count"], skills["past_simple"]["status"]) == (1, "weak")
    assert skills["present_simple"]["score"] > PRIOR_SCORE
    assert skills["present_simple"]["last_practiced_at"]
    assert skills["prepositions"]["status"] == "not_practised"


def test_a_repeated_mistake_is_reported(client, headers, interview):  # noqa: F811
    talk(client, headers, *[wrong("prepositions")] * REPEAT_MIN_MISTAKES)

    body = client.get(f"{LEARNING}/skills", headers=headers).json()

    assert body["repeated_mistakes"] == ["prepositions"]
    prepositions = next(s for s in body["skills"] if s["category"] == "prepositions")
    assert (prepositions["recent_mistakes"], prepositions["repeated"]) == (REPEAT_MIN_MISTAKES, True)


def test_skills_never_include_another_players_messages(client, headers, interview):  # noqa: F811
    talk(client, headers, wrong("past_simple"))
    other = login_headers(client, "other@example.com")

    skills = skills_by_category(client, other)

    assert skills["past_simple"]["opportunities"] == 0


# --- /recommendations ------------------------------------------------------------------------


def test_recommendations_need_a_character(client):
    headers = login_headers(client, "nochar@example.com")

    assert client.get(f"{LEARNING}/recommendations", headers=headers).status_code == 404


def test_a_new_b1_player_is_pointed_to_the_first_skill_of_the_level(client, headers):  # noqa: F811
    assert VALID_PROFILE["english_level"] == "B1"

    body = client.get(f"{LEARNING}/recommendations", headers=headers).json()

    assert body["target"]["category"] == "past_simple"
    assert body["target"]["reason"] == "not_practised"
    assert body["target"]["message"]
    assert body["ranking"][0] == body["target"]
    assert len(body["ranking"]) == 5


def test_a_repeated_mistake_becomes_the_recommended_target(client, headers, interview):  # noqa: F811
    question = wrong("question_formation", original="Where you live?", corrected="Where do you live?")
    talk(client, headers, *[question] * REPEAT_MIN_MISTAKES)

    target = client.get(f"{LEARNING}/recommendations", headers=headers).json()["target"]

    assert (target["category"], target["reason"]) == ("question_formation", "repeated_mistake")
    assert target["score"] < PRIOR_SCORE


# --- /errors ---------------------------------------------------------------------------------


def test_errors_are_listed_newest_first_with_their_quest(client, headers, interview):  # noqa: F811
    talk(
        client,
        headers,
        wrong("past_simple", original="I go", corrected="I went"),
        wrong("prepositions", original="in Monday", corrected="on Monday"),
    )

    body = client.get(f"{LEARNING}/errors", headers=headers).json()

    assert body["total"] == 2
    assert [e["corrected"] for e in body["errors"]] == ["on Monday", "I went"]
    first = body["errors"][0]
    assert (first["category"], first["original"]) == ("prepositions", "in Monday")
    assert first["explanation"] == "Kısa açıklama."
    assert (first["quest_id"], first["quest_title"]) == (interview.id, interview.title)
    assert first["created_at"]


def test_errors_can_be_filtered_by_category_and_paged(client, headers, interview):  # noqa: F811
    talk(client, headers, wrong("past_simple"), wrong("prepositions"), wrong("past_simple"), wrong("past_simple"))

    filtered = client.get(f"{LEARNING}/errors", params={"category": "past_simple"}, headers=headers).json()
    page = client.get(f"{LEARNING}/errors", params={"limit": 2, "offset": 1}, headers=headers).json()

    assert filtered["total"] == 3
    assert {e["category"] for e in filtered["errors"]} == {"past_simple"}
    assert page["total"] == 4
    assert len(page["errors"]) == 2


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"category": "spelling"}])
def test_invalid_error_queries_are_rejected(client, headers, params):  # noqa: F811
    assert client.get(f"{LEARNING}/errors", params=params, headers=headers).status_code == 422


def test_a_new_player_has_no_errors(client, headers):  # noqa: F811
    assert client.get(f"{LEARNING}/errors", headers=headers).json() == {"errors": [], "total": 0}


def test_errors_of_another_player_are_never_listed(client, headers, interview):  # noqa: F811
    talk(client, headers, wrong("past_simple"))
    other = login_headers(client, "other@example.com")

    assert client.get(f"{LEARNING}/errors", headers=other).json() == {"errors": [], "total": 0}


def test_every_ranked_skill_gets_a_message_that_is_true_for_it(client, headers, interview):  # noqa: F811
    talk(client, headers, wrong("past_simple"), right("present_simple"))

    ranking = client.get(f"{LEARNING}/recommendations", headers=headers).json()["ranking"]

    by_category = {item["category"]: item for item in ranking}
    assert by_category["prepositions"]["reason"] == "not_practised"
    assert by_category["prepositions"]["message"] == "You have not practised this skill yet."
    assert all(item["message"] for item in ranking)
