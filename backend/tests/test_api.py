"""HTTP surface tests that do not depend on the LLM."""


async def test_health_returns_ok_and_model_name(client):
    # Act
    resp = await client.get("/health")

    # Assert
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["model"]  # model name is reported


async def test_sessions_list_returns_a_list(client):
    # Act
    resp = await client.get("/sessions/")

    # Assert
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_analytics_usage_returns_an_object(client):
    # Act
    resp = await client.get("/analytics/usage")

    # Assert
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)
