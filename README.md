# FluentAI

FluentAI is a personal English communication companion designed to help you become naturally fluent and confident in English through daily conversations.

Unlike a strict teacher, FluentAI acts as a supportive friend, counselor, and conversation partner. It focuses on real communication, emotional intelligence, and subtle improvement rather than constant correction.

## Key Features

- **Natural Conversations**: Engaging, emotionally intelligent interactions with follow-up questions.
- **Subtle Corrections**: Corrections are provided gently and non-intrusively, modeling natural phrasing.
- **Weakness Analysis**: Tracks grammar mistakes, sentence structure, vocabulary limitations, and speaking patterns over time.
- **Adaptive Learning**: Simplifies or increases difficulty based on your current level.
- **Invisible Learning**: Uses storytelling, debates, and roleplay to improve English organically.
- **Confidence Building**: Focuses on clarity and confidence over textbook perfection.
- **Session Reflections**: Provides brief summaries of what you did well and areas for improvement after each conversation.

## Technology Stack (Minimum Cost / Free Version)

- **LLM**: Gemini 1.5 Flash (via Google Gemini API - Free Tier)
- **STT (Speech-to-Text)**: Web Speech API (Browser-native, Zero cost)
- **TTS (Text-to-Speech)**: Web Speech API (Browser-native, Zero cost)
- **Backend**: FastAPI (Python)
- **Database**: SQLite (Local)
- **Frontend**: Vanilla HTML/CSS/Javascript

## Getting Started

### Prerequisites

- Python 3.11+
- A Google Gemini API Key (obtain from [Google AI Studio](https://aistudio.google.com/))

### Installation

1. Clone the repository (or navigate to the `fluent-ai` directory).
2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
3. Create a `.env` file in the root directory and add your API key:
   ```env
   GEMINI_API_KEY=your_api_key_here
   ```

### Running the Application

1. Start the backend server:
   ```bash
   uvicorn backend.main:app --reload
   ```
2. Open `frontend/index.html` in your web browser.

## Project Structure

- `backend/`: FastAPI server, LLM integration, and database models.
- `frontend/`: Chat interface and voice interaction logic.
- `db/`: Local SQLite database.
