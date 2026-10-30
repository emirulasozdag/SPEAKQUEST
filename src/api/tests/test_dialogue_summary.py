"""Corrections in the history and the conversation summary (#32): both come from stored data only,
so they are the same after a page reload and never include another player's conversation."""

import pytest

from app.content.seed import seed_content
from tests.ai_fakes import reply_json
from tests.test_dialogue_message import headers, interview, send, use_ai  # noqa: F401
from tests.test_player_profile import login_headers

SUMMARY_URL = "/api/dialogue/summary"
HISTORY_URL = "/api/dialogue/history"


@pytest.fixture(autouse=True)
def seeded(db_session):
    seed_content(db_session)


def mistake(category: str, original: str, corrected: str) -> dict:
    return {"category": category, "original": original, "corrected": corrected, "explanation": "Kısa açıklama."}


def summary(client, headers, quest) -> dict:  # noqa: F811
    response = client.get(f"{SUMMARY_URL}/{quest.id}", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_summary_requires_a_token(client):
    assert client.get(f"{SUMMARY_URL}/1").status_code == 401


def test_a_quest_the_player_never_started_has_no_summary(client, headers):  # noqa: F811
    assert client.get(f"{SUMMARY_URL}/1", headers=headers).status_code == 404
    assert client.get(f"{SUMMARY_URL}/9999", headers=headers).status_code == 404


def test_another_players_conversation_cannot_be_summarised(client, headers, interview):  # noqa: F811
    other = login_headers(client, "other@example.com")

    assert client.get(f"{SUMMARY_URL}/{interview.id}", headers=other).status_code == 404


def test_a_conversation_without_player_messages_has_an_empty_summary(client, headers, interview):  # noqa: F811
    assert summary(client, headers, interview) == {
        "quest_id": interview.id,
        "messages_sent": 0,
        "understood": 0,
        "mistakes": 0,
        "top_category": None,
        "examples": [],
    }


def test_a_flawless_conversation_has_no_mistakes_and_no_examples(client, headers, interview):  # noqa: F811
    use_ai(reply_json(detected_errors=[]), reply_json(detected_errors=[]))
    send(client, headers, "Hello, I am Deniz.")
    send(client, headers, "I worked in a restaurant last year.")

    result = summary(client, headers, interview)

    assert (result["messages_sent"], result["understood"], result["mistakes"]) == (2, 2, 0)
    assert result["top_category"] is None and result["examples"] == []


def test_messages_the_npc_did_not_understand_are_counted_apart_from_mistakes(client, headers, interview):  # noqa: F811
    use_ai(
        reply_json(detected_errors=[]),
        reply_json(communication_success=False, detected_errors=[]),
        reply_json(detected_errors=[mistake("past_simple", "I work there", "I worked there")]),
    )
    for text in ("Hello, I am Deniz.", "Banana window.", "I work there last year."):
        send(client, headers, text)

    result = summary(client, headers, interview)

    assert (result["messages_sent"], result["understood"], result["mistakes"]) == (3, 2, 1)


def test_the_most_frequent_category_is_reported(client, headers, interview):  # noqa: F811
    use_ai(
        reply_json(detected_errors=[mistake("prepositions", "in monday", "on Monday")]),
        reply_json(detected_errors=[mistake("past_simple", "I go", "I went")]),
        reply_json(detected_errors=[mistake("past_simple", "I see", "I saw")]),
    )
    for text in ("one", "two", "three"):
        send(client, headers, text)

    result = summary(client, headers, interview)

    assert result["top_category"] == "past_simple"
    assert result["mistakes"] == 3


def test_examples_cover_each_category_first_and_are_at_most_three(client, headers, interview):  # noqa: F811
    use_ai(
        reply_json(detected_errors=[mistake("past_simple", "I go", "I went")]),
        reply_json(detected_errors=[mistake("past_simple", "I see", "I saw")]),
        reply_json(detected_errors=[mistake("past_simple", "I eat", "I ate")]),
        reply_json(detected_errors=[mistake("prepositions", "in monday", "on Monday")]),
        reply_json(detected_errors=[mistake("present_simple", "she go", "she goes")]),
    )
    for text in ("a", "b", "c", "d", "e"):
        send(client, headers, text)

    examples = summary(client, headers, interview)["examples"]

    assert len(examples) == 3
    # past_simple has three mistakes so it comes first, with its newest one; the other two
    # categories follow before a second past_simple example would
    assert [e["category"] for e in examples] == ["past_simple", "prepositions", "present_simple"]
    assert examples[0]["corrected"] == "I ate"
    assert examples[0]["explanation"] == "Kısa açıklama."


def test_with_one_category_the_examples_are_its_newest_mistakes(client, headers, interview):  # noqa: F811
    use_ai(*[reply_json(detected_errors=[mistake("past_simple", f"I go {i}", f"I went {i}")]) for i in range(4)])
    for text in ("a", "b", "c", "d"):
        send(client, headers, text)

    examples = summary(client, headers, interview)["examples"]

    assert [e["corrected"] for e in examples] == ["I went 3", "I went 2", "I went 1"]


def test_the_history_returns_corrections_with_the_message_they_belong_to(client, headers, interview):  # noqa: F811
    use_ai(
        reply_json(detected_errors=[mistake("past_simple", "I work", "I worked")]),
        reply_json(detected_errors=[]),
    )
    send(client, headers, "I work there.")
    send(client, headers, "It was nice.")

    messages = client.get(f"{HISTORY_URL}/{interview.id}", headers=headers).json()["messages"]

    by_text = {m["text"]: m for m in messages if m["role"] == "player"}
    assert by_text["I work there."]["corrections"] == [
        {"category": "past_simple", "original": "I work", "corrected": "I worked", "explanation": "Kısa açıklama."}
    ]
    assert by_text["It was nice."]["corrections"] == []
    assert all(m["corrections"] == [] for m in messages if m["role"] == "npc")


def test_the_history_never_shows_corrections_of_another_player(client, headers, interview, db_session):  # noqa: F811
    use_ai(reply_json(detected_errors=[mistake("past_simple", "I work", "I worked")]))
    send(client, headers, "I work there.")
    other = login_headers(client, "other@example.com")

    assert client.get(f"{HISTORY_URL}/{interview.id}", headers=other).status_code == 404
    assert client.get(f"{SUMMARY_URL}/{interview.id}", headers=other).status_code == 404
