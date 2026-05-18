from httpx import ASGITransport, AsyncClient

from app.main import app


async def _client():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url="https://test")


async def test_signup_creates_user_and_issues_tokens():
    async with await _client() as ac:
        r = await ac.post(
            "/auth/signup",
            json={"email": "new@example.com", "password": "abcd1234"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body and len(body["access_token"]) > 20
    assert r.cookies.get("refresh_token")


async def test_signup_duplicate_email_returns_409():
    async with await _client() as ac:
        first = await ac.post(
            "/auth/signup",
            json={"email": "dup@example.com", "password": "abcd1234"},
        )
        assert first.status_code == 200
        r = await ac.post(
            "/auth/signup",
            json={"email": "dup@example.com", "password": "abcd1234"},
        )
    assert r.status_code == 409
    assert r.json()["detail"] == "EMAIL_ALREADY_EXISTS"


async def test_signup_weak_password_returns_400():
    async with await _client() as ac:
        r = await ac.post(
            "/auth/signup",
            json={"email": "weak@example.com", "password": "12345678"},
        )
    assert r.status_code == 400
    assert r.json()["detail"] == "WEAK_PASSWORD"


async def test_signup_rate_limit_after_5_attempts():
    async with await _client() as ac:
        for i in range(5):
            r = await ac.post(
                "/auth/signup",
                json={"email": f"rl{i}@example.com", "password": "abcd1234"},
            )
            assert r.status_code == 200
        r = await ac.post(
            "/auth/signup",
            json={"email": "rl5@example.com", "password": "abcd1234"},
        )
    assert r.status_code == 429
    assert r.json()["detail"] == "TOO_MANY_REQUESTS"
    assert "retry-after" in {k.lower() for k in r.headers}
