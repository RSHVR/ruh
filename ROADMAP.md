# Ruh — Feature Roadmap

## Provenance Tracking for Groceries

Provenance tracking traces a grocery product's journey from origin to shelf — where raw ingredients were grown or raised, how they were processed, which facilities handled them, and what certifications apply at each step. The goal is to surface supply-chain transparency that labels alone don't provide.

### What this means concretely

- **Origin mapping**: Link ingredients to their source country, region, or farm where data is available (USDA import records, brand transparency pages, third-party audits)
- **Processing chain**: Identify intermediary steps — was the cocoa butter refined in a facility that also processes tree nuts? Was the olive oil cold-pressed at origin or bulk-shipped and rebottled?
- **Contamination risk scoring**: Flag products with long, opaque supply chains (higher likelihood of cross-contamination, undeclared additives, or PFAS exposure from packaging at transit points)
- **Certification verification**: Cross-reference claims (organic, non-GMO, fair trade) against actual certifying body databases rather than trusting label text alone

### Why it matters for Ruh

Ruh already analyzes what's _in_ a product. Provenance tracking answers where it _came from_ — a critical dimension for allergen cross-contamination risk, pesticide residue patterns tied to specific growing regions, and PFAS exposure from food-contact packaging used during transport and storage.

---

## Clinical Partnerships

### Dermatologist Network

Partner with dermatologists to validate and enhance Ruh's analysis for skincare, cosmetics, and personal care products.

- **Ingredient sensitivity profiles**: Dermatologist-reviewed mappings between ingredients and skin conditions (eczema, rosacea, contact dermatitis) that go beyond generic allergen flags
- **Formulation context**: Clinical input on concentration thresholds — a 0.5% retinol is a different risk profile than 0.025%, but both show up as "retinol" on a label
- **Review and endorsement pipeline**: Dermatologists review Ruh's harm scoring methodology for skin-relevant product categories and flag where the algorithm over- or under-weights specific ingredients

### Endocrinologist Network

Partner with endocrinologists to strengthen Ruh's detection and scoring of endocrine-disrupting compounds (EDCs).

- **EDC risk tiering**: Clinician-informed severity rankings for known disruptors (BPA, phthalates, parabens, PFAS, oxybenzone) based on current endocrinology research rather than blanket flagging
- **Cumulative exposure modeling**: Guidance on how to assess combined EDC load when a user scans multiple products in the same category (e.g., shampoo + conditioner + body wash all containing parabens)
- **Vulnerable population flags**: Endocrinologist-defined thresholds for higher-risk groups — pregnant users, children, thyroid disorder patients — where even low-level EDC exposure warrants stronger warnings

---

## Ingredient Interaction & Combinatorial Toxicity Prediction

Ruh currently evaluates ingredients in isolation — flagging known allergens, PFAS compounds, and individual harmful substances. But two individually safe ingredients can become dangerous when combined, heated, or exposed to UV during manufacturing. This feature predicts toxic outcomes from ingredient _combinations_ and manufacturing processes, not just individual ingredients.

### Interaction detection

- **Known dangerous pairs**: Flag established harmful combinations — bleach + ammonia producing chloramine gas, Vitamin C + niacinamide degrading at high concentrations, retinol + AHA/BHA causing excessive irritation and barrier damage
- **pH-dependent reactions**: Detect when combining acidic and alkaline ingredients degrades active compounds or creates new irritants (e.g., mixing L-ascorbic acid with alkaline peptides destabilizes both)
- **Heat/UV-activated transformations**: Identify ingredients that transform during manufacturing — certain preservatives release formaldehyde when heated, some UV filters degrade into toxic byproducts under sunlight exposure

### Manufacturing process modeling

- **Processing order, temperature, and duration**: Model how the sequence and conditions of manufacturing steps affect final product safety — an ingredient added before a high-heat emulsification step has a different safety profile than one added after cooling
- **Chemical transformations**: Account for emulsification, saponification, esterification, and other reactions that fundamentally alter ingredient safety profiles — saponified oils are chemically different from their raw inputs
- **Packaging interactions**: Flag ingredients that leach from or react with container materials — BPA from can linings migrating into acidic formulations, plasticizers transferring from flexible packaging, aluminum reacting with certain preservatives

### Predicted health effects

- **Toxicological outcome mapping**: Map interaction products to known health outcomes — irritation, sensitization, endocrine disruption, carcinogenicity — using established toxicology databases and literature
- **Dose-response modeling**: Move beyond binary "toxic or not" to estimate severity at realistic exposure levels — a trace amount of a reaction byproduct may be negligible, while the same compound at higher concentrations crosses safety thresholds
- **Acute vs. chronic exposure differentiation**: Distinguish between immediate reactions (contact dermatitis from a single use) and cumulative risks (endocrine disruption from daily exposure over months)

### Why it matters for Ruh

Current analysis catches products with individually harmful ingredients. This feature catches the harder problem: products where every ingredient looks safe on its own, but the _formulation_ is the danger. A sunscreen with safe UV filters and safe fragrance compounds that react under sunlight to produce sensitizing byproducts would pass current analysis but fail combinatorial screening. This is the difference between an ingredient list checker and a true product safety analyzer.
