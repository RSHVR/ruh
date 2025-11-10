-- Eject Database Schema
-- Migration 002: Seed allergen and PFAS knowledge base

-- Seed common allergens
INSERT INTO allergens (name, synonyms, severity_default, common_sources) VALUES
('Peanuts', ARRAY['peanut', 'groundnut', 'arachis oil'], 10, ARRAY['peanut butter', 'protein powders', 'snacks', 'sauces']),
('Tree Nuts', ARRAY['almond', 'cashew', 'walnut', 'pecan', 'pistachio', 'hazelnut', 'macadamia'], 9, ARRAY['granola', 'baked goods', 'chocolates']),
('Milk', ARRAY['dairy', 'lactose', 'casein', 'whey', 'butter', 'cream'], 8, ARRAY['protein powders', 'baked goods', 'sauces', 'processed foods']),
('Eggs', ARRAY['egg', 'albumin', 'ovalbumin', 'lysozyme'], 7, ARRAY['baked goods', 'mayonnaise', 'pasta']),
('Fish', ARRAY['cod', 'salmon', 'tuna', 'anchovy'], 8, ARRAY['fish sauce', 'caesar dressing', 'Worcestershire sauce']),
('Shellfish', ARRAY['shrimp', 'crab', 'lobster', 'clam', 'mussel', 'oyster', 'scallop'], 9, ARRAY['seafood dishes', 'Asian cuisine', 'surimi']),
('Soy', ARRAY['soybean', 'soya', 'soy lecithin', 'tofu', 'tempeh', 'edamame'], 6, ARRAY['protein powders', 'processed foods', 'vegetarian products']),
('Wheat', ARRAY['gluten', 'flour', 'semolina', 'durum', 'spelt', 'farro'], 7, ARRAY['bread', 'pasta', 'baked goods', 'sauces']),
('Sesame', ARRAY['sesame seed', 'tahini', 'sesame oil'], 7, ARRAY['baked goods', 'hummus', 'Asian cuisine']),
('Mustard', ARRAY['mustard seed', 'mustard oil'], 5, ARRAY['condiments', 'sauces', 'pickles']),
('Celery', ARRAY['celery seed', 'celeriac'], 4, ARRAY['soups', 'salads', 'spice mixes']),
('Lupin', ARRAY['lupine', 'lupin flour'], 6, ARRAY['gluten-free products', 'vegan products']),
('Mollusks', ARRAY['snail', 'squid', 'octopus', 'cuttlefish'], 7, ARRAY['seafood dishes', 'Mediterranean cuisine']),
('Sulfites', ARRAY['sulfur dioxide', 'sodium sulfite', 'potassium bisulfite'], 5, ARRAY['wine', 'dried fruits', 'processed foods']),
('Corn', ARRAY['maize', 'corn syrup', 'cornstarch'], 4, ARRAY['sweeteners', 'thickeners', 'processed foods']),
('Coconut', ARRAY['coconut oil', 'coconut milk'], 3, ARRAY['tropical foods', 'desserts', 'Asian cuisine'])
ON CONFLICT (name) DO NOTHING;

-- Seed common PFAS compounds
INSERT INTO pfas_compounds (name, cas_number, synonyms, health_impacts, body_effects, sources) VALUES
(
  'PFOA (Perfluorooctanoic Acid)',
  '335-67-1',
  ARRAY['C8', 'pentadecafluorooctanoic acid'],
  ARRAY['kidney cancer', 'testicular cancer', 'thyroid disease', 'high cholesterol', 'pregnancy complications'],
  'PFOA accumulates in the blood and liver, disrupting hormone function and potentially causing cancer. Studies show it can cross the placenta and affect fetal development. It has a half-life of 2-4 years in humans.',
  ARRAY['non-stick cookware', 'water-resistant fabrics', 'food packaging', 'firefighting foam']
),
(
  'PFOS (Perfluorooctanesulfonic Acid)',
  '1763-23-1',
  ARRAY['perfluorooctane sulfonate'],
  ARRAY['immune system suppression', 'thyroid disease', 'reproductive issues', 'developmental delays in children'],
  'PFOS bioaccumulates in the body, particularly in blood and liver tissue. It disrupts the immune system and can reduce vaccine effectiveness in children. Half-life in humans is approximately 5 years.',
  ARRAY['firefighting foam', 'stain-resistant treatments', 'carpets', 'upholstery']
),
(
  'GenX',
  '62037-80-3',
  ARRAY['HFPO-DA', 'perfluoro-2-propoxypropanoic acid'],
  ARRAY['liver damage', 'kidney effects', 'immune system disruption', 'developmental effects'],
  'GenX is a replacement for PFOA but studies show similar health concerns. It affects liver enzymes and can cause kidney weight changes. Research is ongoing but early studies show it may be equally harmful.',
  ARRAY['water contamination', 'industrial emissions', 'manufacturing byproduct']
),
(
  'PFNA (Perfluorononanoic Acid)',
  '375-95-1',
  ARRAY['perfluorononanoate'],
  ARRAY['thyroid disease', 'high cholesterol', 'kidney disease', 'developmental effects'],
  'PFNA concentrates in the liver and blood, with a half-life of 2-4 years. It disrupts lipid metabolism and thyroid hormone production. Animal studies show effects on fetal development.',
  ARRAY['non-stick cookware', 'food packaging', 'textiles']
),
(
  'PFHxS (Perfluorohexanesulfonic Acid)',
  '355-46-4',
  ARRAY['perfluorohexane sulfonate'],
  ARRAY['immune system effects', 'cholesterol elevation', 'thyroid disruption'],
  'PFHxS has a very long half-life in humans (5-27 years) and bioaccumulates extensively. It can reduce antibody response to vaccines and may affect child neurodevelopment.',
  ARRAY['firefighting foam', 'stain-resistant products', 'food contact materials']
),
(
  'PFBS (Perfluorobutanesulfonic Acid)',
  '375-73-5',
  ARRAY['perfluorobutane sulfonate'],
  ARRAY['thyroid effects', 'developmental changes'],
  'PFBS is a shorter-chain PFAS marketed as "safer" but still shows bioaccumulation and thyroid disruption. Limited long-term human studies exist but animal research shows concern.',
  ARRAY['surface treatments', 'cleaning products', 'food packaging']
),
(
  'PFDA (Perfluorodecanoic Acid)',
  '335-76-2',
  ARRAY['perfluorodecanoate'],
  ARRAY['liver damage', 'developmental toxicity', 'immune system effects'],
  'PFDA is highly persistent with a long half-life in humans. It accumulates in the liver and can impair immune function, particularly affecting children''s vaccine response.',
  ARRAY['non-stick coatings', 'textiles', 'food packaging']
),
(
  'PTFE (Polytetrafluoroethylene)',
  '9002-84-0',
  ARRAY['Teflon', 'teflon coating'],
  ARRAY['polymer fume fever when overheated', 'potential breakdown to PFOA'],
  'PTFE itself is generally considered inert, but when heated above 500°F (260°C), it breaks down and releases toxic fumes causing polymer fume fever. Old PTFE products may contain residual PFOA from manufacturing.',
  ARRAY['non-stick cookware', 'plumbing tape', 'medical devices']
)
ON CONFLICT (name) DO NOTHING;

-- Create function to search allergens by synonyms
CREATE OR REPLACE FUNCTION search_allergen(search_term TEXT)
RETURNS TABLE(allergen_id UUID, allergen_name TEXT, severity INTEGER) AS $$
BEGIN
  RETURN QUERY
  SELECT id, name, severity_default
  FROM allergens
  WHERE
    LOWER(name) = LOWER(search_term) OR
    LOWER(search_term) = ANY(SELECT LOWER(unnest(synonyms)));
END;
$$ LANGUAGE plpgsql;

-- Create function to search PFAS compounds by name or CAS
CREATE OR REPLACE FUNCTION search_pfas(search_term TEXT)
RETURNS TABLE(
  pfas_id UUID,
  pfas_name TEXT,
  cas TEXT,
  effects TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT id, name, cas_number, body_effects
  FROM pfas_compounds
  WHERE
    LOWER(name) LIKE '%' || LOWER(search_term) || '%' OR
    cas_number = search_term OR
    LOWER(search_term) = ANY(SELECT LOWER(unnest(synonyms)));
END;
$$ LANGUAGE plpgsql;

-- Add comments
COMMENT ON FUNCTION search_allergen IS 'Search allergens by name or synonym';
COMMENT ON FUNCTION search_pfas IS 'Search PFAS compounds by name, CAS number, or synonym';
