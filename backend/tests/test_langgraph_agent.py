"""Tests for the LangGraph safety agent.

These tests verify the LangGraph + Cohere implementation.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_cohere_api_key():
    """Mock Cohere API key for testing."""
    return "test-cohere-key"


@pytest.fixture
def mock_anthropic_api_key():
    """Mock Anthropic API key for testing."""
    return "test-anthropic-key"


@pytest.fixture
def sample_product_data():
    """Sample product data for testing."""
    return {
        "product_name": "Test Sunscreen SPF 50",
        "brand": "TestBrand",
        "ingredients": [
            "Avobenzone",
            "Homosalate",
            "Octisalate",
            "Octocrylene",
            "Oxybenzone",
            "Water",
            "Glycerin",
            "Fragrance",
        ],
        "materials": [],
        "features": ["Broad spectrum SPF 50", "Water resistant"],
        "warnings": ["For external use only"],
        "description": "A broad spectrum sunscreen.",
    }


@pytest.fixture
def sample_allergen_database():
    """Sample allergen database for testing."""
    return [
        {"name": "Fragrance", "synonyms": ["Parfum", "Perfume"]},
        {"name": "Oxybenzone", "synonyms": ["Benzophenone-3"]},
        {"name": "Milk", "synonyms": ["Lactose", "Casein"]},
    ]


@pytest.fixture
def sample_pfas_database():
    """Sample PFAS database for testing."""
    return [
        {"name": "PFOA", "cas_number": "335-67-1"},
        {"name": "PFOS", "cas_number": "1763-23-1"},
        {"name": "PTFE", "cas_number": "9002-84-0"},
    ]


class TestLangGraphAgentState:
    """Tests for the AgentState definition."""

    def test_state_type_definition(self):
        """Verify SafetyAgentState TypedDict is correctly defined."""
        from src.infrastructure.langgraph_agent import SafetyAgentState

        # Check that we can create a valid state
        state: SafetyAgentState = {
            "messages": [],
            "product_data": {},
            "product_url": "https://example.com/product",
            "allergen_database": [],
            "pfas_database": [],
            "research_findings": {},
            "analysis_result": {},
            "verification_status": "pending",
            "iteration_count": 0,
            "max_iterations": 10,
        }

        assert state["verification_status"] == "pending"
        assert state["iteration_count"] == 0


class TestJsonParsing:
    """Tests for JSON parsing helper functions."""

    def test_parse_analysis_json_direct(self):
        """Test parsing direct JSON."""
        from src.infrastructure.langgraph_agent import _parse_analysis_json

        json_str = '{"product_name": "Test", "allergens_detected": []}'
        result = _parse_analysis_json(json_str)

        assert result["product_name"] == "Test"
        assert result["allergens_detected"] == []

    def test_parse_analysis_json_markdown(self):
        """Test parsing JSON from markdown code block."""
        from src.infrastructure.langgraph_agent import _parse_analysis_json

        text = '''Here is the analysis:

```json
{"product_name": "Test Product", "confidence": 0.8}
```

That's my analysis.'''

        result = _parse_analysis_json(text)
        assert result["product_name"] == "Test Product"
        assert result["confidence"] == 0.8

    def test_parse_analysis_json_embedded(self):
        """Test parsing JSON embedded in text."""
        from src.infrastructure.langgraph_agent import _parse_analysis_json

        text = 'Based on my research, {"product_name": "Test", "brand": "Brand"} is the analysis.'
        result = _parse_analysis_json(text)

        assert result["product_name"] == "Test"
        assert result["brand"] == "Brand"

    def test_parse_analysis_json_invalid(self):
        """Test handling invalid JSON."""
        from src.infrastructure.langgraph_agent import _parse_analysis_json

        text = "This is not JSON at all."
        result = _parse_analysis_json(text)

        assert result["product_name"] == "Unknown"
        assert "error" in result

    def test_parse_verification_json_pass(self):
        """Test parsing verification response with pass status."""
        from src.infrastructure.langgraph_agent import _parse_verification_json

        json_str = '{"status": "pass", "issues": [], "summary": "All good"}'
        result = _parse_verification_json(json_str)

        assert result["status"] == "pass"
        assert result["issues"] == []

    def test_parse_verification_json_fail(self):
        """Test parsing verification response with fail status and corrections."""
        from src.infrastructure.langgraph_agent import _parse_verification_json

        json_str = '''{"status": "fail", "issues": [{"type": "invalid_allergen", "details": "X"}],
            "corrections": {"allergens_to_remove": ["X"]}}'''
        result = _parse_verification_json(json_str)

        assert result["status"] == "fail"
        assert len(result["issues"]) == 1
        assert result["corrections"]["allergens_to_remove"] == ["X"]


class TestRoutingFunctions:
    """Tests for graph routing functions."""

    def test_should_continue_research_with_tool_calls(self):
        """Test routing to tools when tool calls present."""
        from src.infrastructure.langgraph_agent import (
            should_continue_research,
            SafetyAgentState,
        )
        from langchain_core.messages import AIMessage

        # Create a mock message with tool_calls
        message = AIMessage(content="")
        message.tool_calls = [{"name": "web_search", "args": {}, "id": "123"}]

        state: SafetyAgentState = {
            "messages": [message],
            "product_data": {},
            "product_url": "",
            "allergen_database": [],
            "pfas_database": [],
            "research_findings": {},
            "analysis_result": {},
            "verification_status": "pending",
            "iteration_count": 1,
            "max_iterations": 10,
        }

        result = should_continue_research(state)
        assert result == "tools"

    def test_should_continue_research_no_tool_calls(self):
        """Test routing to analyze when no tool calls."""
        from src.infrastructure.langgraph_agent import (
            should_continue_research,
            SafetyAgentState,
        )
        from langchain_core.messages import AIMessage

        message = AIMessage(content="Done researching.")

        state: SafetyAgentState = {
            "messages": [message],
            "product_data": {},
            "product_url": "",
            "allergen_database": [],
            "pfas_database": [],
            "research_findings": {},
            "analysis_result": {},
            "verification_status": "pending",
            "iteration_count": 1,
            "max_iterations": 10,
        }

        result = should_continue_research(state)
        assert result == "analyze"

    def test_should_continue_research_max_iterations(self):
        """Test routing to analyze when max iterations reached."""
        from src.infrastructure.langgraph_agent import (
            should_continue_research,
            SafetyAgentState,
        )
        from langchain_core.messages import AIMessage

        message = AIMessage(content="")
        message.tool_calls = [{"name": "web_search", "args": {}, "id": "123"}]

        state: SafetyAgentState = {
            "messages": [message],
            "product_data": {},
            "product_url": "",
            "allergen_database": [],
            "pfas_database": [],
            "research_findings": {},
            "analysis_result": {},
            "verification_status": "pending",
            "iteration_count": 10,  # At max
            "max_iterations": 10,
        }

        result = should_continue_research(state)
        assert result == "analyze"

    def test_verification_router_pass(self):
        """Test routing to end when verification passes."""
        from src.infrastructure.langgraph_agent import (
            verification_router,
            SafetyAgentState,
        )

        state: SafetyAgentState = {
            "messages": [],
            "product_data": {},
            "product_url": "",
            "allergen_database": [],
            "pfas_database": [],
            "research_findings": {},
            "analysis_result": {},
            "verification_status": "pass",
            "iteration_count": 3,
            "max_iterations": 10,
        }

        result = verification_router(state)
        assert result == "end"

    def test_verification_router_needs_research(self):
        """Test routing back to research when needed."""
        from src.infrastructure.langgraph_agent import (
            verification_router,
            SafetyAgentState,
        )

        state: SafetyAgentState = {
            "messages": [],
            "product_data": {},
            "product_url": "",
            "allergen_database": [],
            "pfas_database": [],
            "research_findings": {},
            "analysis_result": {},
            "verification_status": "needs_research",
            "iteration_count": 3,
            "max_iterations": 10,
        }

        result = verification_router(state)
        assert result == "research"


class TestGraphBuilder:
    """Tests for the graph builder function."""

    def test_build_safety_agent_returns_compiled_graph(self):
        """Test that build_safety_agent returns a compiled StateGraph."""
        from src.infrastructure.langgraph_agent import build_safety_agent

        graph = build_safety_agent()

        # Verify it's a compiled graph with the expected nodes
        assert graph is not None
        # The compiled graph should be invocable
        assert hasattr(graph, "invoke")
        assert hasattr(graph, "ainvoke")


class TestSafetyAgentWrapper:
    """Tests for the ProductSafetyAgentWrapper."""

    def test_wrapper_uses_claude_by_default(self):
        """Test that wrapper uses Claude when use_langgraph_agent is False."""
        with patch("src.infrastructure.safety_agent.settings") as mock_settings:
            mock_settings.use_langgraph_agent = False
            mock_settings.cohere_api_key = ""

            from src.infrastructure.safety_agent import ProductSafetyAgentWrapper

            wrapper = ProductSafetyAgentWrapper()
            assert wrapper.use_langgraph is False

    def test_wrapper_uses_langgraph_when_enabled(self):
        """Test that wrapper uses LangGraph when enabled with Cohere key."""
        with patch("src.infrastructure.safety_agent.settings") as mock_settings:
            mock_settings.use_langgraph_agent = True
            mock_settings.cohere_api_key = "test-key"

            from src.infrastructure.safety_agent import ProductSafetyAgentWrapper

            wrapper = ProductSafetyAgentWrapper()
            assert wrapper.use_langgraph is True


class TestTokenTrackerPricing:
    """Tests for the extended token tracker pricing."""

    def test_cohere_pricing_defined(self):
        """Test that Cohere model pricing is defined."""
        from src.infrastructure.token_tracker import PRICING

        assert "command-r-plus" in PRICING
        assert PRICING["command-r-plus"]["input"] == 2.50
        assert PRICING["command-r-plus"]["output"] == 10.00

        assert "command-r" in PRICING
        assert PRICING["command-r"]["input"] == 0.15
        assert PRICING["command-r"]["output"] == 0.60

    def test_claude_haiku_pricing_defined(self):
        """Test that Claude Haiku pricing is defined."""
        from src.infrastructure.token_tracker import PRICING

        assert "claude-haiku-3" in PRICING
        assert PRICING["claude-haiku-3"]["input"] == 0.80
        assert PRICING["claude-haiku-3"]["output"] == 4.00

        assert "claude-3-5-haiku-20241022" in PRICING

    def test_token_usage_cost_calculation(self):
        """Test cost calculation for different models."""
        from src.infrastructure.token_tracker import TokenUsage

        # Claude Sonnet
        sonnet_usage = TokenUsage(
            call_name="test",
            model="claude-sonnet-4-5-20250929",
            input_tokens=1000,
            output_tokens=500,
        )
        # $3/1M input + $15/1M output
        # 1000/1M * $3 = $0.003
        # 500/1M * $15 = $0.0075
        assert abs(sonnet_usage.input_cost - 0.003) < 0.0001
        assert abs(sonnet_usage.output_cost - 0.0075) < 0.0001

        # Cohere Command R+
        cohere_usage = TokenUsage(
            call_name="test",
            model="command-r-plus",
            input_tokens=1000,
            output_tokens=500,
        )
        # $2.50/1M input + $10/1M output
        # 1000/1M * $2.50 = $0.0025
        # 500/1M * $10 = $0.005
        assert abs(cohere_usage.input_cost - 0.0025) < 0.0001
        assert abs(cohere_usage.output_cost - 0.005) < 0.0001

        # Claude Haiku
        haiku_usage = TokenUsage(
            call_name="test",
            model="claude-haiku-3",
            input_tokens=1000,
            output_tokens=500,
        )
        # $0.80/1M input + $4/1M output
        # 1000/1M * $0.80 = $0.0008
        # 500/1M * $4 = $0.002
        assert abs(haiku_usage.input_cost - 0.0008) < 0.0001
        assert abs(haiku_usage.output_cost - 0.002) < 0.0001
