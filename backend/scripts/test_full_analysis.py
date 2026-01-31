#!/usr/bin/env python3
"""Full end-to-end test of product analysis with LangGraph or Claude fallback.

This script:
1. Scrapes the product page (using client HTML simulation)
2. Extracts product data with Claude Query
3. Analyzes with LangGraph (if Cohere key available) or Claude (fallback)

Usage:
    python scripts/test_full_analysis.py "https://amazon.ca/product/..."
"""

import asyncio
import json
import logging
import sys
import os

# Change to backend directory and add src to path properly
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(backend_dir)
sys.path.insert(0, os.path.join(backend_dir, 'src'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress verbose logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def fetch_product_html(url: str) -> str:
    """Fetch product page HTML using httpx."""
    import httpx

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url, headers=headers)
        return response.text


async def test_full_analysis(product_url: str, use_langgraph: bool = None):
    """Run full product analysis pipeline."""

    from infrastructure.config import settings
    from infrastructure.token_tracker import TokenTracker
    from infrastructure.search_tool_service import SearchToolService
    from infrastructure.database import db
    from infrastructure.product_scraper import ProductScraperService
    from infrastructure.claude_query import ClaudeQueryService

    print("=" * 70)
    print("🧪 FULL PRODUCT ANALYSIS TEST")
    print("=" * 70)
    print(f"Product URL: {product_url}")
    print(f"Cohere API Key: {'✅ Set' if settings.cohere_api_key else '❌ Not set'}")
    print(f"LangGraph Mode: {use_langgraph if use_langgraph is not None else 'Auto'}")
    print("=" * 70)

    # Determine which agent to use
    if use_langgraph is None:
        use_langgraph = bool(settings.cohere_api_key)

    # Initialize services
    token_tracker = TokenTracker()
    token_tracker.start_analysis("test-full-analysis")

    search_service = None
    if settings.tavily_api_key:
        search_service = SearchToolService()
        print("✅ Search service initialized (Tavily)")

    supabase_client = db.client if db.is_available else None

    # Load knowledge bases
    allergen_db = []
    pfas_db = []
    if db.is_available:
        print("\n📚 Loading knowledge bases...")
        allergen_db = await db.get_all_allergens()
        pfas_db = await db.get_all_pfas()
        print(f"   Loaded {len(allergen_db)} allergens, {len(pfas_db)} PFAS compounds")

    # Step 1: Scrape product page
    print("\n" + "-" * 70)
    print("STEP 1: Scraping product page")
    print("-" * 70)

    scraper = ProductScraperService()
    scraped = await scraper.try_scrape(product_url)

    if scraped and scraped.confidence > 0.3:
        print(f"✅ Scraped successfully (confidence: {scraped.confidence:.0%})")
        print(f"   HTML size: {len(scraped.raw_html_product) / 1024:.1f} KB")
    else:
        print("⚠️  Scraping failed or low confidence, using fallback")
        # Try fetching directly
        try:
            html = await fetch_product_html(product_url)
            print(f"   Fetched {len(html) / 1024:.1f} KB via httpx")

            # Process with Amazon scraper
            from infrastructure.scrapers.amazon import AmazonScraper
            amazon_scraper = AmazonScraper()
            scraped = amazon_scraper.process_client_html(
                url=product_url,
                product_html=html,
                reviews_html="",
            )
            print(f"   Processed HTML confidence: {scraped.confidence:.0%}")
        except Exception as e:
            print(f"❌ Fetch failed: {e}")
            return

    # Step 2: Extract product data with Claude Query
    print("\n" + "-" * 70)
    print("STEP 2: Extracting product data with Claude Query")
    print("-" * 70)

    query_service = ClaudeQueryService(token_tracker=token_tracker)
    product_data = await query_service.extract_product_data(scraped)

    if product_data.get("confidence", 0) < 0.3:
        print(f"❌ Extraction failed: {product_data.get('error', 'Unknown error')}")
        return

    print(f"✅ Extracted product: {product_data.get('product_name', 'Unknown')}")
    print(f"   Brand: {product_data.get('brand', 'Unknown')}")
    print(f"   Ingredients: {len(product_data.get('ingredients', []))}")
    print(f"   Materials: {len(product_data.get('materials', []))}")

    if product_data.get('ingredients'):
        print(f"   Sample ingredients: {', '.join(product_data['ingredients'][:5])}...")

    # Step 3: Run safety analysis
    print("\n" + "-" * 70)
    print(f"STEP 3: Safety Analysis ({'LangGraph' if use_langgraph else 'Claude'})")
    print("-" * 70)

    result = None

    if use_langgraph:
        try:
            from infrastructure.langgraph_agent import LangGraphSafetyAgent, set_tool_context, LangGraphToolContext

            set_tool_context(LangGraphToolContext(
                search_service=search_service,
                supabase_client=supabase_client,
                token_tracker=token_tracker,
            ))

            agent = LangGraphSafetyAgent(
                token_tracker=token_tracker,
                search_service=search_service,
                supabase_client=supabase_client,
            )

            result = await agent.analyze_extracted_product(
                product_data=product_data,
                product_url=product_url,
                allergen_database=allergen_db,
                pfas_database=pfas_db,
            )

            await agent.close()
            print("✅ LangGraph analysis complete")

        except Exception as e:
            print(f"❌ LangGraph failed: {e}")
            print("🔄 Falling back to Claude...")
            use_langgraph = False

    if not use_langgraph or result is None:
        from infrastructure.claude_agent import ProductSafetyAgent

        agent = ProductSafetyAgent(
            token_tracker=token_tracker,
            search_service=search_service,
            supabase_client=supabase_client,
        )

        result = await agent.analyze_extracted_product(
            product_data=product_data,
            product_url=product_url,
            allergen_database=allergen_db,
            pfas_database=pfas_db,
        )

        await agent.close()
        print("✅ Claude analysis complete")

    # Step 4: Display results
    print("\n" + "=" * 70)
    print("📊 ANALYSIS RESULTS")
    print("=" * 70)

    print(f"\nProduct: {result.get('product_name', 'Unknown')}")
    print(f"Brand: {result.get('brand', 'Unknown')}")
    print(f"Confidence: {result.get('confidence', 0):.0%}")

    allergens = result.get('allergens_detected', [])
    if allergens:
        print(f"\n🚨 Allergens Detected ({len(allergens)}):")
        for a in allergens:
            print(f"   • {a.get('name')}: {a.get('severity')} severity")
            print(f"     Source: {a.get('source', 'N/A')}")
    else:
        print("\n✅ No known allergens detected")

    pfas = result.get('pfas_detected', [])
    if pfas:
        print(f"\n⚠️  PFAS Detected ({len(pfas)}):")
        for p in pfas:
            print(f"   • {p.get('name')} ({p.get('cas_number', 'N/A')})")
    else:
        print("\n✅ No PFAS detected")

    concerns = result.get('other_concerns', [])
    if concerns:
        print(f"\n⚠️  Other Concerns ({len(concerns)}):")
        for c in concerns:
            print(f"   • {c.get('name')}: {c.get('severity')} ({c.get('category')})")
            if c.get('description'):
                print(f"     {c.get('description')[:100]}...")
    else:
        print("\n✅ No other concerns")

    # Research sources
    sources = result.get('research_sources', [])
    if sources:
        print(f"\n📚 Research Sources ({len(sources)}):")
        for s in sources[:5]:
            print(f"   • [{s.get('type')}] {s.get('finding', '')[:60]}...")

    # Token usage summary
    print("\n" + "=" * 70)
    print("💰 TOKEN USAGE")
    print("=" * 70)
    summary = token_tracker.finish_analysis()

    # Cleanup
    if search_service:
        await search_service.close()

    # Return result for further processing
    return result


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.amazon.ca/gp/product/B0BN2PX8V3/"

    # Parse optional --langgraph or --claude flag
    use_langgraph = None
    if "--langgraph" in sys.argv:
        use_langgraph = True
    elif "--claude" in sys.argv:
        use_langgraph = False

    asyncio.run(test_full_analysis(url, use_langgraph))
