"""Claude Agent for product safety analysis."""

import json
from typing import Dict, Any, List, Optional
from anthropic import Anthropic
from ..infrastructure.config import settings


class ProductSafetyAgent:
    """Claude Agent that analyzes products for harmful substances."""

    def __init__(self) -> None:
        """Initialize the Claude Agent."""
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"

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

        # Call Claude with tools
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            tools=[
                {
                    "name": "web_fetch",
                    "description": "Fetch and extract content from a URL",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "URL to fetch"},
                        },
                        "required": ["url"],
                    },
                },
                {
                    "name": "web_search",
                    "description": "Search the web for information",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query",
                            },
                        },
                        "required": ["query"],
                    },
                },
            ],
        )

        # Parse the response and extract analysis
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
1. Use web_fetch to retrieve the product page content
2. Extract product information: name, brand, ingredients list
3. Query the provided allergen and PFAS databases to match ingredients
4. Identify any harmful substances with confidence levels
5. Return a structured JSON analysis

**Output Format:**
Return your analysis as a JSON object with this exact structure:
{
    "product_name": "string",
    "brand": "string",
    "retailer": "string",
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
            "name": "PFAS compound name",
            "cas_number": "CAS number if known",
            "body_effects": "description of effects on human body",
            "source": "where found",
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

**Databases Available:**
"""
        # Add allergen database info
        if allergen_database:
            prompt += f"\n**Allergen Database ({len(allergen_database)} entries):**\n"
            for allergen in allergen_database[:10]:  # Show first 10 as examples
                prompt += f"- {allergen.get('name')}: synonyms {allergen.get('synonyms', [])}\n"

        # Add PFAS database info
        if pfas_database:
            prompt += f"\n**PFAS Database ({len(pfas_database)} entries):**\n"
            for pfas in pfas_database[:10]:  # Show first 10 as examples
                prompt += f"- {pfas.get('name')} (CAS: {pfas.get('cas_number', 'unknown')}): {pfas.get('body_effects', 'No description')}\n"

        # Add user allergen profile if provided
        if allergen_profile:
            prompt += f"\n**User's Allergen Profile:**\nPay special attention to these allergens: {', '.join(allergen_profile)}\n"

        prompt += """
**Important Guidelines:**
- Be conservative: if uncertain, report the risk with lower confidence
- Check synonyms and alternate names for allergens/PFAS
- Look for ingredients in descriptions, specifications, and reviews
- If ingredients are not listed, note low confidence
- Common PFAS indicators: "non-stick", "water-resistant", "stain-resistant"
"""
        return prompt

    def _build_user_message(self, product_url: str) -> str:
        """Build the user message for Claude."""
        return f"""Analyze this product for harmful substances: {product_url}

Use web_fetch to retrieve the product page and extract all relevant information.
Return your analysis as structured JSON following the format provided in the system prompt."""

    def _parse_response(self, response: Any) -> Dict[str, Any]:
        """Parse Claude's response and extract analysis JSON.

        Args:
            response: Anthropic API response

        Returns:
            Parsed analysis dict
        """
        # Extract text content from response
        content = response.content

        # Look for JSON in the response
        for block in content:
            if hasattr(block, "text"):
                text = block.text
                # Try to parse JSON from the text
                try:
                    # Find JSON block (could be in code fence or plain)
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
                        json_str = text[json_start:json_end]

                    analysis = json.loads(json_str)
                    return analysis
                except (json.JSONDecodeError, ValueError) as e:
                    # If parsing fails, return minimal structure
                    return {
                        "product_name": "Unknown",
                        "brand": "Unknown",
                        "retailer": "Unknown",
                        "ingredients": [],
                        "allergens_detected": [],
                        "pfas_detected": [],
                        "other_concerns": [],
                        "confidence": 0.1,
                        "error": f"Failed to parse response: {str(e)}",
                    }

        # If no text block found, return error
        return {
            "product_name": "Unknown",
            "brand": "Unknown",
            "retailer": "Unknown",
            "ingredients": [],
            "allergens_detected": [],
            "pfas_detected": [],
            "other_concerns": [],
            "confidence": 0.0,
            "error": "No analysis content in response",
        }

    async def find_alternatives(
        self, product_analysis: Dict[str, Any], max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Find safer alternative products.

        Args:
            product_analysis: Analysis of the original product
            max_results: Maximum number of alternatives to return

        Returns:
            List of alternative product dicts
        """
        product_name = product_analysis.get("product_name", "")
        product_category = product_analysis.get("retailer", "")

        search_query = f"safer alternative to {product_name} without harmful chemicals allergen-free"

        # Use Claude to search for alternatives
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": f"""Find {max_results} safer alternatives to this product:
Product: {product_name}
Category: {product_category}

Search for products that:
1. Don't contain the harmful substances found in the original
2. Are readily available on Amazon or similar retailers
3. Have good safety ratings

Return as JSON array:
[
    {{
        "product_name": "string",
        "product_url": "string",
        "brand": "string",
        "reason": "why this is safer"
    }}
]

Use web_search if needed to find current products.""",
                }
            ],
            tools=[
                {
                    "name": "web_search",
                    "description": "Search the web for information",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                        },
                        "required": ["query"],
                    },
                }
            ],
        )

        # Parse alternatives from response
        # For now, return empty list (will implement after testing main analysis)
        return []
