#!/usr/bin/env python3
"""Compare Claude vs Cohere (LangGraph) agents for product safety analysis.

This script runs both agents on the same product data and compares results.

Usage:
    python scripts/compare_agents.py
"""

import asyncio
import json
import logging
import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress verbose logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("cohere").setLevel(logging.WARNING)


async def run_comparison():
    """Run both agents on the same product and compare results."""

    from infrastructure.config import settings
    from infrastructure.token_tracker import TokenTracker
    from infrastructure.search_tool_service import SearchToolService
    from infrastructure.database import db

    print("=" * 70)
    print("🧪 AGENT COMPARISON TEST (Feature Parity)")
    print("=" * 70)
    print(f"Cohere API Key: {'✅ Set' if settings.cohere_api_key else '❌ Not set'}")
    print(f"Anthropic API Key: {'✅ Set' if settings.anthropic_api_key else '❌ Not set'}")
    print(f"Supabase: {'✅ Connected' if db.is_available else '❌ Not available'}")
    print("=" * 70)

    # Product data - PatchRx Pimple Patches
    product_url = "https://www.amazon.ca/dp/B0BNW7WNLL"
    product_data = {
        "product_name": "PatchRx Pimple Patches with Salicylic Acid (120 Pack)",
        "brand": "PatchRx",
        "ingredients": [
            "Salicylic Acid",
            "Tea Tree Oil (Melaleuca Alternifolia)",
            "Hydrocolloid"
        ],
        "materials": [],
        "features": ["Propylene Glycol Free", "Paraben Free", "Cruelty Free"],
        "warnings": [],
        "description": "Pimple patches with salicylic acid and tea tree oil",
        "confidence": 0.8,
    }

    # Load knowledge bases
    allergen_db = []
    pfas_db = []
    if db.is_available:
        print("\n📚 Loading knowledge bases...")
        allergen_db = await db.get_all_allergens()
        pfas_db = await db.get_all_pfas()
        print(f"   Allergens: {len(allergen_db)}")
        print(f"   PFAS: {len(pfas_db)}")

    results = {}

    # =========================================================================
    # RUN COHERE (LANGGRAPH) AGENT
    # =========================================================================
    print("\n" + "=" * 70)
    print("🔵 RUNNING COHERE (LANGGRAPH) AGENT")
    print("=" * 70)

    cohere_tracker = TokenTracker()
    cohere_tracker.start_analysis("cohere")

    search_service_cohere = SearchToolService() if settings.tavily_api_key else None
    supabase_client = db.client if db.is_available else None

    try:
        from infrastructure.langgraph_agent import LangGraphSafetyAgent, set_tool_context, LangGraphToolContext

        set_tool_context(LangGraphToolContext(
            search_service=search_service_cohere,
            supabase_client=supabase_client,
            token_tracker=cohere_tracker,
        ))

        cohere_agent = LangGraphSafetyAgent(
            token_tracker=cohere_tracker,
            search_service=search_service_cohere,
            supabase_client=supabase_client,
        )

        start_time = time.time()
        cohere_result = await cohere_agent.analyze_extracted_product(
            product_data=product_data,
            product_url=product_url,
            allergen_database=allergen_db,
            pfas_database=pfas_db,
        )
        cohere_time = time.time() - start_time

        await cohere_agent.close()
        cohere_summary = cohere_tracker.finish_analysis()

        results["cohere"] = {
            "time_seconds": cohere_time,
            "result": cohere_result,
            "token_usage": cohere_summary,
        }
        print(f"✅ Cohere completed in {cohere_time:.1f}s")

    except Exception as e:
        print(f"❌ Cohere failed: {e}")
        import traceback
        traceback.print_exc()
        results["cohere"] = {"error": str(e)}

    if search_service_cohere:
        await search_service_cohere.close()

    # =========================================================================
    # RUN CLAUDE AGENT
    # =========================================================================
    print("\n" + "=" * 70)
    print("🟣 RUNNING CLAUDE AGENT")
    print("=" * 70)

    claude_tracker = TokenTracker()
    claude_tracker.start_analysis("claude")

    search_service_claude = SearchToolService() if settings.tavily_api_key else None

    try:
        from infrastructure.claude_agent import ProductSafetyAgent

        claude_agent = ProductSafetyAgent(
            token_tracker=claude_tracker,
            search_service=search_service_claude,
            supabase_client=supabase_client,
        )

        start_time = time.time()
        claude_result = await claude_agent.analyze_extracted_product(
            product_data=product_data,
            product_url=product_url,
            allergen_database=allergen_db,
            pfas_database=pfas_db,
        )
        claude_time = time.time() - start_time

        await claude_agent.close()
        claude_summary = claude_tracker.finish_analysis()

        results["claude"] = {
            "time_seconds": claude_time,
            "result": claude_result,
            "token_usage": claude_summary,
        }
        print(f"✅ Claude completed in {claude_time:.1f}s")

    except Exception as e:
        print(f"❌ Claude failed: {e}")
        import traceback
        traceback.print_exc()
        results["claude"] = {"error": str(e)}

    if search_service_claude:
        await search_service_claude.close()

    # =========================================================================
    # COMPARISON
    # =========================================================================
    print("\n" + "=" * 70)
    print("📊 COMPARISON RESULTS")
    print("=" * 70)

    # Extract metrics
    cohere_data = results.get("cohere", {})
    claude_data = results.get("claude", {})

    cohere_result = cohere_data.get("result", {})
    claude_result = claude_data.get("result", {})

    print("\n| Metric | Claude | Cohere |")
    print("|--------|--------|--------|")
    print(f"| Time | {claude_data.get('time_seconds', 0):.1f}s | {cohere_data.get('time_seconds', 0):.1f}s |")
    print(f"| Confidence | {claude_result.get('confidence', 0):.0%} | {cohere_result.get('confidence', 0):.0%} |")
    print(f"| Concerns Found | {len(claude_result.get('other_concerns', []))} | {len(cohere_result.get('other_concerns', []))} |")
    print(f"| Research Sources | {len(claude_result.get('research_sources', []))} | {len(cohere_result.get('research_sources', []))} |")
    print(f"| Allergens | {len(claude_result.get('allergens_detected', []))} | {len(cohere_result.get('allergens_detected', []))} |")
    print(f"| PFAS | {len(claude_result.get('pfas_detected', []))} | {len(cohere_result.get('pfas_detected', []))} |")

    # Show concerns found by each
    print("\n" + "-" * 70)
    print("CLAUDE CONCERNS:")
    for c in claude_result.get('other_concerns', []):
        print(f"  • {c.get('name')}: {c.get('severity')} - {c.get('category')}")

    print("\nCOHERE CONCERNS:")
    for c in cohere_result.get('other_concerns', []):
        print(f"  • {c.get('name')}: {c.get('severity')} - {c.get('category')}")

    # Show research sources
    print("\n" + "-" * 70)
    print(f"CLAUDE SOURCES ({len(claude_result.get('research_sources', []))}):")
    for s in claude_result.get('research_sources', [])[:5]:
        print(f"  • [{s.get('type')}] {s.get('finding', '')[:60]}...")

    print(f"\nCOHERE SOURCES ({len(cohere_result.get('research_sources', []))}):")
    for s in cohere_result.get('research_sources', [])[:5]:
        print(f"  • [{s.get('type')}] {s.get('finding', '')[:60]}...")

    # Save full results
    results["product_tested"] = product_data
    results["product_url"] = product_url

    output_file = "/tmp/agent_comparison_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n📁 Full results saved to: {output_file}")

    return results


if __name__ == "__main__":
    asyncio.run(run_comparison())
