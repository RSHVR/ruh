"""LangGraph-based product safety agent using Cohere Command R+ with Claude verification.

This implements a ReACT agent pattern using LangGraph's StateGraph:
- Research node: Cohere gathers information via tool calls
- Analyze node: Cohere synthesizes findings into harm assessment
- Verify node: Claude Haiku performs adversarial verification

Cost savings: ~40-50% compared to all-Claude approach.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Annotated, Dict, List, Literal, Optional

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langchain_cohere import ChatCohere
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from anthropic import Anthropic

from .config import settings
from .token_tracker import TokenTracker
from .search_tool_service import SearchToolService

logger = logging.getLogger(__name__)


# =============================================================================
# AGENT STATE
# =============================================================================

class AgentState(dict):
    """State for the LangGraph safety analysis agent.

    Using dict subclass for compatibility with LangGraph's state management.
    """

    @property
    def messages(self) -> List[BaseMessage]:
        return self.get("messages", [])

    @property
    def product_data(self) -> Dict[str, Any]:
        return self.get("product_data", {})

    @property
    def product_url(self) -> str:
        return self.get("product_url", "")

    @property
    def research_findings(self) -> Dict[str, Any]:
        return self.get("research_findings", {})

    @property
    def analysis_result(self) -> Dict[str, Any]:
        return self.get("analysis_result", {})

    @property
    def verification_status(self) -> str:
        return self.get("verification_status", "pending")

    @property
    def iteration_count(self) -> int:
        return self.get("iteration_count", 0)


# Type annotation for LangGraph state
from typing import TypedDict

class SafetyAgentState(TypedDict):
    """Typed state definition for LangGraph."""
    messages: Annotated[List[BaseMessage], add_messages]
    product_data: Dict[str, Any]
    product_url: str
    allergen_database: List[Dict[str, Any]]
    pfas_database: List[Dict[str, Any]]
    research_findings: Dict[str, Any]
    analysis_result: Dict[str, Any]
    verification_status: str  # "pending", "pass", "fail", "needs_research"
    iteration_count: int
    max_iterations: int


# =============================================================================
# SYSTEM PROMPTS
# =============================================================================

RESEARCH_SYSTEM_PROMPT = """You are a product safety research agent. Your job is to gather comprehensive information about a product's ingredients and potential harms.

Available tools:
- lookup_ingredient_research: Get pre-computed research for known ingredients from our database (FAST, FREE - USE FIRST!)
- web_search: Search the web for safety information (SLOWER, COSTS MONEY - USE SPARINGLY)

RESEARCH STRATEGY (PRIORITIZE DATABASE LOOKUPS TO SAVE COST):

1. **FIRST - Database Lookups (FREE):**
   - Call lookup_ingredient_research for EACH concerning ingredient
   - Skip well-known safe ingredients: water, glycerin, tocopherol, citric acid, sodium chloride
   - Focus on: preservatives, fragrances, surfactants, dyes, sunscreen agents

2. **THEN - Targeted Web Searches (ONLY IF NEEDED):**
   - search_type="manufacturer": Only if ingredients list was incomplete
   - search_type="regulatory": For products in categories with known recalls
   - search_type="legal": Only for brands with rumored lawsuits
   - DO NOT search for: well-known safe ingredients, ingredients already in our database

3. **SKIP web_search FOR:**
   - Ingredients where lookup_ingredient_research returned good data
   - Well-known safe ingredients (water, glycerin, aloe vera, etc.)
   - Generic vitamin names (Vitamin E, Vitamin C, etc.)

COST AWARENESS:
- Each web_search costs ~$0.008. Each database lookup costs $0.
- A typical analysis should use 3-10 database lookups and 2-4 web searches MAX.
- If lookup_ingredient_research returns data, DO NOT search for that ingredient again.

When you have gathered sufficient information, respond with a summary of your findings WITHOUT using any tools."""


ANALYSIS_SYSTEM_PROMPT = """You are a product safety analyst. Based on research findings, provide a comprehensive harm assessment.

CRITICAL OUTPUT REQUIREMENT: You MUST respond with ONLY a valid JSON object.
- NO explanatory text before the JSON
- NO explanatory text after the JSON
- Start immediately with {{ and end with }}

Output JSON format:
{{
    "product_name": "string",
    "brand": "string",
    "retailer": "string",
    "ingredients": ["list", "of", "ingredients"],
    "allergens_detected": [
        {{
            "name": "allergen name (MUST match knowledge base)",
            "severity": "low|moderate|high|severe",
            "source": "where found in product",
            "confidence": 0.0-1.0
        }}
    ],
    "pfas_detected": [
        {{
            "name": "PFAS compound name (MUST match knowledge base)",
            "cas_number": "CAS number if known",
            "body_effects": "effects on human body",
            "source": "where found",
            "confidence": 0.0-1.0
        }}
    ],
    "other_concerns": [
        {{
            "name": "concern name",
            "category": "under_investigation|carcinogen|regulatory_action|heavy_metal|endocrine_disruptor|other",
            "severity": "low|moderate|high|severe",
            "description": "brief description with source citation",
            "confidence": 0.0-1.0
        }}
    ],
    "research_sources": [
        {{"type": "manufacturer|regulatory|scientific|legal|consumer", "url": "...", "finding": "..."}}
    ],
    "confidence": 0.0-1.0
}}

CRITICAL CLASSIFICATION RULES:
1. ALLERGENS - ONLY substances in the provided Allergen Knowledge Base can go in allergens_detected
2. PFAS - ONLY substances in the provided PFAS Knowledge Base can go in pfas_detected
3. Unknown substances go in other_concerns with category="under_investigation"
4. Every claim must have a source citation"""


VERIFICATION_PROMPT_TEMPLATE = """You are an adversarial reviewer checking product safety analysis quality.

Product: {product_data}

Analysis Result:
{analysis_result}

Allergen Knowledge Base (only these can be in allergens_detected):
{allergen_names}

PFAS Knowledge Base (only these can be in pfas_detected):
{pfas_names}

Check for:
1. Are all detected allergens actually in the knowledge base? List any that aren't.
2. Are all detected PFAS compounds actually in the knowledge base? List any that aren't.
3. Are severity ratings justified by evidence found in research?
4. Are there obvious ingredients that were missed?
5. Is the confidence score appropriate given the evidence quality?
6. Are all claims backed by source citations?

Respond with JSON:
{{
    "status": "pass" | "fail" | "needs_research",
    "issues": [
        {{"type": "invalid_allergen|invalid_pfas|missing_ingredient|unsupported_claim|confidence_mismatch", "details": "..."}}
    ],
    "corrections": {{
        "allergens_to_remove": ["names of allergens not in knowledge base"],
        "pfas_to_remove": ["names of PFAS not in knowledge base"],
        "severity_adjustments": [{{"name": "...", "suggested_severity": "..."}}]
    }},
    "summary": "Brief explanation of pass/fail/needs_research decision"
}}

Be strict but fair. Minor issues shouldn't cause a fail. Focus on:
- Substances incorrectly classified as allergens/PFAS when not in knowledge base
- Major safety concerns that were missed
- Highly inflated severity ratings without evidence"""


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

@dataclass
class LangGraphToolContext:
    """Context object passed to tools for accessing services."""
    search_service: Optional[SearchToolService] = None
    supabase_client: Any = None
    token_tracker: Optional[TokenTracker] = None


# Global context - will be set before running the graph
_tool_context: Optional[LangGraphToolContext] = None


def set_tool_context(context: LangGraphToolContext) -> None:
    """Set the global tool context for LangGraph tools."""
    global _tool_context
    _tool_context = context


@tool
async def web_search(query: str, search_type: str = "general") -> str:
    """Search for product safety information.

    Args:
        query: Search query (keep under 400 characters)
        search_type: Type of search - one of:
            - "manufacturer": Official product pages, MSDS, ingredient lists
            - "regulatory": FDA.gov, Health Canada, EPA recalls and warnings
            - "ingredient": Per-ingredient safety research (PubMed, NIH, IARC, EPA, EWG)
            - "scientific": General scientific studies and research papers
            - "legal": Class action lawsuits, court records, settlements
            - "consumer": Reddit user experiences and reactions
            - "general": No domain filter (default)

    Returns:
        Search results formatted as text
    """
    if not _tool_context or not _tool_context.search_service:
        return "Search service not available"

    try:
        result = await _tool_context.search_service.search(query, search_type)
        return result
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return f"Search failed: {e}"


@tool
async def lookup_ingredient_research(ingredient: str) -> str:
    """Look up pre-computed research for an ingredient from the database.

    This retrieves cached scientific, regulatory, and legal research
    that was pre-computed for known allergens, PFAS, and toxic substances.

    Args:
        ingredient: Ingredient name to look up

    Returns:
        Pre-computed research findings or "No research found"
    """
    if not _tool_context or not _tool_context.supabase_client:
        return "Database not available"

    try:
        # Supabase client is synchronous, wrap in thread executor
        response = await asyncio.to_thread(
            lambda: _tool_context.supabase_client.table("ingredient_research").select(
                "ingredient_name, iarc_classification, ewg_score, health_effects, "
                "regulatory_actions, lawsuits, settlements, confidence_score"
            ).ilike("ingredient_name", f"%{ingredient}%").limit(1).execute()
        )

        if response.data:
            research = response.data[0]
            return json.dumps({
                "ingredient": research.get("ingredient_name"),
                "iarc_classification": research.get("iarc_classification"),
                "ewg_score": research.get("ewg_score"),
                "health_effects": research.get("health_effects", []),
                "regulatory_actions": research.get("regulatory_actions", []),
                "lawsuits_count": len(research.get("lawsuits", [])),
                "settlements_count": len(research.get("settlements", [])),
                "confidence": research.get("confidence_score", 0),
            }, indent=2)

        return f"No pre-computed research found for '{ingredient}'"

    except Exception as e:
        logger.warning(f"Ingredient lookup failed: {e}")
        return f"Lookup failed: {e}"


# =============================================================================
# NODE FUNCTIONS
# =============================================================================

async def research_node(state: SafetyAgentState) -> Dict[str, Any]:
    """Research node - Cohere gathers information using tools.

    This node calls Cohere Command R+ with tool bindings to gather
    safety information about the product.
    """
    logger.info(f"🔍 Research node - iteration {state['iteration_count'] + 1}")

    # Initialize Cohere model with tools
    model = ChatCohere(
        model="command-r-plus",
        temperature=0.3,
        cohere_api_key=settings.cohere_api_key,
    )

    # Bind tools to model
    tools = [web_search, lookup_ingredient_research]
    model_with_tools = model.bind_tools(tools)

    # Build system message with product context
    product_data = state["product_data"]

    # Get preprocessed ingredients if available (from trafilatura_extractor)
    known_safe = product_data.get('_known_safe', [])
    known_concerns = product_data.get('_known_concerns', [])
    needs_research = product_data.get('_needs_research', [])

    # Build ingredient guidance based on preprocessing
    ingredient_guidance = ""
    if known_safe or known_concerns or needs_research:
        ingredient_guidance = f"""

PREPROCESSED INGREDIENT ANALYSIS (SAVE COST BY FOLLOWING THIS):
✅ SKIP RESEARCH (already known safe): {', '.join(known_safe[:15]) if known_safe else 'none'}
⚠️  ALREADY FLAGGED (no research needed): {', '.join([c['name'] for c in known_concerns[:10]]) if known_concerns else 'none'}
🔍 RESEARCH THESE ONLY: {', '.join(needs_research[:20]) if needs_research else 'all ingredients'}

For the flagged concerns, here are the known issues:
{chr(10).join([f"  - {c['name']}: {c['category']} - {c['description']}" for c in known_concerns[:5]]) if known_concerns else '  (none pre-flagged)'}

DO NOT use web_search for ingredients in the SKIP or FLAGGED lists above."""
    else:
        ingredient_guidance = ""

    system_content = RESEARCH_SYSTEM_PROMPT + f"""

PRODUCT BEING ANALYZED:
- Name: {product_data.get('product_name', 'Unknown')}
- Brand: {product_data.get('brand', 'Unknown')}
- URL: {state['product_url']}
- Ingredients: {', '.join(product_data.get('ingredients', [])[:20])}
- Materials: {', '.join(product_data.get('materials', [])[:10])}{ingredient_guidance}

Research this product using the available tools, prioritizing database lookups over web searches."""

    # Get messages from state
    messages = list(state["messages"])

    # If this is the first iteration, add the system message
    if state["iteration_count"] == 0:
        messages = [SystemMessage(content=system_content)] + messages

    # Call Cohere (async)
    response = await model_with_tools.ainvoke(messages)

    logger.info(f"   Cohere response type: {type(response)}")
    if hasattr(response, 'tool_calls') and response.tool_calls:
        logger.info(f"   Tool calls: {len(response.tool_calls)}")
        for tc in response.tool_calls:
            logger.info(f"      - {tc['name']}: {str(tc['args'])[:100]}...")

    return {
        "messages": [response],
        "iteration_count": state["iteration_count"] + 1,
    }


async def analyze_node(state: SafetyAgentState) -> Dict[str, Any]:
    """Analysis node - Cohere synthesizes findings into harm assessment.

    This node takes all the research findings and produces a structured
    safety analysis in JSON format.
    """
    logger.info("📊 Analyze node - synthesizing research into harm assessment")

    model = ChatCohere(
        model="command-r-plus",
        temperature=0.2,  # Lower temperature for consistent output
        cohere_api_key=settings.cohere_api_key,
    )

    # Build context from product data and knowledge bases
    product_data = state["product_data"]
    allergen_db = state.get("allergen_database", [])
    pfas_db = state.get("pfas_database", [])

    # Format knowledge bases compactly
    allergen_names = [a.get("name", "") for a in allergen_db]
    pfas_names = [p.get("name", "") for p in pfas_db]

    # Get pre-flagged concerns from preprocessing (must include in output)
    known_concerns = product_data.get('_known_concerns', [])
    preflagged_section = ""
    if known_concerns:
        preflagged_section = f"""

PRE-FLAGGED CONCERNS (MUST include in other_concerns):
{json.dumps(known_concerns, indent=2)}
These were identified by rule-based preprocessing. Include them in your output's other_concerns array."""

    # Build analysis prompt - exclude internal fields from product_data
    clean_product_data = {k: v for k, v in product_data.items() if not k.startswith('_')}
    analysis_prompt = f"""Based on the research conversation above, provide a comprehensive safety analysis.

PRODUCT DATA:
{json.dumps(clean_product_data, indent=2)}{preflagged_section}

ALLERGEN KNOWLEDGE BASE (only these can go in allergens_detected):
{', '.join(allergen_names[:50])}... ({len(allergen_names)} total)

PFAS KNOWLEDGE BASE (only these can go in pfas_detected):
{', '.join(pfas_names[:30])}... ({len(pfas_names)} total)

Analyze the product and provide your assessment as a JSON object."""

    # Get full message history and add analysis prompt
    messages = list(state["messages"]) + [HumanMessage(content=analysis_prompt)]

    # Call Cohere for analysis (async)
    response = await model.ainvoke(
        [SystemMessage(content=ANALYSIS_SYSTEM_PROMPT)] + messages
    )

    # Parse the JSON response
    analysis_result = _parse_analysis_json(response.content)

    logger.info(f"   Analysis result: {analysis_result.get('product_name', 'Unknown')}")
    logger.info(f"   Allergens: {len(analysis_result.get('allergens_detected', []))}")
    logger.info(f"   PFAS: {len(analysis_result.get('pfas_detected', []))}")
    logger.info(f"   Other concerns: {len(analysis_result.get('other_concerns', []))}")

    return {
        "messages": [response],
        "analysis_result": analysis_result,
    }


async def verify_node(state: SafetyAgentState) -> Dict[str, Any]:
    """Verification node - Claude Haiku checks analysis quality.

    This node uses Claude Haiku (cheaper, faster) to perform adversarial
    verification of the Cohere-generated analysis.
    """
    logger.info("✓ Verify node - Claude Haiku adversarial check")

    client = Anthropic(api_key=settings.anthropic_api_key)

    # Build verification prompt with knowledge bases
    allergen_db = state.get("allergen_database", [])
    pfas_db = state.get("pfas_database", [])
    allergen_names = [a.get("name", "") for a in allergen_db]
    pfas_names = [p.get("name", "") for p in pfas_db]

    verification_prompt = VERIFICATION_PROMPT_TEMPLATE.format(
        product_data=json.dumps(state["product_data"], indent=2),
        analysis_result=json.dumps(state["analysis_result"], indent=2),
        allergen_names=", ".join(allergen_names[:100]),
        pfas_names=", ".join(pfas_names[:50]),
    )

    # Call Claude Haiku for verification (run sync client in thread)
    response = await asyncio.to_thread(
        client.messages.create,
        model="claude-3-5-haiku-20241022",
        max_tokens=1024,
        messages=[{"role": "user", "content": verification_prompt}],
    )

    # Parse verification response
    verification_text = response.content[0].text
    verification_result = _parse_verification_json(verification_text)

    status = verification_result.get("status", "fail")
    issues = verification_result.get("issues", [])

    logger.info(f"   Verification status: {status}")
    logger.info(f"   Issues found: {len(issues)}")

    # Apply corrections if needed
    if verification_result.get("corrections"):
        corrections = verification_result["corrections"]
        analysis = state["analysis_result"].copy()

        # Remove invalid allergens
        if corrections.get("allergens_to_remove"):
            to_remove = set(corrections["allergens_to_remove"])
            analysis["allergens_detected"] = [
                a for a in analysis.get("allergens_detected", [])
                if a.get("name") not in to_remove
            ]
            logger.info(f"   Removed {len(to_remove)} invalid allergens")

        # Remove invalid PFAS
        if corrections.get("pfas_to_remove"):
            to_remove = set(corrections["pfas_to_remove"])
            analysis["pfas_detected"] = [
                p for p in analysis.get("pfas_detected", [])
                if p.get("name") not in to_remove
            ]
            logger.info(f"   Removed {len(to_remove)} invalid PFAS")

        return {
            "messages": [AIMessage(content=verification_text)],
            "verification_status": status,
            "analysis_result": analysis,
        }

    return {
        "messages": [AIMessage(content=verification_text)],
        "verification_status": status,
    }


async def tools_node(state: SafetyAgentState) -> Dict[str, Any]:
    """Execute tool calls from the last message.

    This node handles executing the tools requested by Cohere
    and returning results.
    """
    logger.info("🔧 Tools node - executing tool calls")

    last_message = state["messages"][-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.warning("   No tool calls found")
        return {"messages": []}

    tool_results = []
    tool_map = {
        "web_search": web_search,
        "lookup_ingredient_research": lookup_ingredient_research,
    }

    # Execute tools in parallel for efficiency
    async def execute_tool(tool_call):
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        logger.info(f"   Executing: {tool_name}")

        if tool_name in tool_map:
            try:
                # Tools are async, invoke them directly
                result = await tool_map[tool_name].ainvoke(tool_args)
                return ToolMessage(
                    content=result,
                    tool_call_id=tool_call["id"],
                    name=tool_name,
                )
            except Exception as e:
                logger.error(f"   Tool execution failed: {e}")
                return ToolMessage(
                    content=f"Error: {e}",
                    tool_call_id=tool_call["id"],
                    name=tool_name,
                )
        else:
            return ToolMessage(
                content=f"Unknown tool: {tool_name}",
                tool_call_id=tool_call["id"],
                name=tool_name,
            )

    # Run all tool calls in parallel
    tool_results = await asyncio.gather(*[
        execute_tool(tc) for tc in last_message.tool_calls
    ])

    return {"messages": list(tool_results)}


# =============================================================================
# ROUTING FUNCTIONS
# =============================================================================

def should_continue_research(state: SafetyAgentState) -> Literal["tools", "analyze"]:
    """Determine if research node should continue with tools or move to analysis.

    Returns "tools" if the last message has tool calls, "analyze" otherwise.
    """
    last_message = state["messages"][-1]

    # Check for tool calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        # Respect max iterations to prevent infinite loops
        if state["iteration_count"] >= state["max_iterations"]:
            logger.warning(f"   Max iterations ({state['max_iterations']}) reached, moving to analyze")
            return "analyze"
        return "tools"

    return "analyze"


def verification_router(state: SafetyAgentState) -> Literal["research", "end"]:
    """Route based on verification result.

    Returns:
        "research" if verification failed and we haven't hit max iterations
        "end" if verification passed or we've hit max iterations
    """
    status = state["verification_status"]

    if status == "pass":
        logger.info("   ✅ Verification passed - ending")
        return "end"

    if state["iteration_count"] >= state["max_iterations"]:
        logger.warning(f"   ⚠️  Max iterations reached - ending with status: {status}")
        return "end"

    if status == "needs_research":
        logger.info("   🔄 Needs more research - returning to research node")
        return "research"

    # "fail" status - end with current results (corrections already applied)
    logger.info("   ⚠️  Verification failed but corrections applied - ending")
    return "end"


# =============================================================================
# GRAPH BUILDER
# =============================================================================

def build_safety_agent() -> StateGraph:
    """Build the LangGraph safety analysis state machine.

    Graph structure:
        START → research → (tools ↔ research) → analyze → verify → END
                                                              ↓
                                                          research (if needs_research)
    """
    workflow = StateGraph(SafetyAgentState)

    # Add nodes
    workflow.add_node("research", research_node)
    workflow.add_node("tools", tools_node)
    workflow.add_node("analyze", analyze_node)
    workflow.add_node("verify", verify_node)

    # Set entry point
    workflow.set_entry_point("research")

    # Add edges
    workflow.add_conditional_edges(
        "research",
        should_continue_research,
        {
            "tools": "tools",
            "analyze": "analyze",
        }
    )
    workflow.add_edge("tools", "research")  # Loop back after tool execution
    workflow.add_edge("analyze", "verify")
    workflow.add_conditional_edges(
        "verify",
        verification_router,
        {
            "research": "research",
            "end": END,
        }
    )

    return workflow.compile()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _parse_analysis_json(text: str) -> Dict[str, Any]:
    """Parse JSON from analysis response, handling various formats."""
    try:
        # Try direct JSON parse
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON from markdown code blocks
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        try:
            return json.loads(text[start:end].strip())
        except json.JSONDecodeError:
            pass

    if "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        try:
            return json.loads(text[start:end].strip())
        except json.JSONDecodeError:
            pass

    # Try to find JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    logger.error(f"Failed to parse analysis JSON: {text[:500]}")
    return {
        "product_name": "Unknown",
        "brand": "Unknown",
        "ingredients": [],
        "allergens_detected": [],
        "pfas_detected": [],
        "other_concerns": [],
        "confidence": 0.3,
        "error": "Failed to parse analysis response",
    }


def _parse_verification_json(text: str) -> Dict[str, Any]:
    """Parse JSON from verification response."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to extract from code blocks
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        try:
            return json.loads(text[start:end].strip())
        except json.JSONDecodeError:
            pass

    # Try to find JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    logger.error(f"Failed to parse verification JSON: {text[:500]}")
    return {
        "status": "fail",
        "issues": [{"type": "parse_error", "details": "Could not parse verification response"}],
        "summary": "Verification response parsing failed",
    }


# =============================================================================
# ASYNC WRAPPER
# =============================================================================

class LangGraphSafetyAgent:
    """Async wrapper for the LangGraph safety agent.

    This class provides an interface compatible with the existing
    ProductSafetyAgent for easy integration.
    """

    def __init__(
        self,
        token_tracker: Optional[TokenTracker] = None,
        search_service: Optional[SearchToolService] = None,
        supabase_client: Any = None,
    ):
        """Initialize the LangGraph agent.

        Args:
            token_tracker: Token usage tracker
            search_service: Search service for web searches
            supabase_client: Supabase client for database operations
        """
        self.token_tracker = token_tracker or TokenTracker()
        self.search_service = search_service
        self.supabase_client = supabase_client
        self.graph = build_safety_agent()

        # Set tool context
        set_tool_context(LangGraphToolContext(
            search_service=search_service,
            supabase_client=supabase_client,
            token_tracker=token_tracker,
        ))

    async def analyze_extracted_product(
        self,
        product_data: Dict[str, Any],
        product_url: str,
        allergen_profile: List[str] = None,
        pfas_database: List[Dict[str, Any]] = None,
        allergen_database: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze product using LangGraph agent.

        Args:
            product_data: Extracted product data
            product_url: Product URL
            allergen_profile: User's allergen concerns (unused, for compatibility)
            pfas_database: PFAS knowledge base
            allergen_database: Allergen knowledge base

        Returns:
            Analysis result dictionary
        """
        logger.info(f"🚀 Starting LangGraph analysis for: {product_data.get('product_name', 'Unknown')}")

        # Initialize state
        initial_state: SafetyAgentState = {
            "messages": [
                HumanMessage(content=f"Analyze this product for safety concerns: {product_data.get('product_name', 'Unknown')}")
            ],
            "product_data": product_data,
            "product_url": product_url,
            "allergen_database": allergen_database or [],
            "pfas_database": pfas_database or [],
            "research_findings": {},
            "analysis_result": {},
            "verification_status": "pending",
            "iteration_count": 0,
            "max_iterations": 10,
        }

        # Run the graph (async)
        try:
            final_state = await self.graph.ainvoke(initial_state)

            logger.info(f"✅ LangGraph analysis complete")
            logger.info(f"   Iterations: {final_state.get('iteration_count', 0)}")
            logger.info(f"   Verification: {final_state.get('verification_status', 'unknown')}")

            return final_state.get("analysis_result", {})

        except Exception as e:
            logger.error(f"❌ LangGraph analysis failed: {e}")
            raise

    async def close(self) -> None:
        """Cleanup resources."""
        if self.search_service:
            await self.search_service.close()
