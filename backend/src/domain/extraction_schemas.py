"""Pydantic schemas for Claude structured outputs.

These schemas are used with the Anthropic structured outputs beta to guarantee
valid JSON responses from Claude extraction calls. The schemas define the exact
structure that Claude will output - no parsing errors possible.

Usage:
    from anthropic import transform_schema

    response = client.beta.messages.create(
        betas=["structured-outputs-2025-11-13"],
        output_format={
            "type": "json_schema",
            "schema": transform_schema(ProductExtraction),
        },
        ...
    )
"""

from enum import Enum
from typing import List
from pydantic import BaseModel, Field


# =============================================================================
# PRODUCT EXTRACTION SCHEMA
# =============================================================================

class Specification(BaseModel):
    """A single product specification as key-value pair.

    We use an array of these instead of a dynamic object because
    structured outputs require additionalProperties: false.
    """
    key: str = Field(description="Specification name (e.g., 'Weight', 'Dimensions')")
    value: str = Field(description="Specification value (e.g., '2 lbs', '10x5x3 inches')")


class ProductExtraction(BaseModel):
    """Structured product data extracted from HTML.

    This schema is used by ClaudeQueryService.extract_product_data() to
    guarantee valid JSON output from Claude.
    """
    product_name: str = Field(default="", description="Full product name/title")
    brand: str = Field(default="", description="Brand or manufacturer name")
    price: str = Field(default="", description="Price with currency (e.g., '$29.99')")
    availability: str = Field(default="", description="Stock status (e.g., 'In Stock', 'Out of Stock')")

    ingredients: List[str] = Field(
        default_factory=list,
        description="List of ingredients (for food, cosmetics, etc.)"
    )
    materials: List[str] = Field(
        default_factory=list,
        description="List of materials (e.g., 'PTFE coating', '100% cotton', 'BPA-free plastic')"
    )
    features: List[str] = Field(
        default_factory=list,
        description="Product features and bullet points"
    )

    description: str = Field(default="", description="Product description text")

    specifications: List[Specification] = Field(
        default_factory=list,
        description="Technical specifications as key-value pairs"
    )

    warnings: List[str] = Field(
        default_factory=list,
        description="Warning text, disclaimers, safety notices"
    )

    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Extraction confidence (0.0 = no data found, 1.0 = complete extraction)"
    )


# =============================================================================
# REVIEW INSIGHTS EXTRACTION SCHEMA
# =============================================================================

class SentimentType(str, Enum):
    """Overall sentiment classification."""
    positive = "positive"
    mixed = "mixed"
    negative = "negative"


class FrequencyType(str, Enum):
    """How often an issue is mentioned in reviews."""
    rare = "rare"
    occasional = "occasional"
    common = "common"
    frequent = "frequent"


class SeverityType(str, Enum):
    """Severity level of complaints/concerns."""
    low = "low"
    moderate = "moderate"
    high = "high"
    severe = "severe"


class CategoryType(str, Enum):
    """Category for Q&A questions."""
    safety = "safety"
    ingredients = "ingredients"
    usage = "usage"
    other = "other"


class Complaint(BaseModel):
    """A common complaint from reviews."""
    complaint: str = Field(description="Description of the complaint")
    frequency: FrequencyType = Field(description="How often this complaint appears")
    severity: SeverityType = Field(description="Severity of the issue")
    examples: List[str] = Field(
        default_factory=list,
        description="Actual quotes from reviews mentioning this complaint"
    )


class HealthConcern(BaseModel):
    """A health-related concern from reviews (rashes, allergies, etc.)."""
    concern: str = Field(description="Description of health concern (e.g., 'skin rash', 'allergic reaction')")
    frequency: FrequencyType = Field(description="How often this concern appears")
    severity: SeverityType = Field(description="Severity of the health issue")
    examples: List[str] = Field(
        default_factory=list,
        description="Actual quotes from reviews mentioning this concern"
    )


class PositiveFeedback(BaseModel):
    """Positive feedback aspect from reviews."""
    aspect: str = Field(description="What people liked about the product")
    frequency: FrequencyType = Field(description="How often this positive aspect is mentioned")


class QuestionConcern(BaseModel):
    """A question or concern from the Q&A section."""
    question: str = Field(description="The question asked by customers")
    category: CategoryType = Field(description="Category of the question")
    answered: bool = Field(description="Whether the question was answered")


class RatingDistribution(BaseModel):
    """Distribution of star ratings."""
    star_5: int = Field(default=0, description="Number of 5-star reviews")
    star_4: int = Field(default=0, description="Number of 4-star reviews")
    star_3: int = Field(default=0, description="Number of 3-star reviews")
    star_2: int = Field(default=0, description="Number of 2-star reviews")
    star_1: int = Field(default=0, description="Number of 1-star reviews")


class ReviewInsightsExtraction(BaseModel):
    """Consumer insights extracted from product reviews and Q&A.

    This schema is used by ClaudeQueryService.extract_review_insights() to
    guarantee valid JSON output from Claude.
    """
    overall_sentiment: SentimentType = Field(description="Overall sentiment of reviews")

    total_reviews_analyzed: int = Field(
        default=0,
        description="Approximate number of reviews analyzed"
    )

    rating_distribution: RatingDistribution = Field(
        default_factory=RatingDistribution,
        description="Distribution of star ratings"
    )

    common_complaints: List[Complaint] = Field(
        default_factory=list,
        description="Common complaints and negative feedback"
    )

    health_concerns: List[HealthConcern] = Field(
        default_factory=list,
        description="Health-related concerns (rashes, allergies, irritation, etc.)"
    )

    positive_feedback: List[PositiveFeedback] = Field(
        default_factory=list,
        description="Positive aspects mentioned by reviewers"
    )

    questions_concerns: List[QuestionConcern] = Field(
        default_factory=list,
        description="Questions and concerns from Q&A section"
    )

    verified_purchase_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Ratio of verified purchase reviews (0.0 to 1.0)"
    )

    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Extraction confidence (0.0 = poor data, 1.0 = high quality extraction)"
    )
