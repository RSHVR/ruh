"""The agent threads an optional buyer region into BOTH user-message builders.

The builders are near-pure string builders; the extracted variant calls
self._format_list, so the dummy provides a trivial stub for it.
"""

from types import SimpleNamespace

from src.infrastructure.claude_agent import ProductSafetyAgent


def _dummy_with_format_list():
    d = SimpleNamespace()
    d._format_list = lambda items: ""
    return d


def test_extracted_message_includes_buyer_region_when_set():
    msg = ProductSafetyAgent._build_user_message_from_extracted_data(
        _dummy_with_format_list(), {"product_name": "X"}, "https://u/p", "CA-ON"
    )
    assert "Buyer region: CA-ON" in msg


def test_extracted_message_omits_region_when_none():
    msg = ProductSafetyAgent._build_user_message_from_extracted_data(
        _dummy_with_format_list(), {"product_name": "X"}, "https://u/p", None
    )
    assert "Buyer region" not in msg


def test_fallback_message_includes_buyer_region_when_set():
    msg = ProductSafetyAgent._build_user_message(SimpleNamespace(), "https://u/p", "US-CA")
    assert "Buyer region: US-CA" in msg


def test_fallback_message_omits_region_when_none():
    msg = ProductSafetyAgent._build_user_message(SimpleNamespace(), "https://u/p", None)
    assert "Buyer region" not in msg
