"""NPC trust bounds. Kept free of imports so the trust table model can use them without pulling
in the Story Engine (and, through it, the content schema), which would make an import cycle."""

TRUST_MIN = 0
TRUST_MAX = 100


def clamp_trust(value: int) -> int:
    return max(TRUST_MIN, min(TRUST_MAX, value))
