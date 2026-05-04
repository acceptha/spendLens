from uuid import UUID

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.auth.deps import current_user_id
from app.auth.jwt import create_access_token


@pytest.mark.asyncio
async def test_current_user_id_from_bearer():
    test_app = FastAPI()

    @test_app.get("/me")
    async def me(uid: UUID = Depends(current_user_id)) -> dict:  # noqa: B008
        return {"user_id": str(uid)}

    user_id = UUID("00000000-0000-0000-0000-000000000001")
    token = create_access_token(user_id)
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"user_id": str(user_id)}


@pytest.mark.asyncio
async def test_current_user_id_missing_header_401():
    test_app = FastAPI()

    @test_app.get("/me")
    async def me(uid: UUID = Depends(current_user_id)) -> dict:  # noqa: B008
        return {}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/me")
    assert resp.status_code == 401
