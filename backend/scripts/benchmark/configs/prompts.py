"""Shared prompt building for all benchmark configs.

The static body and KB renderer are lifted from
``backend/src/infrastructure/claude_agent.py`` (the same prompt that runs in
prod today) so we don't drift from the implementation under test.

DETERMINISM CONTRACT
====================
``STATIC_BASE_PROMPT`` is a frozen byte string. ``build_kb_block`` sorts both
allergens and PFAS by lowercase name before rendering and renders synonyms in
sorted order. Two callers passing the same KB rows in different list order MUST
produce byte-identical output — Anthropic's 1hr ephemeral cache only matches on
exact-prefix bytes, and any drift here silently doubles cost on cached configs.

Verified by ``backend/tests/unit/test_prompts.py``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Static cacheable body — lifted from claude_agent.py:421-522 then frozen.
# Edit with care: changing this invalidates every cache entry and resets
# the comparable cost baseline across all Claude-cached configs.
# ---------------------------------------------------------------------------

STATIC_BASE_PROMPT = """You are a product safety analysis expert. You have been provided with pre-extracted product information.

Your final response MUST be a valid JSON object (no surrounding text or code blocks).

**Your Analysis Process:**
1. Review the provided product details (already extracted from the product page)
2. Use web_search strategically to research safety concerns:

   a) **MANUFACTURER SEARCH (IF INGREDIENTS/MATERIALS INCOMPLETE):**
      - Search: "[brand] [product name] official ingredients" OR "[brand] MSDS"
      - search_type: "manufacturer"
      - Goal: Find complete ingredient/material lists from official sources

   b) **REGULATORY SEARCH:**
      - Search: "[product name] recall FDA warning" OR "[brand] safety alert"
      - search_type: "regulatory"
      - Goal: Find recalls, FDA/EPA warnings, Health Canada advisories

   c) **PER-INGREDIENT RESEARCH (CRITICAL - DO THIS FOR CONCERNING INGREDIENTS):**
      - For EACH potentially concerning ingredient, search for its safety profile:
        - "[ingredient name] toxicity studies"
        - "[ingredient name] IARC classification carcinogen"
        - "[ingredient name] endocrine disruptor research"
        - "[ingredient name] EWG safety rating"
      - search_type: "ingredient"
      - Goal: Find scientific safety data for individual chemicals

   d) **LEGAL SEARCH (REQUIRED):**
      - Search: "[brand] [product] class action lawsuit" OR "[brand] settlement"
      - search_type: "legal"
      - Goal: Find documented lawsuits, settlements, regulatory fines

   e) **CONSUMER SEARCH (REQUIRED):**
      - Search: "[brand] [product] reaction allergy breakout reddit"
      - search_type: "consumer"
      - Goal: Find real user reports of adverse reactions

**CRITICAL WEBSEARCH RESTRICTIONS:**
- DO NOT use consumer blogs, forums, review sites, or non-scientific health websites
- DO NOT use marketing materials or unverified sources
- ONLY use credible sources: .gov, .edu, manufacturer official sites, peer-reviewed journals, court records

**Output Format - YOUR ENTIRE RESPONSE MUST BE THIS JSON OBJECT:**
{
    "product_name": "string",
    "brand": "string",
    "retailer": "string",
    "ingredients": ["complete list from manufacturer website if found, else from product page"],
    "allergens_detected": [
        {"name": "allergen name (MUST match knowledge base below)", "severity": "low|moderate|high|severe", "source": "where found", "confidence": 0.0-1.0}
    ],
    "pfas_detected": [
        {"name": "PFAS compound (MUST match knowledge base below)", "cas_number": "CAS number if known", "body_effects": "effects on human body", "source": "where found", "confidence": 0.0-1.0}
    ],
    "other_concerns": [
        {"name": "concern name", "category": "under_investigation|carcinogen|regulatory_action|heavy_metal|endocrine_disruptor|other", "severity": "low|moderate|high|severe", "description": "brief description with source citation", "confidence": 0.0-1.0}
    ],
    "research_sources": [
        {"type": "manufacturer_website", "url": "...", "finding": "..."},
        {"type": "regulatory_action", "url": "...", "finding": "..."},
        {"type": "scientific_study", "url": "...", "finding": "..."}
    ],
    "confidence": 0.0-1.0
}

**CRITICAL CLASSIFICATION RULES - READ CAREFULLY:**

1. **ALLERGENS - ONLY substances in the Allergen Knowledge Base below can go in allergens_detected**
   - If you find an ingredient via websearch that is NOT in the Allergen Knowledge Base → DO NOT add to allergens_detected
   - Minor irritants (citric acid, fragrance, etc.) are NOT allergens unless listed in the knowledge base
   - If a substance causes irritation but is not a priority allergen → add to other_concerns with category="under_investigation", severity="low"

2. **PFAS - ONLY substances in the PFAS Knowledge Base below can go in pfas_detected**
   - If you find a chemical via websearch that is NOT in the PFAS Knowledge Base → DO NOT add to pfas_detected
   - Unknown fluorinated compounds → add to other_concerns with category="under_investigation"
   - Match by CAS number or exact name from the knowledge base

3. **OTHER CONCERNS - Use this for substances not in the knowledge bases**
   - category="under_investigation": Substances with credible evidence but not in our database (MUST have severity="low" max)
   - category="carcinogen": ONLY IARC-classified carcinogens (Groups 1, 2A, 2B) from credible sources
   - category="regulatory_action": ONLY substances with FDA recall, EPA warning, or class action lawsuit
   - category="heavy_metal", "endocrine_disruptor", "other": Other toxins with credible evidence

4. **EVIDENCE REQUIREMENTS for other_concerns:**
   - MUST have credible source (.gov, .edu, peer-reviewed journal, court record)
   - MUST NOT include unverified consumer complaints or blog posts
   - MUST include description with source citation (e.g., "IARC Group 2A carcinogen per iarc.who.int/2023")
"""


def build_kb_block(
    allergen_db: List[Dict[str, Any]],
    pfas_db: List[Dict[str, Any]],
    allergen_profile: Optional[List[str]] = None,
) -> str:
    """Render the knowledge-base block in a byte-deterministic way.

    Sort order: lowercase name. Synonyms are also sorted (and capped at 3) to
    match what the production prompt does. Empty lists render to empty
    sections so the prompt structure stays stable across products.
    """
    allergen_profile = allergen_profile or []
    parts: List[str] = []

    if allergen_db:
        parts.append(
            f"\n**ALLERGEN KNOWLEDGE BASE ({len(allergen_db)} priority allergens):**"
        )
        parts.append(
            "ONLY these substances can be classified as allergens. "
            "If a substance is not on this list, it is NOT an allergen.\n"
        )
        sorted_allergens = sorted(
            allergen_db, key=lambda a: (a.get("name") or "").lower()
        )
        for allergen in sorted_allergens:
            name = allergen.get("name", "")
            synonyms = allergen.get("synonyms", []) or []
            top_synonyms = sorted(s for s in synonyms if s)[:3]
            if top_synonyms:
                parts.append(f"- {name} (synonyms: {', '.join(top_synonyms)})")
            else:
                parts.append(f"- {name}")

    if pfas_db:
        parts.append(
            f"\n**PFAS KNOWLEDGE BASE ({len(pfas_db)} compounds):**"
        )
        parts.append(
            "ONLY these substances can be classified as PFAS. "
            "If a substance is not on this list, it is NOT PFAS.\n"
        )
        sorted_pfas = sorted(pfas_db, key=lambda p: (p.get("name") or "").lower())
        for pfas in sorted_pfas:
            name = pfas.get("name", "")
            cas = pfas.get("cas_number") or ""
            if cas:
                parts.append(f"- {name} (CAS: {cas})")
            else:
                parts.append(f"- {name}")

    if allergen_profile:
        # User profile is deliberately appended AFTER the KB so the KB block
        # stays cacheable across users — the profile changes per request and
        # therefore must not be part of the cached prefix.
        sorted_profile = sorted(allergen_profile)
        parts.append("\n**User's Allergen Profile:**")
        parts.append(f"Pay special attention to: {', '.join(sorted_profile)}")

    return "\n".join(parts) + ("\n" if parts else "")


def build_user_message(product_data: Dict[str, Any], product_url: str) -> str:
    """User-turn message — lifted from claude_agent.py:1041-1080.

    The user turn is NOT cached (varies per product), so it doesn't need the
    same byte-level discipline as the system prompt — but we still build it
    deterministically because the runner replays.
    """
    def fmt_list(items: List[str]) -> str:
        if not items:
            return "None listed"
        return "\n".join(f"{i+1}. {item}" for i, item in enumerate(items))

    return f"""Analyze this product for harmful substances:

**Product Information (pre-extracted from webpage):**
- Product Name: {product_data.get('product_name', 'Unknown')}
- Brand: {product_data.get('brand', 'Unknown')}
- URL: {product_url}

**Ingredients:**
{fmt_list(product_data.get('ingredients', []))}

**Materials:**
{fmt_list(product_data.get('materials', []))}

**Features:**
{fmt_list(product_data.get('features', []))}

**Warnings:**
{fmt_list(product_data.get('warnings', []))}

**Description:**
{product_data.get('description', 'None provided')}

**Your Analysis Task:**
**DO NOT use web_fetch** - Product information has already been extracted above.

**REQUIRED SEARCHES (do ALL of these):**
1. **Manufacturer search** (search_type="manufacturer"): Find official ingredient lists if incomplete above
2. **Regulatory search** (search_type="regulatory"): Find FDA/EPA/Health Canada recalls, warnings
3. **Per-ingredient searches** (search_type="ingredient"): Research 3-5 concerning ingredients individually
4. **Legal search** (search_type="legal"): Find class action lawsuits, settlements against this brand/product
5. **Consumer search** (search_type="consumer"): Find Reddit user reports of reactions, allergies, breakouts

After completing ALL searches, cross-reference findings with the knowledge bases and return the JSON analysis."""
