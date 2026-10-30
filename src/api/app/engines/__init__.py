"""Game logic that lives in Python, never in the AI model.

- learning.py: counts and prioritizes language errors, tracks skill progress.
- story.py:    story state, NPC trust, decisions, quest unlock rules, endings.
- trust.py:    NPC trust bounds, shared by the Story Engine and the trust table.
- quest.py:    combines both engines to pick the next quest for a player.
"""
