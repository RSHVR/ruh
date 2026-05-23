"""Test product definitions for benchmark."""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BenchmarkProduct:
    """A product to test in the benchmark."""

    url: str
    product_name: str
    brand: str
    ingredients: List[str]
    category: str
    materials: List[str] = field(default_factory=list)
    features: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    description: str = ""
    confidence: float = 0.8

    def to_dict(self) -> dict:
        """Convert to dictionary format expected by agents."""
        return {
            "product_name": self.product_name,
            "brand": self.brand,
            "ingredients": self.ingredients,
            "materials": self.materials,
            "features": self.features,
            "warnings": self.warnings,
            "description": self.description,
            "confidence": self.confidence,
        }


# Default test products - User should update these with specific URLs
BENCHMARK_PRODUCTS: List[BenchmarkProduct] = [
    # Product 1: Skincare (existing baseline)
    BenchmarkProduct(
        url="https://www.amazon.ca/dp/B0BNW7WNLL",
        product_name="PatchRx Pimple Patches with Salicylic Acid (120 Pack)",
        brand="PatchRx",
        ingredients=["Salicylic Acid", "Tea Tree Oil (Melaleuca Alternifolia)", "Hydrocolloid"],
        category="skincare",
        features=["Propylene Glycol Free", "Paraben Free", "Cruelty Free"],
        description="Pimple patches with salicylic acid and tea tree oil",
    ),

    # Add more products below - user should provide specific Amazon URLs
    # Example structure:
    #
    # BenchmarkProduct(
    #     url="https://www.amazon.ca/dp/XXXXXXXXXX",
    #     product_name="Product Name",
    #     brand="Brand",
    #     ingredients=["Ingredient 1", "Ingredient 2"],
    #     category="food|skincare|cleaning|cookware|personal_care",
    # ),
]


def add_product(
    url: str,
    product_name: str,
    brand: str,
    ingredients: List[str],
    category: str,
    **kwargs,
) -> BenchmarkProduct:
    """Add a product to the benchmark suite.

    Args:
        url: Amazon product URL
        product_name: Full product name
        brand: Brand name
        ingredients: List of ingredients
        category: Product category (skincare, food, cleaning, etc.)
        **kwargs: Additional fields (materials, features, warnings, etc.)

    Returns:
        The created BenchmarkProduct
    """
    product = BenchmarkProduct(
        url=url,
        product_name=product_name,
        brand=brand,
        ingredients=ingredients,
        category=category,
        **kwargs,
    )
    BENCHMARK_PRODUCTS.append(product)
    return product


def load_products_from_json(json_path: str) -> List[BenchmarkProduct]:
    """Load products from a JSON file.

    Args:
        json_path: Path to JSON file with product definitions

    Returns:
        List of BenchmarkProduct instances
    """
    import json
    from pathlib import Path

    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Product file not found: {json_path}")

    with open(path) as f:
        data = json.load(f)

    products = []
    for item in data:
        products.append(BenchmarkProduct(**item))

    return products
