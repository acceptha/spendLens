import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_seed_transactions_returns_list_no_auth():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/seed/transactions")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 30
    sample = body[0]
    for k in ("txn_date", "amount", "merchant_raw", "category", "essential_reason"):
        assert k in sample
