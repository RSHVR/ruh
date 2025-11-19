"""Product analysis endpoints."""

from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
import logging

from ...domain.models import AnalysisRequest, AnalysisResponse, ProductAnalysis, ReviewInsights
from ...domain.harm_calculator import HarmScoreCalculator
from ...domain.ingredient_matcher import match_ingredients_to_databases
from ...infrastructure.claude_agent import ProductSafetyAgent
from ...infrastructure.product_scraper import ProductScraperService
from ...infrastructure.claude_query import ClaudeQueryService
from ...infrastructure.database import db
from ..auth import verify_api_key
from anthropic import RateLimitError

# Try to import database, but make it optional
try:
    from ...infrastructure.database import db
    DATABASE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Database module not available: {e}. Running without Supabase.")
    DATABASE_AVAILABLE = False
    # Create a mock db object
    class MockDB:
        is_available = False
        def generate_url_hash(self, url): return ""
        async def get_cached_analysis(self, hash): return None
        async def get_all_allergens(self): return []
        async def get_all_pfas(self): return []
        async def store_analysis(self, *args, **kwargs): return False
        async def get_or_create_anonymous_user(self): return None
        async def log_search(self, *args, **kwargs): return False
    db = MockDB()

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize services
scraper_service = ProductScraperService()
query_service = ClaudeQueryService()


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
                retailer=cached_analysis.get('retailer', cached_analysis.get('category', 'Unknown')),
                ingredients=cached_analysis.get('ingredients', []),
                overall_score=cached_analysis.get('overall_score', 100 - cached_analysis.get('harm_score', 0)),
                allergens_detected=cached_analysis.get('allergens_detected', []),
                pfas_detected=cached_analysis.get('pfas_detected', []),
                other_concerns=cached_analysis.get('other_concerns', []),
                confidence=cached_analysis.get('confidence', 80) / 100.0,  # Convert integer 0-100 to float 0.0-1.0
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
                url_hash=url_hash,  # Include for fetching reviews later
            )

        # Step 4: Cache miss - perform new analysis
        logger.info("📝 Cache miss, performing new analysis")

        # Step 4a: Try scraping HTML first
        logger.info("🕷️  Attempting to scrape product page")
        scraped_html = await scraper_service.try_scrape(request.product_url)

        # Step 4b: Load knowledge bases from Supabase (with graceful fallback)
        allergen_db = []
        pfas_db = []
        if db.is_available:
            try:
                logger.info("🔍 Loading allergen and PFAS knowledge bases from Supabase...")
                allergen_db = await db.get_all_allergens()
                pfas_db = await db.get_all_pfas()
                logger.info(f"✅ Loaded {len(allergen_db)} allergens and {len(pfas_db)} PFAS compounds")
            except Exception as e:
                logger.warning(f"⚠️  Failed to load knowledge bases (continuing): {e}")
        else:
            logger.warning("⚠️  Supabase not available - proceeding without knowledge bases")

        # Step 4c: Initialize Claude agent
        agent = ProductSafetyAgent()

        # Step 4d: Branch based on scraping success
        basic_analysis = None  # Store database-only fallback

        if scraped_html is not None and scraped_html.confidence > 0.3:
            # SUCCESS PATH: Scrape → Query → Agent
            logger.info("✅ Scraping succeeded - using two-step Claude process")

            # Claude Query: Extract structured data from HTML
            logger.info("📊 Step 1/2: Claude Query - extracting product data from HTML")
            product_data = await query_service.extract_product_data(scraped_html)

            if product_data.get("confidence", 0) < 0.3:
                logger.warning("⚠️  Claude extraction failed, falling back to web_fetch")
                # Fallback to old method
                try:
                    analysis_data = await agent.analyze_product(
                        product_url=request.product_url,
                        allergen_profile=request.allergen_profile,
                        allergen_database=allergen_db,
                        pfas_database=pfas_db,
                    )
                except RateLimitError as e:
                    logger.warning(f"⚠️  Rate limit hit during web_fetch fallback: {e}")
                    raise HTTPException(
                        status_code=429,
                        detail="Rate limit exceeded. Please try again later.",
                        headers={"Retry-After": "60"}
                    )
            else:
                # NEW: Step 1 - Python-level database comparison (fast, always works)
                logger.info("🔍 Step 1/3: Database matching - comparing ingredients against databases")
                basic_analysis = match_ingredients_to_databases(
                    ingredients=product_data.get('ingredients', []),
                    materials=product_data.get('materials', []),
                    allergen_database=allergen_db,
                    pfas_database=pfas_db
                )
                logger.info(f"✅ Database matching complete: {len(basic_analysis['allergens_detected'])} allergens, {len(basic_analysis['pfas_detected'])} PFAS")

                # Step 2/3 - Try Claude Agent enhancement with web_search
                logger.info("🤖 Step 2/3: Claude Agent - enriching with AI analysis and web_search")
                try:
                    analysis_data = await agent.analyze_extracted_product(
                        product_data=product_data,
                        product_url=request.product_url,
                        allergen_profile=request.allergen_profile,
                        allergen_database=allergen_db,
                        pfas_database=pfas_db,
                    )

                    # Merge basic + enhanced analysis (prefer Claude's findings, supplement with database matches)
                    logger.info("🔀 Step 3/3: Merging database results with AI analysis")
                    # Keep Claude's allergens and PFAS, but add any database-only finds
                    db_allergen_names = {a['name'] for a in basic_analysis['allergens_detected']}
                    ai_allergen_names = {a['name'] for a in analysis_data.get('allergens_detected', [])}
                    db_pfas_names = {p['name'] for p in basic_analysis['pfas_detected']}
                    ai_pfas_names = {p['name'] for p in analysis_data.get('pfas_detected', [])}

                    # Add database findings not found by AI
                    for allergen in basic_analysis['allergens_detected']:
                        if allergen['name'] not in ai_allergen_names:
                            analysis_data.setdefault('allergens_detected', []).append(allergen)

                    for pfas in basic_analysis['pfas_detected']:
                        if pfas['name'] not in ai_pfas_names:
                            analysis_data.setdefault('pfas_detected', []).append(pfas)

                    logger.info(f"✅ Merged analysis: {len(analysis_data['allergens_detected'])} allergens, {len(analysis_data['pfas_detected'])} PFAS")

                except RateLimitError as e:
                    logger.warning(f"⚠️  Rate limit hit - returning database-only results: {e}")
                    # Return basic database results with note about rate limit
                    analysis_data = basic_analysis
                    analysis_data['product_name'] = product_data.get('product_name', 'Unknown Product')
                    analysis_data['brand'] = product_data.get('brand', 'Unknown')
                    analysis_data['ingredients'] = product_data.get('ingredients', [])
                    analysis_data['note'] = 'Rate limit reached - showing database matches only'

                except Exception as e:
                    logger.error(f"⚠️  Claude Agent failed - returning database-only results: {e}")
                    # Return basic database results as fallback
                    analysis_data = basic_analysis
                    analysis_data['product_name'] = product_data.get('product_name', 'Unknown Product')
                    analysis_data['brand'] = product_data.get('brand', 'Unknown')
                    analysis_data['ingredients'] = product_data.get('ingredients', [])
                    analysis_data['note'] = 'AI analysis unavailable - showing database matches only'
        else:
            # FALLBACK PATH: Use Claude web_fetch (old method)
            logger.info("🔄 Scraping not available - using Claude web_fetch fallback")
            try:
                analysis_data = await agent.analyze_product(
                    product_url=request.product_url,
                    allergen_profile=request.allergen_profile,
                    allergen_database=allergen_db,
                    pfas_database=pfas_db,
                )
            except RateLimitError as e:
                logger.warning(f"⚠️  Rate limit hit during web_fetch: {e}")
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please try again later.",
                    headers={"Retry-After": "60"}
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

        # Step 5: Store analysis in Supabase (with graceful fallback)
        if db.is_available:
            try:
                logger.info(f"💾 Storing analysis in Supabase for: {analysis.product_name}")
                # Format data to match what database.py expects
                analysis_response = {
                    "analysis": {
                        "product_name": analysis.product_name,
                        "brand": analysis.brand,
                        "category": analysis.retailer,
                        "retailer": analysis.retailer,
                        "overall_score": analysis.overall_score,
                        "ingredients": analysis.ingredients,
                        "allergens": analysis.allergens_detected,  # database.py maps this to allergens_detected
                        "pfas_compounds": analysis.pfas_detected,  # database.py maps this to pfas_detected
                        "other_concerns": analysis.other_concerns,
                        "confidence": analysis.confidence,
                    }
                }
                store_success = await db.store_analysis(url_hash, request.product_url, analysis_response)
                if store_success:
                    logger.info(f"✅ Successfully stored analysis in Supabase (hash: {url_hash[:16]}...)")
                else:
                    logger.warning(f"⚠️  Failed to store analysis in Supabase (non-fatal)")
            except Exception as e:
                logger.error(f"⚠️  Supabase storage failed (non-fatal): {e}")
        else:
            logger.debug("⚠️  Supabase not available - skipping analysis storage")

        # Step 6: Log search (with graceful fallback)
        if db.is_available:
            try:
                user_id = await db.get_or_create_anonymous_user()
                logger.debug(f"Logging search for user: {user_id}")
                log_success = await db.log_search(user_id, request.product_url)
                if log_success:
                    logger.info(f"✅ Successfully logged search for user {user_id}")
                else:
                    logger.warning(f"⚠️  Failed to log search (non-fatal)")
            except Exception as e:
                logger.error(f"⚠️  Search logging failed (non-fatal): {e}")
        else:
            logger.debug("⚠️  Supabase not available - skipping search logging")

        logger.info(
            f"Analysis complete: {analysis.product_name} - Harm score: {harm_score}"
        )

        return AnalysisResponse(
            analysis=analysis,
            alternatives=[],  # TODO: Implement alternatives
            cached=False,
            cache_age_seconds=None,
            url_hash=url_hash,  # Include for fetching reviews later
        )

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}",
        )


@router.get("/analyze/{url_hash}/reviews", response_model=ReviewInsights)
async def get_review_insights(
    url_hash: str,
    force_refresh: bool = False,
    api_key: str = Depends(verify_api_key)
):
    """Get consumer insights from product reviews and Q&A.

    This endpoint fetches and analyzes customer reviews separately from
    the main product analysis. It can be called after the initial analysis
    to get consumer health complaints and concerns.

    Args:
        url_hash: SHA256 hash of product URL (returned in analysis response)
        force_refresh: Skip cache and re-scrape reviews
        api_key: API key for authentication

    Returns:
        Consumer insights including health complaints and concerns
    """
    try:
        logger.info(f"Fetching review insights for hash: {url_hash}")

        # Step 1: Check cache for reviews (with graceful fallback)
        if not force_refresh and db.is_available:
            try:
                cached_reviews = await db.get_cached_reviews(url_hash)
                if cached_reviews:
                    logger.info("✅ Reviews cache HIT")
                    return ReviewInsights(**cached_reviews)
            except Exception as e:
                logger.warning(f"⚠️  Failed to check reviews cache (continuing): {e}")

        # Step 2: Get original product URL from analysis cache
        if db.is_available:
            try:
                cached_analysis = await db.get_cached_analysis(url_hash)
                if not cached_analysis:
                    raise HTTPException(
                        status_code=404,
                        detail="Product not found. Analyze the product first."
                    )
                product_url = cached_analysis['product_url']
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to retrieve product info: {str(e)}"
                )
        else:
            raise HTTPException(
                status_code=503,
                detail="Database unavailable. Cannot fetch reviews without URL."
            )

        # Step 3: Scrape reviews HTML
        logger.info(f"📝 Scraping reviews for: {product_url}")
        scraped_reviews = await scraper_service.try_scrape(
            product_url,
            include_reviews=True  # Enable reviews scraping
        )

        if not scraped_reviews or not scraped_reviews.has_reviews:
            raise HTTPException(
                status_code=404,
                detail="No reviews available for this product"
            )

        # Step 4: Extract review insights with Claude Query
        logger.info("💬 Extracting consumer insights from reviews")
        review_data = await query_service.extract_review_insights(scraped_reviews)

        if review_data.get("confidence", 0) < 0.3:
            raise HTTPException(
                status_code=500,
                detail="Failed to extract review insights"
            )

        # Step 5: Build response
        insights = ReviewInsights(
            url_hash=url_hash,
            product_url=product_url,
            overall_sentiment=review_data.get("overall_sentiment", "mixed"),
            total_reviews_analyzed=review_data.get("total_reviews_analyzed", 0),
            rating_distribution=review_data.get("rating_distribution", {}),
            common_complaints=review_data.get("common_complaints", []),
            health_concerns=review_data.get("health_concerns", []),
            positive_feedback=review_data.get("positive_feedback", []),
            questions_concerns=review_data.get("questions_concerns", []),
            verified_purchase_ratio=review_data.get("verified_purchase_ratio", 0.0),
            confidence=review_data.get("confidence", 0.8),
            analyzed_at=datetime.utcnow(),
        )

        # Step 6: Cache in Supabase (with graceful fallback)
        if db.is_available:
            try:
                await db.cache_review_insights(url_hash, insights.dict())
                logger.info("✅ Cached review insights")
            except Exception as e:
                logger.warning(f"⚠️  Failed to cache reviews (non-fatal): {e}")

        logger.info(f"✅ Review insights extracted successfully")

        return insights

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Review insights extraction failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Review analysis failed: {str(e)}"
        )
