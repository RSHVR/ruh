-- Migration: Seed allergen and PFAS knowledge base
-- Description: Add common allergens and PFAS compounds
-- Date: 2025-11-10

-- Seed common allergens
INSERT INTO allergens (name, synonyms, severity_default, common_sources) VALUES
    ('Peanuts', ARRAY['groundnuts', 'arachis oil'], 10, ARRAY['snack foods', 'baked goods', 'sauces']),
    ('Tree Nuts', ARRAY['almonds', 'walnuts', 'cashews', 'hazelnuts'], 10, ARRAY['baked goods', 'cereals', 'chocolates']),
    ('Milk', ARRAY['dairy', 'lactose', 'casein', 'whey'], 8, ARRAY['dairy products', 'baked goods', 'sauces']),
    ('Eggs', ARRAY['albumin', 'ovalbumin'], 8, ARRAY['baked goods', 'mayonnaise', 'pasta']),
    ('Soy', ARRAY['soya', 'soybean', 'lecithin'], 7, ARRAY['processed foods', 'sauces', 'tofu']),
    ('Wheat', ARRAY['gluten', 'flour'], 7, ARRAY['bread', 'pasta', 'baked goods']),
    ('Fish', ARRAY['seafood'], 9, ARRAY['sauces', 'supplements']),
    ('Shellfish', ARRAY['crustaceans', 'mollusks'], 9, ARRAY['sauces', 'supplements']),
    ('Sesame', ARRAY['tahini', 'sesame oil'], 7, ARRAY['baked goods', 'sauces', 'snacks']),
    ('Sulfites', ARRAY['sulfur dioxide', 'sodium sulfite'], 6, ARRAY['dried fruits', 'wine', 'processed foods']),
    ('Parabens', ARRAY['methylparaben', 'propylparaben'], 5, ARRAY['cosmetics', 'personal care products']),
    ('Fragrance', ARRAY['parfum', 'perfume'], 4, ARRAY['cosmetics', 'cleaning products']),
    ('Phthalates', ARRAY['DBP', 'DEP', 'DEHP'], 7, ARRAY['cosmetics', 'plastics', 'personal care'])
ON CONFLICT (name) DO NOTHING;

-- Seed common PFAS compounds
INSERT INTO pfas_compounds (name, cas_number, synonyms, health_impacts, body_effects, sources) VALUES
    (
        'PFOA',
        '335-67-1',
        ARRAY['Perfluorooctanoic acid', 'C8'],
        ARRAY['liver damage', 'thyroid disease', 'cancer', 'reproductive issues'],
        'PFOA accumulates in the body and can disrupt hormone function, damage the liver, increase cholesterol levels, and has been linked to testicular and kidney cancer. It persists in the environment and human body for years.',
        ARRAY['https://www.epa.gov/pfas/basic-information-pfas']
    ),
    (
        'PFOS',
        '1763-23-1',
        ARRAY['Perfluorooctane sulfonate'],
        ARRAY['immune system suppression', 'developmental delays', 'liver damage'],
        'PFOS can weaken the immune system, making you more susceptible to infections. It affects liver enzymes, increases cholesterol, and may cause developmental issues in children. Like PFOA, it persists in the body for years.',
        ARRAY['https://www.epa.gov/pfas/basic-information-pfas']
    ),
    (
        'GenX',
        '13252-13-6',
        ARRAY['HFPO-DA', 'FRD-903'],
        ARRAY['liver effects', 'kidney effects', 'immune effects'],
        'GenX is a replacement for PFOA but has similar health concerns. It can damage the liver and kidneys, potentially cause cancer, and affect the immune and reproductive systems. Studies are ongoing.',
        ARRAY['https://www.epa.gov/pfas/basic-information-pfas']
    ),
    (
        'PFNA',
        '375-95-1',
        ARRAY['Perfluorononanoic acid'],
        ARRAY['developmental effects', 'thyroid disruption', 'liver damage'],
        'PFNA affects fetal development, can disrupt thyroid hormone production, and causes liver damage. It has a very long half-life in the human body (2-4 years) and accumulates over time.',
        ARRAY['https://www.epa.gov/pfas/basic-information-pfas']
    ),
    (
        'PFHxS',
        '355-46-4',
        ARRAY['Perfluorohexane sulfonate'],
        ARRAY['cholesterol increase', 'liver effects', 'thyroid effects'],
        'PFHxS increases cholesterol levels, affects liver function, and can disrupt thyroid hormones. It persists in the body for 5-8 years and accumulates with repeated exposure.',
        ARRAY['https://www.epa.gov/pfas/basic-information-pfas']
    ),
    (
        'PFBS',
        '375-73-5',
        ARRAY['Perfluorobutane sulfonate'],
        ARRAY['thyroid effects', 'reproductive effects'],
        'PFBS is a shorter-chain PFAS that exits the body faster than PFOA/PFOS but can still disrupt thyroid function and affect reproduction. Often used as a "safer" replacement, but safety is still under investigation.',
        ARRAY['https://www.epa.gov/pfas/basic-information-pfas']
    ),
    (
        'PTFE',
        '9002-84-0',
        ARRAY['Polytetrafluoroethylene', 'Teflon'],
        ARRAY['polymer fume fever', 'potential PFOA exposure'],
        'PTFE itself is relatively inert, but when heated above 260°C (500°F), it breaks down and releases toxic fumes causing flu-like symptoms (polymer fume fever). Non-stick cookware may also contain PFOA residues from manufacturing.',
        ARRAY['https://www.epa.gov/pfas/basic-information-pfas']
    )
ON CONFLICT (name) DO NOTHING;

-- Add indexes for faster searching
CREATE INDEX IF NOT EXISTS idx_allergens_name ON allergens(name);
CREATE INDEX IF NOT EXISTS idx_pfas_name ON pfas_compounds(name);
CREATE INDEX IF NOT EXISTS idx_pfas_cas ON pfas_compounds(cas_number);
