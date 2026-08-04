# FluentAI — Engineering Task Breakdown

## TASK-001 — Project Setup & Environment
- [ ] Scaffold directory structure
- [ ] Create `backend/requirements.txt` with `google-generativeai`, `fastapi`, `uvicorn`, `websockets`, `sqlalchemy`, `aiosqlite`, `python-dotenv`, `pydantic-settings`
- [ ] Configure `backend/config.py` to use `GEMINI_API_KEY`
- [ ] Create `.env.example`

## TASK-002 — Database Schema & Init
- [ ] Define SQLAlchemy models in `backend/models/database.py` (Sessions, Messages, Weaknesses, VocabGaps, Reflections)
- [ ] Create async DB initialization logic
- [ ] Define Pydantic schemas in `backend/models/schemas.py`

## TASK-003 — Gemini LLM Engine (Free Version)
- [ ] Implement `backend/services/llm_engine.py` using `google-generativeai`
- [ ] Configure system prompt in `backend/prompts/system_prompt.py` for JSON output
- [ ] Implement retry logic for JSON parsing

## TASK-004 — Memory Manager
- [ ] Implement in-memory session history tracking with context window limits in `backend/services/memory_manager.py`

## TASK-005 — Analytics Engine
- [ ] Implement `backend/services/analytics_engine.py` to process LLM observations and persist patterns to DB

## TASK-006 — Session Router
- [ ] Create REST endpoints for starting/ending sessions and history retrieval in `backend/routers/sessions.py`

## TASK-007 — Reflection Engine
- [ ] Implement `backend/services/reflection_engine.py` to generate post-session summaries using Gemini

## TASK-008 — WebSocket Chat Router
- [ ] Implement `backend/routers/chat.py` for real-time bidirectional communication

## TASK-009 — Analytics REST Router
- [ ] Create endpoints for the analytics dashboard in `backend/routers/analytics.py`

## TASK-010 — FastAPI App Entry
- [ ] Wire all components in `backend/main.py` and configure CORS

## TASK-011 — Frontend: Voice Input (STT)
- [ ] Implement Web Speech API capture and live transcript in `frontend/js/voice_input.js`

## TASK-012 — Frontend: Voice Output (TTS)
- [ ] Implement Web Speech Synthesis API in `frontend/js/voice_output.js`

## TASK-013 — Frontend: Chat UI
- [ ] Build the dark glassmorphism chat interface in `index.html`, `style.css`, and `chat.js`

## TASK-014 — Frontend: Reflection Card
- [ ] Build the post-session summary modal

## TASK-015 — Frontend: Analytics Dashboard
- [ ] Build the analytics page in `analytics.html` and `analytics.js`

## TASK-016 — Integration Test (End-to-End)
- [ ] Perform full manual verification of the voice conversation loop
