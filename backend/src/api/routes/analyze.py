"""Product analysis endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
import logging

from ...domain.models import AnalysisRequest, AnalysisResponse, ProductAnalysis
from ...domain.harm_calculator import HarmScoreCalculator
from ...infrastructure.claude_agent import ProductSafetyAgent
from ..auth import verify_api_key

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_product(
    request: AnalysisRequest,
    api_key: str = Depends(verify_api_key)
):
    """Analyze a product for harmful substances.

    Args:
        request: Analysis request with product URL
        api_key: Verified API key from Authorization header

    Returns:
        Analysis response with harm score and details
    """
    try:
        logger.info(f"Analyzing product: {request.product_url}")

        # Initialize Claude agent
        agent = ProductSafetyAgent()

        # For MVP, use empty databases (will integrate Supabase later)
        # TODO: Query Supabase for allergen and PFAS databases
        allergen_db = []
        pfas_db = []

        # Perform analysis using Claude
        analysis_data = await agent.analyze_product(
            product_url=request.product_url,
            allergen_profile=request.allergen_profile,
            allergen_database=allergen_db,
            pfas_database=pfas_db,
        )

        # Calculate harm score
        harm_score = HarmScoreCalculator.calculate(analysis_data)

        # Build ProductAnalysis model
        analysis = ProductAnalysis(
            product_url=request.product_url,
            product_name=analysis_data.get("product_name"),
            brand=analysis_data.get("brand"),
            retailer=analysis_data.get("retailer"),
            ingredients=analysis_data.get("ingredients", []),
            overall_score=100 - harm_score,  # Convert harm to safety score
            allergens_detected=analysis_data.get("allergens_detected", []),
            pfas_detected=analysis_data.get("pfas_detected", []),
            other_concerns=analysis_data.get("other_concerns", []),
            confidence=analysis_data.get("confidence", 0.8),
            analyzed_at=datetime.utcnow(),
        )

        # TODO: Store analysis in Supabase
        # TODO: Find alternatives using Claude

        logger.info(
            f"Analysis complete: {analysis.product_name} - Harm score: {harm_score}"
        )

        return AnalysisResponse(
            analysis=analysis,
            alternatives=[],  # TODO: Implement alternatives
            cached=False,
            cache_age_seconds=None,
        )

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}",
        )
