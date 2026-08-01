"""Both agent output schemas must declare the food-only origin block.

Guards the origin {summary, region, alert} schema + the food-only / active-alert
rule in both prompt variants. Builders are invoked with a dummy self (they don't
touch self).
"""

from types import SimpleNamespace

from src.infrastructure.claude_agent import ProductSafetyAgent

_DUMMY = SimpleNamespace()


def _assert_origin_schema(prompt: str):
    assert '"origin"' in prompt
    assert '"summary"' in prompt
    assert '"region"' in prompt
    assert '"alert"' in prompt
    # food-only framing
    assert "FOOD" in prompt.upper()
    # active advisory / outbreak-recall rule present
    assert "recall" in prompt.lower() or "outbreak" in prompt.lower()


def test_system_prompt_declares_origin_and_alert():
    _assert_origin_schema(ProductSafetyAgent._build_system_prompt(_DUMMY, [], [], []))


def test_extracted_prompt_declares_origin_and_alert():
    _assert_origin_schema(
        ProductSafetyAgent._build_analysis_prompt_for_extracted_data(_DUMMY, [], [], [])
    )
