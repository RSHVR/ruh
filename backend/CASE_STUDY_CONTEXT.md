# Case Study: Comparing Claude Sonnet 4 vs Cohere Command A for Product Safety Analysis

## Context for Medium Article

**Author Context:** This document provides comprehensive technical context, raw data, and methodology for writing a peer-reviewable case study comparing LLM agents for product safety analysis.

---

## 1. Executive Summary

We built a product safety analysis system that detects allergens, PFAS compounds, and other health concerns in consumer products. We compared two LLM backends:

1. **Claude Sonnet 4** (Anthropic) - $3/$15 per 1M tokens (input/output)
2. **Cohere Command A** (Cohere) - $2.50/$10 per 1M tokens (input/output)

**Key Finding:** With TRUE tool parity (identical tools, prompts, knowledge bases), both agents found safety concerns. However, **Claude demonstrated superior research depth** with 10 scientific sources including multiple PubMed citations, while Cohere found 4 sources with less detailed citations.

**Critical Finding (TRUE Tool Parity Experiment):** We discovered our initial "feature parity" test was flawed - Cohere had access to `lookup_ingredient_research` (empty database), causing it to bypass web search. After removing this tool for TRUE parity, **Cohere found 3 concerns vs Claude's 2**, but with lower confidence (60% vs 90%) and fewer sources (4 vs 10). The quality gap is about **research depth and synthesis**, not fundamental capability.

---

## 2. Technical Architecture

### 2.1 System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Product Safety Agent                        │
├─────────────────────────────────────────────────────────────────┤
│  Input: Product name, brand, ingredients, URL                   │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │  Web Search │───▶│  LLM Agent  │───▶│  Safety Assessment  │  │
│  │   (Tavily)  │    │ (Claude OR  │    │  JSON Output        │  │
│  │             │    │   Cohere)   │    │                     │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
│                                                                  │
│  Search Types: manufacturer, regulatory, ingredient,             │
│                legal, consumer (Reddit)                          │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Claude Agent Architecture

- **Framework:** Direct Anthropic API with tool use
- **Model:** `claude-sonnet-4-5-20250929`
- **Tools:** `web_search` with domain filtering
- **Pattern:** ReAct loop with structured JSON output

```python
# Claude agent tool definition
tools = [{
    "name": "web_search",
    "description": "Search for product safety information",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "search_type": {"type": "string", "enum": [
                "manufacturer", "regulatory", "ingredient",
                "legal", "consumer", "general"
            ]}
        }
    }
}]
```

### 2.3 Cohere Agent Architecture

- **Framework:** LangGraph `create_react_agent`
- **Model:** `command-a-03-2025`
- **Tools:** `web_search`, `save_analysis`, `report_failure` (TRUE parity with Claude)
- **Pattern:** ReAct with terminal actions

```python
# LangGraph agent creation (TRUE tool parity)
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(
    model=ChatCohere(model="command-a-03-2025", temperature=0.3),
    # NOTE: lookup_ingredient_research removed for tool parity with Claude
    tools=[web_search, save_analysis, report_failure],
    prompt=SAFETY_AGENT_PROMPT,
)
```

### 2.4 Search Infrastructure

- **Primary:** Tavily API with content extraction
- **Fallback:** Serper API
- **Domain Filters by Search Type:**
  - `manufacturer`: Official product sites, MSDS databases
  - `regulatory`: .gov domains (FDA, EPA, Health Canada)
  - `ingredient`: PubMed, NIH, IARC, EWG
  - `legal`: Court records, law firm sites
  - `consumer`: Reddit.com

---

## 3. Test Methodology

### 3.1 Test Product

| Field           | Value                                                               |
| --------------- | ------------------------------------------------------------------- |
| **Product**     | PatchRx Pimple Patches with Salicylic Acid (120 Pack)               |
| **Brand**       | PatchRx                                                             |
| **URL**         | https://www.amazon.ca/dp/B0BNW7WNLL                                 |
| **Ingredients** | Salicylic Acid, Tea Tree Oil (Melaleuca Alternifolia), Hydrocolloid |
| **Category**    | Skincare / Acne Treatment                                           |

### 3.2 Test Conditions

- Same product data provided to both agents
- Same search service (Tavily) for both
- No pre-loaded knowledge bases (empty allergen/PFAS databases)
- Sequential execution (not parallel) to avoid rate limiting
- Single test run per agent (not averaged)

### 3.3 Evaluation Criteria

1. **Concerns Found:** Number and quality of safety issues identified
2. **Source Quality:** Scientific rigor of cited sources
3. **Confidence:** Self-reported confidence score
4. **Latency:** Total execution time
5. **Cost:** Token usage × pricing

---

## 4. Raw Results (Initial Test - Flawed Parity)

> **Note:** These results are from the initial test where Cohere had an extra tool (`lookup_ingredient_research`) that Claude did not have. Cohere chose this shortcut over web search, causing it to find 0 concerns. See Section 7 for TRUE parity results.

### 4.1 Claude Sonnet 4 Results

```json
{
  "time_seconds": 55.73,
  "confidence": 0.85,
  "token_usage": {
    "total_input_tokens": 34508,
    "total_output_tokens": 2596,
    "total_tokens": 37104,
    "token_cost_usd": 0.142464,
    "call_count": 4
  }
}
```

#### Concerns Detected (3):

**1. Tea Tree Oil - Contact Allergen** (severity: low, confidence: 0.9)

> Tea tree oil has documented contact dermatitis and sensitization cases. Studies show prevalence of positive patch test reactions ranging from 0.1% to 3.5% in routine testing. Oxidized tea tree oil shows increased sensitizing potential. Multiple studies confirm it causes more allergic reactions than other essential oils, with limonene, terpinolene, and alpha-terpinene identified as primary allergens (PubMed PMID: 27173437, PMC9146230, PMID: 17535193).

**2. Salicylic Acid - Skin Irritant** (severity: low, confidence: 0.85)

> MSDS data indicates salicylic acid is classified as irritating to respiratory system and skin (R37/38) and risk of serious damage to eyes (R41). May worsen dryness, eczema, and rosacea in sensitive individuals. WHMIS Canada classifies as CLASS D-2A: Material causing other toxic effects. Not classified as carcinogen by IARC, ACGIH, NTP, or CA Prop 65 (westliberty.edu MSDS).

**3. Hydrocolloid Adhesive - Skin Irritation Risk** (severity: low, confidence: 0.75)

> Studies indicate hydrocolloid dressings can cause skin irritation with repeated application/removal, including erythema, increased TEWL (transepidermal water loss), peeling, and stratum corneum disruption in individuals with sensitive or thin skin (PMC11856799, PMC10792606). Reddit users report allergic reactions to adhesive components in pimple patches.

#### Research Sources (11):

| Type         | URL                                        | Finding                                                                                                           |
| ------------ | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| manufacturer | amazon.com                                 | Product labeled Propylene Glycol Free, Paraffin Free, Alcohol Free, Paraben Free, Formaldehyde Free, Cruelty Free |
| manufacturer | skinsort.com                               | Third-party ingredient analysis confirms three-ingredient formulation                                             |
| regulatory   | N/A                                        | No FDA, Health Canada, or EPA recalls or warnings found                                                           |
| scientific   | pubmed.ncbi.nlm.nih.gov/27173437/          | Tea tree oil contact allergy review: 0.1-3.5% positive reaction rate                                              |
| scientific   | pmc.ncbi.nlm.nih.gov/articles/PMC9146230/  | Spreading allergic contact dermatitis study on tea tree oil                                                       |
| scientific   | pubmed.ncbi.nlm.nih.gov/17535193/          | Retrospective review: 1.8% prevalence of positive reactions                                                       |
| scientific   | westliberty.edu MSDS                       | Salicylic acid WHMIS CLASS D-2A classification                                                                    |
| scientific   | pmc.ncbi.nlm.nih.gov/articles/PMC10792606/ | Hydrocolloid adhesive irritant study                                                                              |
| scientific   | pmc.ncbi.nlm.nih.gov/articles/PMC11856799/ | Hydrocolloid dermatology review                                                                                   |
| consumer     | reddit.com/r/SkincareAddiction             | User reports rash reaction to microdart pimple patch                                                              |
| consumer     | reddit.com/r/30PlusSkinCare                | User reports allergic reaction to adhesive causing swelling                                                       |

### 4.2 Cohere Command A Results

```json
{
  "time_seconds": 29.0,
  "confidence": 0.5,
  "concerns_found": 0,
  "sources_found": 5
}
```

#### Concerns Detected: None

#### Research Sources (5):

| Type         | Finding                                                         |
| ------------ | --------------------------------------------------------------- |
| manufacturer | Product contains Salicylic Acid, Tea Tree Oil, and Hydrocolloid |
| regulatory   | No FDA recall warnings found                                    |
| ingredient   | No relevant information found on safety and toxicity            |
| legal        | No lawsuits or settlements found                                |
| consumer     | No consumer feedback or allergy reactions found on Reddit       |

---

## 5. Comparative Analysis (Initial Test - Flawed Parity)

> **Note:** This analysis is from the flawed test. See Section 7.4 for TRUE parity comparison.

### 5.1 Quantitative Comparison

| Metric               | Claude Sonnet 4 | Cohere Command A | Delta |
| -------------------- | --------------- | ---------------- | ----- |
| **Execution Time**   | 55.7s           | 29.0s            | -48%  |
| **Confidence**       | 85%             | 50%              | -35pp |
| **Concerns Found**   | 3               | 0                | -3    |
| **Sources Cited**    | 11              | 5                | -6    |
| **PubMed Citations** | 4               | 0                | -4    |
| **Reddit Findings**  | 2               | 0                | -2    |
| **Token Cost**       | $0.142          | ~$0.06\*         | -58%  |

\*Cohere cost estimated from similar runs due to error in final test

### 5.2 Qualitative Differences

#### What Claude Found That Cohere Missed:

1. **Tea Tree Oil Sensitization Research**
   - Claude cited 3 PubMed studies documenting 0.1-3.5% contact dermatitis rates
   - Identified specific allergens: limonene, terpinolene, alpha-terpinene
   - Noted that oxidation increases sensitizing potential

2. **MSDS Safety Classifications**
   - Found WHMIS Canada CLASS D-2A classification for salicylic acid
   - Identified R37/38 (skin/respiratory irritant) and R41 (eye damage risk) codes

3. **Real User Reports**
   - Found 2 Reddit threads documenting allergic reactions to pimple patch adhesives
   - Correlated scientific findings with consumer experiences

#### Why Cohere Underperformed:

1. **Shallow Information Synthesis:** Cohere reported "no information found" for ingredient safety despite searching the same databases
2. **No Scientific Literature Integration:** Zero PubMed/PMC citations despite searching ingredient safety
3. **Weak Consumer Research:** Reported "no Reddit feedback found" despite Reddit threads existing

---

## 6. Pricing Analysis

### 6.1 Official Pricing (as of January 2024)

| Model            | Input (per 1M tokens) | Output (per 1M tokens) | Source                |
| ---------------- | --------------------- | ---------------------- | --------------------- |
| Claude Sonnet 4  | $3.00                 | $15.00                 | anthropic.com/pricing |
| Cohere Command A | $2.50                 | $10.00                 | cohere.com/pricing    |

### 6.2 Cost Per Analysis

**Claude Sonnet 4:**

- Input: 34,508 tokens × $3.00/1M = $0.104
- Output: 2,596 tokens × $15.00/1M = $0.039
- **Total: $0.142**

**Cohere Command A (estimated):**

- Input: ~20,000 tokens × $2.50/1M = $0.050
- Output: ~1,000 tokens × $10.00/1M = $0.010
- **Total: ~$0.060**

### 6.3 Cost-Quality Tradeoff

| Scenario | Monthly Analyses | Claude Cost | Cohere Cost | Savings      | Quality Impact           |
| -------- | ---------------- | ----------- | ----------- | ------------ | ------------------------ |
| Small    | 1,000            | $142        | $60         | $82 (58%)    | Misses critical concerns |
| Medium   | 10,000           | $1,420      | $600        | $820 (58%)   | Misses critical concerns |
| Large    | 100,000          | $14,200     | $6,000      | $8,200 (58%) | Misses critical concerns |

---

## 7. Feature Parity Experiment

> **⚠️ CAVEAT: Initial "Feature Parity" Was Flawed**
>
> Our first attempt at feature parity still had a critical difference: Cohere had access to `lookup_ingredient_research` (a database lookup tool) that Claude did not have.
>
> **However, the tool description explicitly warned Cohere:**
>
> ```
> WARNING: This database may be incomplete or empty. ALWAYS use web_search
> for ingredient research first. Only use this tool as a supplementary check
> AFTER you have already searched for the ingredient via web_search.
> ```
>
> Cohere ignored these instructions and used the database lookup instead of web search. When the tool returned nothing, Cohere accepted this and reported 0 concerns - it didn't fall back to web search despite having that option available.
>
> **Fault is shared:**
>
> - **Our fault:** Gave Cohere an extra tool that Claude didn't have (unequal tools)
> - **Cohere's fault:** Ignored explicit instructions to use web_search first
>
> **The results in Sections 4-6 reflect this flawed test.** Section 7.4 onwards shows TRUE parity results after removing the tool entirely. When forced to web search like Claude, Cohere found 3 concerns vs Claude's 2.

### 7.1 Motivation

The initial test had a potential confounder: **the agents had different prompts and context**. An audit revealed:

| Component                     | Claude Agent             | Cohere Agent (Initial)                     |
| ----------------------------- | ------------------------ | ------------------------------------------ |
| System prompt length          | ~1000 lines              | ~30 lines                                  |
| Knowledge bases embedded      | ✅ 32 allergens, 75 PFAS | ❌ None                                    |
| Classification rules          | ✅ Detailed rules        | ❌ None                                    |
| "scientific" search type      | ✅ Available             | ❌ Missing                                 |
| Priority ingredients guidance | ✅ Listed                | ❌ None                                    |
| **Tools available**           | `web_search` only        | `web_search`, `lookup_ingredient_research` |

**Question:** Is the quality gap due to model capability or missing context?

### 7.2 Discovery: Tools Were NOT Equal

A deeper audit revealed a **critical tool difference**:

| Tool                         | Claude        | Cohere (Initial)  |
| ---------------------------- | ------------- | ----------------- |
| `web_search`                 | ✅            | ✅                |
| `lookup_ingredient_research` | ❌            | ✅ ← **Problem!** |
| `save_analysis`              | ❌ (implicit) | ✅                |
| `report_failure`             | ❌            | ✅                |

The `lookup_ingredient_research` tool queried an **empty database table** (`ingredient_research` has 0 rows). Cohere was using this "shortcut" instead of web searching for ingredients, which returned nothing.

### 7.3 TRUE Tool Parity Implementation

We removed `lookup_ingredient_research` from Cohere's tools:

```python
# Build tools - NOTE: lookup_ingredient_research removed for TRUE parity with Claude
self.tools = [
    web_search,
    # lookup_ingredient_research,  # REMOVED: empty database, caused Cohere to skip web search
    save_analysis,
    report_failure,
]
```

Both agents now have:

- Knowledge bases (32 allergens, 75 PFAS compounds) dynamically embedded in prompt
- Classification rules ("only classify as allergen if in knowledge base")
- Search types (including "scientific")
- Evidence requirements (.gov, .edu, peer-reviewed sources)
- Per-ingredient research guidance
- **Identical research tool:** `web_search` only

### 7.4 TRUE Tool Parity Results

| Metric               | Claude | Cohere (TRUE Parity) |
| -------------------- | ------ | -------------------- |
| **Time**             | 40.8s  | 45.1s                |
| **Confidence**       | 90%    | 60%                  |
| **Concerns Found**   | 2      | 3                    |
| **Research Sources** | 10     | 4                    |
| **PubMed Citations** | 4      | 3                    |

### 7.5 Key Finding: Quality Gap Narrows Significantly

With TRUE tool parity, **Cohere found MORE concerns than Claude** (3 vs 2), but with notable differences:

**Claude's Analysis (TRUE Parity):**

```json
{
  "other_concerns": [
    {
      "name": "Tea Tree Oil (Melaleuca Alternifolia)",
      "category": "under_investigation",
      "severity": "low",
      "description": "Contact allergen with documented sensitization rates of 0.1-3.5% in patch testing studies per multiple dermatology research groups. North American Contact Dermatitis Group reports 1.4% positive reaction rate. Oxidized tea tree oil shows increased sensitizing potential per PubMed PMC9146230.",
      "confidence": 0.85
    },
    {
      "name": "Salicylic Acid",
      "category": "under_investigation",
      "severity": "low",
      "description": "May cause mild skin irritation and eye irritation per MSDS data from westliberty.edu and delta.edu. Risk phrases R36/37/38 indicate irritation to eyes, respiratory system, and skin. No IARC carcinogen classification found.",
      "confidence": 0.7
    }
  ],
  "research_sources": [
    {
      "type": "manufacturer_website",
      "url": "incidecoder.com/products/patchrx-pimple-patches",
      "finding": "Confirmed complete ingredient list"
    },
    {
      "type": "manufacturer_website",
      "url": "skinsort.com/products/patchrx/salicylic-pimple-patches",
      "finding": "Confirmed three ingredients"
    },
    {
      "type": "scientific_study",
      "url": "pubmed.ncbi.nlm.nih.gov/16243420/",
      "finding": "Tea tree oil review: topical use relatively safe with minor adverse events"
    },
    {
      "type": "scientific_study",
      "url": "pubmed.ncbi.nlm.nih.gov/16296153/",
      "finding": "German study: 1.1% sensitization rate to 5% tea tree oil"
    },
    {
      "type": "scientific_study",
      "url": "pubmed.ncbi.nlm.nih.gov/22653070/",
      "finding": "NACDG: 1.4% positive reaction rate to tea tree oil"
    },
    {
      "type": "scientific_study",
      "url": "pmc.ncbi.nlm.nih.gov/articles/PMC9146230/",
      "finding": "Oxidized tea tree oil has increased sensitizing potential"
    },
    {
      "type": "scientific_study",
      "url": "westliberty.edu/health-and-safety/files/.../Salicylic-acid.pdf",
      "finding": "MSDS: R36/37/38 irritation classification"
    },
    {
      "type": "consumer_reports",
      "url": "reddit.com/r/SkincareAddiction/...",
      "finding": "Users report rash reactions to patches with salicylic acid"
    },
    {
      "type": "consumer_reports",
      "url": "reddit.com/r/SkincareAddiction/...",
      "finding": "User reported red circle irritation from tea tree oil patch"
    },
    {
      "type": "consumer_reports",
      "url": "reddit.com/r/30PlusSkinCare/...",
      "finding": "Users report allergic reactions to adhesive"
    }
  ],
  "confidence": 0.9
}
```

**Cohere's Analysis (TRUE Parity):**

```json
{
  "other_concerns": [
    {
      "name": "Salicylic Acid",
      "category": "under_investigation",
      "severity": "low",
      "description": "Mild irritant, may cause skin rash in sensitive individuals. <co>PubMed PMID: 19834431</co>",
      "confidence": 0.7
    },
    {
      "name": "Tea Tree Oil",
      "category": "under_investigation",
      "severity": "low",
      "description": "Relatively safe for topical use, but cases of allergic contact dermatitis reported. <co>PubMed PMID: 16243420</co>",
      "confidence": 0.6
    },
    {
      "name": "Hydrocolloid",
      "category": "under_investigation",
      "severity": "low",
      "description": "Can cause irritant contact dermatitis and allergic contact dermatitis. <co>PMC3276804</co>",
      "confidence": 0.5
    }
  ],
  "research_sources": [
    {
      "type": "manufacturer_website",
      "url": "amazon.ca/dp/B0BNW7WNLL",
      "finding": "Product page with ingredients list"
    },
    {
      "type": "scientific_study",
      "url": "pubmed.ncbi.nlm.nih.gov/19834431",
      "finding": "Salicylic Acid - mild irritant"
    },
    {
      "type": "scientific_study",
      "url": "pubmed.ncbi.nlm.nih.gov/16243420",
      "finding": "Tea Tree Oil - relatively safe, cases of allergic contact dermatitis"
    },
    {
      "type": "scientific_study",
      "url": "pmc.ncbi.nlm.nih.gov/articles/PMC3276804",
      "finding": "Hydrocolloid - can cause contact dermatitis"
    }
  ],
  "confidence": 0.6
}
```

### 7.6 Qualitative Differences Analysis

| Aspect                | Claude                              | Cohere                     |
| --------------------- | ----------------------------------- | -------------------------- |
| **Concerns found**    | 2                                   | 3 (found Hydrocolloid)     |
| **Description depth** | Detailed with specific % rates      | Brief with single citation |
| **PubMed citations**  | 4 unique studies                    | 3 unique studies           |
| **Consumer research** | 3 Reddit threads cited              | None                       |
| **Confidence level**  | 90%                                 | 60%                        |
| **Source variety**    | 5 types (mfr, scientific, consumer) | 2 types (mfr, scientific)  |

### 7.7 Key Insights (TRUE Tool Parity - Shortcut Removed)

1. **Cohere CAN find concerns** when given the right tools - it found Hydrocolloid which Claude missed
2. **Claude provides richer context** - specific sensitization percentages, multiple studies per claim
3. **Consumer research gap** - Claude searched Reddit; Cohere did not
4. **Lower confidence is appropriate** - Cohere's 60% reflects its less thorough research
5. **Tool selection was the blocker** - the empty database lookup was causing Cohere to fail entirely

---

## 8. Identical Tools Experiment (Both Have Database Lookup)

### 8.1 Motivation

The TRUE parity test removed `lookup_ingredient_research` from Cohere. But a fairer test is: **give both agents the same tools and see who follows instructions**.

The tool description explicitly warns:

```
WARNING: This database may be incomplete or empty. ALWAYS use web_search
for ingredient research first. Only use this tool as a supplementary check
AFTER you have already searched for the ingredient via web_search.
```

**Question:** Does Claude follow this instruction? Does Cohere?

### 8.2 Test Setup

Both agents given identical tools:

- `web_search` (Tavily API)
- `lookup_ingredient_research` (empty database with warning)
- Terminal actions (save_analysis, report_failure for Cohere)

### 8.3 Results

| Metric               | Claude | Cohere |
| -------------------- | ------ | ------ |
| **Time**             | 38.8s  | 78.9s  |
| **Confidence**       | 88%    | 85%    |
| **Concerns Found**   | 3      | 3      |
| **Research Sources** | 8      | 7      |

Both agents found the same 3 concerns!

### 8.4 Behavioral Analysis

**Claude's Tool Usage (followed instructions perfectly):**

```
Iteration 1: 7 web_search calls
  - manufacturer: PatchRx pimple patches official ingredients
  - regulatory: PatchRx recall FDA warning Health Canada
  - ingredient: salicylic acid toxicity IARC classification
  - ingredient: tea tree oil melaleuca alternifolia toxicity
  - ingredient: hydrocolloid toxicity safety dermatological
  - legal: PatchRx class action lawsuit settlement
  - consumer: PatchRx pimple patches reaction allergy reddit

Iteration 2: 3 lookup_ingredient_research calls (AFTER web search)
  - salicylic acid → "No research found"
  - tea tree oil → "No research found"
  - hydrocolloid → "No research found"

Iteration 3: Synthesized all findings into final JSON
```

Claude used the database lookup **as a supplementary check AFTER web search** - exactly as the warning instructed.

**Cohere's Tool Usage (skipped database entirely):**

```
8 tool calls - ALL web_search:
  - manufacturer, regulatory, 3x ingredient, legal, consumer, save_analysis
  - Did NOT use lookup_ingredient_research at all
```

### 8.5 Key Finding: Instruction-Following Behavior

| Behavior                         | Claude | Cohere                            |
| -------------------------------- | ------ | --------------------------------- |
| Read warning in tool description | ✅ Yes | ❓ Unclear                        |
| Used web_search first            | ✅ Yes | ✅ Yes (this run)                 |
| Used database as supplementary   | ✅ Yes | ❌ Skipped entirely               |
| Consistent across runs           | ✅ Yes | ❌ No (previous run used only DB) |

**Cohere's Non-Determinism:**

- **Run 1 (before TRUE parity):** Used ONLY `lookup_ingredient_research`, skipped web_search → 0 concerns
- **Run 2 (identical tools):** Used ONLY `web_search`, skipped database → 3 concerns

This variability at temperature=0.3 is concerning for production use.

### 8.6 Conclusion

When given identical tools with clear instructions:

- **Claude follows instructions precisely** - web_search first, database as supplementary check
- **Cohere's behavior is inconsistent** - sometimes takes shortcut, sometimes skips the tool entirely
- **Both can find concerns** when behaving correctly
- **Claude is 2x faster** (38.8s vs 78.9s) while following instructions

---

## 9. LangGraph vs Native SDK Experiment

### 9.1 Motivation

Cohere's non-deterministic behavior raised a question: **Is the inconsistency caused by the LangGraph wrapper or Cohere itself?**

We built a native Cohere agent using the Python SDK directly (no LangGraph) to isolate the variable.

### 9.2 Implementation

```python
# Native Cohere agent (no LangGraph wrapper)
import cohere

co = cohere.ClientV2(api_key=settings.cohere_api_key)

response = co.chat(
    model="command-a-03-2025",
    messages=messages,
    tools=TOOLS,  # Same tools as LangGraph version
    temperature=0.3,  # Same temperature
)

# Manual tool execution loop (same as Claude agent pattern)
while response.message.tool_calls:
    # Execute tools, add results to messages
    # Continue until no more tool calls
```

### 9.3 Three-Way Comparison Results

**Original Results (Sequential Prompt):**
| Metric | Claude | Cohere (LangGraph) | Cohere (Native SDK) |
|--------|--------|-------------------|---------------------|
| **Time** | 45.0s | 323.2s | 166.1s |
| **Confidence** | 85% | 70% | 75% |
| **Concerns Found** | 3 | 2 | 3 |
| **Research Sources** | 12 | 5 | 7 |

**Updated Results (Parallel Prompt + Parallel Execution):**
| Metric | Claude | Cohere (LangGraph) | Cohere (Native SDK) |
|--------|--------|-------------------|---------------------|
| **Time** | 44.95s | 38.61s | 41.87s |
| **Confidence** | 80% | 30%_ | 80% |
| **Concerns Found** | 3 | 0_ | 1 |
| **Research Sources** | 11 | 0\* | 7 |

\*LangGraph Cohere had a bug where it didn't call `save_analysis` - returned default result

### 9.4 Concerns Found

**Claude:** Tea Tree Oil, Salicylic Acid, Hydrocolloid (3)
**Cohere (LangGraph):** Salicylic Acid, Hydrocolloid (2) - **missed Tea Tree Oil**
**Cohere (Native):** Salicylic Acid, Tea Tree Oil, Hydrocolloid (3)

### 9.5 Key Findings

1. **LangGraph wrapper DOES affect behavior:**
   - Native Cohere found 3 concerns (same as Claude)
   - LangGraph Cohere found only 2 concerns (missed Tea Tree Oil)

2. **LangGraph adds significant latency:**
   - Native: 166.1s
   - LangGraph: 323.2s (2x slower)

3. **Claude is still fastest:**
   - Claude: 45.0s (3.7x faster than Native Cohere)

4. **Both Cohere versions followed instructions this run:**
   - Neither used `lookup_ingredient_research`
   - Both went straight to web_search

### 9.6 LangGraph Overhead Analysis

| Aspect             | LangGraph | Native SDK |
| ------------------ | --------- | ---------- |
| Tool calls         | 8         | 7          |
| Time per call      | ~40s      | ~24s       |
| Total time         | 323.2s    | 166.1s     |
| Framework overhead | ~50%      | Baseline   |

### 9.7 Conclusion

The LangGraph wrapper introduces:

- **Performance overhead:** 2x slower execution
- **Behavioral differences:** Different tool selection (missed one concern)
- **Additional complexity:** More moving parts that can fail

**For production Cohere deployments, the native SDK may be preferable** for both performance and consistency.

---

## 10. Prompt Wording Affects Tool Batching (Critical Discovery)

### 10.1 The Problem

Our timing comparisons showed Claude completing in ~45s while LangGraph Cohere took ~323s. We hypothesized this was due to:

- LangGraph ReAct pattern forcing turn-by-turn tool calls
- Framework overhead
- Model capability differences

However, a reference implementation (scraper-agent) using the same LangGraph pattern with Cohere executed tools in parallel. Why?

### 10.2 The Discovery

The difference was **prompt wording**:

**Original Prompt (Sequential Behavior):**

```
Execute these searches IN ORDER:

1. MANUFACTURER: web_search(...)
2. REGULATORY: web_search(...)
3. PER-INGREDIENT RESEARCH: ...
4. LEGAL: web_search(...)
5. CONSUMER: web_search(...)
6. save_analysis with COMPLETE JSON
```

**Fixed Prompt (Parallel Behavior):**

```
Execute ALL of these searches (you can call multiple tools at once for efficiency):

- MANUFACTURER: web_search(...)
- REGULATORY: web_search(...)
- LEGAL: web_search(...)
- CONSUMER: web_search(...)
- PER-INGREDIENT RESEARCH: ...

CRITICAL REMINDERS:
- You CAN and SHOULD call multiple web_search tools in a single response for efficiency
```

### 10.3 Results: 8.4x Speedup

| Metric                    | Before (Sequential Prompt) | After (Parallel Prompt) | Improvement   |
| ------------------------- | -------------------------- | ----------------------- | ------------- |
| **LangGraph Cohere Time** | 323.2s                     | **38.6s**               | 8.4x faster   |
| **Tool Batching**         | 1-3 tools per turn         | 7 tools in 1 response   | Full batching |
| **Claude Time**           | 45.0s                      | 35.1s                   | Baseline      |
| **Cohere vs Claude**      | 7x slower                  | **Only 10% slower**     | Near parity   |

### 10.4 Evidence: Tool Call Timestamps

**Before (Sequential):**

```
23:15:01 - Tool: web_search (manufacturer)
23:15:15 - Tool: web_search (regulatory)
23:15:28 - Tool: web_search (ingredient)
... (14+ seconds between each call)
```

**After (Parallel):**

```
23:33:06.592 - Tool: web_search
23:33:06.592 - Tool: web_search
23:33:06.592 - Tool: web_search
23:33:06.592 - Tool: web_search
23:33:06.592 - Tool: web_search
23:33:06.592 - Tool: web_search
23:33:06.592 - Tool: web_search
(All 7 tools at SAME millisecond timestamp)
```

### 10.5 Quality Comparison (Parallel Prompt)

| Metric               | Claude | Cohere (LangGraph) |
| -------------------- | ------ | ------------------ |
| **Time**             | 35.1s  | 38.6s              |
| **Concerns Found**   | 2      | 3                  |
| **Research Sources** | 9      | 2                  |
| **Confidence**       | 88%    | 60%                |

Cohere now matches Claude's speed while finding MORE concerns (3 vs 2), though with fewer sources and lower confidence.

### 10.6 Plot Twist: Native SDK Ignores Sequential Instructions

We discovered that Native Cohere SDK had the **same sequential prompt** (numbered 1-5 steps) but was still 2x faster than LangGraph (166s vs 323s). This reveals a deeper insight:

| Agent            | Prompt Style   | Actual Behavior                       | Time  |
| ---------------- | -------------- | ------------------------------------- | ----- |
| LangGraph Cohere | Numbered steps | **Respected** - executed sequentially | 323s  |
| Native Cohere    | Numbered steps | **Ignored** - batched anyway          | 166s  |
| LangGraph Cohere | "All at once"  | Batched                               | 38.6s |

**LangGraph is more obedient to prompt instructions than Native SDK.**

### 10.7 Key Insights

1. **LangGraph ReAct respects prompt wording** - "IN ORDER" creates sequential; "all at once" enables batching
2. **Native SDK ignores sequential language** - batches regardless of numbered steps
3. **Framework choice affects instruction-following** - LangGraph is more literal/obedient
4. **For LangGraph, prompt wording is critical** - must explicitly encourage batching
5. **For Native SDK, prompt wording matters less** - model decides on its own

### 10.8 Implications for Agent Design

| Use Case                              | Recommendation                                    |
| ------------------------------------- | ------------------------------------------------- |
| Need predictable sequential execution | Use LangGraph with numbered steps                 |
| Need maximum speed                    | Use Native SDK or LangGraph with "batch" language |
| Need instruction-following compliance | Use LangGraph (more obedient)                     |
| Need flexibility                      | Use Native SDK (model decides)                    |

This is a **critical lesson for agentic prompt engineering**: The same prompt can produce different behaviors depending on the framework. LangGraph's ReAct pattern is more literal in interpreting instructions, while Native SDK gives the model more autonomy.

### 10.9 Final Timing Comparison (All Optimizations Applied)

After applying both prompt changes and parallel execution:

| Agent            | Before | After      | Improvement |
| ---------------- | ------ | ---------- | ----------- |
| Claude           | 45.0s  | 44.95s     | Baseline    |
| LangGraph Cohere | 323.2s | **38.61s** | 8.4x faster |
| Native Cohere    | 166.1s | **41.87s** | 4.0x faster |

**Key Insight:** With proper prompt wording and parallel execution, all three agents complete in ~40-45 seconds. The original 7x performance gap was due to:

1. Sequential prompt language (numbered steps)
2. Sequential tool execution in Native SDK (now fixed with `asyncio.gather`)
3. LangGraph respecting sequential instructions (now overridden with "batch" language)

---

## 11. Cohere Drops Reddit/Consumer Sources (Literal Interpretation)

### 11.1 The Problem

After fixing tool batching, we noticed Cohere's output was missing consumer/Reddit sources:

| Agent           | Total Sources | Consumer/Reddit Sources                          |
| --------------- | ------------- | ------------------------------------------------ |
| Claude          | 11            | 2 (Reddit r/SkincareAddiction, r/30PlusSkinCare) |
| Cohere (Native) | 4             | **0**                                            |

Both agents called the same consumer searches. Both received Reddit results. But Cohere excluded them from its final output.

### 11.2 Root Cause: Literal Prompt Interpretation

The system prompt contained this evidence requirement:

```
3. **EVIDENCE REQUIREMENTS:**
   - MUST have credible source (.gov, .edu, peer-reviewed journal, PubMed)
   - MUST include source citation in description
```

**Claude's interpretation:** "Scientific claims need credible sources, but user-reported reactions are different evidence."

**Cohere's interpretation:** "Reddit is not .gov, .edu, or PubMed. Therefore, exclude it."

This is consistent with our earlier finding that **Cohere interprets instructions more literally** than Claude.

### 11.3 The Fix

Updated the evidence requirements to explicitly validate consumer sources:

```python
# Before (Cohere excluded Reddit)
3. **EVIDENCE REQUIREMENTS:**
   - MUST have credible source (.gov, .edu, peer-reviewed journal, PubMed)
   - MUST include source citation in description

# After (Cohere includes Reddit)
3. **EVIDENCE REQUIREMENTS:**
   - Scientific claims: Use .gov, .edu, peer-reviewed journal, PubMed
   - Consumer reports: Reddit user experiences ARE valid evidence for skin reactions, allergies
   - ALWAYS include consumer/Reddit sources in research_sources if users report reactions
   - MUST include source citation in description
```

### 11.4 Results After Fix

| Metric              | Before Fix | After Fix |
| ------------------- | ---------- | --------- |
| **Total Sources**   | 4          | 6         |
| **Consumer/Reddit** | 0          | **1** ✅  |
| **Tool Calls**      | 11         | 17        |

Cohere now performs **per-ingredient consumer searches** (searching Reddit for each of Salicylic Acid, Tea Tree Oil, Hydrocolloid separately) - more thorough than before.

Consumer source found after fix:

> "Some users reported skin irritation after using pimple patches with tea tree oil"
> Source: reddit.com/r/SkincareAddiction

### 11.5 Key Insight: Implicit vs Explicit Instructions

| Instruction Type                       | Claude                            | Cohere                      |
| -------------------------------------- | --------------------------------- | --------------------------- |
| "Sources MUST be .gov/.edu/PubMed"     | Applies to scientific claims only | Applies to ALL sources      |
| "Reddit is valid for consumer reports" | Infers this implicitly            | Requires explicit statement |
| Unstated exceptions                    | Handles gracefully                | Does not infer              |

**Lesson:** When writing prompts for Cohere, you must be exhaustively explicit. Any source type you want included must be explicitly mentioned as valid. Cohere will not infer reasonable exceptions.

### 11.6 Pattern: Cohere Requires Explicit Permissions

This is the third instance of Cohere requiring explicit instructions:

| Finding          | Claude Behavior           | Cohere Behavior                        |
| ---------------- | ------------------------- | -------------------------------------- |
| Tool batching    | Batches by default        | Requires "call multiple tools at once" |
| Database warning | Follows warning           | Ignores warning (uses shortcut)        |
| Reddit sources   | Includes as supplementary | Requires explicit "Reddit is valid"    |

**Cohere's mental model:** "If it's not explicitly permitted, it's forbidden."
**Claude's mental model:** "If it's not explicitly forbidden, use judgment."

---

## 12. Limitations & Caveats

### 12.1 Study Limitations

1. **Single Product Test:** Results based on one skincare product; may not generalize to other categories
2. **No A/B Testing:** Sequential runs, not randomized controlled comparison
3. **Search Variability:** Web search results may vary between runs
4. **No Ground Truth:** No dermatologist validation of identified concerns
5. **Cohere Implementation:** Used LangGraph wrapper; native Cohere API might perform differently

### 12.2 Potential Confounders (Addressed)

| Confounder            | Status        | Notes                                                |
| --------------------- | ------------- | ---------------------------------------------------- |
| Prompt engineering    | ✅ Addressed  | TRUE parity test used identical prompts              |
| Knowledge bases       | ✅ Addressed  | Both agents received same 32 allergens, 75 PFAS      |
| Tool availability     | ✅ Addressed  | Removed `lookup_ingredient_research` for TRUE parity |
| Temperature settings  | Partial       | Claude default (~1.0) vs Cohere 0.3                  |
| Framework differences | Not addressed | Anthropic API vs LangGraph wrapper                   |

### 12.3 What This Study Does NOT Claim

- ❌ Cohere cannot find safety concerns (it can, with proper tools)
- ❌ Claude always finds more concerns (Cohere found Hydrocolloid; Claude missed it)
- ❌ These results generalize to all use cases
- ❌ Cost savings are never worth the quality tradeoff
- ❌ The identified concerns are clinically validated

---

## 13. Reproducibility

### 13.1 Code Repository

```
https://github.com/[username]/ruh
backend/src/infrastructure/claude_agent.py    # Claude implementation
backend/src/infrastructure/langgraph_agent.py # Cohere implementation
backend/src/infrastructure/search_tool_service.py # Search infrastructure
```

### 13.2 Dependencies

```toml
anthropic = ">=0.39.0"
langchain-cohere = ">=0.3.0"
langgraph = ">=0.2.0"
tavily-python = ">=0.3.0"
```

### 13.3 Environment Variables Required

```bash
ANTHROPIC_API_KEY=sk-ant-...
COHERE_API_KEY=...
TAVILY_API_KEY=tvly-...
```

### 13.4 Running the Comparison

```bash
cd backend
source .venv/bin/activate
python scripts/test_full_analysis.py "https://amazon.ca/dp/B0BNW7WNLL" --claude
python scripts/test_full_analysis.py "https://amazon.ca/dp/B0BNW7WNLL" --langgraph
```

---

## 14. Conclusions

### 14.1 Key Takeaways

1. **Instruction-Following is the Key Differentiator:** Claude followed tool description warnings precisely; Cohere's behavior was inconsistent
2. **Both Models CAN Find Concerns:** With identical tools, both found 3 concerns - capability is equivalent
3. **Prompt Wording is Critical for Cohere:** "IN ORDER 1-5" → sequential (323s); "all at once" → parallel (38s) - 8.4x difference
4. **LangGraph is More Obedient Than Native SDK:** LangGraph respects sequential instructions; Native SDK ignores them
5. **Cohere Requires Explicit Permissions:** If source type not explicitly permitted, Cohere excludes it (e.g., Reddit)
6. **Framework Choice Affects Both Speed and Behavior:** LangGraph was 2x slower and affected tool selection
7. **Claude Infers; Cohere is Literal:** Claude handles unstated exceptions gracefully; Cohere needs exhaustive specifications

### 14.2 What the Experiments Proved

| Hypothesis                                   | Result                                                                               |
| -------------------------------------------- | ------------------------------------------------------------------------------------ |
| "Cohere can't find concerns"                 | ❌ Disproven - found 3 concerns when behaving correctly                              |
| "Claude follows tool instructions"           | ✅ Confirmed - used web_search first, database as supplementary                      |
| "Cohere follows tool instructions"           | ❌ Inconsistent - sometimes shortcut, sometimes skipped entirely                     |
| "Quality gap is about instruction-following" | ✅ Supported - same tools, different adherence to warnings                           |
| "Cohere's behavior is deterministic"         | ❌ Disproven - different behavior at same temperature                                |
| "LangGraph is a neutral wrapper"             | ❌ Disproven - affected both performance (2x slower) and behavior (missed 1 concern) |
| "Native SDK performs better than LangGraph"  | ✅ Confirmed - faster and found more concerns                                        |
| "Prompt wording affects tool batching"       | ✅ Confirmed - 8.4x speedup from "IN ORDER" → "all at once"                          |
| "LangGraph is more obedient than Native SDK" | ✅ Confirmed - respects sequential instructions; Native SDK ignores them             |
| "Cohere includes all search results"         | ❌ Disproven - excluded Reddit until explicitly permitted in prompt                  |

### 14.3 Revised Recommendations

| Application                           | Recommended Model | Rationale                                              |
| ------------------------------------- | ----------------- | ------------------------------------------------------ |
| **Production systems**                | **Claude**        | Consistent, predictable behavior; follows instructions |
| **Screening/triage**                  | **Either**        | Both find concerns when working correctly              |
| **Speed-critical**                    | **Claude**        | 2x faster (38.8s vs 78.9s)                             |
| **Budget-constrained (non-critical)** | **Cohere**        | Works when it works; ~40% cheaper                      |
| **Compliance/research**               | **Claude**        | Instruction-following critical for audit trails        |

### 14.4 Critical Lessons for Agent Builders

1. **Tool descriptions are instructions** - Claude reads and follows them; test if your model does too
2. **Non-determinism is dangerous** - Cohere behaved completely differently between runs at same temperature
3. **Test with realistic tool sets** - Extra tools can cause unexpected behavior (shortcuts, skipping)
4. **Warnings in tool descriptions work** - But only if the model reads them
5. **Framework wrappers add overhead** - LangGraph was 2x slower than native SDK and affected behavior
6. **Prompt wording affects tool batching** - Sequential language ("IN ORDER") causes sequential execution in LangGraph
7. **Be exhaustively explicit with Cohere** - Every valid source type must be explicitly permitted; nothing is inferred
8. **LangGraph is more obedient** - Use it when you need strict instruction-following; use Native SDK when you want flexibility
9. **Consider native SDKs for production** - Less abstraction = more control and better performance
10. **Prompt wording affects tool batching** - "IN ORDER" creates sequential execution; "all at once" enables batching (see Section 10)

### 12.5 Future Work

1. Run multiple trials to quantify Cohere's non-determinism rate
2. Test at different temperatures (does higher temp = more shortcut-taking?)
3. Test with clearer/stricter tool descriptions
4. Validate findings with dermatologists/toxicologists
5. Implement hybrid pipeline with determinism checks
6. Test with Cohere Command R+ (newer model)

---

## 13. Raw API Responses

### 13.1 Claude Token Usage Detail

```json
{
  "calls": [
    {
      "call_name": "agent_safety_analysis_custom_iter1",
      "model": "claude-sonnet-4-5-20250929",
      "input_tokens": 2845,
      "output_tokens": 486,
      "total_cost_usd": 0.015825
    },
    {
      "call_name": "agent_safety_analysis_custom_iter2",
      "model": "claude-sonnet-4-5-20250929",
      "input_tokens": 9695,
      "output_tokens": 171,
      "total_cost_usd": 0.03165
    },
    {
      "call_name": "agent_safety_analysis_custom_iter3",
      "model": "claude-sonnet-4-5-20250929",
      "input_tokens": 10921,
      "output_tokens": 107,
      "total_cost_usd": 0.034368
    },
    {
      "call_name": "agent_safety_analysis_custom_iter4",
      "model": "claude-sonnet-4-5-20250929",
      "input_tokens": 11047,
      "output_tokens": 1832,
      "total_cost_usd": 0.060621
    }
  ],
  "total_cost_usd": 0.142464
}
```

### 13.2 Search Queries Executed

**Claude Agent Searches:**

1. `PatchRx Pimple Patches ingredients MSDS` (manufacturer)
2. `PatchRx FDA recall warning Health Canada` (regulatory)
3. `Salicylic acid safety toxicity IARC` (ingredient)
4. `Tea tree oil contact dermatitis allergy` (ingredient)
5. `Hydrocolloid adhesive skin irritation` (ingredient)
6. `PatchRx lawsuit settlement` (legal)
7. `pimple patch allergic reaction reddit` (consumer)

**Cohere Agent Searches:**

1. `PatchRx Pimple Patches ingredients` (manufacturer)
2. `PatchRx FDA recall warning` (regulatory)
3. `Salicylic Acid Tea Tree Oil safety toxicity` (ingredient)
4. `PatchRx lawsuit settlement` (legal)
5. `PatchRx pimple patches reddit reaction` (consumer)

---

## 14. Disclosure

- Author has no financial relationship with Anthropic or Cohere
- Testing conducted using personal API credits
- Code is open source under MIT license

---

_Document compiled: January 31, 2026_
_TRUE tool parity experiment: January 31, 2026_
_LangGraph vs Native SDK experiment: February 1, 2026_
_Test environment: macOS, Python 3.13, M-series Mac_
