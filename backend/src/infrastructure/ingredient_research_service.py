"""Batch ingredient research service for pre-computing safety data.

Runs comprehensive searches on all known ingredients and stores findings
in the ingredient_research table for instant lookup during product analysis.
"""

import asyncio
import logging
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .search_clients.tavily import TavilySearchClient, DOMAIN_FILTERS
from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class IngredientSearchConfig:
    """Configuration for ingredient research searches."""

    # Higher limits for comprehensive pre-computation
    max_results: int = 20
    extract_top_n: int = 5
    extract_depth: str = "advanced"
    chunks_per_source: int = 5  # Max chunks for more content

    # Search types to run per ingredient
    search_types: List[str] = field(default_factory=lambda: [
        "scientific",
        "regulatory",
        "legal",
    ])


# Optimized query templates for different research types
# Uses {name} for full ingredient name, {abbrev} for abbreviation/synonym, {cas} for CAS number
QUERY_TEMPLATES = {
    "scientific": [
        # Toxicity and health effects
        "{name} toxicity health effects human studies",
        "{name} safety assessment research",

        # Carcinogen classification
        "{abbrev} IARC classification carcinogen",
        "{name} cancer risk studies",

        # Endocrine disruption
        "{name} endocrine disruptor hormone",

        # Specific databases
        "{abbrev} PubMed toxicology",
        "{name} NIH safety data",

        # EWG rating (for cosmetic ingredients)
        "{name} EWG Skin Deep rating",
    ],

    "regulatory": [
        # FDA
        "{name} FDA warning ban restriction",
        "{abbrev} FDA safety alert recall",

        # EPA
        "{name} EPA toxic substances",
        "{abbrev} EPA health advisory",

        # Health Canada
        "{name} Health Canada prohibited restricted",

        # EU
        "{name} EU REACH SVHC",
        "{abbrev} European Commission cosmetics regulation",

        # CAS-based lookup
        "CAS {cas} regulatory status" if "{cas}" else None,
    ],

    "legal": [
        # Lawsuits
        "{name} lawsuit class action",
        "{abbrev} personal injury litigation",

        # Settlements
        "{name} settlement damages",

        # Product liability
        "{name} product liability verdict",

        # News coverage of legal issues
        "{abbrev} lawsuit settlement news",
    ],
}


def generate_search_queries(
    ingredient_name: str,
    synonyms: List[str] = None,
    cas_number: str = None,
    search_type: str = "scientific",
) -> List[str]:
    """Generate optimized search queries for an ingredient.

    Uses the full name, abbreviations/synonyms, and CAS number to create
    comprehensive queries that capture different aspects of the research.

    Args:
        ingredient_name: Full ingredient name (e.g., "Butylated Hydroxytoluene")
        synonyms: List of synonyms/abbreviations (e.g., ["BHT", "E321"])
        cas_number: CAS registry number if known
        search_type: Type of research (scientific, regulatory, legal)

    Returns:
        List of optimized search queries
    """
    synonyms = synonyms or []
    templates = QUERY_TEMPLATES.get(search_type, [])

    queries = []
    seen = set()  # Deduplicate

    # Get abbreviation (shortest synonym or first 3 letters of name)
    abbrev = min(synonyms, key=len) if synonyms else ingredient_name.split()[0][:3]

    for template in templates:
        if template is None:
            continue

        # Skip CAS queries if no CAS number
        if "{cas}" in template and not cas_number:
            continue

        # Generate query with full name
        query = template.format(
            name=ingredient_name,
            abbrev=abbrev,
            cas=cas_number or "",
        )

        if query not in seen:
            queries.append(query)
            seen.add(query)

        # Also generate with synonyms for variety
        for synonym in synonyms[:2]:  # Limit to 2 synonyms
            alt_query = template.format(
                name=synonym,
                abbrev=abbrev,
                cas=cas_number or "",
            )
            if alt_query not in seen and alt_query != query:
                queries.append(alt_query)
                seen.add(alt_query)

    return queries


class IngredientResearchService:
    """Service for batch researching ingredients and storing findings."""

    def __init__(
        self,
        supabase_client: Any,
        tavily_api_key: str = None,
        config: IngredientSearchConfig = None,
    ):
        """Initialize the research service.

        Args:
            supabase_client: Supabase client for database operations
            tavily_api_key: Tavily API key (defaults to settings)
            config: Research configuration (defaults to comprehensive settings)
        """
        self._supabase = supabase_client
        self._config = config or IngredientSearchConfig()

        tavily_key = tavily_api_key or settings.tavily_api_key
        if not tavily_key:
            raise ValueError("Tavily API key required for ingredient research")

        self._tavily = TavilySearchClient(api_key=tavily_key)

        # Track progress
        self._total_searches = 0
        self._total_extractions = 0
        self._errors: List[Dict[str, Any]] = []

    async def research_ingredient(
        self,
        ingredient_name: str,
        source_table: str,
        source_id: str = None,
        cas_number: str = None,
        synonyms: List[str] = None,
    ) -> Dict[str, Any]:
        """Research a single ingredient comprehensively.

        Runs scientific, regulatory, and legal searches, extracts content
        from top sources, and compiles findings into a structured format.

        Args:
            ingredient_name: Full ingredient name
            source_table: Source table ('allergens', 'pfas_compounds', 'toxic_substances')
            source_id: UUID of source record
            cas_number: CAS number if known
            synonyms: List of synonyms/abbreviations

        Returns:
            Dict with all research findings ready for database storage
        """
        synonyms = synonyms or []
        logger.info(f"Researching: {ingredient_name} (synonyms: {synonyms[:3]})")

        all_results = {}
        all_queries = []

        # Run searches for each type
        for search_type in self._config.search_types:
            queries = generate_search_queries(
                ingredient_name=ingredient_name,
                synonyms=synonyms,
                cas_number=cas_number,
                search_type=search_type,
            )

            logger.info(f"  {search_type}: {len(queries)} queries")

            type_results = []
            for query in queries:
                try:
                    # Search with higher limits
                    response = await self._tavily.client.search(
                        query=query,
                        search_depth="advanced",
                        max_results=self._config.max_results,
                        chunks_per_source=self._config.chunks_per_source,
                        include_answer=False,
                        include_raw_content=False,
                        timeout=30,
                    )

                    results = response.get("results", [])
                    self._total_searches += 1

                    for r in results:
                        type_results.append({
                            "query": query,
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "content": r.get("content", ""),
                            "score": r.get("score", 0.0),
                        })

                    all_queries.append({
                        "query": query,
                        "search_type": search_type,
                        "result_count": len(results),
                    })

                    # Small delay to avoid rate limits
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.warning(f"  Search failed for '{query[:50]}': {e}")
                    self._errors.append({
                        "ingredient": ingredient_name,
                        "query": query,
                        "error": str(e),
                    })

            # Deduplicate by URL
            seen_urls = set()
            unique_results = []
            for r in type_results:
                if r["url"] not in seen_urls:
                    unique_results.append(r)
                    seen_urls.add(r["url"])

            # Sort by relevance score
            unique_results.sort(key=lambda x: x.get("score", 0), reverse=True)
            all_results[search_type] = unique_results

            logger.info(f"    Found {len(unique_results)} unique sources")

        # Extract full content from top scientific sources
        scientific_sources = all_results.get("scientific", [])
        if scientific_sources:
            top_urls = [r["url"] for r in scientific_sources[:self._config.extract_top_n]]
            try:
                extract_response = await self._tavily.extract(
                    urls=top_urls,
                    extract_depth=self._config.extract_depth,
                )
                self._total_extractions += len(top_urls)

                # Merge extracted content back into results
                for extracted in extract_response.results:
                    for r in scientific_sources:
                        if r["url"] == extracted.url:
                            r["full_content"] = extracted.raw_content[:8000]  # Cap at 8K
                            break

            except Exception as e:
                logger.warning(f"  Extraction failed: {e}")

        # Parse and structure the findings
        research_data = self._structure_findings(
            ingredient_name=ingredient_name,
            source_table=source_table,
            source_id=source_id,
            cas_number=cas_number,
            synonyms=synonyms,
            all_results=all_results,
            all_queries=all_queries,
        )

        return research_data

    def _structure_findings(
        self,
        ingredient_name: str,
        source_table: str,
        source_id: str,
        cas_number: str,
        synonyms: List[str],
        all_results: Dict[str, List[Dict]],
        all_queries: List[Dict],
    ) -> Dict[str, Any]:
        """Structure raw search results into database-ready format."""

        scientific = all_results.get("scientific", [])
        regulatory = all_results.get("regulatory", [])
        legal = all_results.get("legal", [])

        # Extract IARC classification from scientific results
        iarc_class, iarc_details = self._extract_iarc_classification(scientific)

        # Extract EWG score if found
        ewg_score, ewg_details = self._extract_ewg_score(scientific)

        # Structure health effects from scientific content
        health_effects = self._extract_health_effects(scientific)

        # Structure regulatory actions
        regulatory_actions = self._extract_regulatory_actions(regulatory)

        # Structure legal findings
        lawsuits, settlements = self._extract_legal_findings(legal)

        # Calculate confidence based on source count and quality
        total_sources = len(scientific) + len(regulatory) + len(legal)
        high_quality = sum(1 for r in scientific if r.get("score", 0) > 0.7)
        confidence = min(1.0, (total_sources / 50) * 0.5 + (high_quality / 10) * 0.5)

        return {
            "ingredient_name": ingredient_name,
            "source_table": source_table,
            "source_id": source_id,
            "cas_number": cas_number,
            "synonyms": synonyms,

            # Scientific
            "iarc_classification": iarc_class,
            "iarc_details": iarc_details,
            "ewg_score": ewg_score,
            "ewg_details": ewg_details,
            "health_effects": health_effects,
            "scientific_sources": [
                {
                    "url": r["url"],
                    "title": r["title"],
                    "snippet": r["content"][:500],
                    "relevance_score": r.get("score", 0),
                }
                for r in scientific[:20]  # Top 20
            ],

            # Regulatory
            "regulatory_actions": regulatory_actions,

            # Legal
            "lawsuits": lawsuits,
            "settlements": settlements,

            # Raw data for reprocessing
            "raw_search_results": {
                "scientific": scientific[:30],
                "regulatory": regulatory[:20],
                "legal": legal[:20],
            },
            "search_queries_used": all_queries,

            # Metadata
            "total_sources": total_sources,
            "confidence_score": confidence,
            "researched_at": datetime.now(timezone.utc).isoformat(),
            "research_version": "1.0",
        }

    def _extract_iarc_classification(
        self, scientific_results: List[Dict]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extract IARC carcinogen classification from search results."""
        iarc_keywords = {
            "group 1": "Group 1 (Carcinogenic to humans)",
            "group 2a": "Group 2A (Probably carcinogenic)",
            "group 2b": "Group 2B (Possibly carcinogenic)",
            "group 3": "Group 3 (Not classifiable)",
            "group 4": "Group 4 (Probably not carcinogenic)",
        }

        for result in scientific_results:
            content = (result.get("content", "") + " " + result.get("full_content", "")).lower()

            for keyword, classification in iarc_keywords.items():
                if "iarc" in content and keyword in content:
                    # Extract surrounding context
                    idx = content.find(keyword)
                    details = content[max(0, idx-100):idx+200]
                    return classification, details.strip()

        return None, None

    def _extract_ewg_score(
        self, scientific_results: List[Dict]
    ) -> Tuple[Optional[int], Optional[str]]:
        """Extract EWG Skin Deep score from search results."""
        import re

        for result in scientific_results:
            content = result.get("content", "") + " " + result.get("full_content", "")

            # Look for EWG score patterns
            if "ewg" in content.lower() or "skin deep" in content.lower():
                # Try to find score (1-10)
                score_match = re.search(r'(?:score|rated?|rating)[:\s]*(\d+)', content.lower())
                if score_match:
                    score = int(score_match.group(1))
                    if 1 <= score <= 10:
                        return score, content[:300]

        return None, None

    def _extract_health_effects(
        self, scientific_results: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Extract health effects from scientific search results."""
        effects = []
        seen_effects = set()

        effect_keywords = {
            "carcinogen": {"effect": "Cancer risk", "severity": "high"},
            "endocrine disruptor": {"effect": "Hormone disruption", "severity": "high"},
            "reproductive toxin": {"effect": "Reproductive toxicity", "severity": "high"},
            "neurotoxin": {"effect": "Neurotoxicity", "severity": "high"},
            "allergen": {"effect": "Allergic reactions", "severity": "moderate"},
            "skin irritant": {"effect": "Skin irritation", "severity": "low"},
            "respiratory": {"effect": "Respiratory effects", "severity": "moderate"},
            "liver toxicity": {"effect": "Liver damage", "severity": "high"},
            "kidney toxicity": {"effect": "Kidney damage", "severity": "high"},
        }

        for result in scientific_results[:15]:  # Check top 15
            content = (result.get("content", "") + " " + result.get("full_content", "")).lower()

            for keyword, effect_data in effect_keywords.items():
                if keyword in content and effect_data["effect"] not in seen_effects:
                    effects.append({
                        "effect": effect_data["effect"],
                        "severity": effect_data["severity"],
                        "evidence": "Found in scientific literature",
                        "source_url": result["url"],
                    })
                    seen_effects.add(effect_data["effect"])

        return effects

    def _extract_regulatory_actions(
        self, regulatory_results: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Extract regulatory actions from search results."""
        actions = []

        action_keywords = {
            "banned": "Ban",
            "prohibited": "Prohibition",
            "restricted": "Restriction",
            "warning": "Warning",
            "recall": "Recall",
            "phase out": "Phase-out",
            "limit": "Concentration limit",
        }

        agencies = ["fda", "epa", "health canada", "eu", "echa", "reach"]

        for result in regulatory_results[:15]:
            content = (result.get("content", "") + " " + result.get("title", "")).lower()

            # Check for agency + action combinations
            for agency in agencies:
                if agency in content:
                    for keyword, action_type in action_keywords.items():
                        if keyword in content:
                            actions.append({
                                "agency": agency.upper(),
                                "action_type": action_type,
                                "details": result.get("content", "")[:300],
                                "url": result["url"],
                            })
                            break

        # Deduplicate by agency+action
        seen = set()
        unique_actions = []
        for a in actions:
            key = (a["agency"], a["action_type"])
            if key not in seen:
                unique_actions.append(a)
                seen.add(key)

        return unique_actions

    def _extract_legal_findings(
        self, legal_results: List[Dict]
    ) -> Tuple[List[Dict], List[Dict]]:
        """Extract lawsuits and settlements from search results."""
        lawsuits = []
        settlements = []

        for result in legal_results[:15]:
            content = (result.get("content", "") + " " + result.get("title", "")).lower()
            title = result.get("title", "")

            if "settlement" in content or "settled" in content:
                settlements.append({
                    "title": title,
                    "details": result.get("content", "")[:400],
                    "url": result["url"],
                })
            elif "lawsuit" in content or "litigation" in content or "class action" in content:
                lawsuits.append({
                    "title": title,
                    "details": result.get("content", "")[:400],
                    "url": result["url"],
                })

        return lawsuits[:10], settlements[:10]

    async def research_all_ingredients(
        self,
        batch_size: int = 10,
        delay_between_batches: float = 2.0,
    ) -> Dict[str, Any]:
        """Research all ingredients from all source tables.

        Args:
            batch_size: Number of ingredients to process before pausing
            delay_between_batches: Seconds to wait between batches

        Returns:
            Summary of research results
        """
        # Fetch all ingredients from all tables
        ingredients = []

        # Allergens
        response = self._supabase.table("allergens").select("id, name, synonyms, cas_number").execute()
        for row in response.data:
            ingredients.append({
                "source_table": "allergens",
                "source_id": row["id"],
                "name": row["name"],
                "synonyms": row.get("synonyms") or [],
                "cas_number": row.get("cas_number"),
            })

        # PFAS compounds
        response = self._supabase.table("pfas_compounds").select("id, name, synonyms, cas_number").execute()
        for row in response.data:
            ingredients.append({
                "source_table": "pfas_compounds",
                "source_id": row["id"],
                "name": row["name"],
                "synonyms": row.get("synonyms") or [],
                "cas_number": row.get("cas_number"),
            })

        # Toxic substances
        response = self._supabase.table("toxic_substances").select("id, name, synonyms, cas_number").execute()
        for row in response.data:
            ingredients.append({
                "source_table": "toxic_substances",
                "source_id": row["id"],
                "name": row["name"],
                "synonyms": row.get("synonyms") or [],
                "cas_number": row.get("cas_number"),
            })

        logger.info(f"Found {len(ingredients)} ingredients to research")

        # Process in batches
        results = []
        for i in range(0, len(ingredients), batch_size):
            batch = ingredients[i:i + batch_size]
            logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} ingredients)")

            for ing in batch:
                try:
                    research = await self.research_ingredient(
                        ingredient_name=ing["name"],
                        source_table=ing["source_table"],
                        source_id=ing["source_id"],
                        cas_number=ing["cas_number"],
                        synonyms=ing["synonyms"],
                    )

                    # Store in database
                    await self._store_research(research)
                    results.append({"name": ing["name"], "status": "success"})

                except Exception as e:
                    logger.error(f"Failed to research {ing['name']}: {e}")
                    results.append({"name": ing["name"], "status": "error", "error": str(e)})

            # Delay between batches
            if i + batch_size < len(ingredients):
                logger.info(f"Waiting {delay_between_batches}s before next batch...")
                await asyncio.sleep(delay_between_batches)

        # Summary
        successful = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "error")

        return {
            "total_ingredients": len(ingredients),
            "successful": successful,
            "failed": failed,
            "total_searches": self._total_searches,
            "total_extractions": self._total_extractions,
            "estimated_cost": self._total_searches * 0.008 + self._total_extractions * 0.002,
            "errors": self._errors,
        }

    async def _store_research(self, research: Dict[str, Any]) -> None:
        """Store research findings in the database."""
        # Upsert to handle re-runs
        self._supabase.table("ingredient_research").upsert(
            research,
            on_conflict="ingredient_name,source_table",
        ).execute()

        logger.info(f"  Stored research for: {research['ingredient_name']}")

    async def close(self) -> None:
        """Cleanup resources."""
        await self._tavily.close()
