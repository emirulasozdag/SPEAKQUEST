"""The one shape an AI reply must have before the game uses it.

The model is asked for JSON (see docs/decisions/0001-ai-provider.md); parse_analysis() turns the
raw text into a DialogueAnalysis or, when it does not fit, into an AnalysisFailure. Nothing here
touches the database or the game state: callers decide what to do with a failure (the dialogue
flow in #12 uses a safe fallback reply and changes nothing).
"""

import json
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    ValidationError,
    model_validator,
)

from app.content.schema import Slug
from app.engines.categories import SkillCategory

MAX_DETECTED_ERRORS = 5

NpcReply = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=800)]
Sentence = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Explanation = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
Feedback = Annotated[str, StringConstraints(strip_whitespace=True, max_length=400)]

DEFAULT_STORY_ACTION = "continue"


class _AiModel(BaseModel):
    # Extra keys from the model are ignored: the game only ever reads the fields below
    model_config = ConfigDict(extra="ignore", frozen=True)


class DetectedError(_AiModel):
    category: SkillCategory
    original: Sentence
    corrected: Sentence
    explanation: Explanation

    @model_validator(mode="after")
    def _correction_must_differ(self) -> "DetectedError":
        if self.original.casefold() == self.corrected.casefold():
            raise ValueError("corrected must differ from original")
        return self


class DialogueAnalysis(_AiModel):
    """A validated AI reply. The story action is only a suggestion; the Story Engine decides."""

    npc_reply: NpcReply
    # Strict so "true" or 1 from the model is rejected instead of guessed
    communication_success: StrictBool
    detected_errors: list[DetectedError] = Field(default=[], max_length=MAX_DETECTED_ERRORS)
    # Categories the player used correctly in this message; the Learning Engine needs them to
    # raise a skill score, not only to lower it. A category may also appear in detected_errors:
    # "She go to work and I drink coffee" is wrong and right Present Simple in one sentence.
    correctly_used: list[SkillCategory] = []
    feedback: Feedback = ""
    suggested_story_action: Slug = DEFAULT_STORY_ACTION


class AnalysisFailure(BaseModel):
    """Why an AI reply could not be used. Never contains the raw reply."""

    model_config = ConfigDict(frozen=True)

    reason: Literal["invalid_json", "invalid_schema"]
    detail: str


def parse_analysis(raw: str) -> DialogueAnalysis | AnalysisFailure:
    """Validate the model's raw text. Never raises."""
    data = _load_json_object(raw)
    if isinstance(data, AnalysisFailure):
        return data
    try:
        return DialogueAnalysis.model_validate(data)
    except ValidationError as exc:
        problems = [f"{'.'.join(str(part) for part in e['loc']) or 'reply'}: {e['msg']}" for e in exc.errors()]
        return AnalysisFailure(reason="invalid_schema", detail="; ".join(problems[:5]))


def _load_json_object(raw: str) -> dict | AnalysisFailure:
    text = raw.strip() if isinstance(raw, str) else ""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Models often wrap JSON in a ```json fence or add a sentence around it
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return AnalysisFailure(reason="invalid_json", detail="no JSON object found")
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            return AnalysisFailure(reason="invalid_json", detail=f"{exc.msg} at position {exc.pos}")
    if not isinstance(data, dict):
        return AnalysisFailure(reason="invalid_json", detail="top-level value is not an object")
    return data
