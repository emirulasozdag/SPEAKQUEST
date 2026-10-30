"""XP and level rules: the only place that decides how much XP a level needs.

Everything here is a pure function (numbers in, numbers out), so it is easy to test at the
boundaries and nothing can change a player's XP by accident. The database side (writing
player_profiles.xp and quest_progress.xp_awarded when a quest is completed) calls add_xp() and
stores its result; the client never sends XP or a level.
"""

from dataclasses import dataclass

# XP needed to reach each level, starting at level 1. The five MVP quests give 410 XP in total
# (50 + 60 + 80 + 100 + 120), so a player who finishes them reaches level 5 of 6, and the
# first quest already earns level 2. A new threshold list is the only change a longer game needs.
LEVEL_THRESHOLDS = (0, 50, 120, 220, 350, 500)
MAX_LEVEL = len(LEVEL_THRESHOLDS)


@dataclass(frozen=True)
class XpGain:
    xp: int
    level: int
    gained: int
    previous_level: int

    @property
    def leveled_up(self) -> bool:
        return self.level > self.previous_level


@dataclass(frozen=True)
class LevelProgress:
    """Where the player stands inside the current level, for progress bars."""

    level: int
    xp_into_level: int
    # None at the maximum level, where there is nothing more to earn
    xp_needed_for_next: int | None


def level_for_xp(xp: int) -> int:
    """The level a player with this much XP has reached (1 at 0 XP, capped at MAX_LEVEL)."""
    _require_non_negative(xp, "xp")
    level = 1
    for number, threshold in enumerate(LEVEL_THRESHOLDS, start=1):
        if xp >= threshold:
            level = number
    return level


def xp_for_level(level: int) -> int:
    """The XP at which a level starts."""
    if not 1 <= level <= MAX_LEVEL:
        raise ValueError(f"level must be between 1 and {MAX_LEVEL}, got {level}")
    return LEVEL_THRESHOLDS[level - 1]


def add_xp(current_xp: int, amount: int) -> XpGain:
    """Add XP and report the new total and level. XP only ever goes up."""
    _require_non_negative(current_xp, "current_xp")
    _require_non_negative(amount, "amount")
    total = current_xp + amount
    return XpGain(xp=total, level=level_for_xp(total), gained=amount, previous_level=level_for_xp(current_xp))


def progress_in_level(xp: int) -> LevelProgress:
    level = level_for_xp(xp)
    start = xp_for_level(level)
    if level == MAX_LEVEL:
        return LevelProgress(level=level, xp_into_level=xp - start, xp_needed_for_next=None)
    return LevelProgress(level=level, xp_into_level=xp - start, xp_needed_for_next=xp_for_level(level + 1) - start)


def _require_non_negative(value: int, name: str) -> None:
    # bool is an int subclass; True as an XP amount is a bug, not 1 XP
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"{name} cannot be negative, got {value}")
