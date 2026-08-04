"""Access-token gate tests.

require_auth reads get_settings().app_access_token at request time, so patching
the cached settings instance toggles the gate without re-importing the app.
"""
from config import get_settings


async def test_protected_route_blocks_without_token_when_configured(client, monkeypatch):
    # Arrange — enable the gate
    monkeypatch.setattr(get_settings(), "app_access_token", "s3cret-token")

    # Act — no Authorization header
    resp = await client.get("/sessions/")

    # Assert
    assert resp.status_code == 401


async def test_protected_route_allows_with_correct_token(client, monkeypatch):
    # Arrange
    monkeypatch.setattr(get_settings(), "app_access_token", "s3cret-token")

    # Act
    resp = await client.get("/sessions/", headers={"Authorization": "Bearer s3cret-token"})

    # Assert
    assert resp.status_code == 200


async def test_protected_route_open_when_token_empty(client):
    # Act — default test settings leave app_access_token empty
    resp = await client.get("/sessions/")

    # Assert — auth disabled, route reachable
    assert resp.status_code == 200
