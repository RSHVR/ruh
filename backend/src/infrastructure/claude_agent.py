"""Claude Agent for product safety analysis."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional
import httpx
from anthropic import Anthropic, RateLimitError, APIError
from ..infrastructure.config import settings
from ..infrastructure.token_tracker import TokenTracker
from ..infrastructure.search_tool_service import SearchToolService

logger = logging.getLogger(__name__)

# Custom web_search tool definition (replaces Anthropic's native web_search_20250305)
CUSTOM_WEB_SEARCH_TOOL = {
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

IMPORTANT: For products with multiple ingredients, use search_type="ingredient" to research
individual ingredients like "[ingredient name] toxicity" or "[ingredient name] IARC classification".

Results are filtered to credible sources based on search_type.""",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (keep under 400 characters)",
            },
            "search_type": {
                "type": "string",
                "enum": ["manufacturer", "regulatory", "ingredient", "scientific", "legal", "consumer", "general"],
                "description": "Type of search. Use 'ingredient' for per-ingredient safety research.",
            },
        },
        "required": ["query"],
    },
}


class ProductSafetyAgent:
    """Claude Agent that analyzes products for harmful substances."""

    def __init__(
        self,
        token_tracker: Optional[TokenTracker] = None,
        search_service: Optional[SearchToolService] = None,
        supabase_client: Optional[Any] = None,
    ) -> None:
        """Initialize the Claude Agent.

        Args:
            token_tracker: Optional TokenTracker instance for usage tracking.
                          If not provided, a new one will be created.
            search_service: Optional SearchToolService for custom web search.
                           If not provided and use_custom_search is True, one will be created.
            supabase_client: Optional Supabase client for search cache.
        """
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"
        self.http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self.token_tracker = token_tracker or TokenTracker()

        # Initialize search service if custom search is enabled
        self.use_custom_search = settings.use_custom_search
        if self.use_custom_search:
            self.search_service = search_service or SearchToolService(
                supabase_client=supabase_client,
            )
            logger.info("Custom search enabled (Tavily/Serper)")
        else:
            self.search_service = None
            logger.info("Using Anthropic native web_search")

    async def analyze_product(
        self,
        product_url: str,
        allergen_profile: List[str] = None,
        pfas_database: List[Dict[str, Any]] = None,
        allergen_database: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze a product for harmful substances.

        Args:
            product_url: URL of the product to analyze
            allergen_profile: User's known allergens to check for
            pfas_database: List of PFAS compounds from database
            allergen_database: List of allergens from database

        Returns:
            Dict containing analysis results
        """
        allergen_profile = allergen_profile or []
        pfas_database = pfas_database or []
        allergen_database = allergen_database or []

        # Build the analysis prompt
        system_prompt = self._build_system_prompt(
            allergen_profile, pfas_database, allergen_database
        )
        user_message = self._build_user_message(product_url)

        # Enable web search and web fetch tools
        # For fallback mode, we always use native web_fetch (need to fetch the page)
        # but can use custom search if enabled
        if self.use_custom_search and self.search_service:
            tools = [
                CUSTOM_WEB_SEARCH_TOOL,
                {
                    "type": "web_fetch_20250910",
                    "name": "web_fetch",
                    "max_uses": 3,
                },
            ]
        else:
            tools = [
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 5,
                },
                {
                    "type": "web_fetch_20250910",
                    "name": "web_fetch",
                    "max_uses": 3,
                },
            ]

        # Start conversation with Claude
        messages = [{"role": "user", "content": user_message}]

        # For fallback mode with custom search, we need a manual tool loop
        # to handle custom web_search while letting Anthropic handle web_fetch
        if self.use_custom_search and self.search_service:
            logger.info("Calling Claude with CUSTOM web_search + native web_fetch")
            return await self._analyze_product_with_custom_search(
                system_prompt, messages, tools
            )

        logger.info("Calling Claude with NATIVE web_search (max 5) and web_fetch (max 3) tools")

        # Pre-request token counting
        estimated_tokens = self.token_tracker.count_tokens(
            model=self.model,
            messages=messages,
            system=system_prompt,
            tools=tools,
        )

        # Claude handles tool use automatically for native tools
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=tools,
                tool_choice={"type": "auto"},
                extra_headers={
                    "anthropic-beta": "web-fetch-2025-09-10"
                }
            )
        except RateLimitError as e:
            logger.error(f"❌ Rate limit exceeded in analyze_product: {e}")
            raise
        except APIError as e:
            logger.error(f"❌ Claude API error in analyze_product: {e}")
            # Re-raise to be handled by caller
            raise

        # Record token usage with detailed logging
        self.token_tracker.record_usage(
            call_name="agent_fallback_analysis",
            model=self.model,
            usage=response.usage,
            estimated_input=estimated_tokens,
        )

        # Log tool usage information
        logger.info(f"Claude response - Stop reason: {response.stop_reason}")

        # Check what tools Claude used
        tool_uses = []
        for content_block in response.content:
            if hasattr(content_block, 'type'):
                logger.debug(f"Response content block type: {content_block.type}")
                if content_block.type == "tool_use":
                    tool_name = getattr(content_block, 'name', 'unknown')
                    tool_input = getattr(content_block, 'input', {})
                    tool_uses.append({
                        'name': tool_name,
                        'input': tool_input
                    })
                    logger.info(f"🔧 Claude used tool: {tool_name}")
                    if tool_name == "web_search":
                        logger.info(f"   Search query: {tool_input.get('query', 'N/A')}")
                    elif tool_name == "web_fetch":
                        logger.info(f"   Fetch URL: {tool_input.get('url', 'N/A')}")

        if tool_uses:
            logger.info(f"✅ Claude used {len(tool_uses)} tool(s): {[t['name'] for t in tool_uses]}")
        else:
            logger.warning("⚠️  Claude did NOT use any tools (no web_search or web_fetch)")

        # Claude is done, parse final response
        analysis = self._parse_response(response)
        return analysis

    async def _analyze_product_with_custom_search(
        self,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Analyze product using custom search with native web_fetch.

        This is a hybrid approach for the fallback path (when scraping fails):
        - web_fetch: Native Anthropic tool (executed automatically by API)
        - web_search: Custom tool (executed via SearchToolService)

        The API handles native tools inline, so we only loop when Claude
        requests our custom web_search tool.
        """
        max_iterations = 8  # Higher limit since we also have web_fetch
        iteration = 0
        response = None

        logger.info("🔄 Starting hybrid tool loop (custom search + native web_fetch)")

        while iteration < max_iterations:
            iteration += 1

            # Pre-request token counting
            estimated_tokens = self.token_tracker.count_tokens(
                model=self.model,
                messages=messages,
                system=system_prompt,
                tools=tools,
            )

            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=messages,
                    tools=tools,
                    tool_choice={"type": "auto"},
                    extra_headers={
                        "anthropic-beta": "web-fetch-2025-09-10"
                    }
                )
            except RateLimitError as e:
                logger.error(f"❌ Rate limit exceeded: {e}")
                raise
            except APIError as e:
                logger.error(f"❌ Claude API error: {e}")
                raise

            # Record token usage
            self.token_tracker.record_usage(
                call_name=f"agent_fallback_custom_iter{iteration}",
                model=self.model,
                usage=response.usage,
                estimated_input=estimated_tokens,
            )

            # Log what tools Claude used (native tools show up in content)
            for block in response.content:
                if hasattr(block, 'type'):
                    if block.type == "tool_use":
                        tool_name = getattr(block, 'name', 'unknown')
                        tool_input = getattr(block, 'input', {})
                        logger.info(f"🔧 Claude used tool: {tool_name}")
                        if tool_name == "web_fetch":
                            logger.info(f"   Fetch URL: {tool_input.get('url', 'N/A')}")
                        elif tool_name == "web_search":
                            logger.info(f"   Search: {tool_input.get('query', 'N/A')[:60]}...")
                    elif block.type == "server_tool_use":
                        # Native tools like web_fetch appear as server_tool_use
                        tool_name = getattr(block, 'name', 'unknown')
                        logger.info(f"🌐 Anthropic executed native tool: {tool_name}")

            # Check if Claude wants to use our custom tool
            if response.stop_reason == "tool_use":
                # Find custom web_search tool uses (not native tools)
                custom_tool_uses = [
                    b for b in response.content
                    if hasattr(b, "type") and b.type == "tool_use" and b.name == "web_search"
                ]

                if not custom_tool_uses:
                    # No custom tools - might be waiting for something else
                    logger.warning("stop_reason=tool_use but no custom web_search blocks")
                    break

                logger.info(f"🔍 Executing {len(custom_tool_uses)} custom search(es) via Tavily/Serper")

                # Execute searches in parallel
                search_tasks = []
                for tool_use in custom_tool_uses:
                    query = tool_use.input.get("query", "")
                    search_type = tool_use.input.get("search_type", "general")
                    logger.info(f"   → {search_type}: {query[:60]}...")
                    search_tasks.append(
                        self.search_service.search(query, search_type)
                    )

                results = await asyncio.gather(*search_tasks, return_exceptions=True)

                # Build tool results and continue conversation
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for tool_use, result in zip(custom_tool_uses, results):
                    if isinstance(result, Exception):
                        content = f"Search failed: {result}"
                        logger.warning(f"   ✗ Search failed: {result}")
                    else:
                        content = result
                        logger.info(f"   ✓ Got results for: {tool_use.input.get('query', '')[:40]}...")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": content,
                    })
                messages.append({"role": "user", "content": tool_results})

            else:
                # Claude is done (end_turn or max_tokens)
                logger.info(f"✅ Hybrid analysis finished after {iteration} iteration(s)")
                break

        # Log search usage summary
        if self.search_service:
            usage = self.search_service.get_usage_summary()
            if usage['total_searches'] > 0:
                logger.info(
                    f"📊 Search summary: {usage['total_searches']} searches, "
                    f"{usage['cache_hits']} cache hits ({usage['cache_hit_rate']:.0%}), "
                    f"${usage['total_cost']:.4f}"
                )

        if response is None:
            logger.error("❌ No response received after max iterations")
            return {
                "product_name": "Unknown",
                "brand": "Unknown",
                "retailer": "Unknown",
                "ingredients": [],
                "allergens_detected": [],
                "pfas_detected": [],
                "other_concerns": [],
                "confidence": 0.0,
                "error": "Max iterations reached without response",
            }

        return self._parse_response(response)

    def _build_system_prompt(
        self,
        allergen_profile: List[str],
        pfas_database: List[Dict[str, Any]],
        allergen_database: List[Dict[str, Any]],
    ) -> str:
        """Build the system prompt for Claude."""
        prompt = """You are a product safety analysis expert. Your job is to analyze products for harmful substances including allergens, PFAS (forever chemicals), and other toxins.

**Your Analysis Process:**
1. **IMPORTANT:** ONLY use web_fetch if the user message does NOT contain product information (name, brand, ingredients, materials)
   - If product info is already in the message → SKIP web_fetch, proceed to step 2
   - If no product info in message → Use web_fetch to retrieve the product page

2. Use web_search strategically (max 5 searches) to find:
   a) **PRIORITY 1:** Manufacturer's official website for complete ingredient/material lists when missing from product page
      - Search: "[brand] [product name] official ingredients" OR "[brand] official MSDS"
      - ONLY use credible sources: manufacturer.com, official MSDS, .gov sites

   b) **PRIORITY 2:** Regulatory actions and safety recalls
      - Search: "[product] recall FDA warning" OR "[product] safety alert CPSC"
      - ONLY use: FDA.gov, HealthCanada.gc.ca, CPSC.gov, EPA.gov, EU REACH

   c) **PRIORITY 3:** Scientific studies and carcinogen classifications
      - Search: "[ingredient] IARC classification" OR "[ingredient] EPA toxicity"
      - ONLY use: PubMed, peer-reviewed journals, IARC, EPA, NIH

   d) **PRIORITY 4:** Class action lawsuits and documented health impacts
      - Search: "[product] class action lawsuit [ingredient]" OR "[brand] settlement"
      - ONLY use: Court records, major news outlets (.gov, .edu, established media)

3. Cross-reference findings with the knowledge base provided below
4. Return a comprehensive structured JSON analysis

**CRITICAL WEBSEARCH RESTRICTIONS:**
- DO NOT use consumer blogs, forums, or non-scientific health websites
- DO NOT use marketing materials or unverified product review sites (except for lawsuit discovery)
- ONLY use credible sources: .gov, .edu, manufacturer official sites, peer-reviewed journals, major news outlets

**Output Format:**
After fetching and analyzing the product page, return your analysis as a JSON object with this exact structure:
{
    "product_name": "string",
    "brand": "string",
    "retailer": "string (e.g., Amazon, Amazon.ca)",
    "ingredients": ["ingredient1", "ingredient2"],
    "allergens_detected": [
        {
            "name": "allergen name (MUST match knowledge base below)",
            "severity": "low|moderate|high|severe",
            "source": "where found in product",
            "confidence": 0.0-1.0
        }
    ],
    "pfas_detected": [
        {
            "name": "PFAS compound name (MUST match knowledge base below)",
            "cas_number": "CAS number if known",
            "body_effects": "description of effects on human body",
            "source": "where found (e.g., non-stick coating)",
            "confidence": 0.0-1.0
        }
    ],
    "other_concerns": [
        {
            "name": "concern name",
            "category": "under_investigation|carcinogen|regulatory_action|heavy_metal|endocrine_disruptor|other",
            "severity": "low|moderate|high|severe",
            "description": "brief description",
            "confidence": 0.0-1.0
        }
    ],
    "confidence": 0.0-1.0
}

**CRITICAL CLASSIFICATION RULES - READ CAREFULLY:**

1. **ALLERGENS - ONLY substances in the Allergen Knowledge Base below can go in allergens_detected**
   - If you find an ingredient via websearch that is NOT in the Allergen Knowledge Base → DO NOT add to allergens_detected
   - Minor irritants (citric acid, fragrance, etc.) are NOT allergens unless listed in the knowledge base
   - If a substance causes irritation but is not a priority allergen → add to other_concerns with category="under_investigation"

2. **PFAS - ONLY substances in the PFAS Knowledge Base below can go in pfas_detected**
   - If you find a chemical via websearch that is NOT in the PFAS Knowledge Base → DO NOT add to pfas_detected
   - Unknown fluorinated compounds → add to other_concerns with category="under_investigation"
   - Match by CAS number or exact name from the knowledge base

3. **OTHER CONCERNS - Use this for substances not in the knowledge bases**
   - category="under_investigation": Substances with credible evidence but not in our database (max severity=low)
   - category="carcinogen": IARC-classified carcinogens (Groups 1, 2A, 2B) with credible source
   - category="regulatory_action": Substances with FDA recall, EPA warning, or class action lawsuit
   - category="heavy_metal", "endocrine_disruptor", "other": Other toxins with credible evidence

4. **EVIDENCE REQUIREMENTS for other_concerns:**
   - MUST have credible source (.gov, .edu, peer-reviewed journal, court record)
   - MUST NOT include unverified consumer complaints or blog posts
   - MUST include description with source citation

**PFAS Detection Guidelines:**
- Non-stick cookware often contains PTFE (Teflon) - check knowledge base
- "Water-resistant", "stain-resistant" products may have PFAS coatings
- Match against knowledge base by CAS number or exact name
- If ingredients aren't fully listed, note lower confidence

**Allergen Detection:**
- Check ingredient lists carefully against knowledge base
- Look for synonyms listed in knowledge base
- If not in knowledge base → NOT an allergen (may be irritant)
"""

        # Add FULL allergen database (token-efficient format)
        if allergen_database:
            prompt += f"\n**ALLERGEN KNOWLEDGE BASE ({len(allergen_database)} priority allergens):**\n"
            prompt += "ONLY these substances can be classified as allergens. If a substance is not on this list, it is NOT an allergen.\n\n"
            for allergen in allergen_database:
                name = allergen.get('name', '')
                synonyms = allergen.get('synonyms', [])
                if synonyms:
                    prompt += f"- {name} (synonyms: {', '.join(synonyms[:3])})\n"  # Limit synonyms to 3
                else:
                    prompt += f"- {name}\n"

        # Add FULL PFAS database (token-efficient format)
        if pfas_database:
            prompt += f"\n**PFAS KNOWLEDGE BASE ({len(pfas_database)} compounds):**\n"
            prompt += "ONLY these substances can be classified as PFAS. If a substance is not on this list, it is NOT PFAS.\n\n"
            for pfas in pfas_database:
                name = pfas.get('name', '')
                cas = pfas.get('cas_number', '')
                if cas:
                    prompt += f"- {name} (CAS: {cas})\n"
                else:
                    prompt += f"- {name}\n"

        # Add user allergen profile if provided
        if allergen_profile:
            prompt += f"\n**User's Allergen Profile:**\nPay special attention to: {', '.join(allergen_profile)}\n"

        return prompt

    def _build_user_message(self, product_url: str) -> str:
        """Build the user message for Claude (fallback method when scraping fails)."""
        return f"""Analyze this product for harmful substances: {product_url}

**FALLBACK MODE:** Scraping failed, so you need to fetch the product page yourself.

1. Use web_fetch to retrieve the product page and extract product details (name, brand, ingredients)
2. Use web_search to find safety information, consumer reviews, recalls, and scientific studies
3. Provide your comprehensive structured JSON analysis"""

    def _parse_response(self, response: Any) -> Dict[str, Any]:
        """Parse Claude's response and extract analysis JSON with validation."""
        # Extract text content from response
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text

                # Try to extract JSON
                try:
                    # Look for JSON in various formats
                    if "```json" in text:
                        json_start = text.find("```json") + 7
                        json_end = text.find("```", json_start)
                        json_str = text[json_start:json_end].strip()
                    elif "```" in text:
                        json_start = text.find("```") + 3
                        json_end = text.find("```", json_start)
                        json_str = text[json_start:json_end].strip()
                    else:
                        # Try to find JSON object directly
                        json_start = text.find("{")
                        json_end = text.rfind("}") + 1
                        if json_start != -1 and json_end > json_start:
                            json_str = text[json_start:json_end]
                        else:
                            raise ValueError("No JSON found")

                    analysis = json.loads(json_str)

                    # VALIDATION: Check for required fields and valid values
                    if not analysis.get("product_name") or analysis.get("product_name") == "Unknown":
                        logger.warning(f"⚠️  Claude returned 'Unknown' or missing product_name. Raw response: {text[:300]}")

                    # Ensure lists exist
                    analysis.setdefault('allergens_detected', [])
                    analysis.setdefault('pfas_detected', [])
                    analysis.setdefault('other_concerns', [])
                    analysis.setdefault('ingredients', [])

                    # Validate confidence is between 0-1
                    confidence = analysis.get('confidence', 0.8)
                    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
                        logger.warning(f"⚠️  Invalid confidence value: {confidence}, defaulting to 0.5")
                        analysis['confidence'] = 0.5

                    logger.info(f"✅ Successfully parsed Claude response: {analysis.get('product_name', 'Unknown')}")
                    return analysis

                except (json.JSONDecodeError, ValueError) as e:
                    # Log the full error for debugging
                    logger.error(f"❌ JSON parsing failed: {str(e)}")
                    logger.error(f"Raw Claude response text (first 1000 chars): {text[:1000]}")

                    # Return error structure with partial data if possible
                    return {
                        "product_name": "Unknown",
                        "brand": "Unknown",
                        "retailer": "Unknown",
                        "ingredients": [],
                        "allergens_detected": [],
                        "pfas_detected": [],
                        "other_concerns": [],
                        "confidence": 0.1,
                        "error": f"Failed to parse JSON: {str(e)}",
                        "raw_response_preview": text[:500]  # Include preview for debugging
                    }

        # No text block found
        logger.error("❌ No text block found in Claude response")
        return {
            "product_name": "Unknown",
            "brand": "Unknown",
            "retailer": "Unknown",
            "ingredients": [],
            "allergens_detected": [],
            "pfas_detected": [],
            "other_concerns": [],
            "confidence": 0.0,
            "error": "No text content in Claude response",
        }

    async def analyze_extracted_product(
        self,
        product_data: Dict[str, Any],
        product_url: str,
        allergen_profile: List[str] = None,
        pfas_database: List[Dict[str, Any]] = None,
        allergen_database: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze product data that was already extracted by Claude Query.

        Args:
            product_data: Structured data from ClaudeQueryService
            product_url: Original product URL
            allergen_profile: User's allergen concerns
            pfas_database: PFAS compounds knowledge base
            allergen_database: Allergens knowledge base

        Returns:
            Safety analysis with web_search findings
        """
        allergen_profile = allergen_profile or []
        pfas_database = pfas_database or []
        allergen_database = allergen_database or []

        # Build analysis prompt
        system_prompt = self._build_analysis_prompt_for_extracted_data(
            allergen_profile, pfas_database, allergen_database
        )

        # Build user message from extracted data
        user_message = self._build_user_message_from_extracted_data(product_data, product_url)

        # Choose between custom search (Tavily/Serper) or Anthropic native
        if self.use_custom_search and self.search_service:
            return await self._analyze_with_custom_search(
                system_prompt, user_message, product_data
            )
        else:
            return await self._analyze_with_native_search(
                system_prompt, user_message, product_data
            )

    async def _analyze_with_native_search(
        self,
        system_prompt: str,
        user_message: str,
        product_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze using Anthropic's native web_search_20250305 tool."""
        # Enable ONLY web_search (not web_fetch - we already have the product data!)
        tools = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 3,  # Limit to 3 searches: manufacturer site, reviews, safety data
            },
        ]

        messages = [{"role": "user", "content": user_message}]

        logger.info(f"🔍 Calling Claude Agent with NATIVE web_search")
        logger.info(f"   Product: {product_data.get('product_name')}")

        # Pre-request token counting
        estimated_tokens = self.token_tracker.count_tokens(
            model=self.model,
            messages=messages,
            system=system_prompt,
            tools=tools,
        )

        # tool_choice="auto" lets Claude decide when to use web_search
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
                tools=tools,
                tool_choice={"type": "auto"},
            )
        except RateLimitError as e:
            logger.error(f"❌ Rate limit exceeded in analyze_extracted_product: {e}")
            raise
        except APIError as e:
            logger.error(f"❌ Claude API error in analyze_extracted_product: {e}")
            raise

        # Record token usage
        self.token_tracker.record_usage(
            call_name="agent_safety_analysis_native",
            model=self.model,
            usage=response.usage,
            estimated_input=estimated_tokens,
        )

        return self._parse_response(response)

    async def _analyze_with_custom_search(
        self,
        system_prompt: str,
        user_message: str,
        product_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze using custom Tavily/Serper search with manual tool execution loop.

        This implements the manual tool loop pattern:
        1. Call Claude with custom tool definition
        2. If stop_reason="tool_use", execute search locally via SearchToolService
        3. Send tool_result back to Claude
        4. Repeat until stop_reason="end_turn"
        """
        tools = [CUSTOM_WEB_SEARCH_TOOL]
        messages = [{"role": "user", "content": user_message}]

        logger.info(f"🔍 Calling Claude Agent with CUSTOM search (Tavily/Serper)")
        logger.info(f"   Product: {product_data.get('product_name')}")

        # Higher limit for comprehensive analysis:
        # - 1 manufacturer search
        # - 1 regulatory search
        # - 3-5 per-ingredient searches
        # - 1 legal search
        # - 1 consumer search
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Pre-request token counting
            estimated_tokens = self.token_tracker.count_tokens(
                model=self.model,
                messages=messages,
                system=system_prompt,
                tools=tools,
            )

            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,  # Increased for comprehensive analysis with research_sources
                    system=system_prompt,
                    messages=messages,
                    tools=tools,
                    tool_choice={"type": "auto"},
                )
            except RateLimitError as e:
                logger.error(f"❌ Rate limit exceeded: {e}")
                raise
            except APIError as e:
                logger.error(f"❌ Claude API error: {e}")
                raise

            # Record token usage
            self.token_tracker.record_usage(
                call_name=f"agent_safety_analysis_custom_iter{iteration}",
                model=self.model,
                usage=response.usage,
                estimated_input=estimated_tokens,
            )

            # Check if Claude wants to use tools
            if response.stop_reason == "tool_use":
                # Collect all tool_use blocks
                tool_uses = [b for b in response.content if hasattr(b, "type") and b.type == "tool_use"]

                if not tool_uses:
                    logger.warning("stop_reason=tool_use but no tool_use blocks found")
                    break

                logger.info(f"🔧 Claude requested {len(tool_uses)} search(es)")

                # Execute searches IN PARALLEL (Tavily best practice)
                search_tasks = []
                for tool_use in tool_uses:
                    query = tool_use.input.get("query", "")
                    search_type = tool_use.input.get("search_type", "general")
                    logger.info(f"   Search: {query[:60]}... (type={search_type})")
                    search_tasks.append(
                        self.search_service.search(query, search_type)
                    )

                # Run all searches in parallel
                results = await asyncio.gather(*search_tasks, return_exceptions=True)

                # Build tool results
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for tool_use, result in zip(tool_uses, results):
                    if isinstance(result, Exception):
                        content = f"Search failed: {result}"
                        logger.warning(f"Search failed: {result}")
                    else:
                        content = result
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": content,
                    })
                messages.append({"role": "user", "content": tool_results})

            else:
                # Claude is done (stop_reason = "end_turn" or "max_tokens")
                logger.info(f"✅ Claude finished after {iteration} iteration(s)")
                break

        # Log search usage summary
        if self.search_service:
            usage = self.search_service.get_usage_summary()
            logger.info(
                f"Search summary: {usage['total_searches']} searches, "
                f"{usage['cache_hits']} cache hits, ${usage['total_cost']:.4f}"
            )

        return self._parse_response(response)

    def _build_analysis_prompt_for_extracted_data(
        self,
        allergen_profile: List[str],
        pfas_database: List[Dict[str, Any]],
        allergen_database: List[Dict[str, Any]],
    ) -> str:
        """Build system prompt for safety analysis with extracted data."""
        prompt = """You are a product safety analysis expert. You have been provided with pre-extracted product information.

CRITICAL OUTPUT REQUIREMENT: You MUST respond with ONLY a valid JSON object.
- NO explanatory text before the JSON
- NO explanatory text after the JSON
- NO markdown code blocks (no ```json or ```)
- NO comments
- Start immediately with { and end with }

**Your Analysis Process:**
1. Review the provided product details (already extracted from the product page)
2. Use web_search strategically to research safety concerns:

   a) **MANUFACTURER SEARCH (IF INGREDIENTS/MATERIALS INCOMPLETE):**
      - Search: "[brand] [product name] official ingredients" OR "[brand] MSDS"
      - search_type: "manufacturer"
      - Goal: Find complete ingredient/material lists from official sources

   b) **REGULATORY SEARCH:**
      - Search: "[product name] recall FDA warning" OR "[brand] safety alert"
      - search_type: "regulatory"
      - Goal: Find recalls, FDA/EPA warnings, Health Canada advisories

   c) **PER-INGREDIENT RESEARCH (CRITICAL - DO THIS FOR CONCERNING INGREDIENTS):**
      - For EACH potentially concerning ingredient, search for its safety profile:
        - "[ingredient name] toxicity studies"
        - "[ingredient name] IARC classification carcinogen"
        - "[ingredient name] endocrine disruptor research"
        - "[ingredient name] EWG safety rating"
      - search_type: "ingredient"
      - Goal: Find scientific safety data for individual chemicals
      - PRIORITY ingredients to research:
        - Preservatives (phenoxyethanol, parabens, formaldehyde releasers)
        - Antioxidants (BHT, BHA)
        - Fragrance/parfum (phthalates concern)
        - Surfactants with "PEG" or "-eth" (contamination concerns)
        - Colorants/dyes (especially FD&C, CI numbers)
        - Any ingredient you don't recognize

   d) **LEGAL SEARCH (REQUIRED):**
      - Search: "[brand] [product] class action lawsuit" OR "[brand] settlement"
      - search_type: "legal"
      - Goal: Find documented lawsuits, settlements, regulatory fines
      - Lawsuits often reveal safety issues before official recalls

   e) **CONSUMER SEARCH (REQUIRED - real user experiences are critical):**
      - Search: "[brand] [product] reaction allergy breakout reddit"
      - search_type: "consumer"
      - Goal: Find real user reports of adverse reactions, skin issues, allergies
      - This data reveals problems that don't show up in official testing

**CRITICAL WEBSEARCH RESTRICTIONS:**
- DO NOT use consumer blogs, forums, review sites, or non-scientific health websites
- DO NOT use marketing materials or unverified sources
- ONLY use credible sources: .gov, .edu, manufacturer official sites, peer-reviewed journals, court records

**Output Format - YOUR ENTIRE RESPONSE MUST BE THIS JSON OBJECT:**
{
    "product_name": "string",
    "brand": "string",
    "retailer": "string",
    "ingredients": ["complete list from manufacturer website if found, else from product page"],
    "allergens_detected": [
        {
            "name": "allergen name (MUST match knowledge base below)",
            "severity": "low|moderate|high|severe",
            "source": "where found",
            "confidence": 0.0-1.0
        }
    ],
    "pfas_detected": [
        {
            "name": "PFAS compound (MUST match knowledge base below)",
            "cas_number": "CAS number if known",
            "body_effects": "effects on human body",
            "source": "where found",
            "confidence": 0.0-1.0
        }
    ],
    "other_concerns": [
        {
            "name": "concern name",
            "category": "under_investigation|carcinogen|regulatory_action|heavy_metal|endocrine_disruptor|other",
            "severity": "low|moderate|high|severe",
            "description": "brief description with source citation",
            "confidence": 0.0-1.0
        }
    ],
    "research_sources": [
        {"type": "manufacturer_website", "url": "...", "finding": "..."},
        {"type": "regulatory_action", "url": "...", "finding": "..."},
        {"type": "scientific_study", "url": "...", "finding": "..."}
    ],
    "confidence": 0.0-1.0
}

**CRITICAL CLASSIFICATION RULES - READ CAREFULLY:**

1. **ALLERGENS - ONLY substances in the Allergen Knowledge Base below can go in allergens_detected**
   - If you find an ingredient via websearch that is NOT in the Allergen Knowledge Base → DO NOT add to allergens_detected
   - Minor irritants (citric acid, fragrance, etc.) are NOT allergens unless listed in the knowledge base
   - If a substance causes irritation but is not a priority allergen → add to other_concerns with category="under_investigation", severity="low"

2. **PFAS - ONLY substances in the PFAS Knowledge Base below can go in pfas_detected**
   - If you find a chemical via websearch that is NOT in the PFAS Knowledge Base → DO NOT add to pfas_detected
   - Unknown fluorinated compounds → add to other_concerns with category="under_investigation"
   - Match by CAS number or exact name from the knowledge base

3. **OTHER CONCERNS - Use this for substances not in the knowledge bases**
   - category="under_investigation": Substances with credible evidence but not in our database (MUST have severity="low" max)
   - category="carcinogen": ONLY IARC-classified carcinogens (Groups 1, 2A, 2B) from credible sources
   - category="regulatory_action": ONLY substances with FDA recall, EPA warning, or class action lawsuit
   - category="heavy_metal", "endocrine_disruptor", "other": Other toxins with credible evidence

4. **EVIDENCE REQUIREMENTS for other_concerns:**
   - MUST have credible source (.gov, .edu, peer-reviewed journal, court record)
   - MUST NOT include unverified consumer complaints or blog posts
   - MUST include description with source citation (e.g., "IARC Group 2A carcinogen per iarc.who.int/2023")
"""

        # Add FULL allergen database (token-efficient format)
        if allergen_database:
            prompt += f"\n**ALLERGEN KNOWLEDGE BASE ({len(allergen_database)} priority allergens):**\n"
            prompt += "ONLY these substances can be classified as allergens. If a substance is not on this list, it is NOT an allergen.\n\n"
            for allergen in allergen_database:
                name = allergen.get('name', '')
                synonyms = allergen.get('synonyms', [])
                if synonyms:
                    prompt += f"- {name} (synonyms: {', '.join(synonyms[:3])})\n"  # Limit synonyms to 3
                else:
                    prompt += f"- {name}\n"

        # Add FULL PFAS database (token-efficient format)
        if pfas_database:
            prompt += f"\n**PFAS KNOWLEDGE BASE ({len(pfas_database)} compounds):**\n"
            prompt += "ONLY these substances can be classified as PFAS. If a substance is not on this list, it is NOT PFAS.\n\n"
            for pfas in pfas_database:
                name = pfas.get('name', '')
                cas = pfas.get('cas_number', '')
                if cas:
                    prompt += f"- {name} (CAS: {cas})\n"
                else:
                    prompt += f"- {name}\n"

        if allergen_profile:
            prompt += f"\n**User's Allergen Profile:**\nPay special attention to: {', '.join(allergen_profile)}\n"

        return prompt

    def _build_user_message_from_extracted_data(
        self, product_data: Dict[str, Any], product_url: str
    ) -> str:
        """Build user message from pre-extracted product data."""
        message = f"""Analyze this product for harmful substances:

**Product Information (pre-extracted from webpage):**
- Product Name: {product_data.get('product_name', 'Unknown')}
- Brand: {product_data.get('brand', 'Unknown')}
- URL: {product_url}

**Ingredients:**
{self._format_list(product_data.get('ingredients', []))}

**Materials:**
{self._format_list(product_data.get('materials', []))}

**Features:**
{self._format_list(product_data.get('features', []))}

**Warnings:**
{self._format_list(product_data.get('warnings', []))}

**Description:**
{product_data.get('description', 'None provided')}

**Your Analysis Task:**
**DO NOT use web_fetch** - Product information has already been extracted above.

**REQUIRED SEARCHES (do ALL of these):**
1. **Manufacturer search** (search_type="manufacturer"): Find official ingredient lists if incomplete above
2. **Regulatory search** (search_type="regulatory"): Find FDA/EPA/Health Canada recalls, warnings
3. **Per-ingredient searches** (search_type="ingredient"): Research 3-5 concerning ingredients individually
   - Focus on: preservatives, fragrance, BHT/BHA, PEG compounds, dyes
   - Search: "[ingredient] toxicity" or "[ingredient] IARC classification"
4. **Legal search** (search_type="legal"): Find class action lawsuits, settlements against this brand/product
5. **Consumer search** (search_type="consumer"): Find Reddit user reports of reactions, allergies, breakouts

After completing ALL searches, cross-reference findings with the knowledge bases and return the JSON analysis.

**CRITICAL:** Your response must be ONLY the JSON object. No text before it, no text after it."""
        return message

    def _format_list(self, items: List[str]) -> str:
        """Format list as numbered items."""
        if not items:
            return "None listed"
        return "\n".join([f"{i+1}. {item}" for i, item in enumerate(items)])

    async def find_alternatives(
        self, product_analysis: Dict[str, Any], max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Find safer alternative products (placeholder for Phase 4)."""
        # Will implement in Phase 4
        return []

    async def close(self) -> None:
        """Close HTTP client and search service."""
        await self.http_client.aclose()
        if self.search_service:
            await self.search_service.close()
