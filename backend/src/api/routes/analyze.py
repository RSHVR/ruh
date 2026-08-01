"""Product analysis endpoints."""

from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone
import asyncio
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address

from ...domain.models import AnalysisRequest, AnalysisResponse, ProductAnalysis, ReviewInsights, ScrapedProduct
from ...domain.harm_calculator import HarmScoreCalculator
from ...domain.identity import product_identity_ok
from ...domain.ingredient_matcher import match_ingredients_to_databases
from ...infrastructure.safety_agent import ProductSafetyAgentWrapper as ProductSafetyAgent
from ...infrastructure.product_scraper import ProductScraperService
from ...infrastructure.claude_query import ClaudeQueryService
from ...infrastructure.trafilatura_extractor import extract_product_data as trafilatura_extract, preprocess_ingredients
from ...infrastructure.section_parser import parse_sections
from ...infrastructure.database import db
from ...infrastructure.review_vector_service import review_vector_service
from ...infrastructure.validation_logger import validation_logger
from ...infrastructure.token_tracker import TokenTracker
from ...infrastructure import referral_service
from ..auth import verify_api_key, get_auth_context, AuthContext
from ...infrastructure.config import settings
from anthropic import RateLimitError
from typing import List, Dict, Any


def _safe_error_detail(message: str, error: Exception) -> str:
    """Return error detail with str(e) only in debug mode."""
    if settings.debug:
        return f"{message}: {str(error)}"
    return message

# Initialize limiter
limiter = Limiter(key_func=get_remote_address)

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

# Initialize scraper service (stateless, can be reused)
scraper_service = ProductScraperService()


def _auth_fields(auth: AuthContext, url_hash: str = "") -> dict:
    """Build the auth/credit fields to merge into AnalysisResponse.

    Returns an empty dict for legacy API-key callers so existing
    behavior is unchanged.
    """
    if auth.is_api_key:
        return {}

    # Check if this product is already unlocked for the user
    unlocked = False
    if auth.user_id and url_hash:
        try:
            from ...infrastructure.database import db
            if db.is_available:
                resp = db.client.table("unlocked_analyses").select("id").eq(
                    "user_id", str(auth.user_id)
                ).eq("url_hash", url_hash).execute()
                unlocked = bool(resp.data)
        except Exception:
            pass  # Non-fatal — default to not unlocked

    return {
        "user_tier": auth.tier,
        "credits_remaining": auth.credits_remaining,
        "analysis_unlocked": unlocked or auth.tier == "unlimited",
    }


async def _fire_referral_conversion(auth: AuthContext) -> None:
    """Best-effort referral conversion for a JWT user who completed an analysis.

    If this user was invited and this is their first qualifying analysis, the
    referrer is credited by the process_referral_conversion RPC (idempotent, so
    firing on every analysis is safe). Runs off the event loop and swallows all
    errors — referral crediting must never delay or fail the analysis response.
    No-op for legacy API-key callers.
    """
    if auth.is_api_key or not auth.user_id:
        return
    try:
        await asyncio.to_thread(referral_service.process_conversion, auth.user_id)
    except Exception as e:  # defensive — process_conversion already guards internally
        logger.warning("Referral conversion hook failed (non-fatal): %s", e)


def validate_and_filter_substances(
    analysis_data: Dict[str, Any],
    allergen_database: List[Dict[str, Any]],
    pfas_database: List[Dict[str, Any]],
    product_url: str,
    product_name: str
) -> Dict[str, Any]:
    """Validate Claude's detected substances against database and filter/reclassify as needed.

    This implements LOG-ONLY mode initially - we log mismatches but don't remove them yet.

    Args:
        analysis_data: Claude's analysis results
        allergen_database: Full allergen knowledge base
        pfas_database: Full PFAS knowledge base
        product_url: Product URL for logging
        product_name: Product name for logging

    Returns:
        Validated analysis_data with filtered substances
    """
    # Build lookup sets for fast validation (case-insensitive)
    allergen_names = {a.get('name', '').lower() for a in allergen_database}
    allergen_synonyms = set()
    for a in allergen_database:
        for syn in a.get('synonyms', []):
            allergen_synonyms.add(syn.lower())
    all_allergen_matches = allergen_names | allergen_synonyms

    pfas_names = {p.get('name', '').lower() for p in pfas_database}
    pfas_cas_numbers = {p.get('cas_number', '').strip() for p in pfas_database if p.get('cas_number')}

    # Validate allergens
    allergens_detected = analysis_data.get('allergens_detected', [])
    valid_allergens = []
    invalid_allergens = []

    for allergen in allergens_detected:
        name = allergen.get('name', '')
        name_lower = name.lower()

        # Check if in database (exact or synonym match)
        if name_lower in all_allergen_matches:
            valid_allergens.append(allergen)
        else:
            invalid_allergens.append(allergen)
            validation_logger.log_invalid_allergen(
                substance_name=name,
                severity=allergen.get('severity', 'unknown'),
                confidence=allergen.get('confidence', 0.0),
                source=allergen.get('source', 'unknown'),
                product_url=product_url,
                product_name=product_name
            )

    # Validate PFAS
    pfas_detected = analysis_data.get('pfas_detected', [])
    valid_pfas = []
    invalid_pfas = []

    for pfas in pfas_detected:
        name = pfas.get('name', '')
        name_lower = name.lower()
        cas = pfas.get('cas_number', '').strip()

        # Check if in database (by name or CAS number)
        if name_lower in pfas_names or (cas and cas in pfas_cas_numbers):
            valid_pfas.append(pfas)
        else:
            invalid_pfas.append(pfas)
            validation_logger.log_invalid_pfas(
                substance_name=name,
                cas_number=cas if cas else None,
                confidence=pfas.get('confidence', 0.0),
                source=pfas.get('source', 'unknown'),
                product_url=product_url,
                product_name=product_name
            )

    # LOG-ONLY MODE: Keep all substances for now, just log the issues
    # In future, we can switch to STRICT mode by using valid_* lists only
    analysis_data['allergens_detected'] = allergens_detected  # Keep all for now
    analysis_data['pfas_detected'] = pfas_detected  # Keep all for now

    # Log validation summary
    validation_logger.log_validation_summary(
        product_name=product_name,
        product_url=product_url,
        allergens_total=len(allergens_detected),
        allergens_valid=len(valid_allergens),
        allergens_invalid=len(invalid_allergens),
        pfas_total=len(pfas_detected),
        pfas_valid=len(valid_pfas),
        pfas_invalid=len(invalid_pfas)
    )

    # TODO: Once we review logs and are confident, switch to strict mode:
    # analysis_data['allergens_detected'] = valid_allergens
    # analysis_data['pfas_detected'] = valid_pfas
    #
    # # Move invalid substances to other_concerns
    # for allergen in invalid_allergens:
    #     analysis_data.setdefault('other_concerns', []).append({
    #         "name": allergen['name'],
    #         "category": "under_investigation",
    #         "severity": "low",
    #         "description": f"Potential irritant (not a priority allergen): {allergen.get('source', '')}",
    #         "confidence": min(allergen.get('confidence', 0.5), 0.6)
    #     })

    return analysis_data


@router.post("/analyze", response_model=AnalysisResponse)
@limiter.limit("30/minute")  # 30 requests per minute per IP - generous for normal browsing
async def analyze_product(
    request: Request,
    analysis_request: AnalysisRequest,
    auth: AuthContext = Depends(get_auth_context)
):
    """Analyze a product for harmful substances.

    Args:
        request: HTTP request (required by slowapi for rate limiting)
        analysis_request: Analysis request with product URL
        auth: Authentication context (JWT user or legacy API key)

    Returns:
        Analysis response with harm score and details
    """
    try:
        logger.info(f"Analyzing product: {analysis_request.product_url}")

        # Step 1: Generate URL hash for caching (URL is normalized before hashing)
        url_hash = db.generate_url_hash(analysis_request.product_url)
        logger.info(f"Normalized URL hash: {url_hash[:16]}...")

        # Step 2: Check cache (unless force_refresh is requested)
        cached_analysis = None
        if not analysis_request.force_refresh and db.is_available:
            cached_analysis = await db.get_cached_analysis(url_hash)

        # Step 3: If cached, return immediately
        if cached_analysis:
            logger.info(f"Returning cached analysis for: {cached_analysis.get('product_name')}")

            # Calculate cache age
            analyzed_at = datetime.fromisoformat(cached_analysis['analyzed_at'].replace('Z', '+00:00'))
            cache_age = (datetime.now(timezone.utc) - analyzed_at).total_seconds()

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
                research_sources=cached_analysis.get('research_sources') or [],
                ingredients_by_provenance=cached_analysis.get('ingredients_by_provenance'),
                origin=cached_analysis.get('origin'),
                confidence=cached_analysis.get('confidence', 80) / 100.0,  # Convert integer 0-100 to float 0.0-1.0
                analyzed_at=analyzed_at,
            )

            # Get cached review insights if available
            cached_review_insights = None
            if db.is_available:
                try:
                    cached_review_insights = await db.get_cached_reviews(url_hash)
                    if cached_review_insights:
                        logger.info("✅ Returning cached review insights")
                except Exception as e:
                    logger.warning(f"⚠️  Failed to get cached reviews (non-fatal): {e}")

            # Log search
            if db.is_available:
                user_id = await db.get_or_create_anonymous_user()
                await db.log_search(user_id, analysis_request.product_url)

            # A cache hit still counts as the invited user completing an analysis.
            await _fire_referral_conversion(auth)

            return AnalysisResponse(
                analysis=analysis,
                alternatives=[],  # TODO: Implement alternatives
                cached=True,
                cache_age_seconds=int(cache_age),
                url_hash=url_hash,  # Include for fetching reviews later
                review_insights=cached_review_insights,
                **_auth_fields(auth, url_hash),
            )

        # Step 4: Cache miss - perform new analysis
        logger.info("📝 Cache miss, performing new analysis")

        # Initialize shared token tracker for this analysis
        token_tracker = TokenTracker()
        token_tracker.start_analysis(url_hash)

        # Check if client provided HTML (extension captured from user's session)
        client_product_html = analysis_request.product_html
        client_reviews_html = analysis_request.reviews_html

        if client_product_html:
            logger.info(f"📦 Client provided product HTML: {len(client_product_html)} bytes")
        if client_reviews_html:
            logger.info(f"📦 Client provided reviews: {len(client_reviews_html)} bytes")

        # Step 4a: Use client-provided HTML or fall back to scraping
        scraped_html = None
        if client_product_html:
            # Process client HTML using the URL-appropriate scraper (ADR-002).
            # Selector-based extraction compresses ~2MB raw HTML to ~20KB clean text.
            logger.info("✅ Processing client-provided HTML with selector extraction")
            scraped_html = await scraper_service.process_client_html(
                url=analysis_request.product_url,
                product_html=client_product_html,
                reviews_html=client_reviews_html or "",
            )
        else:
            # Fall back to scraping (may fail on Cloud Run)
            logger.info("🕷️  No client HTML, attempting to scrape product page")
            scraped_html = await scraper_service.try_scrape(analysis_request.product_url)

        # Step 4b: Load knowledge bases from Supabase (with graceful fallback)
        allergen_db = []
        pfas_db = []
        toxic_db = []
        if db.is_available:
            try:
                logger.info("🔍 Loading allergen, PFAS, and toxic substance knowledge bases from Supabase...")
                allergen_db = await db.get_all_allergens()
                pfas_db = await db.get_all_pfas()
                toxic_db = await db.get_all_toxic_substances()
                logger.info(f"✅ Loaded {len(allergen_db)} allergens, {len(pfas_db)} PFAS, {len(toxic_db)} toxic substances")
            except Exception as e:
                logger.warning(f"⚠️  Failed to load knowledge bases (continuing): {e}")
        else:
            logger.warning("⚠️  Supabase not available - proceeding without knowledge bases")

        # Step 4c: Initialize Claude services with shared token tracker
        query_service = ClaudeQueryService(token_tracker=token_tracker)
        # Pass supabase client for LangGraph ingredient lookups
        supabase_client = db.client if db.is_available else None
        agent = ProductSafetyAgent(
            token_tracker=token_tracker,
            supabase_client=supabase_client,
        )

        # Step 4d: Branch based on scraping success
        basic_analysis = None  # Store database-only fallback

        if scraped_html is not None and scraped_html.confidence > 0.3:
            # SUCCESS PATH: HTML available → Extract → Agent
            logger.info("✅ HTML available - using optimized extraction pipeline")

            # Step 1: Extract product data (FREE - no LLM call)
            content = scraped_html.raw_html_product
            is_pre_extracted = content.lstrip().startswith("===")

            if is_pre_extracted:
                # Client-submitted HTML was already processed by AmazonScraper
                # into === section === format. Use the dedicated parser.
                logger.info("📊 Step 1a: Section parser - pre-extracted content detected")
                trafilatura_result, needs_llm_fallback = parse_sections(
                    text=content,
                    url=analysis_request.product_url,
                )
            else:
                # Raw HTML - use Trafilatura's CSS selectors / content extraction
                logger.info("📊 Step 1a: Trafilatura - attempting rule-based extraction")
                trafilatura_result, needs_llm_fallback = trafilatura_extract(
                    html=content,
                    url=analysis_request.product_url,
                    min_confidence=0.5
                )

            if not needs_llm_fallback:
                # Trafilatura succeeded - save ~$0.01 Claude Query call
                logger.info(f"✅ Trafilatura extraction succeeded ({trafilatura_result.confidence:.0%} confidence)")
                logger.info(f"   Method: {trafilatura_result.extraction_method}, {len(trafilatura_result.ingredients)} ingredients")
                product_data = trafilatura_result.to_dict()
                # Add product URL for downstream use
                product_data["product_url"] = analysis_request.product_url
            else:
                # Trafilatura low confidence - fall back to Claude Query
                logger.info(f"⚠️  Trafilatura low confidence ({trafilatura_result.confidence:.0%}), falling back to Claude Query")
                product_data = await query_service.extract_product_data(scraped_html)

            if product_data.get("confidence", 0) < 0.3:
                logger.warning("⚠️  Claude extraction failed, falling back to web_fetch")
                # Fallback to old method
                try:
                    analysis_data = await agent.analyze_product(
                        product_url=analysis_request.product_url,
                        allergen_profile=analysis_request.allergen_profile,
                        allergen_database=allergen_db,
                        pfas_database=pfas_db,
                        user_region=analysis_request.user_region,
                    )
                except RateLimitError as e:
                    logger.warning(f"⚠️  Rate limit hit during web_fetch fallback: {e}")
                    raise HTTPException(
                        status_code=429,
                        detail="Rate limit exceeded. Please try again later.",
                        headers={"Retry-After": "60"}
                    )
            else:
                # Step 1/3 - Database matching (fast, uses Supabase knowledge bases)
                logger.info("🔍 Step 1/3: Database matching - comparing ingredients against knowledge bases")
                basic_analysis = match_ingredients_to_databases(
                    ingredients=product_data.get('ingredients', []),
                    materials=product_data.get('materials', []),
                    allergen_database=allergen_db,
                    pfas_database=pfas_db,
                    toxic_database=toxic_db,
                )
                logger.info(
                    f"✅ Database matching: {len(basic_analysis['allergens_detected'])} allergens, "
                    f"{len(basic_analysis['pfas_detected'])} PFAS, "
                    f"{len(basic_analysis.get('other_concerns', []))} toxic substances"
                )

                # Step 2/3 - Classify ingredients based on database results
                logger.info("🔍 Step 2/3: Classifying ingredients to reduce LLM research")
                all_ingredients = product_data.get('ingredients', []) + product_data.get('materials', [])

                # Get names of ingredients that matched the database
                db_matched_names = set()
                for a in basic_analysis.get('allergens_detected', []):
                    db_matched_names.add(a.get('name', '').lower())
                    # Also add the source ingredient
                    source = a.get('source', '')
                    if 'Found in:' in source:
                        db_matched_names.add(source.replace('Found in:', '').strip().lower())
                for p in basic_analysis.get('pfas_detected', []):
                    db_matched_names.add(p.get('name', '').lower())
                    source = p.get('source', '')
                    if 'Found in:' in source:
                        db_matched_names.add(source.replace('Found in:', '').strip().lower())

                # Classify: use trafilatura's safe list + database matches as "known"
                safe_ingredients, hardcoded_concerns, _ = preprocess_ingredients(all_ingredients)

                # Combine database matches + hardcoded concerns
                known_concerns = []
                for a in basic_analysis.get('allergens_detected', []):
                    known_concerns.append({
                        'name': a.get('name'),
                        'category': 'allergen',
                        'description': a.get('health_effects', 'Potential allergen'),
                    })
                for p in basic_analysis.get('pfas_detected', []):
                    known_concerns.append({
                        'name': p.get('name'),
                        'category': 'pfas',
                        'description': p.get('health_effects', 'Forever chemical'),
                    })
                known_concerns.extend(hardcoded_concerns)  # Add fragrance, formaldehyde, etc.

                # Ingredients needing research = not safe AND not already matched
                known_concern_names = {c['name'].lower() for c in known_concerns}
                safe_names = {s.lower() for s in safe_ingredients}
                needs_research = [
                    ing for ing in all_ingredients
                    if ing.lower() not in safe_names
                    and ing.lower() not in db_matched_names
                    and ing.lower() not in known_concern_names
                ]

                logger.info(f"   Classification: {len(safe_ingredients)} safe, {len(known_concerns)} known concerns, {len(needs_research)} need research")

                # Add to product_data for the agent
                product_data['_known_safe'] = safe_ingredients
                product_data['_known_concerns'] = known_concerns
                product_data['_needs_research'] = needs_research

                # Step 3/3 - Try Claude Agent enhancement with web_search
                logger.info("🤖 Step 3/3: Claude Agent - enriching with AI analysis and web_search")
                try:
                    analysis_data = await agent.analyze_extracted_product(
                        product_data=product_data,
                        product_url=analysis_request.product_url,
                        allergen_profile=analysis_request.allergen_profile,
                        allergen_database=allergen_db,
                        pfas_database=pfas_db,
                        user_region=analysis_request.user_region,
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
                    product_url=analysis_request.product_url,
                    allergen_profile=analysis_request.allergen_profile,
                    allergen_database=allergen_db,
                    pfas_database=pfas_db,
                    user_region=analysis_request.user_region,
                )
            except RateLimitError as e:
                logger.warning(f"⚠️  Rate limit hit during web_fetch: {e}")
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please try again later.",
                    headers={"Retry-After": "60"}
                )

        # Step 5: Validate Claude's substances against database (LOG-ONLY mode)
        logger.info("🔍 Validating detected substances against database...")
        analysis_data = validate_and_filter_substances(
            analysis_data=analysis_data,
            allergen_database=allergen_db,
            pfas_database=pfas_db,
            product_url=analysis_request.product_url,
            product_name=analysis_data.get("product_name", "Unknown")
        )

        # Identity guard: a confidently-wrong analysis (fallback drifted to a
        # different page) is worse than an error — fail so the client retries,
        # and never store it.
        if not product_identity_ok(
            analysis_request.product_url,
            analysis_data.get("product_name"),
            analysis_data.get("brand"),
        ):
            logger.error(
                "🚫 Identity guard: analysis %r/%r does not match URL %s — rejecting",
                analysis_data.get("product_name"),
                analysis_data.get("brand"),
                analysis_request.product_url,
            )
            raise HTTPException(
                status_code=422,
                detail="We couldn't verify this page's product — please retry the analysis.",
            )

        # Calculate harm score
        harm_score = HarmScoreCalculator.calculate(analysis_data)

        # Build ProductAnalysis model
        analysis = ProductAnalysis(
            product_url=analysis_request.product_url,
            product_name=analysis_data.get("product_name"),
            brand=analysis_data.get("brand"),
            retailer=analysis_data.get("retailer"),
            ingredients=analysis_data.get("ingredients", []),
            overall_score=100 - harm_score,  # Convert harm to safety score
            allergens_detected=analysis_data.get("allergens_detected", []),
            pfas_detected=analysis_data.get("pfas_detected", []),
            other_concerns=analysis_data.get("other_concerns", []),
            research_sources=analysis_data.get("research_sources", []),
            ingredients_by_provenance=analysis_data.get("ingredients_by_provenance"),
            origin=analysis_data.get("origin"),
            confidence=analysis_data.get("confidence", 0.8),
            analyzed_at=datetime.now(timezone.utc),
        )

        # Finish token tracking and get summary
        token_summary = token_tracker.finish_analysis()

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
                        "research_sources": analysis.research_sources,
                        "ingredients_by_provenance": analysis.ingredients_by_provenance,
                        "origin": analysis.origin,
                        "confidence": analysis.confidence,
                    }
                }

                # Add token usage data if available
                if token_summary:
                    analysis_response["token_usage"] = {
                        "total_input_tokens": token_summary.total_input_tokens,
                        "total_output_tokens": token_summary.total_output_tokens,
                        "total_tokens": token_summary.total_tokens,
                        "total_cost_usd": token_summary.total_cost,
                        "api_call_count": token_summary.call_count,
                        "token_usage_details": [call.to_dict() for call in token_summary.calls],
                    }

                store_success = await db.store_analysis(url_hash, analysis_request.product_url, analysis_response)
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
                log_success = await db.log_search(user_id, analysis_request.product_url)
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

        # Step 7: Store reviews with embeddings (non-blocking, best effort)
        # Merge product page reviews + fetched reviews for comprehensive storage
        reviews_stored = None
        combined_reviews_html = ""
        if client_product_html or client_reviews_html:
            try:
                # Combine both HTML sources - both contain review divs with data-hook="review"
                # Product page has ~8-10 embedded reviews, fetched has ~50 reviews
                if client_product_html and client_reviews_html:
                    combined_reviews_html = client_product_html + "\n<!-- FETCHED_REVIEWS -->\n" + client_reviews_html
                elif client_product_html:
                    combined_reviews_html = client_product_html
                else:
                    combined_reviews_html = client_reviews_html

                # Count total reviews for logging
                review_count = combined_reviews_html.count('data-hook="review"')
                logger.info(f"💬 Storing {review_count} reviews with embeddings (product page + fetched)...")

                stored, failed = await review_vector_service.store_reviews(
                    url_hash=url_hash,
                    product_url=analysis_request.product_url,
                    reviews_html=combined_reviews_html,
                    source="client",
                    pages_fetched=5  # Default assumption from client
                )
                reviews_stored = stored
                logger.info(f"✅ Reviews stored: {stored} success, {failed} failed")
            except Exception as e:
                logger.warning(f"⚠️  Review storage failed (non-fatal): {e}")

        # Step 8: Analyze reviews for health concerns (TOKEN-EFFICIENT)
        # Uses semantic search to find health-relevant reviews first,
        # then only sends those to Claude (saves ~80% tokens)
        logger.info("=" * 60)
        logger.info("📊 STEP 8: REVIEW HEALTH ANALYSIS")
        logger.info(f"   reviews_stored = {reviews_stored}")

        review_insights = None
        if reviews_stored and reviews_stored > 0:
            try:
                logger.info("   🔍 Running semantic search for health-relevant reviews...")

                # Get only health-relevant reviews via semantic search
                relevant_reviews = await review_vector_service.get_health_relevant_reviews(
                    url_hash=url_hash,
                    max_reviews=15
                )

                logger.info(f"   📋 Semantic search returned {len(relevant_reviews)} health-relevant reviews")

                if relevant_reviews:
                    logger.info("   🤖 CALLING CLAUDE FOR REVIEW ANALYSIS...")

                    # Analyze only the relevant subset (saves tokens!)
                    review_insights = await query_service.extract_review_insights_from_list(
                        reviews=relevant_reviews,
                        product_url=analysis_request.product_url
                    )

                    # Log what we found
                    health_concerns = review_insights.get('health_concerns', [])
                    common_complaints = review_insights.get('common_complaints', [])
                    logger.info(f"   ✅ CLAUDE RETURNED: {len(health_concerns)} health concerns, {len(common_complaints)} complaints")

                    # Cache insights if database is available and confidence is good
                    if db.is_available and review_insights.get("confidence", 0) > 0.3:
                        try:
                            await db.cache_review_insights(url_hash, review_insights)
                            logger.info("   ✅ Cached review insights to database")
                        except Exception as e:
                            logger.warning(f"   ⚠️  Failed to cache review insights (non-fatal): {e}")
                else:
                    logger.info("   ⏭️  SKIP CLAUDE: No health-relevant reviews found (semantic search empty)")

            except Exception as e:
                logger.warning(f"   ⚠️  Review analysis failed (non-fatal): {e}")
        else:
            logger.info("   ⏭️  SKIP STEP 8: No reviews stored (reviews_stored=0 or None)")

        logger.info("=" * 60)

        # Invited user just completed a fresh analysis — credit the referrer if any.
        await _fire_referral_conversion(auth)

        return AnalysisResponse(
            analysis=analysis,
            alternatives=[],  # TODO: Implement alternatives
            cached=False,
            cache_age_seconds=None,
            url_hash=url_hash,  # Include for fetching reviews later
            reviews_stored=reviews_stored,
            review_insights=review_insights,
            **_auth_fields(auth, url_hash),
        )

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=_safe_error_detail("Analysis failed", e),
        )


@router.get("/analyze/{url_hash}/reviews", response_model=ReviewInsights)
async def get_review_insights(
    url_hash: str,
    force_refresh: bool = False,
    auth: AuthContext = Depends(get_auth_context)
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
                    detail=_safe_error_detail("Failed to retrieve product info", e)
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
            analyzed_at=datetime.now(timezone.utc),
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
            detail=_safe_error_detail("Review analysis failed", e)
        )


# ============================================
# SEMANTIC REVIEW SEARCH
# ============================================

from pydantic import BaseModel, Field
from typing import Optional, List


class ReviewSearchRequest(BaseModel):
    """Request for semantic review search."""
    query: str = Field(..., description="Search query (e.g., 'skin irritation', 'allergic reaction')")
    url_hash: Optional[str] = Field(None, description="Filter to specific product")
    top_k: int = Field(10, ge=1, le=50, description="Number of results to return")
    min_rating: Optional[int] = Field(None, ge=1, le=5, description="Minimum star rating filter")
    verified_only: bool = Field(False, description="Only include verified purchases")


class ReviewSearchResult(BaseModel):
    """Individual search result."""
    id: str
    url_hash: str
    review_text: str
    review_rating: Optional[int]
    verified_purchase: bool
    similarity: float
    rerank_score: Optional[float] = None


class ReviewSearchResponse(BaseModel):
    """Response for semantic review search."""
    query: str
    results: List[ReviewSearchResult]
    total_results: int


@router.post("/reviews/search", response_model=ReviewSearchResponse)
@limiter.limit("60/minute")
async def search_reviews(
    request: Request,
    search_request: ReviewSearchRequest,
    auth: AuthContext = Depends(get_auth_context)
):
    """Search reviews semantically using Cohere embeddings.

    This endpoint allows searching across all stored reviews using
    natural language queries. Useful for finding health complaints,
    specific issues, or patterns across products.

    Examples:
    - "skin rash or irritation"
    - "allergic reaction"
    - "breathing problems"
    - "chemical smell"
    """
    try:
        logger.info(f"🔍 Searching reviews: '{search_request.query}'")

        results = await review_vector_service.search_reviews(
            query=search_request.query,
            url_hash=search_request.url_hash,
            top_k=search_request.top_k * 3,  # Retrieve more for reranking
            rerank_top_n=search_request.top_k,
            min_rating=search_request.min_rating,
            verified_only=search_request.verified_only
        )

        # Format results
        formatted_results = []
        for r in results:
            formatted_results.append(ReviewSearchResult(
                id=str(r.get('id', '')),
                url_hash=r.get('url_hash', ''),
                review_text=r.get('review_text', '')[:500],  # Truncate for response
                review_rating=r.get('review_rating'),
                verified_purchase=r.get('verified_purchase', False),
                similarity=r.get('similarity', 0.0),
                rerank_score=r.get('rerank_score')
            ))

        logger.info(f"✅ Found {len(formatted_results)} matching reviews")

        return ReviewSearchResponse(
            query=search_request.query,
            results=formatted_results,
            total_results=len(formatted_results)
        )

    except Exception as e:
        logger.error(f"❌ Review search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=_safe_error_detail("Review search failed", e)
        )


@router.get("/reviews/{url_hash}/summary")
async def get_review_summary(
    url_hash: str,
    auth: AuthContext = Depends(get_auth_context)
):
    """Get review statistics for a product.

    Returns rating distribution, verified purchase ratio,
    and total review count.
    """
    try:
        summary = await review_vector_service.get_review_summary(url_hash)

        if not summary:
            raise HTTPException(
                status_code=404,
                detail="No reviews found for this product"
            )

        return summary

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to get review summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=_safe_error_detail("Failed to get review summary", e)
        )
