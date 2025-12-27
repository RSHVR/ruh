"""Claude Query service for structured data extraction.

Uses Anthropic's structured outputs beta to guarantee valid JSON responses.
No more fragile regex-based JSON parsing!
"""

import json
import logging
from typing import Dict, Any

from anthropic import Anthropic

from .config import settings
from ..domain.models import ScrapedProduct
from ..domain.extraction_schemas import ProductExtraction, ReviewInsightsExtraction

logger = logging.getLogger(__name__)

# Structured outputs beta identifier
STRUCTURED_OUTPUTS_BETA = "structured-outputs-2025-11-13"


class ClaudeQueryService:
    """Service for querying Claude to extract structured data from HTML.

    This is a separate, lightweight Claude call focused purely on data extraction.
    No web tools, no analysis - just HTML → JSON parsing.

    Uses structured outputs to guarantee valid JSON matching our schemas.
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

        try:
            logger.info("📊 CLAUDE QUERY API CALL: Sending request with structured outputs...")

            # Use structured outputs beta for guaranteed valid JSON
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=2048,  # Increased for larger extractions without truncation
                betas=[STRUCTURED_OUTPUTS_BETA],
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                output_format={
                    "type": "json_schema",
                    "schema": ProductExtraction.model_json_schema(),
                },
            )

            logger.info("📊 CLAUDE QUERY API SUCCESS: Received response from Anthropic")
            logger.info(f"📊 CLAUDE QUERY TOKENS: Input={response.usage.input_tokens}, Output={response.usage.output_tokens}")

            # Handle special stop reasons
            extracted_data = self._handle_response(response, "product extraction")

            if "error" not in extracted_data:
                logger.info(f"✅ CLAUDE QUERY COMPLETE: Extracted product '{extracted_data.get('product_name', 'Unknown')}'")
                logger.info(f"   Ingredients: {len(extracted_data.get('ingredients', []))}")
                logger.info(f"   Materials: {len(extracted_data.get('materials', []))}")

            return extracted_data

        except Exception as e:
            logger.error(f"❌ CLAUDE QUERY FAILED: {type(e).__name__}: {str(e)}")
            raise

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

        try:
            # Use structured outputs beta for guaranteed valid JSON
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=3072,  # Larger for comprehensive review analysis
                betas=[STRUCTURED_OUTPUTS_BETA],
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                output_format={
                    "type": "json_schema",
                    "schema": ReviewInsightsExtraction.model_json_schema(),
                },
            )

            logger.info(f"Claude Query (reviews) usage: Input={response.usage.input_tokens}, Output={response.usage.output_tokens}")

            # Handle special stop reasons
            insights = self._handle_response(response, "review extraction")

            if "error" not in insights:
                logger.info(f"✅ Extracted review insights")
                logger.info(f"   Common complaints: {len(insights.get('common_complaints', []))}")
                logger.info(f"   Health concerns: {len(insights.get('health_concerns', []))}")

            return insights

        except Exception as e:
            logger.error(f"❌ REVIEW EXTRACTION FAILED: {type(e).__name__}: {str(e)}")
            raise

    def _handle_response(self, response, context: str) -> Dict[str, Any]:
        """Handle Claude response, checking for special stop reasons.

        Args:
            response: Anthropic API response
            context: Description of what we were extracting (for logging)

        Returns:
            Parsed JSON dictionary or error dict
        """
        # Check for refusal (safety concern)
        if response.stop_reason == "refusal":
            logger.warning(f"⚠️  Claude refused {context} - possible safety concern")
            return {"error": "Extraction refused by model", "confidence": 0.0}

        # Check for truncation
        if response.stop_reason == "max_tokens":
            logger.warning(f"⚠️  Response truncated during {context} - consider increasing max_tokens")
            return {"error": "Response truncated", "confidence": 0.0}

        # With structured outputs, the response is guaranteed valid JSON
        # No need for fragile regex extraction!
        if response.content and hasattr(response.content[0], "text"):
            text = response.content[0].text
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                # This should never happen with structured outputs
                logger.error(f"❌ Unexpected JSON parse error (structured outputs should prevent this): {e}")
                logger.debug(f"Raw text: {text[:500]}")
                return {"error": "JSON parse error", "confidence": 0.0}

        return {"error": "No content in response", "confidence": 0.0}

    def _build_extraction_prompt(self) -> str:
        """Build system prompt for HTML extraction.

        Note: With structured outputs, we don't need to specify the JSON format
        in the prompt - the schema handles that. We focus on extraction guidance.
        """
        return """You are a data extraction expert. Your job is to parse HTML from product pages and extract structured product information.

**Extraction Guidelines:**

1. **Product Name & Brand**: Extract the full product title and brand/manufacturer name.

2. **Ingredients**: Look for:
   - "Ingredients:" or "Contains:" sections
   - Ingredient lists (comma-separated or bulleted)
   - Active ingredients, inactive ingredients
   - Food ingredients, cosmetic ingredients, etc.

3. **Materials**: Look for:
   - Material composition (e.g., "100% cotton", "stainless steel")
   - Coating information (e.g., "PTFE coating", "ceramic non-stick")
   - Construction materials
   - "BPA-free", "lead-free", etc.

4. **Features**: Extract bullet points and key product features.

5. **Warnings**: Extract any:
   - Warning text and disclaimers
   - Safety notices
   - Allergy warnings
   - Age restrictions
   - Usage precautions

6. **Specifications**: Extract technical specifications as key-value pairs.

7. **Confidence**: Set based on extraction completeness:
   - 0.0-0.3: Little to no data found
   - 0.4-0.6: Partial extraction
   - 0.7-0.9: Good extraction with some gaps
   - 1.0: Complete extraction of all available data

If a field is not found in the HTML, use empty string or empty array as appropriate."""

    def _build_reviews_extraction_prompt(self) -> str:
        """Build system prompt for reviews extraction.

        Note: With structured outputs, we don't need to specify the JSON format
        in the prompt - the schema handles that. We focus on extraction guidance.
        """
        return """You are a consumer review analysis expert. Your job is to parse HTML from product reviews and Q&A sections and extract key consumer insights, especially health-related complaints.

**Extraction Focus:**

1. **Health Concerns** (HIGHEST PRIORITY):
   - Skin reactions: rashes, irritation, burns, redness
   - Allergic reactions: swelling, hives, breathing issues
   - Sensitivities: itching, tingling, discomfort
   - Adverse effects: headaches, nausea, dizziness
   - Extract actual quotes as examples

2. **Common Complaints**:
   - Quality issues
   - Performance problems
   - Durability concerns
   - Packaging issues

3. **Frequency Classification**:
   - rare: 1-2 mentions
   - occasional: 3-5 mentions
   - common: 6-10 mentions
   - frequent: 10+ mentions

4. **Severity Classification**:
   - low: Minor inconvenience
   - moderate: Significant issue but manageable
   - high: Serious problem affecting usability
   - severe: Safety concern or health impact

5. **Positive Feedback**: What do people like about the product?

6. **Q&A Section**: Safety-related questions, ingredient questions.

7. **Verified Purchases**: Note the ratio of verified vs unverified reviews (verified are more trustworthy).

8. **Confidence**: Based on:
   - Number of reviews analyzed
   - Clarity of review content
   - Consistency of complaints
   - 0.0-0.3: Few reviews or unclear data
   - 0.4-0.6: Moderate sample
   - 0.7-1.0: Good sample with clear patterns"""

    def _build_html_message(self, scraped: ScrapedProduct) -> str:
        """Build user message with HTML.

        Note: We no longer truncate HTML - our scraper already extracts only
        relevant sections (title, ingredients, materials, etc.) so the content
        is pre-filtered. Truncation was causing loss of important ingredient data.
        """
        html_content = scraped.raw_html_product
        html_size_kb = len(html_content) / 1024

        # Log size for monitoring but don't truncate
        if html_size_kb > 50:
            logger.warning(f"⚠️  Large HTML payload: {html_size_kb:.1f}KB - consider optimizing scraper selectors")
        else:
            logger.info(f"📊 HTML payload size: {html_size_kb:.1f}KB")

        return f"""Extract product information from this HTML:

URL: {scraped.url}
Retailer: {scraped.retailer}

HTML Content:
{html_content}"""

    def _build_reviews_message(self, scraped: ScrapedProduct) -> str:
        """Build user message with reviews HTML.

        Note: We no longer truncate reviews - our scraper extracts only review
        sections, and we want to capture all health concerns and complaints.
        """
        reviews_content = scraped.raw_html_reviews
        reviews_size_kb = len(reviews_content) / 1024

        # Log size for monitoring but don't truncate
        if reviews_size_kb > 100:
            logger.warning(f"⚠️  Large reviews payload: {reviews_size_kb:.1f}KB - consider pagination")
        else:
            logger.info(f"📊 Reviews payload size: {reviews_size_kb:.1f}KB")

        return f"""Extract consumer insights from these product reviews and Q&A:

URL: {scraped.url}
Retailer: {scraped.retailer}

Reviews & Q&A HTML Content:
{reviews_content}"""
