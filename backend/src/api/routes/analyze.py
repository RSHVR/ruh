"""Product analysis endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
import logging

from ...domain.models import AnalysisRequest, AnalysisResponse, ProductAnalysis
from ...domain.harm_calculator import HarmScoreCalculator
from ...infrastructure.claude_agent import ProductSafetyAgent
from ...infrastructure.database import db
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

        # Step 1: Generate URL hash for caching
        url_hash = db.generate_url_hash(request.product_url)

        # Step 2: Check cache (unless force_refresh is requested)
        cached_analysis = None
        if not request.force_refresh and db.is_available:
            cached_analysis = await db.get_cached_analysis(url_hash)

        # Step 3: If cached, return immediately
        if cached_analysis:
            logger.info(f"Returning cached analysis for: {cached_analysis.get('product_name')}")

            # Calculate cache age
            analyzed_at = datetime.fromisoformat(cached_analysis['analyzed_at'].replace('Z', '+00:00'))
            cache_age = (datetime.utcnow() - analyzed_at).total_seconds()

            # Build ProductAnalysis from cached data
            analysis = ProductAnalysis(
                product_url=cached_analysis['product_url'],
                product_name=cached_analysis['product_name'],
                brand=cached_analysis['brand'],
                retailer=cached_analysis.get('category', 'Unknown'),  # Using category as retailer for now
                ingredients=cached_analysis.get('raw_analysis', {}).get('ingredients', []),
                overall_score=100 - cached_analysis['harm_score'],
                allergens_detected=cached_analysis.get('allergens', []),
                pfas_detected=cached_analysis.get('pfas_compounds', []),
                other_concerns=cached_analysis.get('other_concerns', []),
                confidence=cached_analysis.get('raw_analysis', {}).get('confidence', 0.8),
                analyzed_at=analyzed_at,
            )

            # Log search
            if db.is_available:
                user_id = await db.get_or_create_anonymous_user()
                await db.log_search(user_id, request.product_url)

            return AnalysisResponse(
                analysis=analysis,
                alternatives=[],  # TODO: Implement alternatives
                cached=True,
                cache_age_seconds=int(cache_age),
            )

        # Step 4: Cache miss - perform new analysis
        logger.info("📝 Cache miss, performing new analysis")

        # Query knowledge bases from Supabase
        if db.is_available:
            logger.info("🔍 Loading allergen and PFAS knowledge bases from Supabase...")
            allergen_db = await db.get_all_allergens()
            pfas_db = await db.get_all_pfas()
            logger.info(f"✅ Loaded {len(allergen_db)} allergens and {len(pfas_db)} PFAS compounds from database")
        else:
            logger.warning("⚠️  Supabase not available - proceeding without knowledge bases")
            allergen_db = []
            pfas_db = []

        # Initialize Claude agent
        agent = ProductSafetyAgent()

        # Perform analysis using Claude with knowledge bases
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

        # Step 5: Store analysis in Supabase
        if db.is_available:
            logger.info(f"💾 Storing analysis in Supabase for: {analysis.product_name}")
            analysis_response = {
                "analysis": {
                    "product_name": analysis.product_name,
                    "brand": analysis.brand,
                    "category": analysis.retailer,
                    "overall_score": analysis.overall_score,
                    "summary": analysis_data.get("summary", ""),
                    "ingredients": analysis.ingredients,
                    "allergens": analysis.allergens_detected,
                    "pfas_compounds": analysis.pfas_detected,
                    "other_concerns": analysis.other_concerns,
                    "safer_alternatives": "",  # TODO: Implement alternatives
                    "confidence": analysis.confidence,
                }
            }
            store_success = await db.store_analysis(url_hash, request.product_url, analysis_response)
            if store_success:
                logger.info(f"✅ Successfully stored analysis in Supabase (hash: {url_hash[:16]}...)")
            else:
                logger.error(f"❌ Failed to store analysis in Supabase")
        else:
            logger.warning("⚠️  Supabase not available - skipping analysis storage")

        # Step 6: Log search
        if db.is_available:
            user_id = await db.get_or_create_anonymous_user()
            logger.debug(f"Logging search for user: {user_id}")
            log_success = await db.log_search(user_id, request.product_url)
            if log_success:
                logger.info(f"✅ Successfully logged search for user {user_id}")
            else:
                logger.error(f"❌ Failed to log search")
        else:
            logger.warning("⚠️  Supabase not available - skipping search logging")

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
