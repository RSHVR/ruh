"""Claude Query service for structured data extraction."""

import json
import logging
from typing import Dict, Any
from anthropic import Anthropic

from .config import settings
from ..domain.models import ScrapedProduct

logger = logging.getLogger(__name__)


class ClaudeQueryService:
    """Service for querying Claude to extract structured data from HTML.

    This is a separate, lightweight Claude call focused purely on data extraction.
    No web tools, no analysis - just HTML → JSON parsing.
    """

    def __init__(self):
        """Initialize Claude Query service."""
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = "claude-sonnet-4-5-20250929"

    async def extract_product_data(self, scraped_html: ScrapedProduct) -> Dict[str, Any]:
        """Extract structured product data from raw HTML.

        Args:
            scraped_html: ScrapedProduct with raw_html_product populated

        Returns:
            Structured product data dictionary with extracted fields
        """
        if scraped_html.confidence < 0.3:
            logger.warning("Low confidence scrape, skipping extraction")
            return {"error": "Scraping failed", "confidence": 0.0}

        system_prompt = self._build_extraction_prompt()
        user_message = self._build_html_message(scraped_html)

        logger.info("📊 CLAUDE QUERY START: Calling Claude to extract product data from HTML")
        logger.info(f"   Original HTML size: {len(scraped_html.raw_html_product) / 1024:.1f}KB")
        logger.info(f"   Message size after processing: {len(user_message) / 1024:.1f}KB")

        # Call Claude - NO TOOLS, just extraction
        try:
            logger.info("📊 CLAUDE QUERY API CALL: Sending request to Anthropic...")
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,  # Small - just need structured output
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                # NO TOOLS - pure extraction
            )
            logger.info("📊 CLAUDE QUERY API SUCCESS: Received response from Anthropic")

            # Log usage
            logger.info(f"📊 CLAUDE QUERY TOKENS: Input={response.usage.input_tokens}, Output={response.usage.output_tokens}")

            # Parse JSON response
            extracted_data = self._parse_json_response(response)

            logger.info(f"✅ CLAUDE QUERY COMPLETE: Extracted product '{extracted_data.get('product_name', 'Unknown')}'")
            logger.info(f"   Ingredients: {len(extracted_data.get('ingredients', []))}")
            logger.info(f"   Materials: {len(extracted_data.get('materials', []))}")

        except Exception as e:
            logger.error(f"❌ CLAUDE QUERY FAILED: {type(e).__name__}: {str(e)}")
            raise

        return extracted_data

    async def extract_review_insights(self, scraped_html: ScrapedProduct) -> Dict[str, Any]:
        """Extract consumer insights from reviews and Q&A HTML.

        Args:
            scraped_html: ScrapedProduct with raw_html_reviews populated

        Returns:
            Structured consumer insights dictionary
        """
        if not scraped_html.has_reviews or len(scraped_html.raw_html_reviews) < 100:
            logger.info("No reviews data to extract")
            return {"error": "No reviews available", "confidence": 0.0}

        system_prompt = self._build_reviews_extraction_prompt()
        user_message = self._build_reviews_message(scraped_html)

        logger.info("💬 Calling Claude Query to extract consumer insights from reviews/Q&A")
        logger.info(f"   Reviews HTML size: {len(scraped_html.raw_html_reviews) / 1024:.1f}KB")

        # Call Claude - NO TOOLS
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1536,  # Larger for review analysis
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        logger.info(f"Claude Query (reviews) usage: {response.usage}")

        # Parse response
        insights = self._parse_json_response(response)

        logger.info(f"✅ Extracted review insights")
        logger.info(f"   Common complaints: {len(insights.get('common_complaints', []))}")
        logger.info(f"   Health concerns: {len(insights.get('health_concerns', []))}")

        return insights

    def _build_extraction_prompt(self) -> str:
        """Build system prompt for HTML extraction."""
        return """You are a data extraction expert. Your job is to parse HTML from product pages and extract structured product information.

**Your Task:**
Parse the provided HTML and extract product details into a clean JSON structure.

**Output Format:**
Return ONLY a JSON object (no explanation text) with this structure:
{
    "product_name": "string",
    "brand": "string",
    "price": "string (with currency)",
    "availability": "string",
    "ingredients": ["ingredient1", "ingredient2", ...],
    "materials": ["material1", "material2", ...],
    "features": ["feature1", "feature2", ...],
    "description": "string (product description)",
    "specifications": {
        "key": "value",
        ...
    },
    "warnings": ["warning1", "warning2", ...],
    "confidence": 0.0-1.0
}

**Extraction Guidelines:**
- For ingredients: Look for "Ingredients:", "Contains:", ingredient lists
- For materials: Look for material composition, coating info (e.g., "PTFE coating", "100% cotton")
- For features: Extract bullet points, key features
- For warnings: Extract any warning text, disclaimers, or safety notices
- Set confidence based on how complete the extraction is (0.0 = no data, 1.0 = complete)
- If a field is not found, use empty string "" or empty array []
- DO NOT include any text outside the JSON object
"""

    def _build_reviews_extraction_prompt(self) -> str:
        """Build system prompt for reviews extraction."""
        return """You are a consumer review analysis expert. Your job is to parse HTML from product reviews and Q&A sections and extract key consumer insights, especially health-related complaints.

**Your Task:**
Parse the provided HTML and extract structured insights about consumer experiences.

**Output Format:**
Return ONLY a JSON object (no explanation text) with this structure:
{
    "overall_sentiment": "positive|mixed|negative",
    "total_reviews_analyzed": number,
    "rating_distribution": {
        "5_star": number,
        "4_star": number,
        "3_star": number,
        "2_star": number,
        "1_star": number
    },
    "common_complaints": [
        {
            "complaint": "string (description)",
            "frequency": "rare|occasional|common|frequent",
            "severity": "low|moderate|high",
            "examples": ["quote1", "quote2"]
        }
    ],
    "health_concerns": [
        {
            "concern": "string (e.g., 'skin rash', 'allergic reaction', 'irritation')",
            "frequency": "rare|occasional|common|frequent",
            "severity": "low|moderate|high|severe",
            "examples": ["quote1", "quote2"]
        }
    ],
    "positive_feedback": [
        {
            "aspect": "string (what people liked)",
            "frequency": "rare|occasional|common|frequent"
        }
    ],
    "questions_concerns": [
        {
            "question": "string (from Q&A)",
            "category": "safety|ingredients|usage|other",
            "answered": boolean
        }
    ],
    "verified_purchase_ratio": 0.0-1.0,
    "confidence": 0.0-1.0
}

**Extraction Guidelines:**
- FOCUS on health-related complaints: rashes, irritation, allergic reactions, burns, sensitivities
- Extract actual quotes from reviews as examples
- Categorize frequency based on how often the issue is mentioned
- Pay attention to critical (1-2 star) reviews for safety issues
- Analyze Q&A for safety-related questions
- Note if complaints come from verified purchases (more trustworthy)
- Set confidence based on sample size and clarity
"""

    def _build_html_message(self, scraped: ScrapedProduct) -> str:
        """Build user message with HTML."""
        # Limit HTML size to prevent 400 errors (max ~100KB or 25k tokens)
        max_chars = 100000  # 100KB limit
        html_content = scraped.raw_html_product
        if len(html_content) > max_chars:
            logger.warning(f"⚠️  HTML too large ({len(html_content)} chars), truncating to {max_chars} chars")
            html_content = html_content[:max_chars] + "\n\n[... HTML truncated due to size ...]"

        return f"""Extract product information from this HTML:

URL: {scraped.url}
Retailer: {scraped.retailer}

HTML Content:
{html_content}

Return the structured JSON object."""

    def _build_reviews_message(self, scraped: ScrapedProduct) -> str:
        """Build user message with reviews HTML."""
        # Limit reviews HTML size to prevent 400 errors
        max_chars = 150000  # 150KB limit (reviews need more space)
        reviews_content = scraped.raw_html_reviews
        if len(reviews_content) > max_chars:
            logger.warning(f"⚠️  Reviews HTML too large ({len(reviews_content)} chars), truncating to {max_chars} chars")
            reviews_content = reviews_content[:max_chars] + "\n\n[... Reviews truncated due to size ...]"

        return f"""Extract consumer insights from these product reviews and Q&A:

URL: {scraped.url}
Retailer: {scraped.retailer}

Reviews & Q&A HTML Content:
{reviews_content}

Return the structured JSON object with consumer insights."""

    def _parse_json_response(self, response: Any) -> Dict[str, Any]:
        """Parse Claude's JSON response.

        Args:
            response: Anthropic API response

        Returns:
            Parsed JSON dictionary
        """
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text.strip()

                # Try to extract JSON
                try:
                    # Remove markdown if present
                    if "```json" in text:
                        text = text.split("```json")[1].split("```")[0].strip()
                    elif "```" in text:
                        text = text.split("```")[1].split("```")[0].strip()

                    # Find JSON object
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    if start != -1 and end > start:
                        json_str = text[start:end]
                        return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON: {e}")
                    logger.debug(f"Raw text: {text[:500]}")

        return {"error": "Failed to extract JSON", "confidence": 0.0}
