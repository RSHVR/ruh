"""Pydantic schemas for Claude structured outputs (GA).

These schemas are used with the Anthropic structured outputs API to guarantee
valid JSON responses from Claude calls. The schemas define the exact
structure that Claude will output - no parsing errors possible.

Usage with .parse() convenience method:
    response = client.messages.parse(
        model="claude-sonnet-4-5-20250929",
        output_format=ProductExtraction,
        ...
    )

Usage with .create() + output_config:
    from anthropic import transform_schema

    response = client.messages.create(
        output_config={
            "format": {
                "type": "json_schema",
                "schema": transform_schema(ProductSafetyAnalysis),
            }
        },
        ...
    )
"""

from enum import Enum
from typing import List
from pydantic import BaseModel, Field, field_validator


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


# =============================================================================
# PRODUCT SAFETY ANALYSIS SCHEMA (Agent output)
# =============================================================================

class ConcernCategory(str, Enum):
    """Category for safety concerns found by agent research."""
    under_investigation = "under_investigation"
    carcinogen = "carcinogen"
    regulatory_action = "regulatory_action"
    heavy_metal = "heavy_metal"
    endocrine_disruptor = "endocrine_disruptor"
    other = "other"


class SourceType(str, Enum):
    """Type of research source found by agent."""
    manufacturer_website = "manufacturer_website"
    regulatory_action = "regulatory_action"
    scientific_study = "scientific_study"
    legal = "legal"
    consumer = "consumer"
    other = "other"  # catch-all so a citation label never invalidates an analysis


class AllergenDetected(BaseModel):
    """An allergen found during product safety analysis."""
    name: str = Field(description="Allergen name matching knowledge base")
    severity: SeverityType = Field(description="Severity level")
    source: str = Field(default="", description="Where this allergen was found")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class PfasDetected(BaseModel):
    """A PFAS compound found during product safety analysis."""
    name: str = Field(description="PFAS compound name matching knowledge base")
    cas_number: str = Field(default="", description="CAS registry number if known")
    body_effects: str = Field(default="", description="Effects on human body")
    source: str = Field(default="", description="Where this PFAS was found")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("cas_number", mode="before")
    @classmethod
    def _coerce_cas(cls, v):
        # Models often emit null when the CAS number is unknown — coerce to "".
        return "" if v is None else str(v)


class OtherConcern(BaseModel):
    """A non-allergen, non-PFAS safety concern."""
    name: str = Field(description="Concern name")
    category: ConcernCategory = Field(description="Concern category")
    severity: SeverityType = Field(description="Severity level")
    description: str = Field(default="", description="Brief description with source citation")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


# Common source-type variants the models emit, normalised to the SourceType enum.
_SOURCE_TYPE_ALIASES = {
    "consumer_report": "consumer", "consumer_reports": "consumer",
    "consumer_complaint": "consumer", "reddit": "consumer",
    "legal_action": "legal", "lawsuit": "legal", "court_record": "legal",
    "manufacturer": "manufacturer_website", "official": "manufacturer_website",
    "regulatory": "regulatory_action", "fda": "regulatory_action",
    "scientific": "scientific_study", "study": "scientific_study",
    "research": "scientific_study", "pubmed": "scientific_study",
}


class ResearchSource(BaseModel):
    """A source found during agent web research."""
    type: SourceType = Field(default=SourceType.other, description="Type of source")
    url: str = Field(default="", description="Source URL")
    finding: str = Field(default="", description="Key finding from this source")

    # Source type is descriptive citation metadata, not a safety signal — it must
    # never invalidate an otherwise-valid analysis. Normalise common variants and
    # fall back to "other" for anything unrecognised, instead of raising.
    @field_validator("type", mode="before")
    @classmethod
    def _normalize_type(cls, v):
        if isinstance(v, SourceType):
            return v
        s = str(v or "").strip().lower()
        s = _SOURCE_TYPE_ALIASES.get(s, s)
        return s if s in {e.value for e in SourceType} else SourceType.other.value


class ProductSafetyAnalysis(BaseModel):
    """Complete product safety analysis output from the Claude agent.

    Used for Pydantic validation of agent responses. Can also be used
    with structured outputs via transform_schema() for constrained decoding.
    """
    product_name: str = Field(default="", description="Full product name")
    brand: str = Field(default="", description="Brand or manufacturer")
    retailer: str = Field(default="", description="Retailer (e.g., Amazon)")
    ingredients: List[str] = Field(
        default_factory=list,
        description="Complete ingredient list"
    )

    @field_validator("ingredients", mode="before")
    @classmethod
    def _coerce_ingredients(cls, v):
        """Accept a comma-separated string for this metadata echo field.

        Models (measured: command-a-plus, 2026-06-10) sometimes emit the
        ingredient list as one comma-joined string. The field is citation-grade
        metadata, not a graded safety output — coerce instead of discarding an
        otherwise-valid analysis (same precedent as SourceType/cas_number)."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        if v is None:
            return []
        return v

    allergens_detected: List[AllergenDetected] = Field(
        default_factory=list,
        description="Allergens found (must match knowledge base)"
    )
    pfas_detected: List[PfasDetected] = Field(
        default_factory=list,
        description="PFAS compounds found (must match knowledge base)"
    )
    other_concerns: List[OtherConcern] = Field(
        default_factory=list,
        description="Other safety concerns with evidence"
    )
    research_sources: List[ResearchSource] = Field(
        default_factory=list,
        description="Sources consulted during research"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Overall analysis confidence"
    )
