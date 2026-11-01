"""The seed command: content files -> database, repeatable and update-in-place."""

import copy
import json

from sqlalchemy import func, select

from app.content.schema import Content, load_content, read_content_files
from app.content.seed import seed_content
from app.models.content import Location, Npc, QuestTemplate


def counts(db) -> tuple[int, int, int]:
    return tuple(db.scalar(select(func.count()).select_from(model)) for model in (Location, Npc, QuestTemplate))


def changed_content(mutate) -> Content:
    raw = copy.deepcopy(read_content_files())
    mutate(raw)
    return Content.model_validate(raw)


def test_first_run_creates_everything_from_the_content_files(db_session):
    content = load_content()

    report = seed_content(db_session)

    assert counts(db_session) == (len(content.locations), len(content.npcs), len(content.quests))
    assert report.created == {"location": 3, "npc": 3, "quest": 5}
    assert report.updated == {} and report.unchanged == {}


def test_running_it_twice_creates_no_duplicates_and_changes_nothing(db_session):
    seed_content(db_session)
    ids = {row.slug: row.id for row in db_session.scalars(select(QuestTemplate))}

    report = seed_content(db_session)

    assert counts(db_session) == (3, 3, 5)
    assert report.created == {} and report.updated == {}
    assert report.unchanged == {"location": 3, "npc": 3, "quest": 5}
    assert {row.slug: row.id for row in db_session.scalars(select(QuestTemplate))} == ids


def test_references_are_resolved_to_ids(db_session):
    seed_content(db_session)

    quest = db_session.scalar(select(QuestTemplate).where(QuestTemplate.slug == "the_job_interview"))

    assert quest.location.slug == "office"
    assert quest.npc.slug == "olivia"
    assert quest.npc.location_id == quest.location_id


def test_content_is_stored_as_the_files_describe_it(db_session):
    seed_content(db_session)
    quest = next(q for q in load_content().quests if q.slug == "the_job_interview")

    row = db_session.scalar(select(QuestTemplate).where(QuestTemplate.slug == "the_job_interview"))

    assert row.title == quest.title and row.chapter == quest.chapter
    assert row.target_skills == ["past_simple"]
    assert (row.min_level, row.max_level) == ("A2", "B1")
    assert row.prerequisites == {"quests_completed": ["meet_your_neighbor"], "flags": [], "min_trust": {}}
    assert row.rewards["xp"] == quest.rewards.xp
    assert [o["id"] for o in row.objectives] == [o.id for o in quest.objectives]
    assert row.allowed_story_actions == quest.allowed_story_actions


def test_a_changed_file_updates_the_row_in_place(db_session):
    seed_content(db_session)
    before = db_session.scalar(select(QuestTemplate).where(QuestTemplate.slug == "the_job_interview")).id

    def reword(raw):
        quest = next(q for q in raw["quests"] if q["slug"] == "the_job_interview")
        quest["title"] = "The Big Interview"
        quest["rewards"]["xp"] = 150
        next(n for n in raw["npcs"] if n["slug"] == "olivia")["role"] = "Head of hiring"

    report = seed_content(db_session, changed_content(reword))

    row = db_session.scalar(select(QuestTemplate).where(QuestTemplate.slug == "the_job_interview"))
    assert (row.title, row.rewards["xp"]) == ("The Big Interview", 150)
    assert row.id == before  # progress that points at this row stays valid
    assert db_session.scalar(select(Npc).where(Npc.slug == "olivia")).role == "Head of hiring"
    assert report.updated == {"quest": 1, "npc": 1}
    assert counts(db_session) == (3, 3, 5)


def test_a_new_quest_in_the_files_is_added(db_session):
    seed_content(db_session)

    def add_quest(raw):
        extra = copy.deepcopy(raw["quests"][0])
        extra.update(
            slug="extra_quest",
            title="Extra",
            prerequisites={"quests_completed": ["meet_your_neighbor"]},
            locked_summary="Something new is waiting.",
        )
        raw["quests"].append(extra)

    report = seed_content(db_session, changed_content(add_quest))

    assert report.created == {"quest": 1}
    assert counts(db_session) == (3, 3, 6)


def test_removing_a_quest_from_the_files_does_not_delete_the_row(db_session):
    # Players may already have progress on it; removing content is a deliberate migration
    seed_content(db_session)

    def remove_a_quest_nobody_refers_to(raw):
        # The content validator rightly refuses to drop a quest that an ending or another quest needs
        for quest in raw["quests"]:
            others = json.dumps([q for q in raw["quests"] if q is not quest] + [raw["endings"]])
            if quest["slug"] not in others:
                raw["quests"].remove(quest)
                return
        raise AssertionError("every quest is referenced; pick another way to remove one")

    seed_content(db_session, changed_content(remove_a_quest_nobody_refers_to))

    assert counts(db_session) == (3, 3, 5)
