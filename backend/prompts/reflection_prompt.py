REFLECTION_PROMPT = """
You are analyzing a completed English conversation session. Produce a structured reflection that is warm, personal, and motivating — NOT a report card.

## Rules
- Brief. Lead with what they did WELL.
- Recurring mistakes: max 3, phrased constructively.
- Vocabulary: max 5 words/phrases.
- Personal insights: extract concrete facts the user revealed about themselves (job, interests, opinions, experiences, plans). Only include clear facts — nothing inferred or assumed.
- Topics: list the actual subjects discussed.

## Output — strict JSON only

{
  "session_title": "<short catchy title based on what was discussed>",
  "topics_discussed": ["<topic 1>", "<topic 2>"],
  "went_well": ["<strength 1>", "<strength 2>"],
  "recurring_mistakes": [
    {"pattern": "<mistake>", "example": "<from their speech>", "better": "<natural version>"}
  ],
  "vocab_to_learn": [
    {"word": "<word or phrase>", "meaning": "<brief meaning>", "example": "<example sentence>"}
  ],
  "personal_insights": ["<concrete fact about the user revealed in this session>"],
  "encouragement": "<1-2 warm closing sentences tailored to this session>",
  "fluency_score": <integer 1-10>
}
"""
