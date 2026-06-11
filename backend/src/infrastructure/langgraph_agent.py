"""LangGraph-based product safety agent using Cohere Command A.

Uses LangGraph's create_react_agent for reliable tool calling - same pattern as scraper-agent.

Cost savings: ~40-50% compared to all-Claude approach.

FEATURE PARITY: This agent now has the same knowledge bases, classification rules,
and search types as the Claude agent for fair comparison.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from langchain_cohere import ChatCohere
from langgraph.prebuilt import create_react_agent
from anthropic import Anthropic

from .config import settings
from .token_tracker import TokenTracker
from .search_tool_service import SearchToolService

logger = logging.getLogger(__name__)


# =============================================================================
# TOOL CONTEXT (shared state across tools)
# =============================================================================

@dataclass
class LangGraphToolContext:
    """Shared context for LangGraph tools."""
    search_service: Optional[SearchToolService] = None
    supabase_client: Any = None
    token_tracker: Optional[TokenTracker] = None


# Global tool context (set before running agent)
_tool_context: Optional[LangGraphToolContext] = None


def set_tool_context(ctx: LangGraphToolContext):
    """Set the global tool context for LangGraph tools."""
    global _tool_context
    _tool_context = ctx


def get_tool_context() -> LangGraphToolContext:
    """Get the current tool context."""
    if _tool_context is None:
        raise RuntimeError("Tool context not set. Call set_tool_context() first.")
    return _tool_context


# =============================================================================
# SYSTEM PROMPT TEMPLATE - Feature parity with Claude agent
# =============================================================================

# Base prompt - knowledge bases get appended dynamically
SAFETY_AGENT_PROMPT_BASE = """You are a product safety research agent. You MUST use tools to complete tasks.

## Your Analysis Process

1. **MANUFACTURER SEARCH** (search_type="manufacturer"):
   - Search: "[brand] [product name] official ingredients" OR "[brand] MSDS"
   - Goal: Find complete ingredient/material lists from official sources

2. **REGULATORY SEARCH** (search_type="regulatory"):
   - Search: "[product name] recall FDA warning" OR "[brand] safety alert Health Canada"
   - Goal: Find FDA/EPA/Health Canada recalls, warnings, advisories

3. **PER-INGREDIENT RESEARCH** (search_type="ingredient" or "scientific"):
   - For EACH potentially concerning ingredient, search individually:
     - "[ingredient name] toxicity studies"
     - "[ingredient name] IARC classification carcinogen"
     - "[ingredient name] contact dermatitis allergy"
     - "[ingredient name] endocrine disruptor research"
   - PRIORITY ingredients to research:
     - Essential oils (tea tree, lavender - sensitization potential)
     - Acids (salicylic acid, glycolic acid - irritation)
     - Preservatives (phenoxyethanol, parabens, formaldehyde releasers)
     - Antioxidants (BHT, BHA)
     - Fragrance/parfum (phthalates concern)
     - Adhesives and polymers (skin barrier disruption)

4. **LEGAL SEARCH** (search_type="legal"):
   - Search: "[brand] class action lawsuit" OR "[brand] settlement"
   - Goal: Find documented lawsuits, settlements, regulatory fines

5. **CONSUMER SEARCH** (search_type="consumer"):
   - Search: "[brand] [product] reaction allergy breakout reddit"
   - Goal: Find real user reports of adverse reactions

6. **SAVE ANALYSIS** - Call save_analysis with COMPLETE findings

## CRITICAL CLASSIFICATION RULES

1. **ALLERGENS - ONLY substances in the Allergen Knowledge Base can go in allergens_detected**
   - If you find an ingredient via websearch that is NOT in the Allergen Knowledge Base → DO NOT add to allergens_detected
   - Minor irritants are NOT allergens unless listed in the knowledge base
   - If a substance causes irritation but is not in the knowledge base → add to other_concerns with category="under_investigation"

2. **PFAS - ONLY substances in the PFAS Knowledge Base can go in pfas_detected**
   - If you find a chemical via websearch that is NOT in the PFAS Knowledge Base → DO NOT add to pfas_detected
   - Unknown fluorinated compounds → add to other_concerns with category="under_investigation"

3. **OTHER CONCERNS - Use for substances NOT in knowledge bases**
   - category="under_investigation": Substances with credible evidence but not in our database
   - category="carcinogen": ONLY IARC-classified carcinogens (Groups 1, 2A, 2B) from credible sources
   - category="regulatory_action": ONLY substances with FDA recall, EPA warning, or class action lawsuit
   - category="endocrine_disruptor", "heavy_metal", "other": Other toxins with credible evidence

4. **EVIDENCE REQUIREMENTS for other_concerns:**
   - Scientific claims: Use .gov, .edu, peer-reviewed journal, PubMed, court record
   - Consumer reports: Reddit user experiences ARE valid evidence for skin reactions, allergies, adverse effects
   - ALWAYS include consumer/Reddit sources in research_sources when users report reactions
   - MUST include description with source citation (e.g., "PubMed PMID: 12345678" or "Reddit r/SkincareAddiction")

## save_analysis JSON format (REQUIRED):

```json
{
  "product_name": "full product name",
  "brand": "brand name",
  "retailer": "retailer name",
  "ingredients": ["list", "of", "ingredients"],
  "allergens_detected": [
    {"name": "allergen (MUST be in knowledge base)", "severity": "low|moderate|high|severe", "source": "where found", "confidence": 0.0-1.0}
  ],
  "pfas_detected": [
    {"name": "PFAS compound (MUST be in knowledge base)", "cas_number": "if known", "source": "where found", "confidence": 0.0-1.0}
  ],
  "other_concerns": [
    {"name": "concern name", "category": "under_investigation|carcinogen|regulatory_action|endocrine_disruptor|heavy_metal|other", "severity": "low|moderate|high", "description": "detailed finding WITH source citation", "confidence": 0.0-1.0}
  ],
  "research_sources": [
    {"type": "manufacturer_website|regulatory_action|scientific_study|consumer_reports", "url": "full URL", "finding": "what was found"}
  ],
  "confidence": 0.0-1.0
}
```

CRITICAL:
- Do ALL searches (manufacturer, regulatory, ingredient/scientific, legal, consumer) before save_analysis
- Research EACH ingredient individually, especially essential oils and acids
- Include ALL findings in research_sources array
- Only classify as allergen/PFAS if in the knowledge base
- Use other_concerns for anything not in knowledge base"""


# =============================================================================
# TOOLS
# =============================================================================

@tool
def web_search(query: str, search_type: str = "general") -> str:
    """Search the web for product safety information.

    Args:
        query: Search query
        search_type: One of: manufacturer, regulatory, ingredient, scientific, legal, consumer, general
            - manufacturer: Official product pages, MSDS, ingredient lists
            - regulatory: FDA.gov, Health Canada, EPA recalls and warnings
            - ingredient: Per-ingredient safety research (PubMed, NIH, EWG)
            - scientific: Scientific studies, IARC classifications, peer-reviewed journals
            - legal: Class action lawsuits, court records, settlements
            - consumer: Reddit user experiences and reactions
            - general: No domain filter

    Returns:
        JSON string with search results
    """
    import nest_asyncio
    nest_asyncio.apply()

    ctx = get_tool_context()

    if not ctx.search_service:
        return json.dumps({"error": "Search service not available", "results": []})

    import asyncio

    async def do_search():
        results = await ctx.search_service.search(
            query=query,
            search_type=search_type,
        )
        return results

    try:
        # search() returns a formatted string for Claude
        results_str = asyncio.get_event_loop().run_until_complete(do_search())

        logger.info(f"🔍 web_search [{search_type}]: {query[:50]}...")

        # Return as JSON with the search results
        return json.dumps({
            "search_type": search_type,
            "query": query,
            "results": results_str[:2000],  # Truncate for context
        })

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return json.dumps({"error": str(e), "results": ""})


@tool
def lookup_ingredient_research(ingredient: str) -> str:
    """Look up pre-computed research for an ingredient from the database.

    WARNING: This database may be incomplete or empty. ALWAYS use web_search
    for ingredient research first. Only use this tool as a supplementary check
    AFTER you have already searched for the ingredient via web_search.

    Args:
        ingredient: Ingredient name to look up

    Returns:
        JSON string with research findings or not found message
    """
    ctx = get_tool_context()

    if not ctx.supabase_client:
        return json.dumps({"ingredient": ingredient, "found": False, "reason": "Database not available"})

    try:
        result = ctx.supabase_client.table("ingredient_research").select("*").ilike(
            "ingredient_name", f"%{ingredient}%"
        ).limit(1).execute()

        if result.data:
            data = result.data[0]
            logger.info(f"📚 Found research for: {ingredient}")
            return json.dumps({
                "ingredient": ingredient,
                "found": True,
                "safety_summary": data.get("safety_summary", ""),
                "concerns": data.get("concerns", []),
                "sources": data.get("sources", []),
            })
        else:
            return json.dumps({"ingredient": ingredient, "found": False})

    except Exception as e:
        logger.error(f"Database lookup failed: {e}")
        return json.dumps({"ingredient": ingredient, "found": False, "error": str(e)})


@tool
def save_analysis(analysis_json: str) -> str:
    """Save the final safety analysis. Call this when you have completed all research.

    This is a TERMINAL action - the agent loop will end after this.

    Args:
        analysis_json: JSON string with the complete safety analysis containing:
            - product_name: string
            - brand: string
            - allergens_detected: list of {name, severity, source, confidence}
            - pfas_detected: list of {name, cas_number, source, confidence}
            - other_concerns: list of {name, category, severity, description, confidence}
            - research_sources: list of {type, url, finding}
            - confidence: float 0-1

    Returns:
        Confirmation that analysis was saved
    """
    logger.info("💾 save_analysis called - ending agent loop")
    logger.info(f"   Input length: {len(analysis_json)} chars")
    logger.debug(f"   Raw input: {analysis_json[:500]}...")

    try:
        analysis = json.loads(analysis_json)
        logger.info(f"   Parsed: {len(analysis.get('other_concerns', []))} concerns, {len(analysis.get('research_sources', []))} sources")
        # Mark as terminal
        analysis["_terminal"] = True
        analysis["_saved"] = True
        return json.dumps(analysis)
    except json.JSONDecodeError as e:
        logger.error(f"   JSON parse error: {e}")
        logger.error(f"   Raw: {analysis_json[:200]}")
        return json.dumps({
            "error": f"Invalid JSON: {e}",
            "_terminal": True,
            "_saved": False
        })


@tool
def report_failure(reason: str) -> str:
    """Report that the analysis cannot be completed. Call only after genuinely trying.

    This is a TERMINAL action - the agent loop will end after this.

    Args:
        reason: Explanation of why analysis failed

    Returns:
        Failure acknowledgment
    """
    logger.warning(f"❌ report_failure: {reason}")
    return json.dumps({
        "status": "failed",
        "reason": reason,
        "_terminal": True,
        "_saved": False
    })


# =============================================================================
# LANGGRAPH AGENT
# =============================================================================

class LangGraphSafetyAgent:
    """Product safety agent using LangGraph's create_react_agent.

    Uses the same pattern as scraper-agent for reliable tool calling.
    Now with FEATURE PARITY: same knowledge bases and classification rules as Claude agent.
    """

    def __init__(
        self,
        token_tracker: Optional[TokenTracker] = None,
        search_service: Optional[SearchToolService] = None,
        supabase_client: Any = None,
        max_iterations: int = 15,
        temperature: float = 0.3,
    ):
        """Initialize the safety agent.

        Args:
            token_tracker: Token tracking service
            search_service: Web search service
            supabase_client: Supabase client for database lookups
            max_iterations: Maximum tool-calling iterations
            temperature: Temperature for model responses (0.0-1.0). Default 0.3.
        """
        self.token_tracker = token_tracker
        self.search_service = search_service
        self.supabase_client = supabase_client
        self.max_iterations = max_iterations
        self.temperature = temperature

        # Initialize Cohere LLM
        self.llm = ChatCohere(
            model="command-a-03-2025",
            temperature=self.temperature,
            cohere_api_key=settings.cohere_api_key,
        )

        # Build tools - Both agents now have lookup_ingredient_research for TRUE parity test
        # Testing whether Claude also takes the "shortcut" or follows the warning
        self.tools = [
            web_search,
            lookup_ingredient_research,  # RE-ENABLED: Testing if Claude also ignores the warning
            save_analysis,
            report_failure,
        ]

        logger.info("🤖 LangGraphSafetyAgent initialized (dynamic prompt per request)")

    def _build_system_prompt(
        self,
        allergen_database: List[Dict[str, Any]] = None,
        pfas_database: List[Dict[str, Any]] = None,
        allergen_profile: List[str] = None,
    ) -> str:
        """Build system prompt with embedded knowledge bases.

        This mirrors Claude's _build_analysis_prompt_for_extracted_data() for feature parity.
        """
        prompt = SAFETY_AGENT_PROMPT_BASE

        # Add allergen knowledge base
        if allergen_database:
            prompt += f"\n\n## ALLERGEN KNOWLEDGE BASE ({len(allergen_database)} priority allergens)\n"
            prompt += "ONLY these substances can be classified as allergens. If not on this list, use other_concerns instead.\n\n"
            for allergen in allergen_database:
                name = allergen.get('name', '')
                synonyms = allergen.get('synonyms', [])
                if synonyms:
                    prompt += f"- {name} (synonyms: {', '.join(synonyms[:3])})\n"
                else:
                    prompt += f"- {name}\n"

        # Add PFAS knowledge base
        if pfas_database:
            prompt += f"\n\n## PFAS KNOWLEDGE BASE ({len(pfas_database)} compounds)\n"
            prompt += "ONLY these substances can be classified as PFAS. If not on this list, use other_concerns instead.\n\n"
            for pfas in pfas_database:
                name = pfas.get('name', '')
                cas = pfas.get('cas_number', '')
                if cas:
                    prompt += f"- {name} (CAS: {cas})\n"
                else:
                    prompt += f"- {name}\n"

        # Add user allergen profile
        if allergen_profile:
            prompt += f"\n\n## USER'S ALLERGEN PROFILE\n"
            prompt += f"Pay special attention to: {', '.join(allergen_profile)}\n"

        return prompt

    def _create_agent_with_prompt(self, system_prompt: str):
        """Create a new agent instance with the given system prompt."""
        return create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_prompt,
        )

    async def analyze_extracted_product(
        self,
        product_data: Dict[str, Any],
        product_url: str,
        allergen_profile: List[str] = None,
        pfas_database: List[Dict[str, Any]] = None,
        allergen_database: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze product using LangGraph agent.

        Args:
            product_data: Extracted product data
            product_url: Product URL
            allergen_profile: User's allergen concerns
            pfas_database: PFAS knowledge base
            allergen_database: Allergen knowledge base

        Returns:
            Analysis result dictionary
        """
        product_name = product_data.get("product_name", "Unknown")
        brand = product_data.get("brand", "Unknown")
        ingredients = product_data.get("ingredients", [])

        logger.info(f"🚀 Starting LangGraph analysis for: {product_name}")
        logger.info(f"   Knowledge bases: {len(allergen_database or [])} allergens, {len(pfas_database or [])} PFAS")

        # Build dynamic system prompt with knowledge bases (FEATURE PARITY with Claude)
        system_prompt = self._build_system_prompt(
            allergen_database=allergen_database,
            pfas_database=pfas_database,
            allergen_profile=allergen_profile,
        )

        # Create agent with the dynamic prompt
        agent = self._create_agent_with_prompt(system_prompt)

        # Build the task prompt with specific instructions for this product
        # Include guidance to search EACH ingredient individually like Claude does
        ingredient_searches = ""
        if ingredients:
            for ing in ingredients[:5]:  # Top 5 ingredients
                ingredient_searches += f'   - web_search(query="{ing} safety toxicity contact dermatitis", search_type="ingredient")\n'

        task_prompt = f"""Analyze this product for safety concerns:

PRODUCT: {product_name}
BRAND: {brand}
URL: {product_url}
INGREDIENTS: {', '.join(ingredients[:20]) if ingredients else 'Not listed - search for them'}

Execute ALL of these searches (you can call multiple tools at once for efficiency):

- MANUFACTURER: web_search(query="{brand} {product_name[:30]} ingredients MSDS", search_type="manufacturer")
- REGULATORY: web_search(query="{brand} {product_name[:30]} FDA recall warning Health Canada", search_type="regulatory")
- LEGAL: web_search(query="{brand} lawsuit settlement class action", search_type="legal")
- CONSUMER: web_search(query="{brand} {product_name[:30]} reddit reaction allergy", search_type="consumer")
- PER-INGREDIENT RESEARCH (search EACH ingredient individually):
{ingredient_searches if ingredient_searches else '   - web_search for each ingredient safety'}

After completing ALL searches, call save_analysis with COMPLETE JSON including ALL findings.

CRITICAL REMINDERS:
- You CAN and SHOULD call multiple web_search tools in a single response for efficiency
- Search EACH ingredient individually (tea tree oil, salicylic acid, etc.)
- Only classify as allergen if in the ALLERGEN KNOWLEDGE BASE
- Only classify as PFAS if in the PFAS KNOWLEDGE BASE
- Use other_concerns for anything not in knowledge bases
- Include source citations (PubMed, .gov, etc.) in descriptions"""

        # Run the agent
        iteration = 0
        final_result = None

        try:
            async for event in agent.astream_events(
                {"messages": [("user", task_prompt)]},
                version="v2",
            ):
                event_type = event.get("event", "")

                if event_type == "on_tool_start":
                    tool_name = event.get("name", "")
                    logger.info(f"   🔧 Tool: {tool_name}")
                    iteration += 1

                    if iteration > self.max_iterations:
                        logger.warning(f"Max iterations ({self.max_iterations}) reached")
                        break

                elif event_type == "on_tool_end":
                    # Get the output - may be ToolMessage object or string
                    raw_output = event.get("data", {}).get("output", "")

                    # Extract content from ToolMessage if needed
                    if hasattr(raw_output, "content"):
                        output = raw_output.content
                    else:
                        output = raw_output

                    # Check for terminal action
                    try:
                        parsed = json.loads(output) if isinstance(output, str) else output
                        if isinstance(parsed, dict):
                            if parsed.get("_terminal"):
                                if parsed.get("_saved"):
                                    final_result = parsed
                                    logger.info("✅ Analysis saved - ending loop")
                                else:
                                    logger.warning(f"❌ Analysis failed: {parsed.get('reason', 'Unknown')}")
                                    final_result = parsed
                                break
                    except (json.JSONDecodeError, TypeError):
                        pass

            # If no terminal action, try to extract from final state
            if final_result is None:
                logger.warning("No terminal action called - returning default result")
                final_result = {
                    "product_name": product_name,
                    "brand": brand,
                    "allergens_detected": [],
                    "pfas_detected": [],
                    "other_concerns": [],
                    "research_sources": [],
                    "confidence": 0.3,
                    "error": "Agent did not call save_analysis",
                }

            # Clean up internal fields
            final_result.pop("_terminal", None)
            final_result.pop("_saved", None)

            logger.info(f"✅ LangGraph analysis complete after {iteration} tool calls")
            return final_result

        except Exception as e:
            logger.error(f"❌ LangGraph analysis failed: {e}")
            return {
                "product_name": product_name,
                "brand": brand,
                "allergens_detected": [],
                "pfas_detected": [],
                "other_concerns": [],
                "research_sources": [],
                "confidence": 0.0,
                "error": str(e),
            }

    async def close(self) -> None:
        """Cleanup resources."""
        if self.search_service:
            await self.search_service.close()
