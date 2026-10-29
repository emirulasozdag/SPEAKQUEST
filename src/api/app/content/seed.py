"""Loads the content files into the database. Safe to run any number of times.

    python -m app.content.seed

Rows are matched by `slug`: a new slug is inserted, a changed one is updated in place (the row id
never changes, so player progress that points at it stays valid) and an unchanged one is left
alone. Rows whose content file was removed are NOT deleted: players may already have progress on
them, so removing content is a deliberate migration, not a side effect of seeding.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.schema import Content, load_content
from app.models.content import Location, Npc, QuestTemplate


@dataclass
class SeedReport:
    created: dict[str, int] = field(default_factory=dict)
    updated: dict[str, int] = field(default_factory=dict)
    unchanged: dict[str, int] = field(default_factory=dict)

    def count(self, kind: str, outcome: str) -> None:
        bucket = {"created": self.created, "updated": self.updated, "unchanged": self.unchanged}[outcome]
        bucket[kind] = bucket.get(kind, 0) + 1

    def summary(self) -> str:
        kinds = sorted({*self.created, *self.updated, *self.unchanged})
        return "; ".join(
            f"{kind}: {self.created.get(kind, 0)} created, {self.updated.get(kind, 0)} updated, "
            f"{self.unchanged.get(kind, 0)} unchanged"
            for kind in kinds
        )


def seed_content(db: Session, content: Content | None = None) -> SeedReport:
    """Write the content to the database in one transaction and return what changed."""
    content = content or load_content()
    report = SeedReport()

    locations = {row.slug: row for row in db.scalars(select(Location))}
    for item in content.locations:
        locations[item.slug] = _upsert(
            db, report, "location", Location, locations.get(item.slug), slug=item.slug,
            name=item.name, description=item.description, sort_order=item.sort_order,
        )
    db.flush()  # the new locations need ids before NPCs can point at them

    npcs = {row.slug: row for row in db.scalars(select(Npc))}
    for item in content.npcs:
        npcs[item.slug] = _upsert(
            db, report, "npc", Npc, npcs.get(item.slug), slug=item.slug,
            location_id=locations[item.location].id, name=item.name, role=item.role,
            personality=item.personality, speaking_style=item.speaking_style, knows=list(item.knows),
        )
    db.flush()

    quests = {row.slug: row for row in db.scalars(select(QuestTemplate))}
    for item in content.quests:
        _upsert(
            db, report, "quest", QuestTemplate, quests.get(item.slug), slug=item.slug,
            title=item.title, chapter=item.chapter, location_id=locations[item.location].id,
            npc_id=npcs[item.npc].id, target_skills=[skill.value for skill in item.target_skills],
            min_level=item.min_level.value, max_level=item.max_level.value, summary=item.summary,
            npc_opening=item.npc_opening,
            objectives=[o.model_dump(mode="json") for o in item.objectives],
            prerequisites=item.prerequisites.model_dump(mode="json"),
            rewards=item.rewards.model_dump(mode="json"),
            allowed_story_actions=list(item.allowed_story_actions),
            decision_points=[p.model_dump(mode="json") for p in item.decision_points],
        )

    db.commit()
    return report


def _upsert(db: Session, report: SeedReport, kind: str, model, existing, **values):
    if existing is None:
        row = model(**values)
        db.add(row)
        report.count(kind, "created")
        return row
    changed = {name: value for name, value in values.items() if getattr(existing, name) != value}
    for name, value in changed.items():
        setattr(existing, name, value)
    report.count(kind, "updated" if changed else "unchanged")
    return existing


def main() -> None:
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        report = seed_content(db)
    print(f"Content seeded. {report.summary()}")


if __name__ == "__main__":
    main()
