"""Claude Agent for product safety analysis."""

import json
from typing import Dict, Any, List, Optional
import httpx
from anthropic import Anthropic
from ..infrastructure.config import settings


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

        # Tool definitions
        tools = [
            {
                "name": "web_fetch",
                "description": "Fetch and extract content from a URL. Returns the HTML content of the page.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch"},
                    },
                    "required": ["url"],
                },
            },
        ]

        # Start conversation with Claude
        messages = [{"role": "user", "content": user_message}]

        # Tool calling loop (max 5 iterations)
        for iteration in range(5):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=tools,
            )

            # Check if Claude wants to use tools
            if response.stop_reason == "tool_use":
                # Process tool calls
                tool_results = []
                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_name = content_block.name
                        tool_input = content_block.input
                        tool_use_id = content_block.id

                        # Execute the tool
                        if tool_name == "web_fetch":
                            result = await self._execute_web_fetch(tool_input["url"])
                        else:
                            result = {"error": f"Unknown tool: {tool_name}"}

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": json.dumps(result),
                        })

                # Add assistant's response and tool results to messages
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            elif response.stop_reason == "end_turn":
                # Claude is done, parse final response
                analysis = self._parse_response(response)
                return analysis
            else:
                # Unexpected stop reason
                break

        # If we hit max iterations or unexpected stop, return error
        return {
            "product_name": "Unknown",
            "brand": "Unknown",
            "retailer": "Unknown",
            "ingredients": [],
            "allergens_detected": [],
            "pfas_detected": [],
            "other_concerns": [],
            "confidence": 0.1,
            "error": "Analysis loop exceeded maximum iterations",
        }

    async def _execute_web_fetch(self, url: str) -> Dict[str, Any]:
        """Execute web fetch tool.

        Args:
            url: URL to fetch

        Returns:
            Dict with page content or error
        """
        try:
            # Browser-like headers to avoid bot detection
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Cache-Control": "max-age=0",
            }

            response = await self.http_client.get(url, headers=headers)
            response.raise_for_status()

            # Return HTML content (truncated to avoid token limits)
            content = response.text[:50000]  # Limit to ~50KB

            return {
                "success": True,
                "url": url,
                "status_code": response.status_code,
                "content": content,
                "content_length": len(content),
            }
        except Exception as e:
            return {
                "success": False,
                "url": url,
                "error": str(e),
            }

    def _build_system_prompt(
        self,
        allergen_profile: List[str],
        pfas_database: List[Dict[str, Any]],
        allergen_database: List[Dict[str, Any]],
    ) -> str:
        """Build the system prompt for Claude."""
        prompt = """You are a product safety analysis expert. Your job is to analyze products for harmful substances including allergens, PFAS (forever chemicals), and other toxins.

**Your Analysis Process:**
1. Use web_fetch to retrieve the product page content
2. Extract product information: name, brand, ingredients list, materials
3. Look for PFAS indicators: "non-stick", "PTFE", "Teflon", "water-resistant", "stain-resistant"
4. Match ingredients against known allergens and PFAS compounds
5. Return a structured JSON analysis

**IMPORTANT:** You MUST call web_fetch first to get the product page content before analyzing.

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

        # Add allergen database info if provided
        if allergen_database:
            prompt += f"\n**Known Allergens ({len(allergen_database)}):**\n"
            for allergen in allergen_database[:10]:
                synonyms = allergen.get("synonyms", [])
                prompt += f"- {allergen.get('name')}: synonyms {synonyms}\n"

        # Add PFAS database info if provided
        if pfas_database:
            prompt += f"\n**Known PFAS Compounds ({len(pfas_database)}):**\n"
            for pfas in pfas_database[:7]:
                prompt += f"- {pfas.get('name')} (CAS: {pfas.get('cas_number', 'N/A')}): {pfas.get('body_effects', 'No info')[:100]}...\n"

        # Add user allergen profile if provided
        if allergen_profile:
            prompt += f"\n**User's Allergen Profile:**\nPay special attention to: {', '.join(allergen_profile)}\n"

        return prompt

    def _build_user_message(self, product_url: str) -> str:
        """Build the user message for Claude."""
        return f"""Analyze this product for harmful substances: {product_url}

First, use web_fetch to retrieve the product page.
Then analyze the content and return your structured JSON analysis."""

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
