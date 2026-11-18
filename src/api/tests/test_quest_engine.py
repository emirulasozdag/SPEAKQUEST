"""Adaptive Quest Engine: the next quest follows the player's weak skill, goal, story and NPCs,
and the story ends with one of the endings once nothing is left to play."""

import pytest
from sqlalchemy import select

from app.content.schema import Conditions, load_content
from app.content.seed import seed_content
from app.engines.categories import SkillCategory
from app.engines.learning import Observation, skill_scores
from app.engines.quest import (
    MIN_OBSERVATIONS,
    PlayerSnapshot,
    QuestCandidate,
    candidates_for,
    choose_next_quest,
    rank_quests,
)
from app.engines.story import StoryProgress
from app.models.dialogue import DialogueMessage, MessageRole
from app.models.learning import ObservationResult, SkillObservation
from app.models.player import EnglishLevel, LearningGoal
from app.models.quest_progress import QuestProgress
from app.models.story import StoryState
from app.models.user import User
from app.services.story import add_trust
from tests.test_player_profile import VALID_PROFILE, login_headers
from tests.test_quest_complete import meet_objectives, quest_by_slug
from tests.test_quests import complete_in_db

PS, QF = SkillCategory.PAST_SIMPLE, SkillCategory.QUESTION_FORMATION
CONTENT = load_content()
NPC_NAMES = {npc.slug: npc.name for npc in CONTENT.npcs}
QUESTS = [
    QuestCandidate(
        slug=quest.slug,
        title=quest.title,
        npc=quest.npc,
        npc_name=NPC_NAMES[quest.npc],
        chapter=quest.chapter,
        target_skills=tuple(quest.target_skills),
        min_level=quest.min_level,
        max_level=quest.max_level,
        prerequisites=quest.prerequisites,
    )
    for quest in CONTENT.quests
]
BOTH_HELPED = StoryProgress(
    completed_quests=frozenset({"meet_your_neighbor", "morning_at_the_cafe"}),
    flags=frozenset({"helped_alex", "watched_mia_bag"}),
    trust={"alex": 20, "mia": 20},
)


def scores(*results: tuple[SkillCategory, bool]):
    """Learning Engine scores from (category, correct) results, one message each, oldest first."""
    observations = [Observation(category, correct, message_id=i) for i, (category, correct) in enumerate(results, 1)]
    return skill_scores(observations, recent_message_ids=list(range(len(results), 0, -1)))


def player(skills=None, story=BOTH_HELPED, goal=LearningGoal.EVERYDAY, level=EnglishLevel.B1) -> PlayerSnapshot:
    return PlayerSnapshot(
        level=level,
        goal=goal,
        skills=skills if skills is not None else scores(),
        story=story,
        started=frozenset(story.completed_quests),
    )


STRUGGLES_WITH_PAST_SIMPLE = scores(*[(PS, False)] * 4, (SkillCategory.PRESENT_SIMPLE, True))
STRUGGLES_WITH_QUESTIONS = scores(*[(PS, True)] * 3, *[(QF, False)] * 4)


# --- candidates ------------------------------------------------------------------------------


def test_only_unlocked_quests_not_started_yet_are_candidates():
    slugs = {quest.slug for quest in candidates_for(player(), QUESTS)}

    assert slugs == {"the_flat_viewing", "the_job_interview", "the_missing_backpack", "a_walk_to_the_market"}


def test_a_quest_behind_a_decision_the_player_did_not_make_is_never_chosen():
    story = StoryProgress(completed_quests=frozenset({"meet_your_neighbor"}), trust={"alex": 5})
    ranking = rank_quests(player(STRUGGLES_WITH_QUESTIONS, story=story), QUESTS)

    assert "the_flat_viewing" not in [item.slug for item in ranking]


def test_nothing_to_start_means_no_recommendation():
    story = StoryProgress(completed_quests=frozenset(quest.slug for quest in QUESTS), flags=BOTH_HELPED.flags)

    assert choose_next_quest(player(story=story), QUESTS) is None


# --- the README demo rule ---------------------------------------------------------------------


def test_a_player_struggling_with_the_past_simple_gets_the_missing_backpack():
    chosen = choose_next_quest(player(STRUGGLES_WITH_PAST_SIMPLE), QUESTS)

    assert chosen.slug == "the_missing_backpack"
    assert "Past Simple" in chosen.reason


def test_a_player_struggling_with_questions_gets_a_different_quest():
    chosen = choose_next_quest(player(STRUGGLES_WITH_QUESTIONS), QUESTS)

    assert chosen.slug == "the_flat_viewing"
    assert "Question Formation" in chosen.reason


def test_the_reason_explains_a_repeated_mistake_and_the_relationship():
    chosen = choose_next_quest(player(STRUGGLES_WITH_PAST_SIMPLE), QUESTS)

    assert chosen.reason == "It practises Past Simple, a mistake you keep making. Mia already trusts you."


# --- learning goal while there is too little data ----------------------------------------------


AFTER_THE_FIRST_QUEST = StoryProgress(completed_quests=frozenset({"meet_your_neighbor"}), trust={"alex": 5})


@pytest.mark.parametrize(
    ("goal", "expected"),
    [
        (LearningGoal.WORK, "the_job_interview"),
        (LearningGoal.EVERYDAY, "morning_at_the_cafe"),
    ],
)
def test_without_enough_data_the_learning_goal_decides(goal, expected):
    chosen = choose_next_quest(player(story=AFTER_THE_FIRST_QUEST, goal=goal), QUESTS)

    assert chosen.slug == expected
    assert "fits your goal" in chosen.reason


def test_with_enough_data_the_weak_skill_wins_over_the_goal():
    skills = scores(*[(PS, False)] * MIN_OBSERVATIONS)

    chosen = choose_next_quest(player(skills, story=AFTER_THE_FIRST_QUEST, goal=LearningGoal.EVERYDAY), QUESTS)

    assert chosen.slug == "the_job_interview"


def test_a_brand_new_player_starts_with_the_starter_quest():
    new = StoryProgress()

    chosen = choose_next_quest(player(story=new, goal=LearningGoal.WORK), QUESTS)

    assert chosen.slug == "meet_your_neighbor"
    assert "continues your story" in chosen.reason


# --- the other criteria ---------------------------------------------------------------------


def test_a_quest_outside_the_players_level_loses_points():
    hard = QuestCandidate(
        slug="hard", title="Hard", npc="olivia", npc_name="Olivia", chapter=1,
        target_skills=(PS,), min_level=EnglishLevel.B1, max_level=EnglishLevel.B1,
    )
    easy = QuestCandidate(
        slug="easy", title="Easy", npc="olivia", npc_name="Olivia", chapter=1,
        target_skills=(PS,), min_level=EnglishLevel.A2, max_level=EnglishLevel.A2,
    )

    ranking = rank_quests(player(STRUGGLES_WITH_PAST_SIMPLE, story=StoryProgress(), level=EnglishLevel.A2), [hard, easy])

    assert [item.slug for item in ranking] == ["easy", "hard"]
    assert ranking[1].breakdown["level_fit"] < 0


def test_more_trust_pulls_the_player_back_to_that_npc():
    def quest(slug: str, npc: str) -> QuestCandidate:
        return QuestCandidate(
            slug=slug, title=slug, npc=npc, npc_name=npc.title(), chapter=1, target_skills=(PS,),
            min_level=EnglishLevel.A2, max_level=EnglishLevel.B1, prerequisites=Conditions(),
        )

    story = StoryProgress(trust={"mia": 40})
    ranking = rank_quests(player(STRUGGLES_WITH_PAST_SIMPLE, story=story), [quest("a", "olivia"), quest("b", "mia")])

    assert ranking[0].slug == "b"
    assert ranking[0].breakdown["npc_trust"] == 4


def test_the_ranking_is_deterministic():
    first = rank_quests(player(STRUGGLES_WITH_QUESTIONS), QUESTS)

    assert all(rank_quests(player(STRUGGLES_WITH_QUESTIONS), QUESTS) == first for _ in range(5))


# --- through the API ------------------------------------------------------------------------


@pytest.fixture
def seeded(db_session):
    seed_content(db_session)


def add_results(db_session, email: str, quest_slug: str, *results: tuple[SkillCategory, bool]) -> None:
    """Player messages with skill observations, in a quest the player has completed."""
    user_id = db_session.scalar(select(User.id).where(User.email == email))
    progress = db_session.scalar(
        select(QuestProgress).where(
            QuestProgress.user_id == user_id,
            QuestProgress.quest_template_id == quest_by_slug(db_session, quest_slug).id,
        )
    )
    for category, correct in results:
        message = DialogueMessage(quest_progress_id=progress.id, role=MessageRole.PLAYER, text="…")
        db_session.add(message)
        db_session.flush()
        result = ObservationResult.CORRECT if correct else ObservationResult.INCORRECT
        db_session.add(SkillObservation(user_id=user_id, message_id=message.id, category=category, result=result))
    db_session.commit()


def demo_player(client, db_session, email: str, *results) -> dict[str, str]:
    """Both "help" decisions made and the café quest done, then these results."""
    headers = login_headers(client, email)
    client.put("/api/player/profile", json=VALID_PROFILE, headers=headers)
    for slug in ("meet_your_neighbor", "morning_at_the_cafe"):
        complete_in_db(db_session, email, slug)
    state = db_session.scalar(select(StoryState).join(User, User.id == StoryState.user_id).where(User.email == email))
    state.flags = ["helped_alex", "watched_mia_bag"]
    # What the two quest rewards (+5) and the two decisions (+15) give when played for real
    add_trust(db_session, state.user_id, {"alex": 20, "mia": 20})
    db_session.commit()
    add_results(db_session, email, "morning_at_the_cafe", *results)
    return headers


def recommended(client, headers) -> list[dict]:
    return [quest for quest in client.get("/api/quests", headers=headers).json() if quest["recommended"]]


def test_two_players_with_different_weaknesses_get_different_quests(client, db_session, seeded):
    past = demo_player(client, db_session, "past@example.com", *[(PS, False)] * 4, (SkillCategory.PRESENT_SIMPLE, True))
    questions = demo_player(client, db_session, "questions@example.com", *[(PS, True)] * 3, *[(QF, False)] * 4)

    [for_past] = recommended(client, past)
    [for_questions] = recommended(client, questions)

    assert for_past["slug"] == "the_missing_backpack"
    assert for_questions["slug"] == "the_flat_viewing"
    assert "Past Simple" in for_past["recommendation_reason"]


def test_the_quest_list_marks_one_recommendation_with_a_reason(client, db_session, seeded):
    headers = login_headers(client, "new@example.com")
    client.put("/api/player/profile", json={**VALID_PROFILE, "learning_goal": "work"}, headers=headers)

    quests = client.get("/api/quests", headers=headers).json()

    assert [quest["slug"] for quest in quests if quest["recommended"]] == ["meet_your_neighbor"]
    assert all(quest["recommendation_reason"] is None for quest in quests if not quest["recommended"])


def locked_reasons(client, headers) -> dict[str, str | None]:
    return {q["slug"]: q["locked_reason"] for q in client.get("/api/quests", headers=headers).json()}


def test_locked_quests_say_what_they_wait_for_without_giving_the_choice_away(client, db_session, seeded):
    headers = login_headers(client, "new@example.com")
    client.put("/api/player/profile", json=VALID_PROFILE, headers=headers)

    reasons = locked_reasons(client, headers)

    assert reasons["meet_your_neighbor"] is None
    assert reasons["the_job_interview"] == "Complete Meet Your Neighbor first."
    assert reasons["the_flat_viewing"] == (
        "Complete Meet Your Neighbor first. Opens through a choice you make in Meet Your Neighbor."
    )
    assert "Help Alex" not in reasons["the_flat_viewing"]


def test_a_choice_made_the_other_way_closes_the_quest_for_good(client, db_session, seeded):
    headers = login_headers(client, "new@example.com")
    client.put("/api/player/profile", json=VALID_PROFILE, headers=headers)
    starter = quest_by_slug(db_session, "meet_your_neighbor")
    client.post(f"/api/quests/{starter.id}/start", headers=headers)
    payload = {"quest_id": starter.id, "decision_id": "help_alex_move", "option_id": "not_now"}
    client.post("/api/story/decision", json=payload, headers=headers)

    reasons = locked_reasons(client, headers)

    assert reasons["the_flat_viewing"] == (
        "Your choice in Meet Your Neighbor took the story another way, so this quest stays closed."
    )
    # Not about a choice, so it still only waits for the quest
    assert reasons["the_job_interview"] == "Complete Meet Your Neighbor first."


def test_no_recommendation_while_a_quest_is_active(client, db_session, seeded):
    headers = login_headers(client, "new@example.com")
    client.put("/api/player/profile", json=VALID_PROFILE, headers=headers)
    starter = quest_by_slug(db_session, "meet_your_neighbor")
    client.post(f"/api/quests/{starter.id}/start", headers=headers)

    assert recommended(client, headers) == []


# --- playing the whole story ----------------------------------------------------------------

EMAIL = "story@example.com"

# Every decision in the story: the quest it belongs to, its id, and the "yes" and "no" options
DECISIONS = {
    "meet_your_neighbor": ("help_alex_move", "help", "not_now"),
    "morning_at_the_cafe": ("watch_mia_bag", "watch", "in_a_hurry"),
    "first_day_at_work": ("late_customer", "stay_and_help", "come_back_tomorrow"),
    "a_walk_to_the_market": ("festival_volunteer", "volunteer", "busy_weekend"),
    "the_river_festival": ("invite_neighbours", "invite", "keep_it_simple"),
}
SAY_YES_TO_EVERYTHING = frozenset(DECISIONS)
NEIGHBOUR_DECISIONS = frozenset({"meet_your_neighbor", "morning_at_the_cafe"})
TOTAL_XP = 50 + 60 + 80 + 100 + 120 + 100 + 70 + 140


def play_through(client, db_session, headers, *, say_yes_in=frozenset()) -> dict:
    """Play every quest the story allows, making every decision; returns the last completion.

    say_yes_in names the quests whose decision is answered "yes"; every other decision is "no".
    """
    last = None
    while True:
        available = [q for q in client.get("/api/quests", headers=headers).json() if q["status"] == "available"]
        if not available:
            return last
        quest = quest_by_slug(db_session, available[0]["slug"])
        assert client.post(f"/api/quests/{quest.id}/start", headers=headers).status_code == 201
        if quest.slug in DECISIONS:
            decision, yes, no = DECISIONS[quest.slug]
            option = yes if quest.slug in say_yes_in else no
            payload = {"quest_id": quest.id, "decision_id": decision, "option_id": option}
            assert client.post("/api/story/decision", json=payload, headers=headers).status_code == 201
        meet_objectives(db_session, EMAIL, quest)
        response = client.post(f"/api/quests/{quest.id}/complete", headers=headers)
        assert response.status_code == 200
        last = response.json()


def quest_statuses(client, headers) -> dict[str, str]:
    return {q["slug"]: q["status"] for q in client.get("/api/quests", headers=headers).json()}


@pytest.fixture
def story_player(client, db_session, seeded):
    headers = login_headers(client, EMAIL)
    client.put("/api/player/profile", json=VALID_PROFILE, headers=headers)
    return headers


def test_saying_yes_to_everyone_plays_all_eight_quests_and_reaches_the_best_ending(
    client, db_session, story_player
):
    assert client.get("/api/story/ending", headers=story_player).status_code == 404

    last = play_through(client, db_session, story_player, say_yes_in=SAY_YES_TO_EVERYTHING)

    statuses = quest_statuses(client, story_player)
    assert set(statuses.values()) == {"completed"} and len(statuses) == 8
    assert last["ending"]["slug"] == "heart_of_the_neighbourhood"
    assert client.get("/api/story/state", headers=story_player).json()["ending"] == "heart_of_the_neighbourhood"
    ending = client.get("/api/story/ending", headers=story_player).json()
    assert ending["title"] == "Heart of the Neighbourhood" and ending["summary"]
    assert ending["quests_completed"] == 8
    assert ending["xp"] == TOTAL_XP
    choices = {d["quest_title"]: d["choice"] for d in ending["decisions"]}
    assert choices == {
        "Meet Your Neighbor": "Help Alex carry the boxes upstairs.",
        "Morning at the Café": "Say yes and watch the backpack until Mia comes back.",
        "First Day at Work": "Stay a little longer and help the traveller book a new ticket.",
        "A Walk to the Market": "Say yes and promise to help at the flower stall on Saturday.",
        "The River Festival": "Call Alex and Mia and invite them to share the empty table.",
    }


def test_the_decisions_are_listed_in_the_order_they_were_made(client, db_session, story_player):
    play_through(client, db_session, story_player, say_yes_in=SAY_YES_TO_EVERYTHING)

    ending = client.get("/api/story/ending", headers=story_player).json()

    titles = [d["quest_title"] for d in ending["decisions"]]
    assert titles[0] == "Meet Your Neighbor"
    # The festival decision can only be made after the market walk opened the festival
    assert titles.index("A Walk to the Market") < titles.index("The River Festival")


def test_helping_only_the_neighbours_at_home_reaches_home_at_last(client, db_session, story_player):
    last = play_through(client, db_session, story_player, say_yes_in=NEIGHBOUR_DECISIONS)

    statuses = quest_statuses(client, story_player)
    assert statuses["the_flat_viewing"] == statuses["the_missing_backpack"] == "completed"
    assert statuses["the_river_festival"] == "locked"
    assert last["ending"]["slug"] == "home_at_last"
    assert client.get("/api/story/ending", headers=story_player).json()["quests_completed"] == 7


def test_skipping_the_festival_party_still_reaches_home_at_last(client, db_session, story_player):
    # Everything but the festival invitation: the best ending needs it, Home at Last does not
    say_yes = SAY_YES_TO_EVERYTHING - {"the_river_festival"}

    last = play_through(client, db_session, story_player, say_yes_in=say_yes)

    assert set(quest_statuses(client, story_player).values()) == {"completed"}
    assert last["ending"]["slug"] == "home_at_last"


def test_helping_only_at_work_reaches_a_place_in_the_city(client, db_session, story_player):
    last = play_through(client, db_session, story_player, say_yes_in={"first_day_at_work"})

    statuses = quest_statuses(client, story_player)
    assert statuses["the_flat_viewing"] == statuses["the_missing_backpack"] == "locked"
    assert statuses["first_day_at_work"] == "completed"
    assert last["ending"]["slug"] == "a_place_in_the_city"
    ending = client.get("/api/story/ending", headers=story_player).json()
    assert ending["title"] == "A Place in the City"
    assert ending["quests_completed"] == 5


def test_the_ending_names_the_skill_that_improved_most(client, db_session, story_player):
    play_through(client, db_session, story_player)
    add_results(db_session, EMAIL, "meet_your_neighbor", (PS, True), (PS, True), (QF, True), (QF, False))

    ending = client.get("/api/story/ending", headers=story_player).json()

    assert ending["most_improved_skill"]["category"] == "past_simple"
    assert ending["most_improved_skill"]["start_score"] == 50
    assert ending["most_improved_skill"]["score"] > 50


def test_saying_no_to_everyone_skips_three_quests_and_reaches_new_in_town(client, db_session, story_player):
    last = play_through(client, db_session, story_player)

    statuses = quest_statuses(client, story_player)
    assert statuses["the_flat_viewing"] == statuses["the_missing_backpack"] == "locked"
    assert statuses["the_river_festival"] == "locked"
    assert last["ending"]["slug"] == "new_in_town"
    ending = client.get("/api/story/ending", headers=story_player).json()
    assert ending["quests_completed"] == 5 and ending["most_improved_skill"] is None
    assert {d["choice"] for d in ending["decisions"]} == {
        "Say you are too tired after the journey.",
        "Say sorry, you are in a hurry.",
        "Politely ask the traveller to come back tomorrow morning.",
        "Say sorry, you already have plans this weekend.",
    }


def test_only_the_last_quest_ends_the_story(client, db_session, story_player):
    starter = quest_by_slug(db_session, "meet_your_neighbor")
    client.post(f"/api/quests/{starter.id}/start", headers=story_player)
    meet_objectives(db_session, EMAIL, starter)

    response = client.post(f"/api/quests/{starter.id}/complete", headers=story_player)

    assert response.json()["ending"] is None


def test_after_the_ending_the_story_is_closed(client, db_session, story_player):
    play_through(client, db_session, story_player)
    starter = quest_by_slug(db_session, "meet_your_neighbor")
    payload = {"quest_id": starter.id, "decision_id": "help_alex_move", "option_id": "help"}

    # The decision was already made, but even a new one would be refused now
    assert client.post("/api/story/decision", json=payload, headers=story_player).status_code == 409
    assert recommended(client, story_player) == []


def test_a_reset_opens_the_story_again(client, db_session, story_player):
    play_through(client, db_session, story_player)

    client.post("/api/player/reset", headers=story_player)

    assert client.get("/api/story/ending", headers=story_player).status_code == 404
    assert [q["slug"] for q in recommended(client, story_player)] == ["meet_your_neighbor"]
