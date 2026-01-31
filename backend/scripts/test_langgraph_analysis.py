#!/usr/bin/env python3
"""Test script for LangGraph safety agent.

Usage:
    python scripts/test_langgraph_analysis.py [product_url]
"""

import asyncio
import json
import logging
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress verbose logs from libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("cohere").setLevel(logging.WARNING)


async def test_langgraph_analysis(product_url: str):
    """Run a test analysis using the LangGraph agent."""

    # Import after setting up path
    from infrastructure.config import settings
    from infrastructure.token_tracker import TokenTracker
    from infrastructure.search_tool_service import SearchToolService
    from infrastructure.database import db

    print("=" * 70)
    print("🧪 LANGGRAPH AGENT TEST")
    print("=" * 70)
    print(f"Product URL: {product_url}")
    print(f"Cohere API Key: {'✅ Set' if settings.cohere_api_key else '❌ Not set'}")
    print(f"Anthropic API Key: {'✅ Set' if settings.anthropic_api_key else '❌ Not set'}")
    print(f"Tavily API Key: {'✅ Set' if settings.tavily_api_key else '❌ Not set'}")
    print(f"Supabase: {'✅ Connected' if db.is_available else '❌ Not available'}")
    print("=" * 70)

    if not settings.cohere_api_key:
        print("❌ COHERE_API_KEY not set in .env - cannot run LangGraph agent")
        print("   Add: COHERE_API_KEY=your-key to .env")
        return

    # Initialize services
    token_tracker = TokenTracker()
    token_tracker.start_analysis("test-analysis")

    search_service = None
    if settings.tavily_api_key:
        search_service = SearchToolService()

    supabase_client = db.client if db.is_available else None

    # Load knowledge bases
    allergen_db = []
    pfas_db = []
    if db.is_available:
        print("\n📚 Loading knowledge bases...")
        allergen_db = await db.get_all_allergens()
        pfas_db = await db.get_all_pfas()
        print(f"   Allergens: {len(allergen_db)}")
        print(f"   PFAS: {len(pfas_db)}")

    # Create mock product data for testing
    # In production, this would come from the scraper + Claude Query
    product_data = {
        "product_name": "Test Product from Amazon",
        "brand": "Unknown",
        "ingredients": [
            "Water", "Glycerin", "Isopropyl Alcohol", "Fragrance",
            "Phenoxyethanol", "Sodium Lauryl Sulfate"
        ],
        "materials": [],
        "features": ["Moisturizing", "Fast-absorbing"],
        "warnings": ["For external use only"],
        "description": "A test product for analysis",
    }

    print("\n🔬 Product Data:")
    print(f"   Name: {product_data['product_name']}")
    print(f"   Ingredients: {', '.join(product_data['ingredients'][:5])}...")

    # Test LangGraph agent
    print("\n" + "=" * 70)
    print("🚀 RUNNING LANGGRAPH ANALYSIS")
    print("=" * 70)

    try:
        from infrastructure.langgraph_agent import LangGraphSafetyAgent, set_tool_context, LangGraphToolContext

        # Set tool context for the agent
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

        print("\n" + "=" * 70)
        print("✅ ANALYSIS RESULT")
        print("=" * 70)
        print(json.dumps(result, indent=2, default=str))

        # Summary
        print("\n" + "=" * 70)
        print("📊 SUMMARY")
        print("=" * 70)
        print(f"Product: {result.get('product_name', 'Unknown')}")
        print(f"Brand: {result.get('brand', 'Unknown')}")
        print(f"Allergens Detected: {len(result.get('allergens_detected', []))}")
        for a in result.get('allergens_detected', []):
            print(f"   - {a.get('name')}: {a.get('severity')} ({a.get('confidence', 0):.0%})")
        print(f"PFAS Detected: {len(result.get('pfas_detected', []))}")
        for p in result.get('pfas_detected', []):
            print(f"   - {p.get('name')}")
        print(f"Other Concerns: {len(result.get('other_concerns', []))}")
        for c in result.get('other_concerns', []):
            print(f"   - {c.get('name')}: {c.get('category')} - {c.get('severity')}")
        print(f"Confidence: {result.get('confidence', 0):.0%}")

        # Token usage
        summary = token_tracker.finish_analysis()

        await agent.close()

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

        # Try fallback to Claude
        print("\n" + "=" * 70)
        print("🔄 FALLING BACK TO CLAUDE AGENT")
        print("=" * 70)

        try:
            from infrastructure.claude_agent import ProductSafetyAgent

            claude_agent = ProductSafetyAgent(
                token_tracker=token_tracker,
                search_service=search_service,
                supabase_client=supabase_client,
            )

            result = await claude_agent.analyze_extracted_product(
                product_data=product_data,
                product_url=product_url,
                allergen_database=allergen_db,
                pfas_database=pfas_db,
            )

            print("\n✅ CLAUDE FALLBACK RESULT:")
            print(json.dumps(result, indent=2, default=str))

            await claude_agent.close()

        except Exception as e2:
            print(f"❌ Claude fallback also failed: {e2}")

    if search_service:
        await search_service.close()


if __name__ == "__main__":
    # Default URL or use provided one
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.amazon.ca/gp/product/B0BN2PX8V3/"

    asyncio.run(test_langgraph_analysis(url))
