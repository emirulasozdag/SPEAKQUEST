from fastapi import APIRouter

from app.core.placeholders import not_implemented

router = APIRouter(prefix="/dialogue", tags=["dialogue"])


@router.post("/message")
def send_message():
    raise not_implemented("NPC dialogue")


@router.get("/history/{quest_id}")
def dialogue_history(quest_id: int):
    raise not_implemented("Dialogue history")
