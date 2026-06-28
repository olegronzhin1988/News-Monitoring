# test_subscriptions_api.py — CRUD endpoint tests for /subscriptions.
#
# Uses the `client` fixture from conftest.py, which wires a real FastAPI
# app to the isolated test database. No mocking needed here since these
# tests never touch external APIs (NewsAPI/Groq/Telegram) — they only
# exercise the subscription CRUD layer.

import pytest


@pytest.mark.asyncio
async def test_create_subscription_returns_201_with_full_payload(client):
    payload = {
        "topic": "Bitcoin",
        "keywords": ["crypto", "blockchain"],
        "language": "en",
        "check_interval_minutes": 30,
    }

    response = await client.post("/subscriptions/", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["topic"] == "Bitcoin"
    assert data["keywords"] == ["crypto", "blockchain"]
    assert data["language"] == "en"
    assert data["check_interval_minutes"] == 30
    assert data["is_active"] is True
    # Server-generated fields must be present.
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_subscription_applies_defaults_when_optional_fields_omitted(client):
    response = await client.post("/subscriptions/", json={"topic": "Tesla"})

    assert response.status_code == 201
    data = response.json()
    assert data["keywords"] == []
    assert data["language"] == "en"
    assert data["check_interval_minutes"] == 60


@pytest.mark.asyncio
async def test_create_subscription_without_topic_returns_422(client):
    # `topic` has no default in SSubscriptionCreate — omitting it must fail validation.
    response = await client.post("/subscriptions/", json={"language": "en"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_subscription_list_returns_all_created_subscriptions(client):
    await client.post("/subscriptions/", json={"topic": "Bitcoin"})
    await client.post("/subscriptions/", json={"topic": "Tesla"})

    response = await client.get("/subscriptions/")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    topics = {item["topic"] for item in data}
    assert topics == {"Bitcoin", "Tesla"}


@pytest.mark.asyncio
async def test_get_subscription_list_respects_skip_and_limit(client):
    for topic in ["A", "B", "C", "D"]:
        await client.post("/subscriptions/", json={"topic": topic})

    response = await client.get("/subscriptions/", params={"skip": 1, "limit": 2})

    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_get_subscription_by_id_returns_matching_subscription(client):
    create_resp = await client.post("/subscriptions/", json={"topic": "Bitcoin"})
    subscription_id = create_resp.json()["id"]

    response = await client.get(f"/subscriptions/{subscription_id}")

    assert response.status_code == 200
    assert response.json()["id"] == subscription_id
    assert response.json()["topic"] == "Bitcoin"


@pytest.mark.asyncio
async def test_get_subscription_by_unknown_id_returns_404(client):
    random_uuid = "11111111-1111-1111-1111-111111111111"

    response = await client.get(f"/subscriptions/{random_uuid}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_subscription_updates_only_provided_fields(client):
    create_resp = await client.post(
        "/subscriptions/",
        json={"topic": "Bitcoin", "check_interval_minutes": 60, "language": "en"},
    )
    subscription_id = create_resp.json()["id"]

    response = await client.patch(
        f"/subscriptions/{subscription_id}",
        json={"check_interval_minutes": 15},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["check_interval_minutes"] == 15
    # Untouched fields must remain exactly as they were.
    assert data["topic"] == "Bitcoin"
    assert data["language"] == "en"


@pytest.mark.asyncio
async def test_patch_subscription_can_set_falsy_values(client):
    # Regression guard: exclude_unset must be used in the PATCH endpoint so that
    # explicitly-sent falsy values (False, 0) are not mistaken for "not provided".
    create_resp = await client.post("/subscriptions/", json={"topic": "Bitcoin"})
    subscription_id = create_resp.json()["id"]

    response = await client.patch(
        f"/subscriptions/{subscription_id}",
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.asyncio
async def test_patch_unknown_subscription_returns_404(client):
    random_uuid = "11111111-1111-1111-1111-111111111111"

    response = await client.patch(
        f"/subscriptions/{random_uuid}",
        json={"topic": "New topic"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_subscription_returns_204_and_removes_it(client):
    create_resp = await client.post("/subscriptions/", json={"topic": "Bitcoin"})
    subscription_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/subscriptions/{subscription_id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/subscriptions/{subscription_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_unknown_subscription_returns_404(client):
    random_uuid = "11111111-1111-1111-1111-111111111111"

    response = await client.delete(f"/subscriptions/{random_uuid}")

    assert response.status_code == 404
