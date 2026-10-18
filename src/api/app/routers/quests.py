from fastapi import APIRouter

from app.core.placeholders import not_implemented

router = APIRouter(prefix="/quests", tags=["quests"])


@router.get("")
def list_quests():
    raise not_implemented("Quest list")


@router.get("/active")
def active_quest():
    raise not_implemented("Active quest")


@router.post("/{quest_id}/start")
def start_quest(quest_id: int):
    raise not_implemented("Quest start")


@router.post("/{quest_id}/complete")
def complete_quest(quest_id: int):
    raise not_implemented("Quest completion")
