from fastapi import APIRouter

from app.core.placeholders import not_implemented

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/errors")
def language_errors():
    raise not_implemented("Language error history")


@router.get("/skills")
def skills():
    raise not_implemented("Skill progress")


@router.get("/recommendations")
def recommendations():
    raise not_implemented("Learning recommendations")
