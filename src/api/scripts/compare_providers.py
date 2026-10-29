"""Run the 10 sample player sentences through Gemini and/or OpenAI and print a comparison.

Used once, for docs/decisions/0001-ai-provider.md. It is not part of the app and not run by CI.
It calls the real providers, so you need your own keys in the environment (never in a file that
is committed):

    GEMINI_API_KEY, GEMINI_MODEL
    OPENAI_API_KEY, OPENAI_MODEL

Run from src/api:  python scripts/compare_providers.py [gemini] [openai]
Uses only the standard library plus the app's own schema, so nothing new is installed.
"""

import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.ai.schemas import AnalysisFailure, parse_analysis  # noqa: E402

SAMPLES = Path(__file__).resolve().parents[3] / "docs" / "decisions" / "0001-samples.json"

# A deliberately small prompt: the real prompts are written in issue #8
SYSTEM = (
    "You are an NPC in an English-learning story game and also a careful English teacher. "
    "The player is an A2-B1 learner. Reply ONLY with one JSON object with these keys: "
    "npc_reply (short, in character, English), communication_success (true if a native speaker "
    "would understand the message, even with grammar mistakes), detected_errors (list of "
    "{category, original, corrected, explanation}; category is one of present_simple, past_simple, "
    "question_formation, prepositions, vocabulary_usage; explanation is one short sentence in "
    "Turkish), correctly_used (categories the player used correctly), feedback (one short "
    "encouraging sentence), suggested_story_action (one of continue, npc_pleased, npc_confused)."
)


def post(url: str, headers: dict, body: dict) -> dict:
    request = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def ask_gemini(sample: dict) -> str:
    model = os.environ["GEMINI_MODEL"]
    data = post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        {"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
        {
            "systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": user_text(sample)}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3},
        },
    )
    return data["candidates"][0]["content"]["parts"][0]["text"]


def ask_openai(sample: dict) -> str:
    data = post(
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        {
            "model": os.environ["OPENAI_MODEL"],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user_text(sample)},
            ],
        },
    )
    return data["choices"][0]["message"]["content"]


def user_text(sample: dict) -> str:
    return f"Scene: {sample['context']}\nPlayer says: {sample['player']}"


def run(name: str, ask) -> None:
    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
    print(f"\n## {name}\n")
    print("| # | beklenen | geçerli şema | doğru kategori | iletişim | süre (sn) |")
    print("|---|---|---|---|---|---|")
    times, valid, right = [], 0, 0
    for sample in samples:
        started = time.perf_counter()
        try:
            result = parse_analysis(ask(sample))
        except urllib.error.HTTPError as exc:
            # The provider's error body explains the cause (bad model name, quota, key); it never holds our key
            body = exc.read().decode("utf-8", errors="replace")[:300].replace("\n", " ")
            print(f"| {sample['id']} | {sample['category']} | istek hatası: HTTP {exc.code} | {body} | - | - |")
            continue
        except (urllib.error.URLError, KeyError, IndexError, TimeoutError) as exc:
            print(f"| {sample['id']} | {sample['category']} | istek hatası: {type(exc).__name__} | {exc} | - | - |")
            continue
        elapsed = time.perf_counter() - started
        times.append(elapsed)
        if isinstance(result, AnalysisFailure):
            # detail names the failing field only; it never includes the model's text
            print(f"| {sample['id']} | {sample['category']} | hayır ({result.reason}) | {result.detail} | - | {elapsed:.1f} |")
            continue
        valid += 1
        found = {error.category.value for error in result.detected_errors} or {"none"}
        match = sample["category"] in found
        right += match
        print(f"| {sample['id']} | {sample['category']} | evet | {'evet' if match else 'hayır: ' + ', '.join(sorted(found))} | {result.communication_success} | {elapsed:.1f} |")
    median = f"{statistics.median(times):.1f} sn" if times else "ölçülemedi"
    print(f"\nGeçerli şema: {valid}/{len(samples)} · doğru kategori: {right}/{len(samples)} · medyan süre: {median}")


def main() -> None:
    wanted = sys.argv[1:] or ["gemini", "openai"]
    providers = {"gemini": ask_gemini, "openai": ask_openai}
    for name in wanted:
        if name not in providers:
            raise SystemExit(f"unknown provider {name!r}; use gemini or openai")
        prefix = name.upper()
        missing = [key for key in (f"{prefix}_API_KEY", f"{prefix}_MODEL") if not os.environ.get(key)]
        if missing:
            print(f"\n## {name}\n\nAtlandı: {', '.join(missing)} ayarlı değil.")
            continue
        run(name, providers[name])


if __name__ == "__main__":
    main()
