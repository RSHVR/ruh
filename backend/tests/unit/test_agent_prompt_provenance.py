"""The agent's BOTH output schemas must declare ingredients_by_provenance.

The prompt builders are pure string builders that don't touch ``self``, so we
invoke them with a dummy self to avoid constructing the full agent (which would
need an Anthropic client). This guards that the declared/found/inferred schema
stays in both prompt variants.
"""

from types import SimpleNamespace

from src.infrastructure.claude_agent import ProductSafetyAgent

_DUMMY = SimpleNamespace()


def test_system_prompt_declares_provenance_schema():
    prompt = ProductSafetyAgent._build_system_prompt(_DUMMY, [], [], [])
    assert "ingredients_by_provenance" in prompt
    for key in ("declared", "found", "inferred", "stage"):
        assert key in prompt


def test_extracted_data_prompt_declares_provenance_schema():
    prompt = ProductSafetyAgent._build_analysis_prompt_for_extracted_data(_DUMMY, [], [], [])
    assert "ingredients_by_provenance" in prompt
    for key in ("declared", "found", "inferred", "stage"):
        assert key in prompt
    # research_sources must remain in this variant (back-compat).
    assert "research_sources" in prompt
