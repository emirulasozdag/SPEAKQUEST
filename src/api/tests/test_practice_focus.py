"""Personalised dialogues (#20): the NPC asks questions that make the player use the structure
they need most, chosen from their own mistakes or, without evidence, from the scene."""

import dataclasses
import itertools

import pytest

from app.content.seed import seed_content
from app.engines.categories import SkillCategory
from app.engines.learning import (
    REPEAT_MIN_MISTAKES,
    SCENE_REASON,
    Observation,
    TargetReason,
    choose_practice_focus,
    skill_scores,
)
from app.models.player import EnglishLevel
from app.services.ai.prompts import PRACTICE_GUIDE, SKILL_LABELS, build_prompt
from tests.ai_fakes import job_interview_context, reply_json
from tests.test_dialogue_message import EMAIL, headers, interview, send, use_ai  # noqa: F401
from tests.test_quest_complete import quest_by_slug
from tests.test_quests import complete_in_db

PAST = SkillCategory.PAST_SIMPLE
PREPS = SkillCategory.PREPOSITIONS
PRESENT = SkillCategory.PRESENT_SIMPLE


def scores_after(*messages: tuple[tuple[SkillCategory, bool], ...]):
    """Skill scores after these messages, oldest first; each message lists (skill, correct)."""
    ids = itertools.count(1)
    observations, message_ids = [], []
    for results in messages:
        message_id = next(ids)
        message_ids.append(message_id)
        observations += [Observation(skill, correct, message_id) for skill, correct in results]
    return skill_scores(observations, list(reversed(message_ids)))


# --- choosing the focus ----------------------------------------------------------------------


@pytest.mark.parametrize("scene_skill", list(SkillCategory))
def test_a_new_player_practises_what_the_scene_was_written_for(scene_skill):
    focus = choose_practice_focus(scores_after(), EnglishLevel.A2, [scene_skill])

    assert (focus.category, focus.reason) == (scene_skill, SCENE_REASON)


def test_a_repeated_mistake_wins_over_the_scene():
    scores = scores_after(*[((PREPS, False),)] * REPEAT_MIN_MISTAKES)

    focus = choose_practice_focus(scores, EnglishLevel.B1, [PAST])

    assert (focus.category, focus.reason) == (PREPS, TargetReason.REPEATED_MISTAKE.value)


def test_a_weak_practised_skill_wins_over_the_scene():
    # Two prepositions mistakes, then three messages without them: weak, not repeated, not recent
    scores = scores_after(((PREPS, False),), ((PREPS, False),), (), (), ())

    focus = choose_practice_focus(scores, EnglishLevel.B1, [PAST])

    assert (focus.category, focus.reason) == (PREPS, TargetReason.WEAKEST_SKILL.value)


def test_when_every_skill_is_strong_the_scene_decides_again():
    strong = tuple((skill, True) for skill in SkillCategory)
    scores = scores_after(*[strong] * 6, (), (), ())

    focus = choose_practice_focus(scores, EnglishLevel.A2, [PAST])

    assert (focus.category, focus.reason) == (PAST, SCENE_REASON)


def test_without_scene_skills_the_learning_target_is_used():
    focus = choose_practice_focus(scores_after(), EnglishLevel.A2, [])

    assert focus.category == PRESENT  # the first skill of the A2 order
    assert focus.reason == TargetReason.NOT_PRACTISED.value


# --- the prompt ------------------------------------------------------------------------------


def test_without_a_focus_the_prompt_has_no_practice_section():
    assert "PRACTICE FOCUS" not in build_prompt(job_interview_context(), "Hi").system


@pytest.mark.parametrize("skill", list(SkillCategory))
def test_the_focus_tells_the_npc_how_to_create_a_need_for_the_structure(skill):
    context = dataclasses.replace(job_interview_context(), practice_focus=skill)

    system = build_prompt(context, "Hi").system

    section = system.split("PRACTICE FOCUS", 1)[1].split("TEACHING RULES", 1)[0]
    assert SKILL_LABELS[skill] in section
    assert PRACTICE_GUIDE[skill] in section
    assert "Never name the grammar point" in section
    assert "without looking harder for this kind of mistake" in section


def test_the_focus_changes_only_the_practice_section():
    plain = build_prompt(job_interview_context(), "Hi").system
    focused = build_prompt(dataclasses.replace(job_interview_context(), practice_focus=PAST), "Hi").system

    before, _, after = focused.partition("\nPRACTICE FOCUS")
    rest = after.split("\nTEACHING RULES", 1)[1]
    assert plain == before + "\nTEACHING RULES" + rest


def test_every_skill_has_a_label_and_a_guide():
    assert set(SKILL_LABELS) == set(PRACTICE_GUIDE) == set(SkillCategory)


# --- through the dialogue flow ---------------------------------------------------------------


@pytest.fixture(autouse=True)
def seeded(db_session):
    seed_content(db_session)


def focus_section(system: str) -> str:
    return system.split("PRACTICE FOCUS", 1)[1].split("TEACHING RULES", 1)[0]


def test_a_new_player_in_the_job_interview_is_asked_about_the_past(client, headers, interview):  # noqa: F811
    fake = use_ai(reply_json())

    send(client, headers, "Good morning.")

    assert SKILL_LABELS[PAST] in focus_section(fake.calls[0][0])


def test_the_players_own_repeated_mistake_steers_the_next_reply(client, headers, interview):  # noqa: F811
    mistake = {
        "category": "prepositions",
        "original": "in Monday",
        "corrected": "on Monday",
        "explanation": "Günler 'on' alır.",
    }
    fake = use_ai(*[reply_json(detected_errors=[mistake], correctly_used=[])] * REPEAT_MIN_MISTAKES, reply_json())
    for index in range(REPEAT_MIN_MISTAKES):
        send(client, headers, f"I can start in Monday {index}.")

    send(client, headers, "Thank you.")

    first, last = fake.calls[0][0], fake.calls[-1][0]
    assert SKILL_LABELS[PAST] in focus_section(first)  # before any mistake: the scene's skill
    assert SKILL_LABELS[PREPS] in focus_section(last)  # after three: the player's repeated mistake


def test_the_focus_follows_the_scene_in_another_quest(client, headers, db_session):  # noqa: F811
    complete_in_db(db_session, EMAIL, "meet_your_neighbor")
    cafe = quest_by_slug(db_session, "morning_at_the_cafe")
    assert client.post(f"/api/quests/{cafe.id}/start", headers=headers).status_code == 201
    fake = use_ai(reply_json())

    send(client, headers, "Good morning!")

    assert SKILL_LABELS[SkillCategory(cafe.target_skills[0])] in focus_section(fake.calls[0][0])
