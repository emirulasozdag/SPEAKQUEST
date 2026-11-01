from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import RateLimiter, raise_if_limited
from app.models.user import User
from app.schemas.dialogue import (
    CorrectionOut,
    DialogueHistoryOut,
    DialogueMessageOut,
    DialogueSummaryOut,
    DialogueTurnOut,
    ObjectiveStateOut,
    SendMessageRequest,
    StoryActionOut,
)
from app.services import dialogue as dialogue_service
from app.services.ai.client import AiClient, get_ai_client

router = APIRouter(prefix="/dialogue", tags=["dialogue"])

# Messages per player, so one player cannot use up the shared AI quota (settings.dialogue_rate_*)
message_limiter = RateLimiter()
TOO_MANY_MESSAGES = "You are sending messages very fast. Please wait a moment and try again."

_REFUSAL_STATUS = {
    "empty": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "too_long": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "no_active_quest": status.HTTP_409_CONFLICT,
    "no_character": status.HTTP_409_CONFLICT,
}


@router.post("/message", response_model=DialogueTurnOut)
def send_message(
    payload: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client: AiClient | None = Depends(get_ai_client),
) -> DialogueTurnOut:
    """Send a message to the NPC of the active quest and get the reply and language feedback.

    422 for an empty or too long message; 409 without a character or an active quest; 429 when the
    player sent more than settings.dialogue_rate_limit messages inside the window. When the AI
    is unavailable the answer is still 200, with status "ai_unavailable", a fallback reply and
    nothing saved, so the player can send the message again.
    """
    settings = get_settings()
    key = str(current_user.id)
    window = settings.dialogue_rate_window_seconds
    raise_if_limited(message_limiter, key, settings.dialogue_rate_limit, window, detail=TOO_MANY_MESSAGES)
    # Every attempt counts, also one the AI could not answer: each of them may call the provider
    message_limiter.hit(key, window)
    try:
        turn = dialogue_service.send_message(db, current_user.id, payload.message, client)
    except dialogue_service.MessageRefusedError as refused:
        raise HTTPException(status_code=_REFUSAL_STATUS[refused.reason], detail=refused.message) from None

    if turn.status != "ok":
        return DialogueTurnOut(status=turn.status, quest_id=turn.quest_id, npc_reply=turn.npc_reply)
    analysis = turn.analysis
    return DialogueTurnOut(
        status="ok",
        quest_id=turn.quest_id,
        npc_reply=turn.npc_reply,
        communication_success=analysis.communication_success,
        corrections=[
            CorrectionOut(category=e.category, original=e.original, corrected=e.corrected, explanation=e.explanation)
            for e in analysis.detected_errors
        ],
        feedback=analysis.feedback,
        story_action=StoryActionOut(suggested=turn.story.action, accepted=turn.story.accepted),
        objectives=[ObjectiveStateOut(id=o.id, description=o.description, met=o.met) for o in turn.objectives],
        newly_met=list(turn.newly_met),
        player_message=DialogueMessageOut.model_validate(turn.player_message),
        npc_message=DialogueMessageOut.model_validate(turn.npc_message),
    )


@router.get("/history/{quest_id}", response_model=DialogueHistoryOut)
def dialogue_history(
    quest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DialogueHistoryOut:
    """The logged-in player's conversation for a quest they started, oldest first.

    404 when the quest is unknown or this player never started it, so another player's
    conversation is indistinguishable from one that does not exist.
    """
    try:
        messages = dialogue_service.get_history(db, current_user.id, quest_id)
    except dialogue_service.DialogueNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You have not started this quest.") from None
    found = dialogue_service.get_corrections(db, current_user.id, [m.id for m in messages])
    out = []
    for message in messages:
        item = DialogueMessageOut.model_validate(message)
        item.corrections = [CorrectionOut.model_validate(e, from_attributes=True) for e in found.get(message.id, [])]
        out.append(item)
    return DialogueHistoryOut(quest_id=quest_id, messages=out)


@router.get("/summary/{quest_id}", response_model=DialogueSummaryOut)
def dialogue_summary(
    quest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DialogueSummaryOut:
    """What the player's conversation for a quest showed: how often they were understood, the most
    frequent mistake category and up to three example corrections. Same 404 rule as the history."""
    try:
        summary = dialogue_service.get_summary(db, current_user.id, quest_id)
    except dialogue_service.DialogueNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You have not started this quest.") from None
    return DialogueSummaryOut(
        quest_id=quest_id,
        messages_sent=summary.messages_sent,
        understood=summary.understood,
        mistakes=summary.mistakes,
        top_category=summary.top_category,
        examples=[CorrectionOut.model_validate(e, from_attributes=True) for e in summary.examples],
    )
