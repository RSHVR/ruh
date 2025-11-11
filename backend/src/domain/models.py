"""Domain models for Eject product safety analysis."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SeverityLevel(str, Enum):
    """Severity levels for allergens and toxins."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    SEVERE = "severe"


class AllergenDetection(BaseModel):
    """Detected allergen in a product."""

    name: str
    severity: SeverityLevel
    source: str  # Where it was found (e.g., "ingredients list")
    confidence: float = Field(ge=0.0, le=1.0)


class PFASDetection(BaseModel):
    """Detected PFAS compound in a product."""

    name: str
    cas_number: Optional[str] = None
    body_effects: str  # Detailed explanation of effects on human body
    source: str
    confidence: float = Field(ge=0.0, le=1.0)


class ToxinConcern(BaseModel):
    """Other toxin or harmful substance detected."""

    name: str
    category: str  # e.g., "heavy metal", "carcinogen", "endocrine disruptor"
    severity: SeverityLevel
    description: str
    confidence: float = Field(ge=0.0, le=1.0)


class ProductAnalysis(BaseModel):
    """Complete analysis of a product's safety."""

    id: Optional[UUID] = None
    product_url: str
    product_name: Optional[str] = None
    brand: Optional[str] = None
    retailer: Optional[str] = None
    ingredients: list[str] = []

    # Analysis results
    overall_score: int = Field(ge=0, le=100)  # 0=dangerous, 100=safe (inverted for clarity)
    allergens_detected: list[AllergenDetection] = []
    pfas_detected: list[PFASDetection] = []
    other_concerns: list[ToxinConcern] = []

    # Metadata
    confidence: float = Field(ge=0.0, le=1.0)
    analyzed_at: Optional[datetime] = None
    analysis_version: str = "1.0.0"
    claude_model: str = "claude-sonnet-4-5-20250929"

    @property
    def harm_score(self) -> int:
        """Calculate harm score (0-100, where 100 is most harmful)."""
        return 100 - self.overall_score

    @property
    def risk_level(self) -> str:
        """Get human-readable risk level."""
        harm = self.harm_score
        if harm <= 20:
            return "Safe"
        elif harm <= 40:
            return "Low Risk"
        elif harm <= 60:
            return "Moderate Risk"
        elif harm <= 80:
            return "High Risk"
        else:
            return "Dangerous"


class AlternativeProduct(BaseModel):
    """Safer alternative product recommendation."""

    id: Optional[UUID] = None
    product_url: str
    product_name: str
    brand: Optional[str] = None

    # Scores
    safety_score: int = Field(ge=0, le=100)
    safety_improvement: int  # Delta from original product
    price: Optional[float] = None
    price_difference: Optional[float] = None

    # Ranking
    rank: int = Field(ge=1, le=5)

    # Affiliate
    affiliate_link: Optional[str] = None
    affiliate_network: Optional[str] = None

    recommended_at: Optional[datetime] = None


class AnalysisRequest(BaseModel):
    """Request to analyze a product."""

    product_url: str
    user_id: Optional[UUID] = None  # Anonymous UUID from extension
    allergen_profile: list[str] = []  # User's known allergens
    force_refresh: bool = False  # Skip cache and re-analyze


class AnalysisResponse(BaseModel):
    """Response containing product analysis and alternatives."""

    analysis: ProductAnalysis
    alternatives: list[AlternativeProduct] = []
    cached: bool = False
    cache_age_seconds: Optional[int] = None
    url_hash: str = ""  # SHA256 hash of product URL for fetching reviews


class ScrapedProduct(BaseModel):
    """Raw scraped product data from e-commerce site."""

    url: str
    retailer: str

    # Product sections (for ingredient/material analysis)
    raw_html_product: str = ""

    # Reviews/Q&A sections (for consumer insights)
    raw_html_reviews: str = ""

    # Metadata
    raw_html_snippet: str = ""  # First 1KB for logging
    confidence: float
    scrape_method: str
    scraped_at: datetime
    has_reviews: bool = False
    error_message: Optional[str] = None


class HealthConcern(BaseModel):
    """Consumer health concern from reviews."""

    concern: str  # e.g., "skin rash", "allergic reaction"
    frequency: str  # "rare", "occasional", "common", "frequent"
    severity: str  # "low", "moderate", "high", "severe"
    examples: list[str]  # Actual review quotes


class CommonComplaint(BaseModel):
    """Common complaint from reviews."""

    complaint: str
    frequency: str
    severity: str
    examples: list[str]


class PositiveFeedback(BaseModel):
    """Positive feedback from reviews."""

    aspect: str
    frequency: str


class QuestionConcern(BaseModel):
    """Question/concern from Q&A section."""

    question: str
    category: str  # "safety", "ingredients", "usage", "other"
    answered: bool


class ReviewInsights(BaseModel):
    """Consumer insights extracted from reviews and Q&A."""

    url_hash: str
    product_url: str
    overall_sentiment: str  # "positive", "mixed", "negative"
    total_reviews_analyzed: int
    rating_distribution: dict[str, int]  # {"5_star": 100, "4_star": 20, ...}
    common_complaints: list[CommonComplaint]
    health_concerns: list[HealthConcern]
    positive_feedback: list[PositiveFeedback]
    questions_concerns: list[QuestionConcern]
    verified_purchase_ratio: float
    confidence: float
    analyzed_at: datetime
