"""LLM client and prompts (implemented in the AI integration phase).

Responsibilities:
- Send only the context the model needs (quest, NPC, story state, player message).
- Ask for structured JSON: npc_reply, communication_success, detected_errors, correctly_used,
  feedback, suggested_story_action (the shape lives in schemas.py).
- Validate the response with parse_analysis() before anything reaches the database or game state.
- Fall back to a safe reply when the provider fails, so the game never crashes.

The API key is read from settings.ai_api_key and never sent to the frontend.
"""
