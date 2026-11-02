"""Measure the AI language analysis on the labelled sentences in docs/evaluation/ (#20).

Every sentence goes through the same path as a real dialogue turn: the app's own prompt
(services/ai/prompts.py), its validation and its one repair attempt (services/ai/analysis.py),
with the scene, NPC and level taken from the content files. Only the player's earlier
conversation is shortened to the one NPC line the sentence answers.

It calls the real AI provider configured for the app, so it needs AI_PROVIDER and AI_API_KEY. The
key lives only in the API container's environment; run the script there and keep the files on the
host, so the key never reaches a file or the console:

    docker compose exec -T api python scripts/evaluate_analysis.py analyse --label before \
        < docs/evaluation/sentences.json > docs/evaluation/runs/before.json

    git show main:src/api/app/services/ai/prompts.py > src/api/old_prompts.py   # an older prompt
    docker compose exec -T api python scripts/evaluate_analysis.py analyse --label old \
        --prompt-file old_prompts.py < docs/evaluation/sentences.json > docs/evaluation/runs/old.json

    docker compose exec -T api python scripts/evaluate_analysis.py focus --label after \
        > docs/evaluation/runs/focus.json

    cd src/api && python scripts/evaluate_analysis.py compare \
        ../../docs/evaluation/runs/before.json ../../docs/evaluation/runs/after.json   # no AI call

JSON goes to stdout, a short readable summary to stderr. The script is not part of the app, and CI
does not run it because it calls the real provider (the free Gemini tier is enough). Its dataset
check and scoring are pure functions, tested in tests/test_evaluation.py.
"""

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.content.schema import load_content  # noqa: E402
from app.engines.categories import SkillCategory  # noqa: E402
from app.models.player import EnglishLevel  # noqa: E402
from app.services.ai.analysis import AnalysisResult, analyze_message  # noqa: E402
from app.services.ai.prompts import (  # noqa: E402
    DialogueContext,
    HistoryLine,
    NpcProfile,
    QuestBrief,
    build_prompt,
)

KINDS = ("error", "correct", "unclear")
MIN_SENTENCES = 40
# The free Gemini tier allows a few requests per minute; one sentence may need two calls (repair)
DEFAULT_DELAY_SECONDS = 4.5
# Provider problems that pass by themselves (quota per minute, overload, slow or broken network):
# the sentence is tried again after a pause instead of being recorded as unanswered. Anything
# else (a wrong key, an invalid reply after the repair attempt) is a real result and is kept.
TRANSIENT_REASONS = frozenset({"rate_limited", "unavailable", "timeout", "network"})
RETRY_PAUSE_SECONDS = 15
RETRY_ATTEMPTS = 6


# --- dataset ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Sentence:
    id: str
    kind: str
    scene: str
    level: EnglishLevel
    npc_line: str
    player: str
    errors: frozenset[SkillCategory]
    understood: bool


def load_dataset(data: Mapping, min_sentences: int = MIN_SENTENCES) -> list[Sentence]:
    """Validate the labelled set and return it. Raises ValueError with every problem found."""
    problems = []
    sentences = []
    seen = set()
    scenes = {quest.slug for quest in load_content().quests}
    for raw in data.get("sentences", []):
        sid = raw.get("id", "?")
        try:
            sentence = Sentence(
                id=raw["id"],
                kind=raw["kind"],
                scene=raw["scene"],
                level=EnglishLevel(raw["level"]),
                npc_line=raw["npc_line"].strip(),
                player=raw["player"].strip(),
                errors=frozenset(SkillCategory(c) for c in raw["errors"]),
                understood=raw["understood"],
            )
        except (KeyError, ValueError) as exc:
            problems.append(f"{sid}: {exc}")
            continue
        # Strict: a quoted "false" would otherwise count as true and silently flip the label
        if not isinstance(sentence.understood, bool):
            problems.append(f"{sid}: understood must be true or false")
        if sentence.scene not in scenes:
            problems.append(f"{sid}: unknown scene {sentence.scene!r}, use a quest slug")
        if sentence.id in seen:
            problems.append(f"{sid}: duplicate id")
        seen.add(sentence.id)
        if sentence.kind not in KINDS:
            problems.append(f"{sid}: kind must be one of {KINDS}")
        if sentence.kind == "error" and not (sentence.errors and sentence.understood):
            problems.append(f"{sid}: an 'error' sentence has at least one error and is understood")
        if sentence.kind == "correct" and (sentence.errors or not sentence.understood):
            problems.append(f"{sid}: a 'correct' sentence has no errors and is understood")
        if sentence.kind == "unclear" and (sentence.errors or sentence.understood):
            problems.append(f"{sid}: an 'unclear' sentence is not understood and has no error labels")
        if not sentence.player or not sentence.npc_line:
            problems.append(f"{sid}: empty text")
        sentences.append(sentence)
    if len(sentences) < min_sentences:
        problems.append(f"at least {min_sentences} sentences are needed, found {len(sentences)}")
    if problems:
        raise ValueError("; ".join(problems))
    return sentences


def context_for(sentence: Sentence, content=None, practice_focus: SkillCategory | None = None) -> DialogueContext:
    """The dialogue context a real turn in this scene would have, with the NPC's line before."""
    content = content or load_content()
    quest = next(q for q in content.quests if q.slug == sentence.scene)
    npc = next(n for n in content.npcs if n.slug == quest.npc)
    return DialogueContext(
        # With the quest, as in the game: the NPC also knows this quest's own facts (#64)
        npc=NpcProfile.from_content(npc, quest),
        quest=QuestBrief.from_template(quest),
        level=sentence.level,
        history=(HistoryLine(speaker="npc", text=sentence.npc_line),),
        practice_focus=practice_focus,
    )


# --- one run ---------------------------------------------------------------------------------


def outcome_record(sentence: Sentence, result: AnalysisResult, seconds: float) -> dict:
    """What one analysis returned, in the shape the scoring functions read."""
    record = {"id": sentence.id, "status": result.status, "seconds": round(seconds, 2)}
    if not result.ok:
        record["reason"] = result.reason
        return record
    analysis = result.analysis
    record.update(
        communication_success=analysis.communication_success,
        detected=sorted({str(e.category) for e in analysis.detected_errors}),
        corrections=[
            {
                "category": str(e.category),
                "original": e.original,
                "corrected": e.corrected,
                "explanation": e.explanation,
            }
            for e in analysis.detected_errors
        ],
        npc_reply=analysis.npc_reply,
    )
    return record


def analyse_with_retry(client, context: DialogueContext, text: str, sleep: Callable[[float], None]) -> AnalysisResult:
    """analyze_message(), waiting and trying again while the provider has a passing problem."""
    for attempt in range(RETRY_ATTEMPTS):
        if attempt:
            sleep(RETRY_PAUSE_SECONDS)
        result = analyze_message(client, context, text)
        if result.ok or result.reason not in TRANSIENT_REASONS:
            return result
    return result


def run_analysis(client, sentences: Sequence[Sentence], delay: float, repeat: int, sleep=time.sleep) -> list[dict]:
    content = load_content()
    records = []
    for round_ in range(repeat):
        for index, sentence in enumerate(sentences):
            if records:
                sleep(delay)
            started = time.perf_counter()
            result = analyse_with_retry(client, context_for(sentence, content), sentence.player, sleep)
            records.append({**outcome_record(sentence, result, time.perf_counter() - started), "round": round_ + 1})
            print(f"  {round_ + 1}.{index + 1:>2}/{len(sentences)} {sentence.id} {result.status}", file=sys.stderr)
    return records


# --- scoring (pure) --------------------------------------------------------------------------


def _rate(part: int, whole: int) -> dict:
    return {"count": part, "of": whole, "rate": round(part / whole, 3) if whole else None}


def score(sentences: Iterable[Sentence], records: Iterable[dict]) -> dict:
    """Every metric of one run. Records the AI could not answer are counted and left out."""
    by_id = {s.id: s for s in sentences}
    records = list(records)
    answered = [r for r in records if r["status"] == "ok"]

    graded = [(by_id[r["id"]], r) for r in answered if by_id[r["id"]].kind in ("error", "correct")]
    categories = {}
    for category in SkillCategory:
        tp = fp = fn = tn = 0
        for sentence, record in graded:
            expected, found = category in sentence.errors, category.value in record["detected"]
            tp += expected and found
            fn += expected and not found
            fp += found and not expected
            tn += not expected and not found
        categories[category.value] = {
            "expected": tp + fn,
            "recall": round(tp / (tp + fn), 3) if tp + fn else None,
            "precision": round(tp / (tp + fp), 3) if tp + fp else None,
            "accuracy": round((tp + tn) / len(graded), 3) if graded else None,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        }

    errors = [(s, r) for s, r in graded if s.kind == "error"]
    correct = [(s, r) for s, r in graded if s.kind == "correct"]
    unclear = [(by_id[r["id"]], r) for r in answered if by_id[r["id"]].kind == "unclear"]

    confusion: dict[str, Counter] = {category.value: Counter() for category in SkillCategory}
    for sentence, record in errors:
        for category in sentence.errors:
            confusion[category.value].update(record["detected"] or ["(none)"])

    return {
        "records": len(records),
        "answered": len(answered),
        "unavailable": _rate(len(records) - len(answered), len(records)),
        "categories": categories,
        "exact_match": _rate(sum(set(r["detected"]) == {c.value for c in s.errors} for s, r in graded), len(graded)),
        "error_found": _rate(sum(_found_any(s, r) for s, r in errors), len(errors)),
        "clean_false_positive": _rate(sum(bool(r["detected"]) for _, r in correct), len(correct)),
        # The issue's key number: understandable sentences with small mistakes judged as not understood
        "minor_error_false_failure": _rate(sum(r["communication_success"] is False for _, r in errors), len(errors)),
        "correct_false_failure": _rate(sum(r["communication_success"] is False for _, r in correct), len(correct)),
        "unclear_flagged": _rate(sum(r["communication_success"] is False for _, r in unclear), len(unclear)),
        "confusion": {category: dict(counter) for category, counter in confusion.items()},
        "misses": [
            {"id": s.id, "player": s.player, "expected": sorted(c.value for c in s.errors), "detected": r["detected"]}
            for s, r in graded
            if set(r["detected"]) != {c.value for c in s.errors}
        ],
        "communication_misses": [
            {"id": s.id, "player": s.player, "expected": s.understood, "got": r["communication_success"]}
            for s, r in [*graded, *unclear]
            if r["communication_success"] != s.understood
        ],
    }


def _found_any(sentence: Sentence, record: dict) -> bool:
    """At least one of the sentence's labelled categories was detected."""
    return bool({c.value for c in sentence.errors} & set(record["detected"]))


# --- practice focus (pure parts) -------------------------------------------------------------

# Rough signs that an NPC reply invites the player to use a structure. They are heuristics for a
# quick, repeatable comparison (focus on vs off); the replies are saved for a human to read.
FOCUS_SIGNS: Mapping[SkillCategory, re.Pattern] = {
    SkillCategory.PRESENT_SIMPLE: re.compile(
        r"\b(usually|normally|often|every (day|morning|week|evening|weekend)|how often|"
        r"do you (like|work|live|have|go|do|want|need)|does (she|he|it|your))\b",
        re.I,
    ),
    SkillCategory.PAST_SIMPLE: re.compile(
        r"\b(did you|what happened|yesterday|last (week|year|night|time)|when did|where did|were you|was it)\b", re.I
    ),
    SkillCategory.QUESTION_FORMATION: re.compile(
        r"(any questions|ask me|want to know|like to know|anything you('d| would) like to ask|"
        r"questions for me|curious about|what would you ask)",
        re.I,
    ),
    SkillCategory.PREPOSITIONS: re.compile(
        r"\b(where exactly|what time|which floor|where (is|was|do|did|are)|when do you|"
        r"how do you get to|next to|in front of|on the|at the)\b",
        re.I,
    ),
    SkillCategory.VOCABULARY_USAGE: re.compile(
        r"\b(describe|what is it like|what was it like|what kind of|how would you|tell me (more )?about|"
        r"in your own words|what word)\b",
        re.I,
    ),
}

# Neutral player lines that do not push the conversation towards any structure themselves
FOCUS_SCENES = (
    ("meet_your_neighbor", "Hi! I'm the new neighbour. Nice to meet you.", "Oh, hi! You must be the new neighbour."),
    ("morning_at_the_cafe", "Good morning! It's a nice place.", "Good morning! Welcome to the Corner Café."),
    ("the_job_interview", "Good morning. Thank you for meeting me.", "Good morning! Please, have a seat."),
)


def invites(category: SkillCategory, reply: str) -> bool:
    """True when the reply asks something and shows a sign of the category (FOCUS_SIGNS)."""
    return "?" in reply and bool(FOCUS_SIGNS[category].search(reply))


def score_focus(records: Iterable[dict]) -> dict:
    """For each skill: how often the reply invited it with the focus on, and with it off."""
    table = {}
    for category in SkillCategory:
        rows = [r for r in records if r.get("status") == "ok" and r["skill"] == category.value]
        on = [r for r in rows if r["focus"]]
        off = [r for r in rows if not r["focus"]]
        table[category.value] = {
            "focus_on": _rate(sum(invites(category, r["npc_reply"]) for r in on), len(on)),
            "focus_off": _rate(sum(invites(category, r["npc_reply"]) for r in off), len(off)),
        }
    return table


def run_focus(client, delay: float, repeat: int, sleep=time.sleep) -> list[dict]:
    content = load_content()
    records = []
    for round_ in range(repeat):
        for scene, player, npc_line in FOCUS_SCENES:
            for category in SkillCategory:
                for focus in (True, False):
                    if records:
                        sleep(delay)
                    sentence = Sentence("focus", "correct", scene, EnglishLevel.A2, npc_line, player, frozenset(), True)
                    context = context_for(sentence, content, category if focus else None)
                    result = analyse_with_retry(client, context, player, sleep)
                    record = {"scene": scene, "skill": category.value, "focus": focus, "status": result.status,
                              "round": round_ + 1}
                    if result.ok:
                        record["npc_reply"] = result.analysis.npc_reply
                    records.append(record)
                    print(f"  {scene} {category.value} focus={focus} {result.status}", file=sys.stderr)
    return records


# --- reports ---------------------------------------------------------------------------------


def _pct(value: dict | float | None) -> str:
    rate = value.get("rate") if isinstance(value, dict) else value
    return "–" if rate is None else f"{rate * 100:.0f}%"


def _frac(value: dict) -> str:
    return f"{_pct(value)} ({value['count']}/{value['of']})"


def summary_markdown(metrics: dict) -> str:
    lines = [
        "| Kategori | Beklenen | Recall | Precision | Doğruluk |",
        "|---|---|---|---|---|",
    ]
    for category, m in metrics["categories"].items():
        cells = [category, str(m["expected"]), _pct(m["recall"]), _pct(m["precision"]), _pct(m["accuracy"])]
        lines.append("| " + " | ".join(cells) + " |")
    lines += [
        "",
        "- Anlaşılır ama küçük hatalı cümlede yanlışlıkla başarısız: "
        f"**{_frac(metrics['minor_error_false_failure'])}**",
        f"- Hatasız cümlede yanlışlıkla başarısız: {_frac(metrics['correct_false_failure'])}",
        f"- Anlaşılmaz cümleyi doğru yakalama: {_frac(metrics['unclear_flagged'])}",
        f"- Hatasız cümlede uydurulan hata: {_frac(metrics['clean_false_positive'])}",
        f"- Hatalı cümlede doğru kategorinin bulunması: {_frac(metrics['error_found'])}",
        f"- Kategori kümesinin birebir doğru olması: {_frac(metrics['exact_match'])}",
        f"- Kullanılamayan cevap: {_frac(metrics['unavailable'])}",
    ]
    return "\n".join(lines)


def compare_markdown(before: dict, after: dict) -> str:
    b, a = before["metrics"], after["metrics"]
    rows = [
        ("Yanlışlıkla başarısız (küçük hatalı)", "minor_error_false_failure", False),
        ("Yanlışlıkla başarısız (hatasız)", "correct_false_failure", False),
        ("Anlaşılmazı yakalama", "unclear_flagged", True),
        ("Hatasızda uydurulan hata", "clean_false_positive", False),
        ("Hatalıda doğru kategori", "error_found", True),
        ("Kategori kümesi birebir", "exact_match", True),
        ("Kullanılamayan cevap", "unavailable", False),
    ]
    lines = [f"| Ölçüt | Önce ({before['label']}) | Sonra ({after['label']}) | Yön |", "|---|---|---|---|"]
    for title, key, higher_is_better in rows:
        delta = (a[key]["rate"] or 0) - (b[key]["rate"] or 0)
        better = delta > 0 if higher_is_better else delta < 0
        mark = "=" if abs(delta) < 0.0005 else ("daha iyi" if better else "daha kötü")
        lines.append(f"| {title} | {_frac(b[key])} | {_frac(a[key])} | {mark} |")
    lines += ["", "| Kategori | Recall önce → sonra | Precision önce → sonra |", "|---|---|---|"]
    for category in b["categories"]:
        cb, ca = b["categories"][category], a["categories"][category]
        recall = f"{_pct(cb['recall'])} → {_pct(ca['recall'])}"
        precision = f"{_pct(cb['precision'])} → {_pct(ca['precision'])}"
        lines.append(f"| {category} | {recall} | {precision} |")
    return "\n".join(lines)


def prompt_fingerprint(sentences: Sequence[Sentence]) -> str:
    """A short hash of the system prompt for the first sentence, so two runs show whether the
    prompt changed between them."""
    system = build_prompt(context_for(sentences[0]), "x").system
    return hashlib.sha256(system.encode()).hexdigest()[:12]


def use_prompt_file(path: str) -> None:
    """Measure another version of services/ai/prompts.py, e.g. main's (`git show main:...`).

    Only the prompt text changes; validation, the repair attempt and the scoring stay the same, so
    two runs differ in nothing but the prompt. The run's prompt fingerprint shows which one was used.
    """
    global build_prompt
    spec = importlib.util.spec_from_file_location("evaluated_prompts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from app.services.ai import analysis

    analysis.build_prompt, analysis.build_repair_prompt = module.build_prompt, module.build_repair_prompt
    build_prompt = module.build_prompt


# --- command line ----------------------------------------------------------------------------


def _client():
    from app.core.config import get_settings
    from app.services.ai.client import build_client

    settings = get_settings()
    return build_client(settings), (settings.ai_model or "default")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    analyse = sub.add_parser("analyse", help="score the labelled sentences (dataset on stdin)")
    focus = sub.add_parser("focus", help="compare NPC replies with and without a practice focus")
    analyse.add_argument(
        "--min-sentences", type=int, default=MIN_SENTENCES, help="smaller for the held-out set (holdout.json)"
    )
    analyse.add_argument("--prompt-file", help="measure this prompts.py instead of the app's own")
    for command in (analyse, focus):
        command.add_argument("--label", required=True)
        command.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS)
        command.add_argument("--repeat", type=int, default=1)
    compare = sub.add_parser("compare", help="Markdown comparison of two analyse runs (no AI call)")
    compare.add_argument("before")
    compare.add_argument("after")
    args = parser.parse_args(argv)
    # The reports contain Turkish letters and arrows; a Windows console would otherwise fail on them
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    if args.command == "compare":
        before, after = (json.loads(Path(p).read_text(encoding="utf-8")) for p in (args.before, args.after))
        print(compare_markdown(before, after))
        return 0

    if getattr(args, "prompt_file", None):
        use_prompt_file(args.prompt_file)
    client, model = _client()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if args.command == "analyse":
        sentences = load_dataset(json.load(sys.stdin), args.min_sentences)
        records = run_analysis(client, sentences, args.delay, args.repeat)
        metrics = score(sentences, records)
        out = {"label": args.label, "model": model, "started": started, "prompt": prompt_fingerprint(sentences),
               "repeat": args.repeat, "metrics": metrics, "records": records}
        print(summary_markdown(metrics), file=sys.stderr)
    else:
        records = run_focus(client, args.delay, args.repeat)
        metrics = score_focus(records)
        out = {"label": args.label, "model": model, "started": started, "repeat": args.repeat,
               "metrics": metrics, "records": records}
        for skill, m in metrics.items():
            print(f"{skill}: focus on {_frac(m['focus_on'])}, off {_frac(m['focus_off'])}", file=sys.stderr)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
