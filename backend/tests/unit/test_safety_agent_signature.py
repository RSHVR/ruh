"""Pin the wrapper's signature to the route's call shape.

Regression: user_region was added to ProductSafetyAgent but not to
ProductSafetyAgentWrapper — every fresh analysis 500ed in prod
(TypeError: unexpected keyword argument) while unit tests passed, because
integration tests mock the agent. This test fails on any future drift
between what analyze.py passes and what the wrapper accepts.
"""

import inspect

from src.infrastructure.safety_agent import ProductSafetyAgentWrapper


def test_wrapper_accepts_route_kwargs_extracted():
    params = inspect.signature(
        ProductSafetyAgentWrapper.analyze_extracted_product
    ).parameters
    for kwarg in ("product_data", "product_url", "allergen_profile",
                  "pfas_database", "allergen_database", "user_region"):
        assert kwarg in params, f"wrapper.analyze_extracted_product missing {kwarg}"


def test_wrapper_accepts_route_kwargs_direct():
    params = inspect.signature(ProductSafetyAgentWrapper.analyze_product).parameters
    for kwarg in ("product_url", "allergen_profile", "pfas_database",
                  "allergen_database", "user_region"):
        assert kwarg in params, f"wrapper.analyze_product missing {kwarg}"
