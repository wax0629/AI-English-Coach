import httpx
import pytest

from app.main import app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_health_check() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.anyio
async def test_readiness_masks_provider_configuration() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/readiness")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload["services"]) == {"openai_realtime", "gemini_live", "azure_pronunciation", "report_llm"}
    assert all("configured" in service for service in payload["services"].values())
    assert "key" not in str(payload).lower()
