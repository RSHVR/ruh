#!/usr/bin/env python3
"""Compare Claude vs Cohere (LangGraph) vs Cohere (Native SDK) agents.

This script tests whether Cohere's non-determinism is caused by LangGraph wrapper
by running the native SDK version alongside the LangGraph version.

Usage:
    python scripts/compare_all_agents.py
"""

import asyncio
import json
import logging
import sys
import os
import time
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class Timer:
    """High-precision timer for measuring agent execution."""

    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.start_wall = None
        self.end_wall = None

    def start(self):
        self.start_time = time.perf_counter()
        self.start_wall = datetime.now()
        print(f"⏱️  [{self.name}] Started at {self.start_wall.strftime('%H:%M:%S.%f')[:-3]}")

    def stop(self):
        self.end_time = time.perf_counter()
        self.end_wall = datetime.now()
        elapsed = self.end_time - self.start_time
        print(f"⏱️  [{self.name}] Finished at {self.end_wall.strftime('%H:%M:%S.%f')[:-3]} ({elapsed:.2f}s)")
        return elapsed

    @property
    def elapsed(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0

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
    """Run all three agents on the same product and compare results."""

    from infrastructure.config import settings
    from infrastructure.token_tracker import TokenTracker
    from infrastructure.search_tool_service import SearchToolService
    from infrastructure.database import db

    print("=" * 70)
    print("🧪 THREE-WAY AGENT COMPARISON")
    print("   Claude vs Cohere (LangGraph) vs Cohere (Native SDK)")
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
    supabase_client = db.client if db.is_available else None

    # =========================================================================
    # RUN COHERE (LANGGRAPH) AGENT
    # =========================================================================
    print("\n" + "=" * 70)
    print("🔵 RUNNING COHERE (LANGGRAPH) AGENT")
    print("=" * 70)

    cohere_lg_tracker = TokenTracker()
    cohere_lg_tracker.start_analysis("cohere_langgraph")
    search_service_cohere_lg = SearchToolService() if settings.tavily_api_key else None

    try:
        from infrastructure.langgraph_agent import LangGraphSafetyAgent, set_tool_context, LangGraphToolContext

        set_tool_context(LangGraphToolContext(
            search_service=search_service_cohere_lg,
            supabase_client=supabase_client,
            token_tracker=cohere_lg_tracker,
        ))

        cohere_lg_agent = LangGraphSafetyAgent(
            token_tracker=cohere_lg_tracker,
            search_service=search_service_cohere_lg,
            supabase_client=supabase_client,
        )

        timer = Timer("Cohere LangGraph")
        timer.start()
        cohere_lg_result = await cohere_lg_agent.analyze_extracted_product(
            product_data=product_data,
            product_url=product_url,
            allergen_database=allergen_db,
            pfas_database=pfas_db,
        )
        cohere_lg_time = timer.stop()

        await cohere_lg_agent.close()
        cohere_lg_summary = cohere_lg_tracker.finish_analysis()

        results["cohere_langgraph"] = {
            "time_seconds": cohere_lg_time,
            "result": cohere_lg_result,
            "token_usage": cohere_lg_summary,
        }
        print(f"✅ Cohere (LangGraph) completed in {cohere_lg_time:.2f}s")

    except Exception as e:
        print(f"❌ Cohere (LangGraph) failed: {e}")
        import traceback
        traceback.print_exc()
        results["cohere_langgraph"] = {"error": str(e)}

    if search_service_cohere_lg:
        await search_service_cohere_lg.close()

    # =========================================================================
    # RUN COHERE (NATIVE SDK) AGENT
    # =========================================================================
    print("\n" + "=" * 70)
    print("🟢 RUNNING COHERE (NATIVE SDK) AGENT")
    print("=" * 70)

    search_service_cohere_native = SearchToolService() if settings.tavily_api_key else None

    try:
        from infrastructure.cohere_native_agent import NativeCohereSafetyAgent

        cohere_native_agent = NativeCohereSafetyAgent(
            search_service=search_service_cohere_native,
            supabase_client=supabase_client,
        )

        timer = Timer("Cohere Native")
        timer.start()
        cohere_native_result = await cohere_native_agent.analyze_product(
            product_name=product_data["product_name"],
            brand=product_data["brand"],
            ingredients=product_data["ingredients"],
            product_url=product_url,
            allergen_database=allergen_db,
            pfas_database=pfas_db,
        )
        cohere_native_time = timer.stop()

        await cohere_native_agent.close()

        results["cohere_native"] = {
            "time_seconds": cohere_native_time,
            "result": cohere_native_result,
        }
        print(f"✅ Cohere (Native) completed in {cohere_native_time:.2f}s")

    except Exception as e:
        print(f"❌ Cohere (Native) failed: {e}")
        import traceback
        traceback.print_exc()
        results["cohere_native"] = {"error": str(e)}

    if search_service_cohere_native:
        await search_service_cohere_native.close()

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

        timer = Timer("Claude")
        timer.start()
        claude_result = await claude_agent.analyze_extracted_product(
            product_data=product_data,
            product_url=product_url,
            allergen_database=allergen_db,
            pfas_database=pfas_db,
        )
        claude_time = timer.stop()

        await claude_agent.close()
        claude_summary = claude_tracker.finish_analysis()

        results["claude"] = {
            "time_seconds": claude_time,
            "result": claude_result,
            "token_usage": claude_summary,
        }
        print(f"✅ Claude completed in {claude_time:.2f}s")

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
    print("📊 THREE-WAY COMPARISON RESULTS")
    print("=" * 70)

    # Extract metrics
    cohere_lg_data = results.get("cohere_langgraph", {})
    cohere_native_data = results.get("cohere_native", {})
    claude_data = results.get("claude", {})

    cohere_lg_result = cohere_lg_data.get("result", {})
    cohere_native_result = cohere_native_data.get("result", {})
    claude_result = claude_data.get("result", {})

    print(f"\n📅 Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n| Metric | Claude | Cohere (LangGraph) | Cohere (Native) |")
    print("|--------|--------|-------------------|-----------------|")
    print(f"| Time | {claude_data.get('time_seconds', 0):.2f}s | {cohere_lg_data.get('time_seconds', 0):.2f}s | {cohere_native_data.get('time_seconds', 0):.2f}s |")
    print(f"| Confidence | {claude_result.get('confidence', 0):.0%} | {cohere_lg_result.get('confidence', 0):.0%} | {cohere_native_result.get('confidence', 0):.0%} |")
    print(f"| Concerns Found | {len(claude_result.get('other_concerns', []))} | {len(cohere_lg_result.get('other_concerns', []))} | {len(cohere_native_result.get('other_concerns', []))} |")
    print(f"| Research Sources | {len(claude_result.get('research_sources', []))} | {len(cohere_lg_result.get('research_sources', []))} | {len(cohere_native_result.get('research_sources', []))} |")

    # Speed comparison
    print("\n" + "-" * 70)
    print("SPEED ANALYSIS:")
    claude_t = claude_data.get('time_seconds', 0)
    lg_t = cohere_lg_data.get('time_seconds', 0)
    native_t = cohere_native_data.get('time_seconds', 0)
    if claude_t > 0:
        print(f"  Claude baseline: {claude_t:.2f}s")
        if lg_t > 0:
            print(f"  LangGraph vs Claude: {lg_t/claude_t:.2f}x {'slower' if lg_t > claude_t else 'faster'}")
        if native_t > 0:
            print(f"  Native vs Claude: {native_t/claude_t:.2f}x {'slower' if native_t > claude_t else 'faster'}")
        if lg_t > 0 and native_t > 0:
            print(f"  LangGraph vs Native: {lg_t/native_t:.2f}x {'slower' if lg_t > native_t else 'faster'}")

    # Show concerns found by each
    print("\n" + "-" * 70)
    print("CLAUDE CONCERNS:")
    for c in claude_result.get('other_concerns', []):
        print(f"  • {c.get('name')}: {c.get('severity')} - {c.get('category')}")

    print("\nCOHERE (LANGGRAPH) CONCERNS:")
    for c in cohere_lg_result.get('other_concerns', []):
        print(f"  • {c.get('name')}: {c.get('severity')} - {c.get('category')}")

    print("\nCOHERE (NATIVE) CONCERNS:")
    for c in cohere_native_result.get('other_concerns', []):
        print(f"  • {c.get('name')}: {c.get('severity')} - {c.get('category')}")

    # Check tool usage from metadata
    print("\n" + "-" * 70)
    print("TOOL USAGE:")
    native_meta = cohere_native_result.get('_metadata', {})
    if native_meta:
        print(f"  Cohere (Native): {native_meta.get('tool_calls', 'N/A')} tool calls")

    # Save full results
    results["product_tested"] = product_data
    results["product_url"] = product_url

    output_file = "/tmp/three_way_comparison.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n📁 Full results saved to: {output_file}")

    # Key finding
    print("\n" + "=" * 70)
    print("🔍 KEY FINDING: LangGraph vs Native Comparison")
    print("=" * 70)

    lg_concerns = len(cohere_lg_result.get('other_concerns', []))
    native_concerns = len(cohere_native_result.get('other_concerns', []))

    if lg_concerns == native_concerns:
        print(f"✅ Both Cohere agents found {lg_concerns} concerns")
        print("   LangGraph wrapper does NOT appear to affect behavior")
    else:
        print(f"⚠️  LangGraph found {lg_concerns} concerns, Native found {native_concerns}")
        print("   This suggests LangGraph wrapper MAY affect model behavior")

    return results


if __name__ == "__main__":
    asyncio.run(run_comparison())
