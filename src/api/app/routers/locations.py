from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.content import Location, QuestTemplate
from app.models.user import User
from app.schemas.locations import LocationOut, LocationQuestOut, NpcOut
from app.services.quests import quest_statuses

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("", response_model=list[LocationOut])
def list_locations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LocationOut]:
    """Every place on the map, with its characters and the player's status for each quest."""
    locations = db.scalars(_with_content().order_by(Location.sort_order, Location.id)).all()
    statuses = _statuses(db, current_user, locations)
    return [_to_output(location, statuses) for location in locations]


@router.get("/{location_id}", response_model=LocationOut)
def get_location(
    location_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LocationOut:
    location = db.scalar(_with_content().where(Location.id == location_id))
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found.")
    return _to_output(location, _statuses(db, current_user, [location]))


def _with_content():
    # Load NPCs and quests together with the places, so a map of N places is not N+1 queries
    return select(Location).options(
        selectinload(Location.npcs),
        selectinload(Location.quests).selectinload(QuestTemplate.npc),
    )


def _statuses(db: Session, user: User, locations: list[Location]):
    return quest_statuses(db, user.id, [quest for location in locations for quest in location.quests])


def _to_output(location: Location, statuses) -> LocationOut:
    return LocationOut(
        id=location.id,
        slug=location.slug,
        name=location.name,
        description=location.description,
        sort_order=location.sort_order,
        npcs=[NpcOut(id=npc.id, slug=npc.slug, name=npc.name, role=npc.role) for npc in location.npcs],
        quests=[
            LocationQuestOut(
                id=quest.id,
                slug=quest.slug,
                title=quest.title,
                chapter=quest.chapter,
                summary=quest.summary,
                npc_slug=quest.npc.slug,
                status=statuses[quest.slug],
            )
            for quest in location.quests
        ],
    )
