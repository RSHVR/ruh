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
                "max_uses": 2  # Reduced to avoid token limits
            },
            {
                "type": "web_fetch_20250910",
                "name": "web_fetch",
                "max_uses": 1  # Just one fetch of the product page
            }
        ]

        # Start conversation with Claude
        messages = [{"role": "user", "content": user_message}]

        logger.info(f"Calling Claude with web_search (max 2) and web_fetch (max 1) tools")

        # Claude handles tool use automatically - uses both tools in parallel
        # Add retry logic for rate limits
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=8192,  # Increased for tool results but still under 10k total
                    system=system_prompt,
                    messages=messages,
                    tools=tools,
                    extra_headers={
                        "anthropic-beta": "web-fetch-2025-09-10"
                    }
                )
                break  # Success, exit retry loop
            except RateLimitError as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Rate limit hit (429), retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Rate limit exceeded after {max_retries} attempts")
                    raise
            except APIError as e:
                if "overloaded" in str(e).lower() and attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"API overloaded (500), retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"API error: {e}")
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
1. Use web_fetch to retrieve the product page and extract product information (name, brand, ingredients, materials)
2. Use web_search to find:
   - Recent product recalls or safety warnings
   - Scientific studies on ingredient safety
   - Regulatory actions or warnings
   - PFAS contamination reports for this product category
3. Cross-reference findings with the knowledge base provided below
4. Return a comprehensive structured JSON analysis

**IMPORTANT:** Use BOTH web_fetch (for product page) AND web_search (for safety data) in parallel for the most accurate and comprehensive analysis.

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
        """Build the user message for Claude."""
        return f"""Analyze this product for harmful substances: {product_url}

1. Fetch the product page to get ingredients/materials
2. Search for the most critical safety concern (recall OR toxic ingredient)
3. Return concise JSON analysis

Keep searches focused to stay under token limits."""

    def _parse_response(self, response: Any) -> Dict[str, Any]:
        """Parse Claude's response and extract analysis JSON."""
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
                    return analysis

                except (json.JSONDecodeError, ValueError) as e:
                    # Return error structure
                    return {
                        "product_name": "Unknown",
                        "brand": "Unknown",
                        "retailer": "Unknown",
                        "ingredients": [],
                        "allergens_detected": [],
                        "pfas_detected": [],
                        "other_concerns": [],
                        "confidence": 0.1,
                        "error": f"Failed to parse JSON: {str(e)}. Raw text: {text[:500]}",
                    }

        # No text block found
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

    async def find_alternatives(
        self, product_analysis: Dict[str, Any], max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Find safer alternative products (placeholder for Phase 4)."""
        # Will implement in Phase 4
        return []

    async def close(self) -> None:
        """Close HTTP client."""
        await self.http_client.aclose()
