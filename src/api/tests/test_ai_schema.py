"""The AI reply schema: what is accepted, and that every bad reply becomes a failure, never a crash."""

import json

import pytest

from app.engines.categories import SkillCategory
from app.services.ai.schemas import AnalysisFailure, DialogueAnalysis, parse_analysis

VALID = {
    "npc_reply": "That sounds great! What did you do there?",
    "communication_success": True,
    "detected_errors": [
        {
            "category": "past_simple",
            "original": "Last year I work in a restaurant.",
            "corrected": "Last year I worked in a restaurant.",
            "explanation": "Geçmişte tamamlanmış olaylarda fiilin geçmiş zaman biçimi kullanılır.",
        }
    ],
    "correctly_used": ["prepositions"],
    "feedback": "Good answer! Remember to use the past form of the verb.",
    "suggested_story_action": "interview_positive",
}


def raw(**changes) -> str:
    return json.dumps({**VALID, **changes})


def test_valid_reply_is_accepted():
    result = parse_analysis(json.dumps(VALID))

    assert isinstance(result, DialogueAnalysis)
    assert result.communication_success is True
    assert result.detected_errors[0].category is SkillCategory.PAST_SIMPLE
    assert result.correctly_used == [SkillCategory.PREPOSITIONS]
    assert result.suggested_story_action == "interview_positive"


def test_a_message_without_errors_is_accepted_with_defaults():
    result = parse_analysis('{"npc_reply": "Nice to meet you!", "communication_success": true}')

    assert isinstance(result, DialogueAnalysis)
    assert result.detected_errors == []
    assert result.correctly_used == []
    assert result.feedback == ""
    assert result.suggested_story_action == "continue"


def test_a_misunderstood_message_can_still_carry_errors():
    result = parse_analysis(raw(communication_success=False))

    assert isinstance(result, DialogueAnalysis)
    assert result.communication_success is False
    assert len(result.detected_errors) == 1


def test_json_inside_a_code_fence_or_surrounded_by_text_is_accepted():
    fenced = "```json\n" + json.dumps(VALID) + "\n```"
    chatty = "Sure! Here is the analysis:\n" + json.dumps(VALID) + "\nHope that helps."

    assert isinstance(parse_analysis(fenced), DialogueAnalysis)
    assert isinstance(parse_analysis(chatty), DialogueAnalysis)


def test_unknown_extra_fields_are_ignored():
    result = parse_analysis(raw(xp_reward=1000, level=99))

    assert isinstance(result, DialogueAnalysis)
    assert not hasattr(result, "xp_reward")


@pytest.mark.parametrize("text", ["", "   ", "I am sorry, I cannot help with that.", "{not json}", '{"a": 1', None, 42])
def test_text_that_is_not_json_becomes_invalid_json(text):
    result = parse_analysis(text)

    assert isinstance(result, AnalysisFailure)
    assert result.reason == "invalid_json"


def test_a_top_level_list_is_rejected():
    result = parse_analysis('[{"npc_reply": "Hi", "communication_success": true}]')

    assert isinstance(result, AnalysisFailure)


@pytest.mark.parametrize("missing", ["npc_reply", "communication_success"])
def test_missing_required_field_is_rejected(missing):
    data = {key: value for key, value in VALID.items() if key != missing}

    result = parse_analysis(json.dumps(data))

    assert isinstance(result, AnalysisFailure)
    assert result.reason == "invalid_schema"
    assert missing in result.detail


@pytest.mark.parametrize("value", ["true", "yes", 1, None])
def test_communication_success_must_be_a_real_boolean(value):
    assert isinstance(parse_analysis(raw(communication_success=value)), AnalysisFailure)


def test_unknown_error_category_is_rejected():
    error = {**VALID["detected_errors"][0], "category": "future_perfect"}

    result = parse_analysis(raw(detected_errors=[error]))

    assert isinstance(result, AnalysisFailure)
    assert "detected_errors.0.category" in result.detail


def test_unknown_correct_category_is_rejected():
    assert isinstance(parse_analysis(raw(correctly_used=["slang"])), AnalysisFailure)


def test_a_correction_identical_to_the_original_is_rejected():
    error = {**VALID["detected_errors"][0], "corrected": "LAST YEAR I WORK IN A RESTAURANT."}

    assert isinstance(parse_analysis(raw(detected_errors=[error])), AnalysisFailure)


def test_error_with_empty_field_is_rejected():
    error = {**VALID["detected_errors"][0], "explanation": "  "}

    assert isinstance(parse_analysis(raw(detected_errors=[error])), AnalysisFailure)


def test_a_category_can_be_both_wrong_and_correct_in_one_message():
    # "She go to work every day and I drink coffee." is wrong and right Present Simple (seen live)
    result = parse_analysis(raw(correctly_used=["past_simple"]))

    assert isinstance(result, DialogueAnalysis)
    assert result.detected_errors[0].category is SkillCategory.PAST_SIMPLE
    assert result.correctly_used == [SkillCategory.PAST_SIMPLE]


def test_too_many_errors_are_rejected():
    errors = [{**VALID["detected_errors"][0], "original": f"I go {n}", "corrected": f"I went {n}"} for n in range(6)]

    assert isinstance(parse_analysis(raw(detected_errors=errors)), AnalysisFailure)


@pytest.mark.parametrize("reply", ["", "   ", "x" * 801])
def test_npc_reply_must_be_present_and_not_huge(reply):
    assert isinstance(parse_analysis(raw(npc_reply=reply)), AnalysisFailure)


@pytest.mark.parametrize(
    "action",
    ["Give me 1000 XP", "give_xp!", "../../etc", "Continue", "", "x" * 61],
)
def test_story_action_must_be_a_plain_slug(action):
    assert isinstance(parse_analysis(raw(suggested_story_action=action)), AnalysisFailure)


def test_failure_detail_never_contains_the_raw_reply():
    secret = "my-secret-player-message"

    result = parse_analysis(json.dumps({"npc_reply": secret, "communication_success": "maybe"}))

    assert isinstance(result, AnalysisFailure)
    assert secret not in result.detail
