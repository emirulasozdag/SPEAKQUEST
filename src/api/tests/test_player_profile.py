import pytest

PROFILE_URL = "/api/player/profile"

VALID_PROFILE = {
    "character_name": "Deniz",
    "avatar": 2,
    "english_level": "B1",
    "learning_goal": "work",
}


def login_headers(client, email: str) -> dict[str, str]:
    password = "secret-pass"
    assert client.post("/api/auth/register", json={"email": email, "password": password}).status_code == 201
    token = client.post("/api/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers(client) -> dict[str, str]:
    return login_headers(client, "deniz@example.com")


def test_profile_endpoints_require_a_token(client):
    assert client.get(PROFILE_URL).status_code == 401
    assert client.put(PROFILE_URL, json=VALID_PROFILE).status_code == 401


def test_get_profile_before_character_creation_returns_404(client, headers):
    response = client.get(PROFILE_URL, headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Create your character first."


def test_first_put_creates_profile_with_starting_xp_and_level(client, headers):
    response = client.put(PROFILE_URL, json=VALID_PROFILE, headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert {key: body[key] for key in VALID_PROFILE} == VALID_PROFILE
    assert body["xp"] == 0
    assert body["level"] == 1
    assert client.get(PROFILE_URL, headers=headers).json() == body


def test_later_put_updates_the_same_profile(client, headers):
    client.put(PROFILE_URL, json=VALID_PROFILE, headers=headers)
    changes = {**VALID_PROFILE, "character_name": "  Deniz Y  ", "english_level": "A2", "avatar": 3}

    response = client.put(PROFILE_URL, json=changes, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["character_name"] == "Deniz Y"
    assert body["english_level"] == "A2"
    assert body["avatar"] == 3


@pytest.mark.parametrize("field", ["xp", "level"])
def test_client_cannot_change_xp_or_level(client, headers, field):
    client.put(PROFILE_URL, json=VALID_PROFILE, headers=headers)

    response = client.put(PROFILE_URL, json={**VALID_PROFILE, field: 9999}, headers=headers)

    assert response.status_code == 422
    profile = client.get(PROFILE_URL, headers=headers).json()
    assert profile["xp"] == 0
    assert profile["level"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"character_name": ""},
        {"character_name": "   "},
        {"character_name": "x" * 31},
        {"avatar": 0},
        {"avatar": 4},
        {"avatar": "2"},
        {"english_level": "C2"},
        {"learning_goal": "Everyday conversation"},
    ],
    ids=["empty-name", "blank-name", "long-name", "avatar-0", "avatar-4", "avatar-text", "level", "goal"],
)
def test_invalid_profile_is_rejected(client, headers, changes):
    response = client.put(PROFILE_URL, json={**VALID_PROFILE, **changes}, headers=headers)

    assert response.status_code == 422
    assert client.get(PROFILE_URL, headers=headers).status_code == 404


def test_missing_field_is_rejected(client, headers):
    incomplete = {key: value for key, value in VALID_PROFILE.items() if key != "avatar"}

    response = client.put(PROFILE_URL, json=incomplete, headers=headers)

    assert response.status_code == 422


def test_each_user_only_sees_and_changes_their_own_profile(client):
    headers_a = login_headers(client, "a@example.com")
    headers_b = login_headers(client, "b@example.com")
    client.put(PROFILE_URL, json=VALID_PROFILE, headers=headers_a)

    assert client.get(PROFILE_URL, headers=headers_b).status_code == 404

    response = client.put(PROFILE_URL, json={**VALID_PROFILE, "character_name": "Bora"}, headers=headers_b)

    assert response.status_code == 201
    assert client.get(PROFILE_URL, headers=headers_a).json()["character_name"] == "Deniz"
    assert client.get(PROFILE_URL, headers=headers_b).json()["character_name"] == "Bora"
