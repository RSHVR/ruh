"""Native Cohere Agent for product safety analysis (no LangGraph wrapper)."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import cohere
from .config import settings
from .search_tool_service import SearchToolService

logger = logging.getLogger(__name__)


# Tool definitions in Cohere's native format
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": """Search the web for product safety information.

Use this tool to find:
- Manufacturer official ingredient/material lists and MSDS sheets
- FDA/EPA/CPSC recalls and safety alerts
- Per-ingredient scientific studies, IARC classifications, and toxicity data
- Class action lawsuits and consumer complaints

SEARCH TYPES:
- "manufacturer": Official product pages, MSDS, ingredient lists
- "regulatory": FDA.gov, Health Canada, EPA recalls and warnings
- "ingredient": Per-ingredient safety research (PubMed, NIH, IARC, EPA, EWG)
- "scientific": General scientific studies and research papers
- "legal": Class action lawsuits, court records, settlements
- "consumer": Reddit user experiences and reactions
- "general": No domain filter

IMPORTANT: For products with multiple ingredients, search each ingredient individually.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (keep under 400 characters)"
                    },
                    "search_type": {
                        "type": "string",
                        "enum": ["manufacturer", "regulatory", "ingredient", "scientific", "legal", "consumer", "general"],
                        "description": "Type of search to perform"
                    }
                },
                "required": ["query", "search_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_ingredient_research",
            "description": """Look up pre-computed research for an ingredient from the database.

WARNING: This database may be incomplete or empty. ALWAYS use web_search
for ingredient research first. Only use this tool as a supplementary check
AFTER you have already searched for the ingredient via web_search.

Args:
    ingredient: Ingredient name to look up

Returns:
    JSON string with research findings or not found message""",
            "parameters": {
                "type": "object",
                "properties": {
                    "ingredient": {
                        "type": "string",
                        "description": "Ingredient name to look up"
                    }
                },
                "required": ["ingredient"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_analysis",
            "description": "Save the final analysis results. Call this ONLY when you have completed all research and are ready to submit your findings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "analysis_json": {
                        "type": "string",
                        "description": "The complete analysis as a JSON string"
                    }
                },
                "required": ["analysis_json"]
            }
        }
    }
]


class NativeCohereSafetyAgent:
    """Native Cohere Agent that analyzes products for harmful substances.

    Uses the Cohere Python SDK directly without LangGraph wrapper.
    """

    def __init__(
        self,
        search_service: Optional[SearchToolService] = None,
        supabase_client: Optional[Any] = None,
        temperature: float = 0.3,
    ) -> None:
        """Initialize the Native Cohere Agent.

        Args:
            search_service: Web search service
            supabase_client: Supabase client for database lookups
            temperature: Temperature for model responses (0.0-1.0). Default 0.3.
        """
        self.client = cohere.ClientV2(api_key=settings.cohere_api_key)
        self.model = "command-a-03-2025"
        self.temperature = temperature
        self.supabase_client = supabase_client

        # Initialize search service
        self.search_service = search_service or SearchToolService(
            supabase_client=supabase_client,
        )

        logger.info("🤖 NativeCohereSafetyAgent initialized (no LangGraph)")

    def _build_system_prompt(
        self,
        allergen_database: List[Dict[str, Any]] = None,
        pfas_database: List[Dict[str, Any]] = None,
        allergen_profile: List[str] = None,
    ) -> str:
        """Build system prompt with embedded knowledge bases."""
        prompt = """You are a product safety research agent. Your job is to analyze products for potential health concerns including allergens, PFAS (forever chemicals), and other harmful substances.

## YOUR TASK

Given product information, you must:
1. Use web_search to research each ingredient's safety profile
2. Look for regulatory actions, recalls, and scientific studies
3. Check for consumer reports of adverse reactions
4. Compile findings into a structured analysis

## REQUIRED SEARCHES (call ALL of these - you can batch multiple tools at once)

- **Manufacturer search** (search_type="manufacturer"): Find official ingredient lists
- **Regulatory search** (search_type="regulatory"): Find FDA/EPA/Health Canada recalls, warnings
- **Per-ingredient searches** (search_type="ingredient"): Research EACH potentially concerning ingredient individually
- **Legal search** (search_type="legal"): Find class action lawsuits, settlements
- **Consumer search** (search_type="consumer"): Find Reddit user reports of reactions

You CAN and SHOULD call multiple web_search tools in a single response for efficiency.

## CRITICAL CLASSIFICATION RULES

1. **ALLERGENS - ONLY substances in the Allergen Knowledge Base can go in allergens_detected**
   - If not in knowledge base → use other_concerns with category="under_investigation"

2. **PFAS - ONLY substances in the PFAS Knowledge Base can go in pfas_detected**
   - Unknown fluorinated compounds → other_concerns

3. **EVIDENCE REQUIREMENTS:**
   - Scientific claims: Use .gov, .edu, peer-reviewed journal, PubMed
   - Consumer reports: Reddit user experiences ARE valid evidence for skin reactions, allergies
   - ALWAYS include consumer/Reddit sources in research_sources if users report reactions
   - MUST include source citation in description

## OUTPUT FORMAT

When you have completed ALL research, call save_analysis with a JSON object containing:
{
    "product_name": "string",
    "brand": "string",
    "ingredients": ["list", "of", "ingredients"],
    "allergens_detected": [...],
    "pfas_detected": [...],
    "other_concerns": [
        {
            "name": "concern name",
            "category": "under_investigation|carcinogen|regulatory_action|heavy_metal|endocrine_disruptor|other",
            "severity": "low|moderate|high|severe",
            "description": "description with source citation",
            "confidence": 0.0-1.0
        }
    ],
    "research_sources": [
        {"type": "...", "url": "...", "finding": "..."}
    ],
    "confidence": 0.0-1.0
}
"""

        # Add allergen database
        if allergen_database:
            prompt += f"\n## ALLERGEN KNOWLEDGE BASE ({len(allergen_database)} priority allergens)\n"
            prompt += "ONLY these substances can be classified as allergens:\n"
            for allergen in allergen_database:
                name = allergen.get('name', '')
                synonyms = allergen.get('synonyms', [])
                if synonyms:
                    prompt += f"- {name} (synonyms: {', '.join(synonyms[:3])})\n"
                else:
                    prompt += f"- {name}\n"

        # Add PFAS database
        if pfas_database:
            prompt += f"\n## PFAS KNOWLEDGE BASE ({len(pfas_database)} compounds)\n"
            prompt += "ONLY these substances can be classified as PFAS:\n"
            for pfas in pfas_database:
                name = pfas.get('name', '')
                cas = pfas.get('cas_number', '')
                if cas:
                    prompt += f"- {name} (CAS: {cas})\n"
                else:
                    prompt += f"- {name}\n"

        # Add user allergen profile
        if allergen_profile:
            prompt += f"\n## User's Allergen Profile\nPay special attention to: {', '.join(allergen_profile)}\n"

        return prompt

    async def _execute_tool(self, tool_call: Any) -> str:
        """Execute a tool call and return the result."""
        func_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        if func_name == "web_search":
            query = args.get("query", "")
            search_type = args.get("search_type", "general")
            logger.info(f"   🔍 web_search: {query[:60]}... (type={search_type})")

            try:
                result = await self.search_service.search(query, search_type)
                return result
            except Exception as e:
                logger.error(f"Search failed: {e}")
                return json.dumps({"error": str(e), "results": ""})

        elif func_name == "lookup_ingredient_research":
            ingredient = args.get("ingredient", "")
            logger.info(f"   📚 lookup_ingredient_research: {ingredient}")
            return await self._lookup_ingredient_research(ingredient)

        elif func_name == "save_analysis":
            analysis_json = args.get("analysis_json", "{}")
            logger.info(f"   💾 save_analysis called")
            return json.dumps({"status": "saved", "analysis": analysis_json})

        else:
            return json.dumps({"error": f"Unknown tool: {func_name}"})

    async def _lookup_ingredient_research(self, ingredient: str) -> str:
        """Look up pre-computed research for an ingredient from the database."""
        if not self.supabase_client:
            return json.dumps({
                "ingredient": ingredient,
                "found": False,
                "reason": "Database not available"
            })

        try:
            result = self.supabase_client.table("ingredient_research").select("*").ilike(
                "ingredient_name", f"%{ingredient}%"
            ).execute()

            if result.data and len(result.data) > 0:
                research = result.data[0]
                logger.info(f"   ✓ Found research for: {ingredient}")
                return json.dumps({
                    "ingredient": ingredient,
                    "found": True,
                    "safety_summary": research.get("safety_summary", ""),
                    "concerns": research.get("concerns", []),
                    "sources": research.get("sources", []),
                })
            else:
                logger.info(f"   ✗ No research found for: {ingredient}")
                return json.dumps({
                    "ingredient": ingredient,
                    "found": False,
                    "reason": "No pre-computed research available for this ingredient"
                })

        except Exception as e:
            logger.error(f"Database lookup failed: {e}")
            return json.dumps({
                "ingredient": ingredient,
                "found": False,
                "reason": f"Database error: {str(e)}"
            })

    async def analyze_product(
        self,
        product_name: str,
        brand: str,
        ingredients: List[str],
        product_url: str,
        allergen_profile: List[str] = None,
        pfas_database: List[Dict[str, Any]] = None,
        allergen_database: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze a product for harmful substances using native Cohere SDK.

        This is a direct port of the LangGraph agent but without the wrapper.
        """
        start_time = time.time()

        allergen_profile = allergen_profile or []
        pfas_database = pfas_database or []
        allergen_database = allergen_database or []

        logger.info(f"🚀 Starting Native Cohere analysis for: {product_name}")
        logger.info(f"   Knowledge bases: {len(allergen_database)} allergens, {len(pfas_database)} PFAS")

        # Build system prompt
        system_prompt = self._build_system_prompt(
            allergen_database=allergen_database,
            pfas_database=pfas_database,
            allergen_profile=allergen_profile,
        )

        # Build user message
        user_message = f"""Analyze this product for safety concerns:

**Product:** {product_name}
**Brand:** {brand}
**URL:** {product_url}

**Ingredients:**
{chr(10).join([f"- {ing}" for ing in ingredients])}

Perform comprehensive research using web_search for each ingredient, then compile your findings and call save_analysis with the complete JSON analysis."""

        # Initialize messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        # Agent loop
        max_iterations = 15
        iteration = 0
        final_analysis = None
        tool_call_count = 0

        while iteration < max_iterations:
            iteration += 1

            try:
                response = self.client.chat(
                    model=self.model,
                    messages=messages,
                    tools=TOOLS,
                    temperature=self.temperature,
                )
            except Exception as e:
                logger.error(f"Cohere API error: {e}")
                raise

            # Check if model wants to call tools
            if response.message.tool_calls:
                tool_calls = response.message.tool_calls
                tool_call_count += len(tool_calls)
                logger.info(f"   🔧 Tool calls: {[tc.function.name for tc in tool_calls]}")

                # Add assistant message with tool calls
                messages.append({
                    "role": "assistant",
                    "tool_plan": response.message.tool_plan,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in tool_calls
                    ]
                })

                # Check for terminal action first
                save_analysis_tc = None
                non_terminal_tcs = []
                for tc in tool_calls:
                    if tc.function.name == "save_analysis":
                        save_analysis_tc = tc
                    else:
                        non_terminal_tcs.append(tc)

                # Execute non-terminal tools IN PARALLEL using asyncio.gather
                if non_terminal_tcs:
                    logger.info(f"   ⚡ Executing {len(non_terminal_tcs)} tools in parallel...")
                    tasks = [self._execute_tool(tc) for tc in non_terminal_tcs]
                    results = await asyncio.gather(*tasks)

                    # Add all tool results to messages
                    for tc, result in zip(non_terminal_tcs, results):
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": [
                                {
                                    "type": "document",
                                    "document": {"data": result}
                                }
                            ]
                        })

                # Handle save_analysis terminal action
                if save_analysis_tc:
                    logger.info(f"💾 save_analysis called - ending agent loop")
                    try:
                        args = json.loads(save_analysis_tc.function.arguments)
                        analysis_str = args.get("analysis_json", "{}")
                        final_analysis = json.loads(analysis_str)
                        logger.info(f"   Parsed: {len(final_analysis.get('other_concerns', []))} concerns, {len(final_analysis.get('research_sources', []))} sources")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse analysis JSON: {e}")
                        final_analysis = {"error": "Failed to parse analysis"}

                # Check if we got final analysis
                if final_analysis is not None:
                    break

            else:
                # No tool calls - model is done
                if response.message.content:
                    text = response.message.content[0].text
                    logger.info(f"Model response without tools: {text[:100]}...")

                    # Try to extract JSON from response
                    try:
                        if "```json" in text:
                            json_start = text.find("```json") + 7
                            json_end = text.find("```", json_start)
                            final_analysis = json.loads(text[json_start:json_end].strip())
                        elif "{" in text:
                            json_start = text.find("{")
                            json_end = text.rfind("}") + 1
                            final_analysis = json.loads(text[json_start:json_end])
                    except json.JSONDecodeError:
                        logger.warning("Could not extract JSON from final response")
                break

        elapsed_time = time.time() - start_time
        logger.info(f"✅ Native Cohere analysis complete after {tool_call_count} tool calls in {elapsed_time:.1f}s")

        # Return analysis or error
        if final_analysis:
            final_analysis["_metadata"] = {
                "agent": "native_cohere",
                "model": self.model,
                "temperature": self.temperature,
                "tool_calls": tool_call_count,
                "iterations": iteration,
                "elapsed_seconds": elapsed_time
            }
            return final_analysis
        else:
            return {
                "product_name": product_name,
                "brand": brand,
                "ingredients": ingredients,
                "allergens_detected": [],
                "pfas_detected": [],
                "other_concerns": [],
                "research_sources": [],
                "confidence": 0.0,
                "error": "No analysis produced",
                "_metadata": {
                    "agent": "native_cohere",
                    "model": self.model,
                    "tool_calls": tool_call_count,
                    "iterations": iteration,
                    "elapsed_seconds": elapsed_time
                }
            }

    async def close(self) -> None:
        """Close search service."""
        if self.search_service:
            await self.search_service.close()
