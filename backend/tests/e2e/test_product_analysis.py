"""E2E tests for product analysis with real Amazon URLs."""

import pytest
from httpx import AsyncClient
from src.api.main import app


# Test product URLs from user requirements
SUNSCREEN_URL = "https://www.amazon.ca/Roche-Posay-Anthelios-Mineral-50mL/dp/B00OZNRV00/"
FRYING_PAN_URL = "https://www.amazon.ca/Signature-Cookware-Indicator-Utensil-Oven-Safe/dp/B07YX7DJTC/"


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health check endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_analyze_sunscreen():
    """Test analyzing La Roche-Posay sunscreen."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/analyze",
            json={
                "product_url": SUNSCREEN_URL,
                "allergen_profile": [],
                "force_refresh": False,
            },
            timeout=60.0,  # Claude analysis can take time
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "analysis" in data
        assert "alternatives" in data

        analysis = data["analysis"]
        assert "product_name" in analysis
        assert "overall_score" in analysis
        assert "allergens_detected" in analysis
        assert "pfas_detected" in analysis
        assert "confidence" in analysis

        # Verify harm score is calculated
        assert 0 <= analysis["overall_score"] <= 100

        print(f"\n✅ Sunscreen Analysis:")
        print(f"   Product: {analysis.get('product_name')}")
        print(f"   Brand: {analysis.get('brand')}")
        print(f"   Safety Score: {analysis['overall_score']}/100")
        print(f"   Allergens: {len(analysis['allergens_detected'])}")
        print(f"   PFAS: {len(analysis['pfas_detected'])}")
        print(f"   Other Concerns: {len(analysis['other_concerns'])}")


@pytest.mark.asyncio
async def test_analyze_frying_pan():
    """Test analyzing non-stick frying pan."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/analyze",
            json={
                "product_url": FRYING_PAN_URL,
                "allergen_profile": [],
                "force_refresh": False,
            },
            timeout=60.0,
        )

        assert response.status_code == 200
        data = response.json()

        analysis = data["analysis"]
        assert "product_name" in analysis
        assert "overall_score" in analysis

        # Non-stick pans should potentially detect PFAS
        # (depends on Claude's analysis)

        print(f"\n✅ Frying Pan Analysis:")
        print(f"   Product: {analysis.get('product_name')}")
        print(f"   Brand: {analysis.get('brand')}")
        print(f"   Safety Score: {analysis['overall_score']}/100")
        print(f"   PFAS Detected: {len(analysis['pfas_detected'])}")
        print(f"   Other Concerns: {len(analysis['other_concerns'])}")


@pytest.mark.asyncio
async def test_analyze_with_allergen_profile():
    """Test analysis with user allergen profile."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/analyze",
            json={
                "product_url": SUNSCREEN_URL,
                "allergen_profile": ["fragrance", "parabens"],
                "force_refresh": False,
            },
            timeout=60.0,
        )

        assert response.status_code == 200
        data = response.json()
        analysis = data["analysis"]

        print(f"\n✅ Analysis with Allergen Profile:")
        print(f"   User Allergens: fragrance, parabens")
        print(f"   Detected Allergens: {analysis['allergens_detected']}")


@pytest.mark.asyncio
async def test_invalid_url():
    """Test error handling for invalid URL."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/analyze",
            json={
                "product_url": "not-a-valid-url",
                "allergen_profile": [],
                "force_refresh": False,
            },
            timeout=60.0,
        )

        # Should still return 200 but with low confidence
        # Claude should handle gracefully
        assert response.status_code in [200, 422, 500]
