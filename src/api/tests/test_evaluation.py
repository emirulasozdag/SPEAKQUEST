"""The AI evaluation tooling (#20): the labelled dataset is valid and the scoring is right.

The real measurement calls the AI provider and is run by hand (scripts/evaluate_analysis.py);
these tests check, without any AI, that what it reports can be trusted.
"""

import dataclasses
import json
import re
from pathlib import Path

import pytest

from app.engines.categories import SkillCategory
from app.models.player import EnglishLevel
from app.services.ai.prompts import build_prompt
from scripts.evaluate_analysis import (
    FOCUS_SCENES,
    MIN_SENTENCES,
    Sentence,
    compare_markdown,
    context_for,
    invites,
    load_dataset,
    run_analysis,
    score,
    score_focus,
    summary_markdown,
)
from tests.ai_fakes import FakeAiClient, reply_json

DATASET = Path(__file__).resolve().parents[3] / "docs" / "evaluation" / "sentences.json"
HOLDOUT = DATASET.with_name("holdout.json")


def dataset() -> dict:
    return json.loads(DATASET.read_text(encoding="utf-8"))


def sentence(sid, kind="error", errors=("past_simple",), understood=True) -> Sentence:
    labels = frozenset(SkillCategory(e) for e in errors)
    return Sentence(sid, kind, "the_job_interview", EnglishLevel.B1, "Hi.", "text", labels, understood)


def record(sid, detected=(), understood=True, status="ok") -> dict:
    if status != "ok":
        return {"id": sid, "status": status, "reason": "invalid_reply"}
    return {"id": sid, "status": "ok", "detected": sorted(detected), "communication_success": understood}


# --- the labelled dataset --------------------------------------------------------------------


def test_the_dataset_is_valid_and_large_enough():
    sentences = load_dataset(dataset())

    assert len(sentences) >= MIN_SENTENCES


def test_every_category_has_enough_error_sentences_and_there_are_clean_and_unclear_ones():
    sentences = load_dataset(dataset())

    for category in SkillCategory:
        assert sum(category in s.errors for s in sentences) >= 5, category
    assert sum(s.kind == "correct" for s in sentences) >= 5
    assert sum(s.kind == "unclear" for s in sentences) >= 3


def test_the_dataset_covers_both_levels_and_every_quest():
    sentences = load_dataset(dataset())

    assert {s.level for s in sentences} == set(EnglishLevel)
    assert {s.scene for s in sentences} == {
        "meet_your_neighbor",
        "morning_at_the_cafe",
        "the_flat_viewing",
        "the_job_interview",
        "the_missing_backpack",
    }


def test_every_sentence_builds_a_real_dialogue_context():
    for item in load_dataset(dataset()):
        context = context_for(item)
        assert context.history[0].text == item.npc_line
        assert context.level == item.level


def test_the_held_out_set_is_valid_and_shares_no_sentence_with_the_main_set():
    holdout = load_dataset(json.loads(HOLDOUT.read_text(encoding="utf-8")), min_sentences=10)
    main_set = load_dataset(dataset())

    assert {s.kind for s in holdout} == {"error", "correct", "unclear"}
    assert not {s.id for s in holdout} & {s.id for s in main_set}
    assert not {s.player.lower() for s in holdout} & {s.player.lower() for s in main_set}


def test_the_labelling_status_is_recorded():
    labelling = dataset()["labelling"]

    assert labelling["drafted_by"]
    assert "reviewed_by" in labelling


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"kind": "error", "errors": []}, "at least one error"),
        ({"kind": "correct", "errors": ["past_simple"]}, "no errors"),
        ({"kind": "unclear", "understood": True, "errors": []}, "not understood"),
        ({"errors": ["spelling"]}, "spelling"),
        ({"level": "C2"}, "C2"),
        ({"kind": "joke"}, "kind must be"),
        ({"understood": "false"}, "true or false"),
        ({"scene": "the_space_station"}, "unknown scene"),
    ],
)
def test_wrong_labels_are_rejected(change, problem):
    data = dataset()
    data["sentences"][0] = {**data["sentences"][0], **change}

    with pytest.raises(ValueError, match=problem):
        load_dataset(data)


def test_duplicate_ids_and_a_too_small_set_are_rejected():
    data = dataset()
    data["sentences"][1] = {**data["sentences"][1], "id": data["sentences"][0]["id"]}
    with pytest.raises(ValueError, match="duplicate"):
        load_dataset(data)

    with pytest.raises(ValueError, match=f"at least {MIN_SENTENCES}"):
        load_dataset({"sentences": dataset()["sentences"][:10]})


# Function words that two unrelated sentences share all the time
_STOPWORDS = frozenset(
    "a an the i you he she it we they my your his her our their me him us them is am are was were be "
    "do does did don't didn't to of in on at for with and but or so not no yes this that there here "
    "very too can could will would have has had what where when why how who every some any lot much many".split()
)


def content_bigrams(text: str) -> set[str]:
    """Pairs of content words that follow each other once function words are left out, so
    'make my homework' and 'make homework' share 'make homework'."""
    words = [w for w in re.findall(r"[a-z][a-z']+", text.lower()) if w not in _STOPWORDS]
    return {f"{a} {b}" for a, b in zip(words, words[1:])}


def test_the_prompt_never_contains_the_evaluation_sentences():
    # Rule examples taken from the evaluation set would measure memory, not the rule
    from app.models.player import EnglishLevel as Level

    prompts = []
    for skill in [None, *SkillCategory]:
        for level in Level:
            context = dataclasses.replace(context_for(load_dataset(dataset())[0]), level=level, practice_focus=skill)
            prompts.append(build_prompt(context, "x").system.lower())
    prompt_text = "\n".join(prompts)
    prompt_bigrams = content_bigrams(prompt_text)

    holdout = load_dataset(json.loads(HOLDOUT.read_text(encoding="utf-8")), min_sentences=10)
    for item in [*load_dataset(dataset()), *holdout]:
        assert item.player.lower() not in prompt_text, item.id
        shared = content_bigrams(item.player) & prompt_bigrams
        assert not shared, f"{item.id} shares {shared} with the prompt"


# --- scoring ---------------------------------------------------------------------------------


def test_category_recall_precision_and_accuracy():
    sentences = [
        sentence("a", errors=("past_simple",)),
        sentence("b", errors=("past_simple",)),
        sentence("c", errors=("prepositions",)),
        sentence("d", kind="correct", errors=()),
    ]
    records = [
        record("a", ["past_simple"]),  # found
        record("b", []),  # missed
        record("c", ["past_simple"]),  # wrong category: a false positive for past_simple
        record("d", []),
    ]

    past = score(sentences, records)["categories"]["past_simple"]

    assert (past["tp"], past["fn"], past["fp"], past["tn"]) == (1, 1, 1, 1)
    assert (past["recall"], past["precision"], past["accuracy"]) == (0.5, 0.5, 0.5)


def test_the_false_failure_rate_counts_understandable_sentences_judged_not_understood():
    sentences = [sentence("a"), sentence("b"), sentence("c"), sentence("d")]
    records = [record("a", understood=False), record("b"), record("c"), record("d")]

    metrics = score(sentences, records)

    assert metrics["minor_error_false_failure"] == {"count": 1, "of": 4, "rate": 0.25}
    assert metrics["communication_misses"][0]["id"] == "a"


def test_unclear_sentences_count_for_communication_but_not_for_categories():
    sentences = [sentence("u", kind="unclear", errors=(), understood=False), sentence("a")]
    records = [record("u", ["vocabulary_usage"], understood=False), record("a", ["past_simple"])]

    metrics = score(sentences, records)

    assert metrics["unclear_flagged"] == {"count": 1, "of": 1, "rate": 1.0}
    assert metrics["categories"]["vocabulary_usage"]["fp"] == 0
    assert metrics["exact_match"]["of"] == 1


def test_clean_sentences_with_an_invented_mistake_are_counted():
    sentences = [sentence("c1", kind="correct", errors=()), sentence("c2", kind="correct", errors=())]
    records = [record("c1", ["prepositions"]), record("c2", [])]

    assert score(sentences, records)["clean_false_positive"] == {"count": 1, "of": 2, "rate": 0.5}


def test_unanswered_records_are_counted_and_left_out_of_every_rate():
    sentences = [sentence("a"), sentence("b")]
    records = [record("a", ["past_simple"]), record("b", status="ai_unavailable")]

    metrics = score(sentences, records)

    assert metrics["unavailable"] == {"count": 1, "of": 2, "rate": 0.5}
    assert metrics["error_found"] == {"count": 1, "of": 1, "rate": 1.0}


def test_the_confusion_table_shows_where_missed_categories_went():
    sentences = [sentence("a", errors=("question_formation",)), sentence("b", errors=("question_formation",))]
    records = [record("a", ["present_simple"]), record("b", [])]

    confusion = score(sentences, records)["confusion"]["question_formation"]

    assert confusion == {"present_simple": 1, "(none)": 1}


def test_repeated_rounds_are_scored_as_separate_samples():
    sentences = [sentence("a")]
    records = [record("a", ["past_simple"]), record("a", [])]

    assert score(sentences, records)["error_found"] == {"count": 1, "of": 2, "rate": 0.5}


def test_reports_render_every_metric():
    sentences = [sentence("a"), sentence("c", kind="correct", errors=())]
    metrics = score(sentences, [record("a", ["past_simple"]), record("c")])

    summary = summary_markdown(metrics)
    comparison = compare_markdown({"label": "before", "metrics": metrics}, {"label": "after", "metrics": metrics})

    assert "past_simple" in summary and "yanlışlıkla başarısız" in summary
    assert "Önce (before)" in comparison and "| = |" in comparison


# --- a run with a fake AI --------------------------------------------------------------------


def test_a_run_sends_every_sentence_through_the_real_analysis_path():
    sentences = load_dataset(dataset())[:3]
    fake = FakeAiClient(*[reply_json() for _ in sentences])

    records = run_analysis(fake, sentences, delay=0, repeat=1, sleep=lambda _: None)

    assert [r["id"] for r in records] == [s.id for s in sentences]
    assert all(r["status"] == "ok" for r in records)
    assert records[0]["detected"] == ["past_simple"]
    # The app's real prompt was used, with the sentence as the player's message
    system, user = fake.calls[0]
    assert "TEACHING RULES" in system
    assert sentences[0].player in user and sentences[0].npc_line in user


def test_a_rate_limited_sentence_is_retried_after_a_pause():
    from app.services.ai.client import AiError

    sentences = load_dataset(dataset())[:1]
    fake = FakeAiClient(AiError("rate_limited"), reply_json())
    pauses = []

    records = run_analysis(fake, sentences, delay=0, repeat=1, sleep=pauses.append)

    assert records[0]["status"] == "ok"
    assert pauses  # it waited before trying again


# --- practice focus heuristics ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("category", "reply", "expected"),
    [
        (SkillCategory.PAST_SIMPLE, "Nice! What did you do yesterday?", True),
        (SkillCategory.PAST_SIMPLE, "I did my best yesterday.", False),  # no question
        (SkillCategory.PRESENT_SIMPLE, "What do you usually do on Sundays?", True),
        (SkillCategory.QUESTION_FORMATION, "Do you have any questions for me?", True),
        (SkillCategory.PREPOSITIONS, "Which floor is your flat on?", True),
        (SkillCategory.VOCABULARY_USAGE, "How would you describe your old room?", True),
        (SkillCategory.VOCABULARY_USAGE, "Do you want sugar?", False),
    ],
)
def test_reply_signs_for_each_skill(category, reply, expected):
    assert invites(category, reply) is expected


def test_focus_scores_compare_replies_with_and_without_the_focus():
    records = [
        {"status": "ok", "skill": "past_simple", "focus": True, "npc_reply": "What did you do last week?"},
        {"status": "ok", "skill": "past_simple", "focus": True, "npc_reply": "Welcome!"},
        {"status": "ok", "skill": "past_simple", "focus": False, "npc_reply": "Welcome! Coffee?"},
        {"status": "ai_unavailable", "skill": "past_simple", "focus": False},
    ]

    past = score_focus(records)["past_simple"]

    assert past["focus_on"] == {"count": 1, "of": 2, "rate": 0.5}
    assert past["focus_off"] == {"count": 0, "of": 1, "rate": 0.0}


def test_focus_scenes_are_real_quests():
    from app.content.schema import load_content

    slugs = {q.slug for q in load_content().quests}
    assert {scene for scene, _, _ in FOCUS_SCENES} <= slugs


def test_the_compare_command_prints_a_report_from_two_run_files(tmp_path, capsys):
    from scripts.evaluate_analysis import main

    sentences = [sentence("a"), sentence("c", kind="correct", errors=())]
    before = score(sentences, [record("a", []), record("c", ["prepositions"])])
    after = score(sentences, [record("a", ["past_simple"]), record("c")])
    (tmp_path / "before.json").write_text(json.dumps({"label": "before", "metrics": before}), encoding="utf-8")
    (tmp_path / "after.json").write_text(json.dumps({"label": "after", "metrics": after}), encoding="utf-8")

    assert main(["compare", str(tmp_path / "before.json"), str(tmp_path / "after.json")]) == 0

    report = capsys.readouterr().out
    assert "daha iyi" in report and "→" in report


def test_another_prompt_file_can_be_measured_with_the_same_pipeline(tmp_path, monkeypatch):
    import scripts.evaluate_analysis as evaluation
    from app.services.ai import analysis, prompts

    # Registered so monkeypatch puts the app's own prompt back after the test
    monkeypatch.setattr(analysis, "build_prompt", analysis.build_prompt)
    monkeypatch.setattr(analysis, "build_repair_prompt", analysis.build_repair_prompt)
    monkeypatch.setattr(evaluation, "build_prompt", evaluation.build_prompt)
    source = Path(prompts.__file__).read_text(encoding="utf-8")
    other = tmp_path / "other_prompts.py"
    other.write_text(source.replace("TEACHING RULES", "TEACHING RULES (OTHER VERSION)"), encoding="utf-8")

    sentences = load_dataset(dataset())[:1]
    own_fingerprint = evaluation.prompt_fingerprint(sentences)

    evaluation.use_prompt_file(str(other))
    fake = FakeAiClient(reply_json())
    run_analysis(fake, sentences, delay=0, repeat=1, sleep=lambda _: None)

    assert "TEACHING RULES (OTHER VERSION)" in fake.calls[0][0]
    # The run records which prompt it measured
    assert evaluation.prompt_fingerprint(sentences) != own_fingerprint
