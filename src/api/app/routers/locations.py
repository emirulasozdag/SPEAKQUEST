from fastapi import APIRouter

from app.core.placeholders import not_implemented

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("")
def list_locations():
    raise not_implemented("Location list")


@router.get("/{location_id}")
def get_location(location_id: int):
    raise not_implemented("Location details")
