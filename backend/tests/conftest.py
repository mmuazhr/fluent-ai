"""Test fixtures for FluentAI backend.

Environment overrides are applied BEFORE importing the app/config so that the
lru_cached Settings never touch the real .env (no live Gemini key or remote
Postgres DSN is used — an isolated sqlite database is used instead).
"""
import os
import sys
import tempfile
from pathlib import Path

# --- Env overrides MUST precede any app/config import ---
_TEST_DB = Path(tempfile.gettempdir()) / "fluentai_test.db"
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB}"
os.environ["GEMINI_API_KEY"] = "test-dummy-key"
os.environ["APP_ACCESS_TOKEN"] = ""  # auth disabled by default for tests
os.environ["VAULT_ROOT"] = ""  # vault writer is a no-op in tests

# Ensure backend/ (the package root) is importable regardless of CWD.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from main import app


@pytest_asyncio.fixture
async def client():
    """An httpx client bound to the ASGI app with lifespan (init_db) executed."""
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
