"""Claude Agent for product safety analysis."""

import json
import logging
import time
from typing import Dict, Any, List, Optional
import httpx
from anthropic import Anthropic, RateLimitError, APIError
from ..infrastructure.config import settings

logger = logging.getLogger(__name__)


class ProductSafetyAgent:
    """Claude Agent that analyzes products for harmful substances."""

    def __init__(self) -> None:
        """Initialize the Claude Agent."""
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"
        self.http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

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

        # Enable Claude's built-in web search and web fetch tools in parallel
        # Limit uses to prevent token overflow
        tools = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 5,  # Limit searches to prevent token overuse
            },
            {
                "type": "web_fetch_20250910",
                "name": "web_fetch",
                "max_uses": 3,  # Limit fetches to prevent token overuse
            },
        ]

        # Start conversation with Claude
        messages = [{"role": "user", "content": user_message}]

        logger.info(f"Calling Claude with web_search (max 2) and web_fetch (max 1) tools")

        # Claude handles tool use automatically - we just need to call the API
        # The API will execute web_search and web_fetch internally
        # tool_choice="auto" lets Claude decide when to use tools
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=tools,
                tool_choice={"type": "auto"},  # Claude decides when to use tools
                extra_headers={
                    "anthropic-beta": "web-fetch-2025-09-10"
                }
            )
        except RateLimitError as e:
            logger.error(f"❌ Rate limit exceeded in analyze_product: {e}")
            # Re-raise to be handled by caller
            raise
        except APIError as e:
            logger.error(f"❌ Claude API error in analyze_product: {e}")
            # Re-raise to be handled by caller
            raise

        # Log tool usage information
        logger.info(f"Claude response - Stop reason: {response.stop_reason}")
        logger.info(f"Claude response - Usage: {response.usage}")

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
   a) **PRIORITY 1:** Manufacturer's official website for complete ingredient lists
      - Search: "[brand] [product name] official ingredients" OR "[brand] official website"

   b) **PRIORITY 2:** Consumer reviews and reported health concerns
      - Search: "[product name] consumer reviews health concerns" OR "[product] skin reaction"

   c) **PRIORITY 3:** Safety warnings and regulatory actions
      - Search: "[product] recall FDA warning" OR "[product] safety alert"

   d) **PRIORITY 4:** Scientific studies and PFAS testing (if applicable)
      - Search: "[ingredient] safety study" OR "[product category] PFAS testing"

3. Cross-reference findings with the knowledge base provided below
4. Return a comprehensive structured JSON analysis

**CRITICAL:** Check if product data is already provided in the user message before calling web_fetch. Do NOT fetch if data is already available.

**Output Format:**
After fetching and analyzing the product page, return your analysis as a JSON object with this exact structure:
{
    "product_name": "string",
    "brand": "string",
    "retailer": "string (e.g., Amazon, Amazon.ca)",
    "ingredients": ["ingredient1", "ingredient2"],
    "allergens_detected": [
        {
            "name": "allergen name",
            "severity": "low|moderate|high|severe",
            "source": "where found in product",
            "confidence": 0.0-1.0
        }
    ],
    "pfas_detected": [
        {
            "name": "PFAS compound name (e.g., PTFE, PFOA)",
            "cas_number": "CAS number if known",
            "body_effects": "description of effects on human body",
            "source": "where found (e.g., non-stick coating)",
            "confidence": 0.0-1.0
        }
    ],
    "other_concerns": [
        {
            "name": "toxin name",
            "category": "heavy metal|carcinogen|endocrine disruptor|other",
            "severity": "low|moderate|high|severe",
            "description": "brief description",
            "confidence": 0.0-1.0
        }
    ],
    "confidence": 0.0-1.0
}

**PFAS Detection Guidelines:**
- Non-stick cookware often contains PTFE (Teflon) - this is PFAS
- "Water-resistant", "stain-resistant" products may have PFAS coatings
- Look for PTFE, PFOA, PFOS, GenX in materials or descriptions
- If ingredients aren't fully listed, note lower confidence

**Allergen Detection:**
- Check ingredient lists carefully
- Look in product descriptions and specifications
- Note synonyms (e.g., "fragrance" = "parfum")
"""

        # Add allergen database info if provided (limit to reduce tokens)
        if allergen_database:
            prompt += f"\n**Top Allergens ({min(5, len(allergen_database))}):**\n"
            for allergen in allergen_database[:5]:  # Only top 5 to save tokens
                prompt += f"- {allergen.get('name')}\n"

        # Add PFAS database info if provided (limit to reduce tokens)
        if pfas_database:
            prompt += f"\n**Top PFAS Compounds ({min(3, len(pfas_database))}):**\n"
            for pfas in pfas_database[:3]:  # Only top 3 to save tokens
                prompt += f"- {pfas.get('name')} (CAS: {pfas.get('cas_number', 'N/A')})\n"

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

        # Enable ONLY web_search (not web_fetch - we already have the product data!)
        tools = [
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 3,  # Limit to 3 searches: manufacturer site, reviews, safety data
            },
        ]

        messages = [{"role": "user", "content": user_message}]

        logger.info(f"🔍 Calling Claude Agent for safety analysis with web_search")
        logger.info(f"   Product: {product_data.get('product_name')}")

        # tool_choice="auto" lets Claude decide when to use web_search
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,  # Reduced from 4096
                system=system_prompt,
                messages=messages,
                tools=tools,
                tool_choice={"type": "auto"},  # Claude decides when to search
            )
        except RateLimitError as e:
            logger.error(f"❌ Rate limit exceeded in analyze_extracted_product: {e}")
            # Re-raise to be handled by caller (will fallback to database-only results)
            raise
        except APIError as e:
            logger.error(f"❌ Claude API error in analyze_extracted_product: {e}")
            # Re-raise to be handled by caller
            raise

        logger.info(f"Claude Agent usage: {response.usage}")
        logger.info(f"   Input tokens: {response.usage.input_tokens}")
        logger.info(f"   Output tokens: {response.usage.output_tokens}")

        # Parse analysis
        analysis = self._parse_response(response)
        return analysis

    def _build_analysis_prompt_for_extracted_data(
        self,
        allergen_profile: List[str],
        pfas_database: List[Dict[str, Any]],
        allergen_database: List[Dict[str, Any]],
    ) -> str:
        """Build system prompt for safety analysis with extracted data."""
        prompt = """You are a product safety analysis expert. You have been provided with pre-extracted product information.

**Your Analysis Process:**
1. Review the provided product details (already extracted from the product page)
2. Use web_search strategically (max 3 searches) to find:
   a) **SEARCH 1 (REQUIRED):** Manufacturer's official website for complete ingredient lists
      - Search: "[brand] [product name] official ingredients" OR "[brand] official website"
      - Look for manufacturer's product page, ingredient disclosure, or safety data

   b) **SEARCH 2 (REQUIRED):** Consumer reviews and health concerns
      - Search: "[product name] [brand] consumer reviews health concerns" OR "[product] skin reaction allergic"
      - Look for patterns of reported reactions, rashes, allergies, or complaints

   c) **SEARCH 3 (IF NEEDED):** Safety warnings or scientific studies
      - Search: "[product] recall FDA warning" OR "[ingredient] safety study PFAS"
      - Look for regulatory actions, recalls, scientific research on ingredients

**IMPORTANT:** Prioritize manufacturer website and consumer reviews. Only use the third search if critical safety data is missing.

**Output Format:**
Return JSON with this exact structure:
{
    "product_name": "string",
    "brand": "string",
    "retailer": "string",
    "ingredients": ["complete list from manufacturer website if found, else from product page"],
    "allergens_detected": [
        {
            "name": "allergen name",
            "severity": "low|moderate|high|severe",
            "source": "where found",
            "confidence": 0.0-1.0
        }
    ],
    "pfas_detected": [
        {
            "name": "PFAS compound (e.g., PTFE, PFOA)",
            "cas_number": "CAS number if known",
            "body_effects": "effects on human body",
            "source": "where found",
            "confidence": 0.0-1.0
        }
    ],
    "other_concerns": [
        {
            "name": "concern name",
            "category": "heavy metal|carcinogen|endocrine disruptor|other",
            "severity": "low|moderate|high|severe",
            "description": "brief description",
            "confidence": 0.0-1.0
        }
    ],
    "research_sources": [
        {"type": "manufacturer_website", "url": "...", "finding": "..."},
        {"type": "consumer_review", "url": "...", "finding": "..."},
        {"type": "safety_recall", "url": "...", "finding": "..."}
    ],
    "confidence": 0.0-1.0
}
"""

        # Add knowledge bases
        if allergen_database:
            prompt += f"\n**Known Allergens ({len(allergen_database)}):**\n"
            for allergen in allergen_database[:10]:
                synonyms = allergen.get("synonyms", [])
                prompt += f"- {allergen.get('name')}: synonyms {synonyms}\n"

        if pfas_database:
            prompt += f"\n**Known PFAS Compounds ({len(pfas_database)}):**\n"
            for pfas in pfas_database[:7]:
                prompt += f"- {pfas.get('name')} (CAS: {pfas.get('cas_number', 'N/A')}): {pfas.get('body_effects', 'No info')[:100]}\n"

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

1. Use web_search (ONLY) to find the manufacturer's official website for complete ingredient/material lists
2. Use web_search to find safety warnings, recalls, regulatory actions for this product
3. Use web_search to find consumer reviews mentioning health concerns or complaints (skin reactions, allergies, etc.)
4. Use web_search to find PFAS testing results for this product category (if applicable)
5. Cross-reference all findings with the provided knowledge bases
6. Provide comprehensive structured JSON analysis

**CRITICAL:** The product page has already been scraped. DO NOT call web_fetch. ONLY use web_search for external research.

**Focus your web_search on:
- "[brand] [product] official ingredients site:manufacturer-domain.com"
- "[product name] safety recall OR warning"
- "[product name] consumer complaints OR reactions OR rash"
- "[product category] PFAS contamination OR testing"
"""
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
        """Close HTTP client."""
        await self.http_client.aclose()
