"""LLM client and prompts for the NPC dialogue.

- schemas.py:  the one shape an AI reply must have (DialogueAnalysis) and parse_analysis().
- prompts.py:  builds the prompt from an explicit, limited DialogueContext; the player's text is data.
- client.py:   AiClient interface, the Gemini implementation, timeout, one retry, build_client().
- analysis.py: analyze_message() ties them together and falls back safely when the AI fails.

Nothing here writes to the database or changes game state. The API key is read from
settings.ai_api_key, is sent only in a request header and is never logged or sent to the frontend.
"""
