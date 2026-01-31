#!/usr/bin/env python3
"""Batch research all ingredients in the database.

This script runs comprehensive searches on all known ingredients
(allergens, PFAS compounds, toxic substances) and stores the findings
in the ingredient_research table.

Usage:
    python scripts/batch_research_ingredients.py [--dry-run] [--limit N]

Options:
    --dry-run   Show what would be researched without making API calls
    --limit N   Only research the first N ingredients (for testing)
    --single NAME  Research a single ingredient by name
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import create_client
from src.infrastructure.config import settings
from src.infrastructure.ingredient_research_service import (
    IngredientResearchService,
    IngredientSearchConfig,
    generate_search_queries,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("ingredient_research.log"),
    ],
)
logger = logging.getLogger(__name__)


async def dry_run(supabase_client):
    """Show what would be researched without making API calls."""
    print("\n" + "=" * 70)
    print("DRY RUN - No API calls will be made")
    print("=" * 70)

    # Fetch counts
    allergens = supabase_client.table("allergens").select("name, synonyms").execute()
    pfas = supabase_client.table("pfas_compounds").select("name, synonyms, cas_number").execute()
    toxics = supabase_client.table("toxic_substances").select("name, synonyms, cas_number").execute()

    print(f"\nIngredients to research:")
    print(f"  - Allergens: {len(allergens.data)}")
    print(f"  - PFAS compounds: {len(pfas.data)}")
    print(f"  - Toxic substances: {len(toxics.data)}")
    print(f"  - TOTAL: {len(allergens.data) + len(pfas.data) + len(toxics.data)}")

    # Show sample queries for first ingredient of each type
    print("\n" + "-" * 70)
    print("Sample queries that would be generated:")
    print("-" * 70)

    samples = [
        ("allergens", allergens.data[0] if allergens.data else None),
        ("pfas_compounds", pfas.data[0] if pfas.data else None),
        ("toxic_substances", toxics.data[0] if toxics.data else None),
    ]

    for table, sample in samples:
        if not sample:
            continue

        print(f"\n{table.upper()}: {sample['name']}")
        print(f"  Synonyms: {sample.get('synonyms', [])[:3]}")

        for search_type in ["scientific", "regulatory", "legal"]:
            queries = generate_search_queries(
                ingredient_name=sample["name"],
                synonyms=sample.get("synonyms", []),
                cas_number=sample.get("cas_number"),
                search_type=search_type,
            )
            print(f"\n  {search_type.upper()} queries ({len(queries)}):")
            for q in queries[:3]:
                print(f"    - {q}")
            if len(queries) > 3:
                print(f"    ... and {len(queries) - 3} more")

    # Estimate costs
    total_ingredients = len(allergens.data) + len(pfas.data) + len(toxics.data)
    queries_per_ingredient = 8 + 7 + 5  # scientific + regulatory + legal
    total_queries = total_ingredients * queries_per_ingredient
    extractions = total_ingredients * 5  # 5 extractions per ingredient

    print("\n" + "-" * 70)
    print("Cost estimate:")
    print("-" * 70)
    print(f"  Total ingredients: {total_ingredients}")
    print(f"  Queries per ingredient: ~{queries_per_ingredient}")
    print(f"  Total searches: ~{total_queries}")
    print(f"  Total extractions: ~{extractions}")
    print(f"  Search cost: ${total_queries * 0.008:.2f}")
    print(f"  Extraction cost: ${extractions * 0.002:.2f}")
    print(f"  TOTAL ESTIMATED COST: ${total_queries * 0.008 + extractions * 0.002:.2f}")
    print()


async def research_single(supabase_client, ingredient_name: str):
    """Research a single ingredient by name."""
    print(f"\nResearching: {ingredient_name}")
    print("=" * 70)

    # Find the ingredient in the database
    ingredient = None
    source_table = None

    for table in ["allergens", "pfas_compounds", "toxic_substances"]:
        response = supabase_client.table(table).select("*").ilike("name", f"%{ingredient_name}%").execute()
        if response.data:
            ingredient = response.data[0]
            source_table = table
            break

    if not ingredient:
        print(f"ERROR: Ingredient '{ingredient_name}' not found in database")
        print("Searching in all tables: allergens, pfas_compounds, toxic_substances")
        return

    print(f"Found in: {source_table}")
    print(f"Full name: {ingredient['name']}")
    print(f"Synonyms: {ingredient.get('synonyms', [])}")
    print(f"CAS number: {ingredient.get('cas_number', 'N/A')}")

    # Research it
    service = IngredientResearchService(
        supabase_client=supabase_client,
        config=IngredientSearchConfig(
            max_results=20,
            extract_top_n=5,
        ),
    )

    try:
        research = await service.research_ingredient(
            ingredient_name=ingredient["name"],
            source_table=source_table,
            source_id=ingredient["id"],
            cas_number=ingredient.get("cas_number"),
            synonyms=ingredient.get("synonyms", []),
        )

        print("\n" + "-" * 70)
        print("RESULTS")
        print("-" * 70)

        print(f"\nIARC Classification: {research.get('iarc_classification', 'Not found')}")
        print(f"EWG Score: {research.get('ewg_score', 'Not found')}")
        print(f"Confidence: {research.get('confidence_score', 0):.0%}")
        print(f"Total sources: {research.get('total_sources', 0)}")

        health_effects = research.get("health_effects", [])
        if health_effects:
            print(f"\nHealth Effects ({len(health_effects)}):")
            for effect in health_effects:
                print(f"  - {effect['effect']} ({effect['severity']})")

        regulatory = research.get("regulatory_actions", [])
        if regulatory:
            print(f"\nRegulatory Actions ({len(regulatory)}):")
            for action in regulatory[:5]:
                print(f"  - {action['agency']}: {action['action_type']}")

        lawsuits = research.get("lawsuits", [])
        if lawsuits:
            print(f"\nLawsuits ({len(lawsuits)}):")
            for lawsuit in lawsuits[:3]:
                print(f"  - {lawsuit['title'][:60]}...")

        scientific = research.get("scientific_sources", [])
        print(f"\nScientific Sources ({len(scientific)}):")
        for source in scientific[:5]:
            print(f"  - {source['title'][:60]}...")
            print(f"    {source['url']}")

        # Ask to save
        save = input("\nSave to database? (y/n): ").lower().strip()
        if save == "y":
            await service._store_research(research)
            print("Saved!")

    finally:
        await service.close()


async def research_all(supabase_client, limit: int = None):
    """Research all ingredients."""
    service = IngredientResearchService(
        supabase_client=supabase_client,
        config=IngredientSearchConfig(
            max_results=20,
            extract_top_n=5,
        ),
    )

    try:
        # If limit specified, we need to manually limit
        if limit:
            print(f"\nResearching first {limit} ingredients only")

            # Fetch limited ingredients
            all_ingredients = []

            response = supabase_client.table("allergens").select("id, name, synonyms, cas_number").limit(limit).execute()
            for row in response.data:
                if len(all_ingredients) >= limit:
                    break
                all_ingredients.append({
                    "source_table": "allergens",
                    "source_id": row["id"],
                    "name": row["name"],
                    "synonyms": row.get("synonyms") or [],
                    "cas_number": row.get("cas_number"),
                })

            if len(all_ingredients) < limit:
                response = supabase_client.table("pfas_compounds").select("id, name, synonyms, cas_number").limit(limit - len(all_ingredients)).execute()
                for row in response.data:
                    if len(all_ingredients) >= limit:
                        break
                    all_ingredients.append({
                        "source_table": "pfas_compounds",
                        "source_id": row["id"],
                        "name": row["name"],
                        "synonyms": row.get("synonyms") or [],
                        "cas_number": row.get("cas_number"),
                    })

            if len(all_ingredients) < limit:
                response = supabase_client.table("toxic_substances").select("id, name, synonyms, cas_number").limit(limit - len(all_ingredients)).execute()
                for row in response.data:
                    if len(all_ingredients) >= limit:
                        break
                    all_ingredients.append({
                        "source_table": "toxic_substances",
                        "source_id": row["id"],
                        "name": row["name"],
                        "synonyms": row.get("synonyms") or [],
                        "cas_number": row.get("cas_number"),
                    })

            print(f"Processing {len(all_ingredients)} ingredients...")

            results = []
            for ing in all_ingredients:
                try:
                    research = await service.research_ingredient(
                        ingredient_name=ing["name"],
                        source_table=ing["source_table"],
                        source_id=ing["source_id"],
                        cas_number=ing["cas_number"],
                        synonyms=ing["synonyms"],
                    )
                    await service._store_research(research)
                    results.append({"name": ing["name"], "status": "success"})
                except Exception as e:
                    logger.error(f"Failed: {ing['name']}: {e}")
                    results.append({"name": ing["name"], "status": "error", "error": str(e)})

            summary = {
                "total_ingredients": len(all_ingredients),
                "successful": sum(1 for r in results if r["status"] == "success"),
                "failed": sum(1 for r in results if r["status"] == "error"),
                "total_searches": service._total_searches,
                "total_extractions": service._total_extractions,
                "estimated_cost": service._total_searches * 0.008 + service._total_extractions * 0.002,
            }
        else:
            summary = await service.research_all_ingredients(
                batch_size=10,
                delay_between_batches=2.0,
            )

        print("\n" + "=" * 70)
        print("RESEARCH COMPLETE")
        print("=" * 70)
        print(f"Total ingredients: {summary['total_ingredients']}")
        print(f"Successful: {summary['successful']}")
        print(f"Failed: {summary['failed']}")
        print(f"Total searches: {summary['total_searches']}")
        print(f"Total extractions: {summary['total_extractions']}")
        print(f"Estimated cost: ${summary['estimated_cost']:.2f}")

        if summary.get("errors"):
            print(f"\nErrors ({len(summary['errors'])}):")
            for err in summary["errors"][:10]:
                print(f"  - {err['ingredient']}: {err['error'][:50]}")

    finally:
        await service.close()


async def main():
    parser = argparse.ArgumentParser(description="Batch research ingredients")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--limit", type=int, help="Limit number of ingredients")
    parser.add_argument("--single", type=str, help="Research single ingredient by name")
    args = parser.parse_args()

    # Initialize Supabase client
    supabase = create_client(settings.supabase_url, settings.supabase_key)

    if args.dry_run:
        await dry_run(supabase)
    elif args.single:
        await research_single(supabase, args.single)
    else:
        # Confirm before running full batch
        if not args.limit:
            print("\n⚠️  WARNING: This will research ALL ingredients in the database.")
            print("Estimated cost: $25-50 depending on result counts.")
            confirm = input("Continue? (yes/no): ").lower().strip()
            if confirm != "yes":
                print("Aborted.")
                return

        await research_all(supabase, args.limit)


if __name__ == "__main__":
    asyncio.run(main())
