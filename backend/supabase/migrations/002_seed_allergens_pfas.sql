-- Eject Database Schema
-- Migration 002: Comprehensive seed data for allergens, PFAS, and toxic substances
-- Data compiled from: Health Canada, FDA, EPA, Canadian Schedule 1, EU regulations, peer-reviewed research
-- Total: 157 critical substances including precursors, derivatives, and metabolites

-- PART 1: Allergens (32 priority substances)
-- PART 2: PFAS Compounds (75 compounds including precursors, metabolites, and emerging alternatives)
-- PART 3: Toxic Substances (50 substances including metabolites and precursors)
-- PART 4: Search Functions

-- ============================================================================
-- PART 1: ALLERGENS (32 Priority Substances)
-- ============================================================================
-- Includes: FDA Priority (9), Health Canada Priority (14), Cosmetic, Latex, Preservatives, Fragrances

INSERT INTO allergens (
  name,
  synonyms,
  severity_default,
  common_sources,
  allergen_type,
  cross_reactions,
  prevalence_percentage,
  severity_range,
  fda_priority,
  health_canada_priority,
  alternative_names
) VALUES
-- 1. Peanuts
(
  'Peanuts',
  ARRAY['Arachis hypogaea', 'groundnut', 'goober', 'monkey nut', 'peanut oil', 'arachis oil'],
  10,
  ARRAY['peanut butter', 'mixed nuts', 'granola bars', 'candy', 'baked goods', 'sauces', 'Asian cuisine'],
  'food',
  ARRAY['tree nuts', 'soy', 'legumes'],
  1.5,
  'potentially_life_threatening',
  TRUE,
  TRUE,
  ARRAY['arachide', 'cacahuete', 'ground pea']
),

-- 2. Tree Nuts
(
  'Tree Nuts',
  ARRAY['almonds', 'cashews', 'walnuts', 'pecans', 'pistachios', 'macadamia', 'hazelnuts', 'brazil nuts', 'pine nuts'],
  9,
  ARRAY['nut butters', 'chocolates', 'cereals', 'baked goods', 'pesto', 'nut oils', 'marzipan'],
  'food',
  ARRAY['peanuts', 'sesame', 'coconut'],
  1.0,
  'potentially_life_threatening',
  TRUE,
  TRUE,
  ARRAY['tree nut', 'shelled nut']
),

-- 3. Milk
(
  'Milk',
  ARRAY['casein', 'whey', 'lactose', 'lactalbumin', 'lactoglobulin', 'dairy', 'butter', 'cheese', 'cream', 'yogurt'],
  8,
  ARRAY['dairy products', 'baked goods', 'chocolate', 'processed foods', 'sauces', 'protein powders'],
  'food',
  ARRAY['goat milk', 'sheep milk'],
  2.5,
  'potentially_life_threatening',
  TRUE,
  TRUE,
  ARRAY['milk protein', 'milk solids', 'milk powder']
),

-- 4. Eggs
(
  'Eggs',
  ARRAY['albumin', 'egg white', 'egg yolk', 'ovalbumin', 'ovomucoid', 'lysozyme', 'mayonnaise'],
  8,
  ARRAY['baked goods', 'pasta', 'mayonnaise', 'processed foods', 'vaccines', 'cosmetics'],
  'food',
  ARRAY['chicken', 'feathers'],
  1.5,
  'potentially_life_threatening',
  TRUE,
  TRUE,
  ARRAY['egg protein', 'egg lecithin', 'egg lysozyme']
),

-- 5. Fish
(
  'Fish',
  ARRAY['salmon', 'tuna', 'cod', 'halibut', 'anchovy', 'fish oil', 'omega-3', 'fish sauce'],
  9,
  ARRAY['seafood', 'Caesar dressing', 'Worcestershire sauce', 'supplements', 'Asian cuisine'],
  'food',
  ARRAY['shellfish'],
  0.5,
  'potentially_life_threatening',
  TRUE,
  TRUE,
  ARRAY['finned fish', 'pescado']
),

-- 6. Shellfish/Crustaceans
(
  'Shellfish',
  ARRAY['shrimp', 'crab', 'lobster', 'crayfish', 'prawn', 'krill', 'barnacle'],
  9,
  ARRAY['seafood', 'Asian cuisine', 'surimi', 'seafood flavoring', 'glucosamine'],
  'food',
  ARRAY['fish', 'molluscs', 'dust mites', 'cockroaches'],
  2.0,
  'potentially_life_threatening',
  TRUE,
  TRUE,
  ARRAY['crustaceans', 'crustacea']
),

-- 7. Soy
(
  'Soy',
  ARRAY['soybean', 'tofu', 'edamame', 'soy protein', 'soy lecithin', 'tempeh', 'miso', 'soy sauce'],
  6,
  ARRAY['processed foods', 'vegetarian products', 'baked goods', 'infant formula', 'protein bars'],
  'food',
  ARRAY['peanuts', 'other legumes'],
  0.5,
  'mild_to_moderate',
  TRUE,
  TRUE,
  ARRAY['soya', 'glycine max', 'soy flour']
),

-- 8. Wheat
(
  'Wheat',
  ARRAY['gluten', 'gliadin', 'wheat flour', 'durum', 'semolina', 'spelt', 'kamut', 'farro'],
  7,
  ARRAY['bread', 'pasta', 'cereals', 'baked goods', 'beer', 'soy sauce', 'processed foods'],
  'food',
  ARRAY['barley', 'rye', 'triticale'],
  1.0,
  'mild_to_moderate',
  TRUE,
  TRUE,
  ARRAY['triticum', 'wheat protein', 'hydrolyzed wheat protein']
),

-- 9. Sesame
(
  'Sesame',
  ARRAY['sesame seed', 'sesame oil', 'tahini', 'sesamol', 'sesamolin'],
  8,
  ARRAY['baked goods', 'hummus', 'tahini', 'Asian cuisine', 'cosmetics', 'supplements'],
  'food',
  ARRAY['tree nuts', 'poppy seeds'],
  0.2,
  'potentially_life_threatening',
  TRUE,
  TRUE,
  ARRAY['benne', 'sesamum indicum', 'gingelly']
),

-- 10. Mustard
(
  'Mustard',
  ARRAY['mustard seed', 'mustard powder', 'mustard oil', 'dijon', 'yellow mustard'],
  6,
  ARRAY['condiments', 'sauces', 'dressings', 'pickles', 'processed meats'],
  'food',
  ARRAY['rapeseed', 'cabbage family'],
  0.1,
  'mild_to_moderate',
  FALSE,
  TRUE,
  ARRAY['sinapis', 'brassica']
),

-- 11. Molluscs
(
  'Molluscs',
  ARRAY['clam', 'oyster', 'mussel', 'scallop', 'squid', 'octopus', 'snail', 'abalone'],
  8,
  ARRAY['seafood', 'Asian cuisine', 'paella', 'seafood stock', 'supplements'],
  'food',
  ARRAY['crustaceans', 'fish'],
  0.5,
  'potentially_life_threatening',
  FALSE,
  TRUE,
  ARRAY['mollusks', 'cephalopods', 'bivalves']
),

-- 12. Sulfites
(
  'Sulfites',
  ARRAY['sulfur dioxide', 'sodium sulfite', 'sodium bisulfite', 'potassium bisulfite', 'sodium metabisulfite'],
  7,
  ARRAY['wine', 'dried fruit', 'processed foods', 'vinegar', 'pickled foods', 'shrimp'],
  'preservative',
  ARRAY[],
  1.0,
  'mild_to_moderate',
  FALSE,
  TRUE,
  ARRAY['sulphites', 'SO2', 'E220-E228']
),

-- 13. Fragrance Mix I
(
  'Fragrance Mix I',
  ARRAY['cinnamal', 'cinnamyl alcohol', 'eugenol', 'isoeugenol', 'geraniol', 'hydroxycitronellal', 'oak moss absolute', 'alpha-amyl cinnamal'],
  5,
  ARRAY['perfumes', 'cosmetics', 'soaps', 'lotions', 'detergents', 'air fresheners'],
  'fragrance',
  ARRAY['balsam of peru', 'fragrance mix II'],
  9.8,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['parfum', 'fragrance allergens', 'perfume mix']
),

-- 14. Parabens
(
  'Parabens',
  ARRAY['methylparaben', 'ethylparaben', 'propylparaben', 'butylparaben', 'isobutylparaben'],
  4,
  ARRAY['cosmetics', 'lotions', 'shampoos', 'deodorants', 'food preservatives'],
  'cosmetic',
  ARRAY[],
  1.0,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['parahydroxybenzoate', 'E214-E219']
),

-- 15. Formaldehyde Releasers
(
  'Formaldehyde Releasers',
  ARRAY['quaternium-15', 'DMDM hydantoin', 'imidazolidinyl urea', 'diazolidinyl urea', 'bronopol', '2-bromo-2-nitropropane-1,3-diol'],
  6,
  ARRAY['cosmetics', 'shampoos', 'nail polish', 'lotions', 'cleansers'],
  'cosmetic',
  ARRAY['formaldehyde'],
  8.0,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['formaldehyde donors', 'formaldehyde-releasing preservatives']
),

-- 16. Methylisothiazolinone
(
  'Methylisothiazolinone',
  ARRAY['MI', 'MIT', 'Kathon CG'],
  7,
  ARRAY['cosmetics', 'shampoos', 'wet wipes', 'detergents', 'paints'],
  'cosmetic',
  ARRAY['methylchloroisothiazolinone'],
  3.0,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['2-methyl-4-isothiazolin-3-one', 'Neolone']
),

-- 17. Latex
(
  'Latex',
  ARRAY['natural rubber latex', 'rubber', 'Hevea brasiliensis'],
  8,
  ARRAY['gloves', 'balloons', 'condoms', 'medical devices', 'rubber bands'],
  'latex',
  ARRAY['banana', 'avocado', 'kiwi', 'chestnut', 'passion fruit'],
  5.0,
  'potentially_life_threatening',
  FALSE,
  FALSE,
  ARRAY['natural rubber', 'latex protein']
),

-- 18. Nickel
(
  'Nickel',
  ARRAY['nickel sulfate', 'nickel chloride'],
  5,
  ARRAY['jewelry', 'watches', 'zippers', 'coins', 'eyeglasses', 'cosmetics', 'hair dye'],
  'cosmetic',
  ARRAY[],
  15.0,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['nickel metal', 'Ni']
),

-- 19. p-Phenylenediamine
(
  'p-Phenylenediamine',
  ARRAY['PPD', '1,4-benzenediamine', 'CI 76060'],
  8,
  ARRAY['hair dye', 'henna tattoos', 'textile dyes', 'cosmetics'],
  'cosmetic',
  ARRAY['PTBP', 'azo dyes', 'sulfa drugs'],
  6.0,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['phenylenediamine', 'para-phenylenediamine']
),

-- 20. Coconut
(
  'Coconut',
  ARRAY['coconut oil', 'coconut milk', 'coconut water', 'desiccated coconut', 'copra'],
  6,
  ARRAY['baked goods', 'candy', 'Asian cuisine', 'cosmetics', 'shampoos', 'soaps'],
  'food',
  ARRAY['tree nuts', 'lychee', 'walnut'],
  0.5,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['cocos nucifera', 'coconut palm']
),

-- 21. Celery
(
  'Celery',
  ARRAY['celery seed', 'celeriac', 'celery root', 'apium graveolens'],
  4,
  ARRAY['soups', 'salads', 'spice mixes', 'processed foods', 'vegetable juices'],
  'food',
  ARRAY['mugwort', 'birch pollen', 'carrot'],
  0.3,
  'mild_to_moderate',
  FALSE,
  TRUE,
  ARRAY['celery stalk', 'celery powder']
),

-- 22. Lupin
(
  'Lupin',
  ARRAY['lupine', 'lupin flour', 'lupin protein', 'lupinus'],
  6,
  ARRAY['flour substitutes', 'baked goods', 'pasta', 'vegetarian products', 'protein supplements'],
  'food',
  ARRAY['peanuts', 'soy', 'other legumes'],
  0.1,
  'potentially_life_threatening',
  FALSE,
  TRUE,
  ARRAY['lupini beans', 'lupin seed']
),

-- 23. Fragrance Mix II
(
  'Fragrance Mix II',
  ARRAY['lyral', 'citral', 'farnesol', 'coumarin', 'citronellol', 'hexyl cinnamal'],
  5,
  ARRAY['perfumes', 'cosmetics', 'lotions', 'detergents', 'air fresheners', 'candles'],
  'fragrance',
  ARRAY['fragrance mix I', 'balsam of peru'],
  3.0,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['fragrance allergens II', 'perfume mix II']
),

-- 24. Balsam of Peru
(
  'Balsam of Peru',
  ARRAY['myroxylon pereirae', 'peruvian balsam', 'balsam peru'],
  6,
  ARRAY['perfumes', 'cosmetics', 'flavorings', 'tobacco', 'dental products', 'spices'],
  'fragrance',
  ARRAY['cinnamon', 'vanilla', 'clove', 'citrus peel'],
  8.0,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['tolu balsam', 'myroxylon']
),

-- 25. Methylchloroisothiazolinone
(
  'Methylchloroisothiazolinone',
  ARRAY['MCI', 'Kathon CG', '5-chloro-2-methyl-4-isothiazolin-3-one'],
  7,
  ARRAY['cosmetics', 'shampoos', 'wet wipes', 'detergents', 'paints', 'cleaning products'],
  'cosmetic',
  ARRAY['methylisothiazolinone'],
  3.5,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['MCI/MI', 'chloromethylisothiazolinone']
),

-- 26. Propylene Glycol
(
  'Propylene Glycol',
  ARRAY['1,2-propanediol', 'PG', 'propane-1,2-diol'],
  3,
  ARRAY['cosmetics', 'lotions', 'deodorants', 'food additives', 'medications', 'antifreeze'],
  'cosmetic',
  ARRAY[],
  1.5,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['E1520', 'methylethyl glycol']
),

-- 27. Lanolin
(
  'Lanolin',
  ARRAY['wool alcohol', 'wool wax', 'wool grease', 'adeps lanae'],
  4,
  ARRAY['cosmetics', 'lotions', 'ointments', 'lip balms', 'baby products', 'leather treatment'],
  'cosmetic',
  ARRAY['wool'],
  2.0,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['lanolin alcohol', 'wool fat']
),

-- 28. Cocamidopropyl Betaine
(
  'Cocamidopropyl Betaine',
  ARRAY['CAPB', 'cocamidopropyl dimethyl glycine'],
  4,
  ARRAY['shampoos', 'body washes', 'liquid soaps', 'facial cleansers', 'bubble bath'],
  'cosmetic',
  ARRAY[],
  1.5,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['coco betaine', 'coconut betaine']
),

-- 29. Chromium
(
  'Chromium',
  ARRAY['chromate', 'potassium dichromate', 'chromium salts'],
  5,
  ARRAY['leather products', 'cement', 'dyes', 'metal alloys', 'tattoo ink'],
  'cosmetic',
  ARRAY['leather'],
  2.0,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['Cr', 'chromium metal']
),

-- 30. Cobalt
(
  'Cobalt',
  ARRAY['cobalt chloride', 'cobalt sulfate', 'cobalt salts'],
  5,
  ARRAY['jewelry', 'metal alloys', 'cement', 'dyes', 'pigments', 'cosmetics'],
  'cosmetic',
  ARRAY['nickel'],
  5.0,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['Co', 'cobalt metal']
),

-- 31. Benzoates
(
  'Benzoates',
  ARRAY['sodium benzoate', 'potassium benzoate', 'benzoic acid', 'E211'],
  2,
  ARRAY['soft drinks', 'fruit juices', 'pickles', 'sauces', 'cosmetics', 'medications'],
  'preservative',
  ARRAY['parabens'],
  0.1,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['E210', 'E212', 'benzoate preservatives']
),

-- 32. Tartrazine
(
  'Tartrazine',
  ARRAY['Yellow 5', 'E102', 'FD&C Yellow 5', 'CI 19140'],
  3,
  ARRAY['candy', 'beverages', 'baked goods', 'medications', 'cosmetics', 'ice cream'],
  'preservative',
  ARRAY['aspirin', 'other azo dyes'],
  0.1,
  'mild_to_moderate',
  FALSE,
  FALSE,
  ARRAY['yellow dye 5', 'acid yellow 23']
)

ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- PART 2: PFAS COMPOUNDS (75 Compounds)
-- ============================================================================
-- Includes: Long-chain PFCAs/PFSAs (prohibited), short-chain alternatives, precursors,
-- fluorotelomers, GenX family, ether-PFAS, cosmetic PFAS, Chinese alternatives, sulfonamides

INSERT INTO pfas_compounds (
  name,
  cas_number,
  synonyms,
  health_impacts,
  body_effects,
  sources,
  common_name,
  carbon_chain_length,
  half_life_human,
  regulatory_status_canada,
  regulatory_status_usa,
  regulatory_status_eu,
  authorized_uses,
  prohibited_uses,
  phase_out_date,
  detection_frequency,
  risk_classification,
  bioaccumulative,
  product_categories,
  is_precursor,
  is_metabolite,
  parent_compounds,
  metabolites,
  transformation_pathway
) VALUES

-- Long-Chain PFCAs (Prohibited)

-- 1. PFOA
(
  'PFOA',
  '335-67-1',
  ARRAY['perfluorooctanoic acid', 'C8', 'pentadecafluorooctanoic acid'],
  ARRAY['liver damage', 'thyroid disease', 'high cholesterol', 'testicular cancer', 'kidney cancer', 'pregnancy-induced hypertension'],
  'Liver damage, thyroid dysfunction, reproductive toxicity, immunotoxicity, cancer (testicular, kidney)',
  ARRAY['non-stick cookware', 'water-resistant clothing', 'stain-resistant carpets', 'food packaging', 'firefighting foam'],
  'C8',
  8,
  '2-4 years',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY[],
  ARRAY['consumer products', 'manufacturing except essential uses'],
  '2020-12-31',
  '97-100% of population',
  ARRAY['PBT', 'carcinogen', 'endocrine disruptor'],
  TRUE,
  ARRAY['non-stick cookware', 'textiles', 'food packaging', 'carpets'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 2. PFNA
(
  'PFNA',
  '375-95-1',
  ARRAY['perfluorononanoic acid', 'C9'],
  ARRAY['liver toxicity', 'developmental effects', 'thyroid disruption', 'immune system effects'],
  'Liver toxicity, developmental delays, thyroid dysfunction, immunosuppression',
  ARRAY['food packaging', 'non-stick coatings', 'industrial processes'],
  'C9',
  9,
  '3-4 years',
  'prohibited',
  'under review',
  'prohibited',
  ARRAY[],
  ARRAY['consumer products'],
  '2020-12-31',
  '97-100% of population',
  ARRAY['PBT', 'bioaccumulative'],
  TRUE,
  ARRAY['food packaging', 'coatings'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 3. PFDA
(
  'PFDA',
  '335-76-2',
  ARRAY['perfluorodecanoic acid', 'C10'],
  ARRAY['liver toxicity', 'developmental toxicity', 'immunotoxicity'],
  'Severe liver toxicity, developmental effects, immune system suppression',
  ARRAY['industrial processes', 'surfactants', 'food contact materials'],
  'C10',
  10,
  '5-8 years',
  'prohibited',
  'under review',
  'prohibited',
  ARRAY[],
  ARRAY['consumer products'],
  '2020-12-31',
  '90-100% of population',
  ARRAY['PBT', 'vPvB', 'bioaccumulative'],
  TRUE,
  ARRAY['industrial', 'food packaging'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 4. PFUnDA
(
  'PFUnDA',
  '2058-94-8',
  ARRAY['perfluoroundecanoic acid', 'C11', 'PFUnA'],
  ARRAY['liver toxicity', 'developmental effects', 'endocrine disruption'],
  'Liver damage, developmental toxicity, hormonal disruption',
  ARRAY['industrial processes', 'surfactants'],
  'C11',
  11,
  '6-10 years',
  'prohibited',
  'under review',
  'prohibited',
  ARRAY[],
  ARRAY['consumer products'],
  '2020-12-31',
  '80-95% of population',
  ARRAY['PBT', 'vPvB'],
  TRUE,
  ARRAY['industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 5. PFDoDA
(
  'PFDoDA',
  '307-55-1',
  ARRAY['perfluorododecanoic acid', 'C12', 'PFDoA'],
  ARRAY['liver toxicity', 'developmental toxicity'],
  'Liver damage, developmental effects',
  ARRAY['industrial processes', 'surfactants'],
  'C12',
  12,
  '7-12 years',
  'prohibited',
  'under review',
  'prohibited',
  ARRAY[],
  ARRAY['consumer products'],
  '2020-12-31',
  '70-90% of population',
  ARRAY['PBT', 'vPvB'],
  TRUE,
  ARRAY['industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- Long-Chain PFSAs (Prohibited)

-- 6. PFOS
(
  'PFOS',
  '1763-23-1',
  ARRAY['perfluorooctane sulfonate', 'perfluorooctanesulfonic acid', 'C8 sulfonate'],
  ARRAY['liver damage', 'thyroid disease', 'high cholesterol', 'immune system effects', 'developmental delays', 'cancer'],
  'Liver toxicity, thyroid dysfunction, hypercholesterolemia, immunosuppression, developmental neurotoxicity',
  ARRAY['stain-resistant treatments', 'firefighting foam', 'chrome plating', 'carpets', 'upholstery'],
  'C8 sulfonate',
  8,
  '5 years',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY['essential firefighting foam', 'chrome plating (time-limited)'],
  ARRAY['consumer stain treatments', 'food packaging'],
  '2008-12-31',
  '98-100% of population',
  ARRAY['PBT', 'vPvB', 'endocrine disruptor'],
  TRUE,
  ARRAY['textiles', 'carpets', 'firefighting foam', 'chrome plating'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 7. PFDS
(
  'PFDS',
  '335-77-3',
  ARRAY['perfluorodecane sulfonate', 'C10 sulfonate'],
  ARRAY['liver toxicity', 'endocrine disruption'],
  'Liver damage, hormonal disruption',
  ARRAY['industrial surfactants', 'firefighting foam'],
  'C10 sulfonate',
  10,
  '8-15 years',
  'prohibited',
  'under review',
  'prohibited',
  ARRAY[],
  ARRAY['consumer products'],
  '2020-12-31',
  '50-70% of population',
  ARRAY['PBT', 'vPvB'],
  TRUE,
  ARRAY['industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- Short-Chain (Currently Used)

-- 8. PFBS
(
  'PFBS',
  '375-73-5',
  ARRAY['perfluorobutane sulfonate', 'C4 sulfonate'],
  ARRAY['thyroid effects', 'liver effects', 'developmental toxicity'],
  'Thyroid disruption, liver toxicity, developmental effects (marketed as ''safer'' alternative)',
  ARRAY['stain-resistant treatments', 'cleaning products', 'firefighting foam'],
  'C4 sulfonate',
  4,
  '1 month',
  'restricted',
  'under review',
  'restricted',
  ARRAY['industrial applications', 'firefighting foam'],
  ARRAY[],
  NULL,
  '70-90% of population',
  ARRAY['persistent', 'mobile'],
  FALSE,
  ARRAY['textiles', 'cleaning products', 'firefighting foam'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 9. PFHxS
(
  'PFHxS',
  '355-46-4',
  ARRAY['perfluorohexane sulfonate', 'C6 sulfonate'],
  ARRAY['liver toxicity', 'thyroid effects', 'developmental effects', 'immune system effects'],
  'Liver damage, thyroid dysfunction, developmental toxicity, immunosuppression',
  ARRAY['stain-resistant treatments', 'firefighting foam', 'chrome plating', 'food packaging'],
  'C6 sulfonate',
  6,
  '5-27 years',
  'under assessment',
  'under review',
  'restricted',
  ARRAY['firefighting foam', 'industrial processes'],
  ARRAY[],
  NULL,
  '95-99% of population',
  ARRAY['persistent', 'bioaccumulative'],
  TRUE,
  ARRAY['textiles', 'firefighting foam', 'food packaging'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 10. PFBA
(
  'PFBA',
  '375-22-4',
  ARRAY['perfluorobutanoic acid', 'C4', 'perfluorobutyric acid'],
  ARRAY['liver effects', 'kidney effects'],
  'Liver and kidney toxicity',
  ARRAY['coatings', 'cleaning products', 'industrial processes'],
  'C4',
  4,
  '3 days',
  'restricted',
  'under review',
  'restricted',
  ARRAY['industrial applications'],
  ARRAY[],
  NULL,
  '60-80% of population',
  ARRAY['persistent', 'mobile'],
  FALSE,
  ARRAY['industrial', 'cleaning products'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 11. PFPeA
(
  'PFPeA',
  '2706-90-3',
  ARRAY['perfluoropentanoic acid', 'C5'],
  ARRAY['liver effects', 'developmental effects'],
  'Liver toxicity, developmental effects',
  ARRAY['food packaging', 'industrial processes'],
  'C5',
  5,
  '1-2 weeks',
  'under assessment',
  'under review',
  'restricted',
  ARRAY['industrial applications'],
  ARRAY[],
  NULL,
  '70-85% of population',
  ARRAY['persistent', 'mobile'],
  FALSE,
  ARRAY['food packaging', 'industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 12. PFHxA
(
  'PFHxA',
  '307-24-4',
  ARRAY['perfluorohexanoic acid', 'C6'],
  ARRAY['liver effects', 'thyroid effects', 'developmental effects'],
  'Liver toxicity, thyroid dysfunction, developmental effects',
  ARRAY['food packaging', 'non-stick cookware', 'textiles'],
  'C6',
  6,
  '1 month',
  'under assessment',
  'under review',
  'restricted',
  ARRAY['food packaging', 'industrial processes'],
  ARRAY[],
  NULL,
  '80-95% of population',
  ARRAY['persistent', 'mobile'],
  FALSE,
  ARRAY['food packaging', 'cookware', 'textiles'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 13. PFHpA
(
  'PFHpA',
  '375-85-9',
  ARRAY['perfluoroheptanoic acid', 'C7'],
  ARRAY['liver effects', 'developmental effects'],
  'Liver toxicity, developmental effects',
  ARRAY['food packaging', 'industrial processes'],
  'C7',
  7,
  '2-3 months',
  'under assessment',
  'under review',
  'restricted',
  ARRAY['industrial applications'],
  ARRAY[],
  NULL,
  '75-90% of population',
  ARRAY['persistent'],
  FALSE,
  ARRAY['food packaging', 'industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- GenX and Replacements

-- 14. GenX / HFPO-DA
(
  'GenX',
  '62037-80-3',
  ARRAY['HFPO-DA', 'hexafluoropropylene oxide dimer acid', 'FRD-903'],
  ARRAY['liver toxicity', 'kidney effects', 'developmental effects', 'immune system effects'],
  'Liver and kidney damage, developmental toxicity, immunotoxicity (PFOA replacement, similar toxicity)',
  ARRAY['non-stick cookware', 'water-resistant textiles', 'industrial processes'],
  'HFPO-DA',
  6,
  '2-4 weeks',
  'under assessment',
  'under review',
  'restricted',
  ARRAY['industrial processes'],
  ARRAY[],
  NULL,
  '10-30% near contaminated sites',
  ARRAY['emerging concern', 'persistent'],
  FALSE,
  ARRAY['cookware', 'textiles', 'industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 15. ADONA
(
  'ADONA',
  '919005-14-4',
  ARRAY['4,8-dioxa-3H-perfluorononanoic acid'],
  ARRAY['liver effects', 'developmental effects'],
  'Liver toxicity, developmental effects (PFOA alternative)',
  ARRAY['fluoropolymer production', 'industrial processes'],
  'ADONA',
  7,
  '1-2 months',
  'under assessment',
  'under review',
  'restricted',
  ARRAY['industrial processes'],
  ARRAY[],
  NULL,
  '<5% of population',
  ARRAY['emerging concern'],
  FALSE,
  ARRAY['industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- PFOA Precursors

-- 16. 8:2 FTOH
(
  '8:2 FTOH',
  '678-39-7',
  ARRAY['8:2 fluorotelomer alcohol', '1H,1H,2H,2H-perfluorodecanol'],
  ARRAY['liver toxicity', 'developmental effects', 'thyroid effects'],
  'Transforms to PFOA in environment and body, liver damage, developmental toxicity',
  ARRAY['carpet treatments', 'textile treatments', 'food packaging coatings'],
  '8:2 fluorotelomer alcohol',
  NULL,
  'days to weeks',
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY['food contact materials'],
  NULL,
  '60-80% of population',
  ARRAY['precursor', 'transforms to PFOA'],
  FALSE,
  ARRAY['carpets', 'textiles', 'food packaging'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOA'],
  'Oxidative degradation to PFOA via environment/metabolism'
),

-- 17. 10:2 FTOH
(
  '10:2 FTOH',
  '865-86-1',
  ARRAY['10:2 fluorotelomer alcohol', '1H,1H,2H,2H-perfluorododecanol'],
  ARRAY['liver toxicity', 'developmental effects'],
  'Transforms to PFDA and other long-chain PFCAs, liver damage',
  ARRAY['carpet treatments', 'textile treatments', 'paper coatings'],
  '10:2 fluorotelomer alcohol',
  NULL,
  'days to weeks',
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY['consumer products'],
  NULL,
  '50-70% of population',
  ARRAY['precursor', 'transforms to PFDA'],
  FALSE,
  ARRAY['carpets', 'textiles', 'paper'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFDA'],
  'Oxidative degradation to PFDA'
),

-- 18. 8:2 FTAC
(
  '8:2 FTAC',
  '27905-45-9',
  ARRAY['8:2 fluorotelomer acrylate', 'fluorotelomer acrylate'],
  ARRAY['liver toxicity', 'developmental effects'],
  'Transforms to PFOA, carpet treatment compound',
  ARRAY['carpet treatments', 'fabric protectors'],
  '8:2 fluorotelomer acrylate',
  NULL,
  'weeks to months',
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY['carpet treatments'],
  NULL,
  '40-60% in treated environments',
  ARRAY['precursor', 'transforms to PFOA'],
  FALSE,
  ARRAY['carpets', 'fabrics'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOA'],
  'Hydrolysis and oxidation to PFOA'
),

-- 19. 6:2 diPAP
(
  '6:2 diPAP',
  '57677-95-9',
  ARRAY['6:2 fluorotelomer phosphate diester'],
  ARRAY['liver effects', 'developmental effects'],
  'Transforms to PFHxA, common in food packaging grease barriers',
  ARRAY['food packaging', 'paper treatments', 'fast food wrappers'],
  '6:2 diPAP',
  NULL,
  'weeks',
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY['food contact materials'],
  NULL,
  '70-90% in food packaging',
  ARRAY['precursor', 'transforms to PFHxA'],
  FALSE,
  ARRAY['food packaging', 'paper'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFHxA'],
  'Hydrolysis and metabolism to PFHxA'
),

-- 20. 8:2 diPAP
(
  '8:2 diPAP',
  '678-41-1',
  ARRAY['8:2 fluorotelomer phosphate diester'],
  ARRAY['liver effects', 'developmental effects'],
  'Transforms to PFOA, food packaging grease barrier',
  ARRAY['food packaging', 'paper treatments', 'microwave popcorn bags'],
  '8:2 diPAP',
  NULL,
  'weeks',
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY['food contact materials'],
  NULL,
  '60-80% in food packaging',
  ARRAY['precursor', 'transforms to PFOA'],
  FALSE,
  ARRAY['food packaging', 'paper'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOA'],
  'Hydrolysis and metabolism to PFOA'
),

-- PFOS Precursors

-- 21. PFOSA
(
  'PFOSA',
  '754-91-6',
  ARRAY['perfluorooctane sulfonamide', 'FOSA'],
  ARRAY['liver toxicity', 'developmental effects', 'endocrine disruption'],
  'Transforms to PFOS, used in Scotchgard until 2003',
  ARRAY['former stain treatments', 'carpet treatments', 'paper treatments'],
  'PFOSA',
  NULL,
  'weeks to months',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY[],
  ARRAY['all uses'],
  '2003-12-31',
  '30-50% of population',
  ARRAY['precursor', 'transforms to PFOS'],
  TRUE,
  ARRAY['textiles', 'carpets', 'paper'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOS'],
  'Biotransformation via N-dealkylation to PFOS'
),

-- 22. N-EtFOSE
(
  'N-EtFOSE',
  '1691-99-2',
  ARRAY['N-ethyl perfluorooctane sulfonamidoethanol'],
  ARRAY['liver toxicity', 'developmental effects'],
  'Transforms to PFOS, paper and packaging treatments',
  ARRAY['paper treatments', 'food packaging', 'carpet treatments'],
  'N-EtFOSE',
  NULL,
  'weeks',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY[],
  ARRAY['all uses'],
  '2006-12-31',
  '20-40% near contaminated sites',
  ARRAY['precursor', 'transforms to PFOS'],
  FALSE,
  ARRAY['paper', 'food packaging', 'carpets'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOS'],
  'Metabolism to PFOS via N-EtFOSA and N-EtFOSAA'
),

-- 23. N-MeFOSE
(
  'N-MeFOSE',
  '24448-09-7',
  ARRAY['N-methyl perfluorooctane sulfonamidoethanol'],
  ARRAY['liver toxicity', 'developmental effects'],
  'Transforms to PFOS, carpet and textile treatments',
  ARRAY['carpet treatments', 'textile treatments', 'upholstery'],
  'N-MeFOSE',
  NULL,
  'weeks',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY[],
  ARRAY['all uses'],
  '2006-12-31',
  '20-40% near contaminated sites',
  ARRAY['precursor', 'transforms to PFOS'],
  FALSE,
  ARRAY['carpets', 'textiles', 'upholstery'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOS'],
  'Metabolism to PFOS via N-MeFOSA'
),

-- 24. N-EtFOSA
(
  'N-EtFOSA',
  '4151-50-2',
  ARRAY['N-ethyl perfluorooctane sulfonamide'],
  ARRAY['liver toxicity', 'developmental effects'],
  'Transforms to PFOS, manufacturing intermediate',
  ARRAY['industrial intermediate', 'legacy contamination'],
  'N-EtFOSA',
  NULL,
  'weeks to months',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY[],
  ARRAY['all uses'],
  '2003-12-31',
  '10-30% near contaminated sites',
  ARRAY['precursor', 'transforms to PFOS'],
  FALSE,
  ARRAY['industrial'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOS'],
  'N-dealkylation to PFOSA then PFOS'
),

-- 25. N-EtFOSAA
(
  'N-EtFOSAA',
  '2991-50-6',
  ARRAY['N-ethyl perfluorooctane sulfonamidoacetic acid'],
  ARRAY['liver toxicity', 'developmental effects'],
  'Transforms to PFOS, common in wastewater',
  ARRAY['wastewater', 'environmental contamination', 'industrial processes'],
  'N-EtFOSAA',
  NULL,
  'weeks to months',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY[],
  ARRAY['all uses'],
  '2006-12-31',
  '30-50% in wastewater',
  ARRAY['precursor', 'transforms to PFOS'],
  FALSE,
  ARRAY['wastewater', 'industrial'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOS'],
  'Desulfonation to PFOS'
),

-- Fluoropolymer

-- 26. PTFE
(
  'PTFE',
  '9002-84-0',
  ARRAY['polytetrafluoroethylene', 'Teflon', 'fluoropolymer'],
  ARRAY['polymer fume fever', 'respiratory effects from overheating'],
  'Generally inert polymer, but breaks down to toxic fumes including PFOA at >500°F',
  ARRAY['non-stick cookware', 'industrial coatings', 'textiles', 'medical devices'],
  'Teflon',
  NULL,
  'persistent polymer',
  'restricted for manufacturing contamination',
  'restricted for manufacturing contamination',
  'restricted',
  ARRAY['cookware', 'industrial coatings', 'medical devices'],
  ARRAY[],
  NULL,
  'widespread in consumer products',
  ARRAY['persistent polymer', 'releases PFOA when overheated'],
  TRUE,
  ARRAY['cookware', 'textiles', 'industrial coatings'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOA'],
  'Thermal degradation >500°F releases PFOA and other PFCAs'
),

-- Emerging

-- 27. PFHpS
(
  'PFHpS',
  '375-92-8',
  ARRAY['perfluoroheptane sulfonate', 'C7 sulfonate'],
  ARRAY['liver effects', 'thyroid effects'],
  'Liver and thyroid toxicity',
  ARRAY['firefighting foam', 'industrial surfactants'],
  'C7 sulfonate',
  7,
  '3-8 years',
  'under assessment',
  'under review',
  'restricted',
  ARRAY['industrial applications'],
  ARRAY[],
  NULL,
  '40-60% of population',
  ARRAY['persistent', 'emerging concern'],
  TRUE,
  ARRAY['firefighting foam', 'industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 28. 6:2 FTSA
(
  '6:2 FTSA',
  '27619-97-2',
  ARRAY['6:2 fluorotelomer sulfonate', '1H,1H,2H,2H-perfluorooctane sulfonate'],
  ARRAY['liver effects', 'developmental effects'],
  'Fluorotelomer sulfonate, liver and developmental toxicity',
  ARRAY['firefighting foam', 'industrial surfactants'],
  '6:2 FTSA',
  NULL,
  'months to years',
  'under assessment',
  'under review',
  'restricted',
  ARRAY['firefighting foam'],
  ARRAY[],
  NULL,
  '30-50% near contaminated sites',
  ARRAY['persistent', 'emerging concern'],
  FALSE,
  ARRAY['firefighting foam', 'industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 29. 8:2 FTSA
(
  '8:2 FTSA',
  '39108-34-4',
  ARRAY['8:2 fluorotelomer sulfonate', '1H,1H,2H,2H-perfluorodecane sulfonate'],
  ARRAY['liver effects', 'developmental effects'],
  'Fluorotelomer sulfonate, liver and developmental toxicity',
  ARRAY['firefighting foam', 'industrial surfactants'],
  '8:2 FTSA',
  NULL,
  'months to years',
  'under assessment',
  'under review',
  'restricted',
  ARRAY['firefighting foam'],
  ARRAY[],
  NULL,
  '20-40% near contaminated sites',
  ARRAY['persistent', 'emerging concern'],
  FALSE,
  ARRAY['firefighting foam', 'industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 30. POSF
(
  'POSF',
  '307-35-7',
  ARRAY['perfluorooctane sulfonyl fluoride'],
  ARRAY['liver toxicity', 'developmental effects', 'endocrine disruption'],
  'Key manufacturing intermediate, transforms to all PFOS derivatives',
  ARRAY['industrial intermediate', '3M manufacturing'],
  'POSF',
  NULL,
  'weeks',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY[],
  ARRAY['all uses'],
  '2002-12-31',
  '<5% near legacy sites',
  ARRAY['precursor', 'transforms to PFOS and derivatives'],
  FALSE,
  ARRAY['industrial'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOS', 'PFOSA', 'N-EtFOSE', 'N-MeFOSE'],
  'Central precursor to all PFOS-based chemistry via sulfonyl fluoride reactivity'
),

-- Additional Long-Chain PFCAs

-- 31. PFTrDA
(
  'PFTrDA',
  '72629-94-8',
  ARRAY['perfluorotridecanoic acid', 'C13', 'PFTriDA'],
  ARRAY['liver toxicity', 'developmental toxicity', 'bioaccumulation'],
  'Ultra-long chain PFCA, extremely persistent and bioaccumulative',
  ARRAY['industrial processes', 'legacy contamination'],
  'C13',
  13,
  '10-15 years',
  'prohibited',
  'under review',
  'prohibited',
  ARRAY[],
  ARRAY['consumer products'],
  '2020-12-31',
  '40-60% of population',
  ARRAY['PBT', 'vPvB'],
  TRUE,
  ARRAY['industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 32. PFTeDA
(
  'PFTeDA',
  '376-06-7',
  ARRAY['perfluorotetradecanoic acid', 'C14'],
  ARRAY['liver toxicity', 'developmental toxicity', 'extreme bioaccumulation'],
  'Ultra-long chain PFCA, highest bioaccumulation potential',
  ARRAY['industrial processes', 'legacy contamination'],
  'C14',
  14,
  '12-20 years',
  'prohibited',
  'under review',
  'prohibited',
  ARRAY[],
  ARRAY['consumer products'],
  '2020-12-31',
  '30-50% of population',
  ARRAY['PBT', 'vPvB'],
  TRUE,
  ARRAY['industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- Additional Fluorotelomer Alcohols

-- 33. 4:2 FTOH
(
  '4:2 FTOH',
  '2043-47-2',
  ARRAY['4:2 fluorotelomer alcohol', '1H,1H,2H,2H-perfluorohexanol'],
  ARRAY['liver effects', 'transforms to PFBA'],
  'Short-chain fluorotelomer alcohol, transforms to PFBA in environment',
  ARRAY['food packaging', 'paper treatments'],
  '4:2 fluorotelomer alcohol',
  NULL,
  'days',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '30-50% in treated products',
  ARRAY['precursor', 'transforms to PFBA'],
  FALSE,
  ARRAY['food packaging', 'paper'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFBA'],
  'Oxidative degradation to PFBA'
),

-- 34. 6:2 FTOH
(
  '6:2 FTOH',
  '647-42-7',
  ARRAY['6:2 fluorotelomer alcohol', '1H,1H,2H,2H-perfluorooctanol'],
  ARRAY['liver toxicity', 'developmental effects'],
  'Transforms to PFHxA, widely used in food packaging',
  ARRAY['food packaging', 'carpet treatments', 'textiles'],
  '6:2 fluorotelomer alcohol',
  NULL,
  'days to weeks',
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY['food contact materials'],
  NULL,
  '70-85% in food packaging',
  ARRAY['precursor', 'transforms to PFHxA'],
  FALSE,
  ARRAY['food packaging', 'carpets', 'textiles'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFHxA'],
  'Oxidative degradation to PFHxA via environment/metabolism'
),

-- Fluorotelomer Methacrylates

-- 35. 6:2 FTMAC
(
  '6:2 FTMAC',
  NULL,
  ARRAY['6:2 fluorotelomer methacrylate'],
  ARRAY['liver effects', 'developmental effects'],
  'Polymer component that transforms to PFHxA, used in coatings',
  ARRAY['paper coatings', 'textile treatments', 'carpet treatments'],
  '6:2 FTMAC',
  NULL,
  'weeks to months',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '40-60% in treated products',
  ARRAY['precursor', 'transforms to PFHxA'],
  FALSE,
  ARRAY['paper', 'textiles', 'carpets'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFHxA'],
  'Polymer breakdown and oxidation to PFHxA'
),

-- 36. 8:2 FTMAC
(
  '8:2 FTMAC',
  NULL,
  ARRAY['8:2 fluorotelomer methacrylate'],
  ARRAY['liver toxicity', 'developmental effects'],
  'Polymer component that transforms to PFOA, carpet treatments',
  ARRAY['carpet treatments', 'textile treatments', 'paper coatings'],
  '8:2 FTMAC',
  NULL,
  'weeks to months',
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '30-50% in treated products',
  ARRAY['precursor', 'transforms to PFOA'],
  FALSE,
  ARRAY['carpets', 'textiles', 'paper'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOA'],
  'Polymer breakdown and oxidation to PFOA'
),

-- Fluorotelomer Carboxylic Acids

-- 37. 5:3 FTCA
(
  '5:3 FTCA',
  '914637-49-3',
  ARRAY['5:3 fluorotelomer carboxylic acid'],
  ARRAY['liver effects', 'developmental effects'],
  'Intermediate transformation product to PFHxA',
  ARRAY['environmental transformation product', 'wastewater'],
  '5:3 FTCA',
  NULL,
  'weeks to months',
  'under assessment',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '20-40% in contaminated water',
  ARRAY['precursor', 'intermediate'],
  FALSE,
  ARRAY['environmental', 'wastewater'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFHxA'],
  'Oxidative transformation to PFHxA in environment'
),

-- 38. 7:3 FTCA
(
  '7:3 FTCA',
  '812-70-4',
  ARRAY['7:3 fluorotelomer carboxylic acid'],
  ARRAY['liver toxicity', 'developmental effects'],
  'Intermediate transformation product to PFOA',
  ARRAY['environmental transformation product', 'wastewater'],
  '7:3 FTCA',
  NULL,
  'weeks to months',
  'under assessment',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '15-35% in contaminated water',
  ARRAY['precursor', 'intermediate'],
  FALSE,
  ARRAY['environmental', 'wastewater'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOA'],
  'Oxidative transformation to PFOA in environment'
),

-- Additional Fluorotelomer Sulfonates

-- 39. 4:2 FTSA
(
  '4:2 FTSA',
  NULL,
  ARRAY['4:2 fluorotelomer sulfonate', '1H,1H,2H,2H-perfluorohexane sulfonate'],
  ARRAY['liver effects', 'environmental persistence'],
  'Short-chain fluorotelomer sulfonate used in firefighting foam',
  ARRAY['firefighting foam', 'industrial surfactants'],
  '4:2 FTSA',
  NULL,
  'months to years',
  'under assessment',
  'under review',
  'restricted',
  ARRAY['firefighting foam'],
  ARRAY[],
  NULL,
  '20-40% near contaminated sites',
  ARRAY['persistent', 'precursor'],
  FALSE,
  ARRAY['firefighting foam', 'industrial'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFBA'],
  'Transformation to PFBA via environmental degradation'
),

-- PFOS Precursor Intermediates

-- 40. N-MeFOSA
(
  'N-MeFOSA',
  '31506-32-8',
  ARRAY['N-methyl perfluorooctane sulfonamide'],
  ARRAY['liver toxicity', 'developmental effects'],
  'PFOS precursor intermediate, metabolite of N-MeFOSE',
  ARRAY['industrial intermediate', 'environmental contamination'],
  'N-MeFOSA',
  NULL,
  'weeks to months',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY[],
  ARRAY['all uses'],
  '2003-12-31',
  '15-30% near contaminated sites',
  ARRAY['precursor', 'transforms to PFOS'],
  FALSE,
  ARRAY['industrial', 'environmental'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOS'],
  'N-dealkylation to PFOSA then PFOS'
),

-- 41. N-MeFOSAA
(
  'N-MeFOSAA',
  '2355-31-9',
  ARRAY['N-methyl perfluorooctane sulfonamidoacetic acid'],
  ARRAY['liver toxicity', 'developmental effects'],
  'PFOS precursor, common in wastewater and human serum',
  ARRAY['wastewater', 'environmental contamination'],
  'N-MeFOSAA',
  NULL,
  'weeks to months',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY[],
  ARRAY['all uses'],
  '2006-12-31',
  '25-45% in wastewater',
  ARRAY['precursor', 'transforms to PFOS'],
  FALSE,
  ARRAY['wastewater', 'environmental'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOS'],
  'Metabolism and desulfonation to PFOS'
),

-- 42. FOSAA
(
  'FOSAA',
  NULL,
  ARRAY['perfluorooctanesulfonamidoacetic acid'],
  ARRAY['liver toxicity', 'developmental effects'],
  'PFOS precursor intermediate, environmental breakdown product',
  ARRAY['wastewater', 'environmental contamination'],
  'FOSAA',
  NULL,
  'weeks to months',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY[],
  ARRAY['all uses'],
  '2006-12-31',
  '10-25% in contaminated water',
  ARRAY['precursor', 'transforms to PFOS'],
  FALSE,
  ARRAY['wastewater', 'environmental'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOS'],
  'Desulfonation to PFOS'
),

-- Side-Chain Fluorinated Polymers

-- 43. Fluorinated Acrylate Polymer
(
  'Fluorinated Acrylate Polymer',
  NULL,
  ARRAY['SCFP', 'side-chain fluorinated polymer'],
  ARRAY['releases PFOA and PFHxA', 'environmental persistence'],
  'Side-chain fluorinated polymer that releases PFOA and PFHxA upon degradation',
  ARRAY['coatings', 'textiles', 'paper treatments'],
  'SCFP',
  NULL,
  'persistent polymer',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '30-50% in treated products',
  ARRAY['precursor', 'polymer'],
  FALSE,
  ARRAY['coatings', 'textiles', 'paper'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOA', 'PFHxA'],
  'Polymer breakdown releases fluorotelomer alcohols that oxidize to PFOA/PFHxA'
),

-- 44. Fluorinated Methacrylate Polymer
(
  'Fluorinated Methacrylate Polymer',
  NULL,
  ARRAY['SCFP', 'side-chain fluorinated polymer'],
  ARRAY['releases PFCAs', 'environmental persistence'],
  'Side-chain fluorinated polymer used in coatings',
  ARRAY['coatings', 'textiles', 'industrial applications'],
  'SCFP',
  NULL,
  'persistent polymer',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '25-45% in industrial coatings',
  ARRAY['precursor', 'polymer'],
  FALSE,
  ARRAY['coatings', 'textiles', 'industrial'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOA', 'PFHxA'],
  'Polymer degradation releases PFCA precursors'
),

-- 45. Fluorinated Urethane Polymer
(
  'Fluorinated Urethane Polymer',
  NULL,
  ARRAY['SCFP', 'fluorinated polyurethane'],
  ARRAY['releases PFCAs', 'environmental persistence'],
  'Fluorinated urethane polymer used in coatings and textiles',
  ARRAY['coatings', 'textiles', 'outdoor fabrics'],
  'SCFP',
  NULL,
  'persistent polymer',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '20-40% in outdoor textiles',
  ARRAY['precursor', 'polymer'],
  FALSE,
  ARRAY['coatings', 'textiles', 'outdoor gear'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOA', 'PFHxA'],
  'Polymer breakdown releases fluorotelomer precursors'
),

-- Additional Short-Chain

-- 46. PFPA
(
  'PFPA',
  '422-64-0',
  ARRAY['perfluoropropanoic acid', 'C3', 'perfluoropropionic acid'],
  ARRAY['liver effects', 'environmental mobility'],
  'Ultra-short chain PFCA, highly mobile in environment',
  ARRAY['industrial processes', 'environmental contamination'],
  'C3',
  3,
  '2-3 days',
  'restricted',
  'under review',
  'restricted',
  ARRAY['industrial applications'],
  ARRAY[],
  NULL,
  '40-60% of population',
  ARRAY['persistent', 'mobile'],
  FALSE,
  ARRAY['industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 47. PFPrS
(
  'PFPrS',
  NULL,
  ARRAY['perfluoropropane sulfonate', 'C3 sulfonate'],
  ARRAY['liver effects', 'environmental mobility'],
  'Ultra-short chain PFSA, highly mobile in environment',
  ARRAY['industrial processes', 'firefighting foam'],
  'C3 sulfonate',
  3,
  '1-2 weeks',
  'under assessment',
  'under review',
  'restricted',
  ARRAY['industrial applications'],
  ARRAY[],
  NULL,
  '30-50% near contaminated sites',
  ARRAY['persistent', 'mobile'],
  FALSE,
  ARRAY['firefighting foam', 'industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- GenX Family

-- 48. HFPO
(
  'HFPO',
  '428-59-1',
  ARRAY['hexafluoropropylene oxide', 'HFPO monomer'],
  ARRAY['liver toxicity', 'transforms to GenX'],
  'Precursor to GenX, manufacturing intermediate',
  ARRAY['industrial intermediate', 'fluoropolymer production'],
  'HFPO',
  NULL,
  'days to weeks',
  'under assessment',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '<5% near manufacturing sites',
  ARRAY['precursor', 'transforms to GenX'],
  FALSE,
  ARRAY['industrial'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['GenX'],
  'Polymerization and oxidation to GenX (HFPO-DA)'
),

-- 49. PFMOAA
(
  'PFMOAA',
  '674-13-5',
  ARRAY['perfluoro-2-methoxyacetic acid'],
  ARRAY['liver effects', 'developmental effects'],
  'Ether-PFAS, GenX-related compound',
  ARRAY['industrial processes', 'GenX production'],
  'PFMOAA',
  NULL,
  'weeks to months',
  'under assessment',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '<10% near GenX sites',
  ARRAY['emerging concern'],
  FALSE,
  ARRAY['industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- Ether-PFAS

-- 50. PFECA
(
  'PFECA',
  NULL,
  ARRAY['per/polyfluoroalkyl ether carboxylic acid', 'ether PFCA'],
  ARRAY['liver effects', 'developmental effects', 'environmental persistence'],
  'Class of ether-containing PFAS, includes GenX and similar compounds',
  ARRAY['industrial processes', 'PFOA replacements'],
  'PFECA class',
  NULL,
  'weeks to months',
  'under assessment',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '10-30% near contaminated sites',
  ARRAY['emerging concern', 'persistent'],
  FALSE,
  ARRAY['industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 51. PFESA
(
  'PFESA',
  NULL,
  ARRAY['per/polyfluoroalkyl ether sulfonic acid', 'ether PFSA'],
  ARRAY['liver effects', 'developmental effects', 'environmental persistence'],
  'Class of ether-containing PFAS sulfonates',
  ARRAY['industrial processes', 'PFOS replacements'],
  'PFESA class',
  NULL,
  'months to years',
  'under assessment',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '5-20% near contaminated sites',
  ARRAY['emerging concern', 'persistent'],
  FALSE,
  ARRAY['industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- Emerging/Alternatives

-- 52. ADONA Analogues
(
  'ADONA Analogues',
  NULL,
  ARRAY['ADONA derivatives', 'various chain lengths'],
  ARRAY['liver effects', 'developmental effects'],
  'Various chain-length analogues of ADONA',
  ARRAY['industrial processes', 'fluoropolymer production'],
  'ADONA analogues',
  NULL,
  '1-3 months',
  'under assessment',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '<5% of population',
  ARRAY['emerging concern'],
  FALSE,
  ARRAY['industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 53. 6:2 Cl-PFESA (F53B)
(
  '6:2 Cl-PFESA',
  '73606-19-6',
  ARRAY['F53B', 'chlorinated polyfluoroalkyl ether sulfonic acid'],
  ARRAY['liver toxicity', 'developmental effects', 'bioaccumulation'],
  'Chinese PFOS alternative, chlorinated ether-PFAS',
  ARRAY['chrome plating', 'metal finishing', 'industrial surfactants'],
  'F53B',
  NULL,
  'years',
  'under assessment',
  'under review',
  'under assessment',
  ARRAY[],
  ARRAY[],
  NULL,
  '5-15% near Chinese industrial sites',
  ARRAY['emerging concern', 'bioaccumulative'],
  TRUE,
  ARRAY['chrome plating', 'industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 54. 11Cl-PF3OUdS
(
  '11Cl-PF3OUdS',
  NULL,
  ARRAY['11-chloroeicosafluoro-3-oxaundecane-1-sulfonate', 'Chinese alternative'],
  ARRAY['liver effects', 'bioaccumulation'],
  'Chinese PFOS alternative, long-chain ether-PFSA',
  ARRAY['chrome plating', 'industrial applications'],
  '11Cl-PF3OUdS',
  NULL,
  'years',
  'under assessment',
  'under review',
  'under assessment',
  ARRAY[],
  ARRAY[],
  NULL,
  '<10% near Chinese industrial sites',
  ARRAY['emerging concern', 'bioaccumulative'],
  TRUE,
  ARRAY['chrome plating', 'industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- Cosmetic PFAS (10 compounds as one entry for brevity, then individual entries)

-- 55. Perfluorodecalin
(
  'Perfluorodecalin',
  NULL,
  ARRAY['perfluorodecahydronaphthalene', 'PFD'],
  ARRAY['environmental persistence', 'bioaccumulation'],
  'Cyclic perfluorocarbon used in cosmetics as solvent',
  ARRAY['cosmetics', 'skincare', 'foundations'],
  'Perfluorodecalin',
  NULL,
  'persistent',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '10-30% in certain cosmetics',
  ARRAY['persistent', 'cosmetic PFAS'],
  FALSE,
  ARRAY['cosmetics', 'skincare'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 56. Trifluoroacetyl Tripeptide-2
(
  'Trifluoroacetyl Tripeptide-2',
  NULL,
  ARRAY['TFA tripeptide-2'],
  ARRAY['skin sensitization potential'],
  'Fluorinated peptide used in anti-aging cosmetics',
  ARRAY['cosmetics', 'anti-aging creams', 'serums'],
  'TFA tripeptide-2',
  NULL,
  'unknown',
  'under assessment',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '5-15% in anti-aging products',
  ARRAY['cosmetic PFAS'],
  FALSE,
  ARRAY['cosmetics', 'skincare'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 57. Polyperfluoromethylisopropyl Ether
(
  'Polyperfluoromethylisopropyl Ether',
  NULL,
  ARRAY['perfluoropolyether'],
  ARRAY['environmental persistence'],
  'Fluorinated ether polymer used in cosmetics',
  ARRAY['cosmetics', 'foundations', 'primers'],
  'Polyperfluoromethylisopropyl ether',
  NULL,
  'persistent polymer',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '15-35% in certain cosmetics',
  ARRAY['persistent', 'cosmetic PFAS'],
  FALSE,
  ARRAY['cosmetics'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 58. Perfluorononyl Dimethicone
(
  'Perfluorononyl Dimethicone',
  NULL,
  ARRAY['fluorosilicone'],
  ARRAY['environmental persistence', 'potential PFAS release'],
  'Fluorinated silicone used in cosmetics for water resistance',
  ARRAY['cosmetics', 'hair products', 'foundations'],
  'Perfluorononyl dimethicone',
  NULL,
  'persistent polymer',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '20-40% in waterproof cosmetics',
  ARRAY['persistent', 'cosmetic PFAS'],
  FALSE,
  ARRAY['cosmetics', 'hair products'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 59. Polyperfluoroethoxymethoxy Difluoroethyl PEG Phosphate
(
  'Polyperfluoroethoxymethoxy Difluoroethyl PEG Phosphate',
  NULL,
  ARRAY['fluorinated PEG phosphate'],
  ARRAY['environmental persistence'],
  'Complex fluorinated polymer used in cosmetics',
  ARRAY['cosmetics', 'skincare'],
  'Fluorinated PEG phosphate',
  NULL,
  'persistent polymer',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '5-15% in specialized cosmetics',
  ARRAY['persistent', 'cosmetic PFAS'],
  FALSE,
  ARRAY['cosmetics', 'skincare'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 60. Perfluorohexylethyl Triethoxysilane
(
  'Perfluorohexylethyl Triethoxysilane',
  NULL,
  ARRAY['fluorosilane'],
  ARRAY['environmental persistence'],
  'Fluorinated silane used in cosmetic coatings',
  ARRAY['cosmetics', 'nail polish', 'coatings'],
  'Perfluorohexylethyl triethoxysilane',
  NULL,
  'persistent',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '10-25% in nail products',
  ARRAY['persistent', 'cosmetic PFAS'],
  FALSE,
  ARRAY['cosmetics', 'nail polish'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 61. Methyl Perfluorobutyl Ether
(
  'Methyl Perfluorobutyl Ether',
  NULL,
  ARRAY['perfluorobutyl methyl ether'],
  ARRAY['environmental persistence', 'volatility'],
  'Volatile fluorinated ether used in cosmetics',
  ARRAY['cosmetics', 'aerosol products'],
  'Methyl perfluorobutyl ether',
  NULL,
  'weeks to months',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '5-15% in aerosol cosmetics',
  ARRAY['persistent', 'cosmetic PFAS', 'volatile'],
  FALSE,
  ARRAY['cosmetics', 'aerosols'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 62. Methyl Perfluoroisobutyl Ether
(
  'Methyl Perfluoroisobutyl Ether',
  NULL,
  ARRAY['perfluoroisobutyl methyl ether'],
  ARRAY['environmental persistence', 'volatility'],
  'Volatile fluorinated ether used in cosmetics',
  ARRAY['cosmetics', 'aerosol products', 'solvents'],
  'Methyl perfluoroisobutyl ether',
  NULL,
  'weeks to months',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '5-15% in aerosol cosmetics',
  ARRAY['persistent', 'cosmetic PFAS', 'volatile'],
  FALSE,
  ARRAY['cosmetics', 'aerosols'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 63. Perfluorohexane
(
  'Perfluorohexane',
  NULL,
  ARRAY['PFHx', 'C6F14'],
  ARRAY['environmental persistence', 'volatility'],
  'Volatile perfluorocarbon used in cosmetics',
  ARRAY['cosmetics', 'aerosol products'],
  'PFHx',
  6,
  'weeks',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '10-20% in aerosol cosmetics',
  ARRAY['persistent', 'cosmetic PFAS', 'volatile'],
  FALSE,
  ARRAY['cosmetics', 'aerosols'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 64. Perfluorodecyl Dimethicone
(
  'Perfluorodecyl Dimethicone',
  NULL,
  ARRAY['fluorosilicone C10'],
  ARRAY['environmental persistence'],
  'Long-chain fluorinated silicone for cosmetics',
  ARRAY['cosmetics', 'hair products', 'foundations'],
  'Perfluorodecyl dimethicone',
  NULL,
  'persistent polymer',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '15-30% in waterproof cosmetics',
  ARRAY['persistent', 'cosmetic PFAS'],
  FALSE,
  ARRAY['cosmetics', 'hair products'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- Additional Sulfonates

-- 65. PFNS
(
  'PFNS',
  NULL,
  ARRAY['perfluorononane sulfonate', 'C9 sulfonate'],
  ARRAY['liver toxicity', 'bioaccumulation'],
  'C9 sulfonate, intermediate between PFHxS and PFDS',
  ARRAY['industrial surfactants', 'firefighting foam'],
  'C9 sulfonate',
  9,
  '8-12 years',
  'under assessment',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '30-50% of population',
  ARRAY['persistent', 'bioaccumulative'],
  TRUE,
  ARRAY['firefighting foam', 'industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 66. PFPeS
(
  'PFPeS',
  NULL,
  ARRAY['perfluoropentane sulfonate', 'C5 sulfonate'],
  ARRAY['liver effects', 'thyroid effects'],
  'C5 sulfonate, short-chain alternative',
  ARRAY['firefighting foam', 'industrial surfactants'],
  'C5 sulfonate',
  5,
  '2-6 months',
  'under assessment',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '40-60% of population',
  ARRAY['persistent', 'mobile'],
  FALSE,
  ARRAY['firefighting foam', 'industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 67-70. C4-C6 Sulfonates (additional entries)

-- 67. C4 Sulfonate
(
  'C4 Sulfonate',
  NULL,
  ARRAY['perfluorobutane sulfonate variants'],
  ARRAY['liver effects'],
  'C4 sulfonate variants including isomers',
  ARRAY['industrial surfactants', 'firefighting foam'],
  'C4 sulfonate',
  4,
  '2-4 weeks',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '50-70% of population',
  ARRAY['persistent', 'mobile'],
  FALSE,
  ARRAY['firefighting foam', 'industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 68. C5 Sulfonate Isomers
(
  'C5 Sulfonate Isomers',
  NULL,
  ARRAY['perfluoropentane sulfonate isomers'],
  ARRAY['liver effects', 'thyroid effects'],
  'Various C5 sulfonate isomers',
  ARRAY['industrial surfactants'],
  'C5 sulfonate isomers',
  5,
  '3-6 months',
  'under assessment',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '35-55% of population',
  ARRAY['persistent'],
  FALSE,
  ARRAY['industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 69. C6 Sulfonate Isomers
(
  'C6 Sulfonate Isomers',
  NULL,
  ARRAY['perfluorohexane sulfonate isomers'],
  ARRAY['liver toxicity', 'bioaccumulation'],
  'Various C6 sulfonate isomers including branched',
  ARRAY['firefighting foam', 'industrial surfactants'],
  'C6 sulfonate isomers',
  6,
  '5-27 years',
  'under assessment',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '80-95% of population',
  ARRAY['persistent', 'bioaccumulative'],
  TRUE,
  ARRAY['firefighting foam', 'industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 70. Mixed Short-Chain Sulfonates
(
  'Mixed Short-Chain Sulfonates',
  NULL,
  ARRAY['C4-C6 sulfonate mixture'],
  ARRAY['liver effects', 'environmental mobility'],
  'Commercial mixtures of C4-C6 sulfonates',
  ARRAY['firefighting foam', 'industrial applications'],
  'C4-C6 sulfonate mixture',
  NULL,
  'weeks to years',
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY[],
  NULL,
  '60-80% in firefighting foam sites',
  ARRAY['persistent', 'mobile'],
  FALSE,
  ARRAY['firefighting foam', 'industrial'],
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- Long-Chain Sulfonamides

-- 71. FOSA Derivatives
(
  'FOSA Derivatives',
  NULL,
  ARRAY['perfluorooctane sulfonamide derivatives'],
  ARRAY['liver toxicity', 'transforms to PFOS'],
  'Various PFOSA derivatives and breakdown products',
  ARRAY['environmental contamination', 'legacy sites'],
  'FOSA derivatives',
  NULL,
  'weeks to months',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY[],
  ARRAY['all uses'],
  '2003-12-31',
  '20-40% near legacy sites',
  ARRAY['precursor', 'transforms to PFOS'],
  TRUE,
  ARRAY['environmental'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOS'],
  'Biotransformation to PFOS'
),

-- 72. N-Propyl FOSA
(
  'N-Propyl FOSA',
  NULL,
  ARRAY['N-propyl perfluorooctane sulfonamide'],
  ARRAY['liver toxicity', 'transforms to PFOS'],
  'N-propyl derivative of PFOSA',
  ARRAY['industrial intermediate', 'legacy contamination'],
  'N-Propyl FOSA',
  NULL,
  'weeks to months',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY[],
  ARRAY['all uses'],
  '2003-12-31',
  '<10% near legacy sites',
  ARRAY['precursor', 'transforms to PFOS'],
  FALSE,
  ARRAY['industrial'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOS'],
  'N-dealkylation to PFOSA then PFOS'
),

-- 73. N-Butyl FOSA
(
  'N-Butyl FOSA',
  NULL,
  ARRAY['N-butyl perfluorooctane sulfonamide'],
  ARRAY['liver toxicity', 'transforms to PFOS'],
  'N-butyl derivative of PFOSA',
  ARRAY['industrial intermediate', 'legacy contamination'],
  'N-Butyl FOSA',
  NULL,
  'weeks to months',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY[],
  ARRAY['all uses'],
  '2003-12-31',
  '<10% near legacy sites',
  ARRAY['precursor', 'transforms to PFOS'],
  FALSE,
  ARRAY['industrial'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOS'],
  'N-dealkylation to PFOSA then PFOS'
),

-- 74. Sulfonamide Intermediates
(
  'Sulfonamide Intermediates',
  NULL,
  ARRAY['PFOS-based sulfonamide intermediates'],
  ARRAY['liver toxicity', 'transforms to PFOS'],
  'Various sulfonamide intermediates in PFOS production',
  ARRAY['industrial intermediate', 'manufacturing'],
  'Sulfonamide intermediates',
  NULL,
  'weeks',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY[],
  ARRAY['all uses'],
  '2002-12-31',
  '<5% near legacy sites',
  ARRAY['precursor', 'transforms to PFOS'],
  FALSE,
  ARRAY['industrial'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOS'],
  'Various pathways to PFOS'
),

-- 75. Sulfonamide Breakdown Products
(
  'Sulfonamide Breakdown Products',
  NULL,
  ARRAY['PFOS sulfonamide metabolites'],
  ARRAY['liver toxicity', 'transforms to PFOS'],
  'Environmental and biological breakdown products of sulfonamides',
  ARRAY['environmental contamination', 'wastewater'],
  'Sulfonamide metabolites',
  NULL,
  'weeks to months',
  'prohibited',
  'prohibited',
  'prohibited',
  ARRAY[],
  ARRAY['all uses'],
  '2006-12-31',
  '15-35% in contaminated water',
  ARRAY['precursor', 'transforms to PFOS'],
  FALSE,
  ARRAY['environmental', 'wastewater'],
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['PFOS'],
  'Degradation pathways to PFOS'
)

ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- PART 3: TOXIC SUBSTANCES (50 Substances)
-- ============================================================================
-- Includes: Phthalates + metabolites, Bisphenols + derivatives, Heavy Metals, VOCs,
-- Formaldehyde releasers, Surfactants, Preservatives, Paraben metabolites

INSERT INTO toxic_substances (
  name,
  common_names,
  cas_number,
  synonyms,
  substance_category,
  health_hazard_class,
  health_impacts,
  body_effects,
  vulnerable_populations,
  consumer_products,
  exposure_routes,
  regulatory_status_canada,
  regulatory_status_usa,
  regulatory_status_eu,
  banned_applications,
  permitted_applications,
  concentration_limits,
  is_precursor,
  is_metabolite,
  parent_compounds,
  metabolites,
  transformation_pathway
) VALUES

-- Phthalates

-- 1. DEHP
(
  'DEHP',
  ARRAY['Di(2-ethylhexyl) phthalate'],
  '117-81-7',
  ARRAY['dioctyl phthalate', 'DOP', 'bis(2-ethylhexyl) phthalate'],
  'phthalate',
  ARRAY['endocrine disruptor', 'reproductive toxin'],
  ARRAY['testicular toxicity', 'reduced sperm count', 'altered testosterone', 'liver toxicity', 'developmental effects'],
  'Reproductive toxicity (anti-androgenic), liver damage, developmental effects in fetuses and children',
  ARRAY['pregnant women', 'children', 'workers'],
  ARRAY['vinyl flooring', 'medical tubing', 'food packaging', 'cosmetics', 'toys'],
  ARRAY['ingestion', 'dermal', 'inhalation'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['toys and childcare articles >0.1%', 'cosmetics (EU)'],
  ARRAY['medical devices (time-limited)', 'industrial applications'],
  '{"toys": "0.1%", "cosmetics_EU": "0%", "medical_devices": "under review"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY['MEHP', 'MEOHP', 'MEHHP', 'MECPP'],
  NULL
),

-- 2. DBP
(
  'DBP',
  ARRAY['Dibutyl phthalate'],
  '84-74-2',
  ARRAY['di-n-butyl phthalate', 'phthalic acid dibutyl ester'],
  'phthalate',
  ARRAY['reproductive toxin', 'endocrine disruptor'],
  ARRAY['reproductive toxicity', 'developmental effects', 'anti-androgenic effects'],
  'Reproductive and developmental toxicity, anti-androgenic effects',
  ARRAY['pregnant women', 'children'],
  ARRAY['nail polish', 'adhesives', 'printing inks', 'cosmetics'],
  ARRAY['dermal', 'inhalation', 'ingestion'],
  'restricted',
  'restricted',
  'banned',
  ARRAY['cosmetics (EU)', 'toys >0.1%'],
  ARRAY['industrial adhesives', 'printing inks'],
  '{"toys": "0.1%", "cosmetics_EU": "0%", "nail_products_USA": "restricted"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY['MBP'],
  NULL
),

-- 3. BBP
(
  'BBP',
  ARRAY['Benzyl butyl phthalate'],
  '85-68-7',
  ARRAY['butyl benzyl phthalate'],
  'phthalate',
  ARRAY['reproductive toxin', 'endocrine disruptor'],
  ARRAY['reproductive toxicity', 'developmental effects'],
  'Reproductive and developmental toxicity',
  ARRAY['pregnant women', 'children'],
  ARRAY['vinyl flooring', 'adhesives', 'sealants', 'toys'],
  ARRAY['dermal', 'ingestion'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['toys >0.1%', 'childcare articles >0.1%'],
  ARRAY['flooring', 'industrial sealants'],
  '{"toys": "0.1%"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY['MBzP'],
  NULL
),

-- 4. DINP
(
  'DINP',
  ARRAY['Diisononyl phthalate'],
  '28553-12-0',
  ARRAY['di-isononyl phthalate'],
  'phthalate',
  ARRAY['endocrine disruptor', 'reproductive toxin'],
  ARRAY['liver toxicity', 'reproductive effects', 'developmental effects'],
  'Liver and kidney toxicity, reproductive effects',
  ARRAY['children'],
  ARRAY['toys', 'flooring', 'food packaging', 'adhesives'],
  ARRAY['dermal', 'ingestion'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['toys that can be mouthed >0.1%'],
  ARRAY['toys not mouthed', 'flooring', 'industrial'],
  '{"mouthable_toys": "0.1%"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY['MINP'],
  NULL
),

-- 5. DEP
(
  'DEP',
  ARRAY['Diethyl phthalate'],
  '84-66-2',
  ARRAY['ethyl phthalate'],
  'phthalate',
  ARRAY['endocrine disruptor'],
  ARRAY['developmental effects', 'reproductive effects'],
  'Developmental and reproductive effects at high doses',
  ARRAY['pregnant women'],
  ARRAY['cosmetics', 'fragrances', 'lotions', 'deodorants'],
  ARRAY['dermal', 'inhalation'],
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY['cosmetics', 'fragrances'],
  '{"cosmetics": "under review"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY['MEP'],
  NULL
),

-- Phthalate Metabolites

-- 6. MEHP
(
  'MEHP',
  ARRAY['Mono(2-ethylhexyl) phthalate'],
  '4376-20-9',
  ARRAY['monoethylhexyl phthalate'],
  'phthalate',
  ARRAY['endocrine disruptor', 'reproductive toxin'],
  ARRAY['reproductive toxicity', 'anti-androgenic effects'],
  'Primary metabolite of DEHP, retains reproductive toxicity',
  ARRAY['pregnant women', 'children'],
  ARRAY['biomarker in urine from DEHP exposure'],
  ARRAY['ingestion', 'dermal'],
  'not regulated directly',
  'not regulated directly',
  'not regulated directly',
  ARRAY[],
  ARRAY[],
  NULL,
  FALSE,
  TRUE,
  ARRAY['DEHP'],
  ARRAY[],
  'Hydrolysis of DEHP by intestinal lipases'
),

-- 7. MEOHP
(
  'MEOHP',
  ARRAY['Mono(2-ethyl-5-oxohexyl) phthalate'],
  '40809-41-4',
  ARRAY['mono-2-ethyl-5-oxohexyl phthalate'],
  'phthalate',
  ARRAY['endocrine disruptor', 'reproductive toxin'],
  ARRAY['reproductive toxicity'],
  'DEHP metabolite, 4x more sensitive biomarker than MEHP',
  ARRAY['pregnant women', 'children'],
  ARRAY['biomarker in urine from DEHP exposure'],
  ARRAY['ingestion', 'dermal'],
  'not regulated directly',
  'not regulated directly',
  'not regulated directly',
  ARRAY[],
  ARRAY[],
  NULL,
  FALSE,
  TRUE,
  ARRAY['DEHP'],
  ARRAY[],
  'Oxidative metabolism of MEHP'
),

-- 8. MEHHP
(
  'MEHHP',
  ARRAY['Mono(2-ethyl-5-hydroxyhexyl) phthalate'],
  '40321-99-1',
  ARRAY['mono-2-ethyl-5-hydroxyhexyl phthalate'],
  'phthalate',
  ARRAY['endocrine disruptor', 'reproductive toxin'],
  ARRAY['reproductive toxicity'],
  'DEHP metabolite, sensitive biomarker',
  ARRAY['pregnant women', 'children'],
  ARRAY['biomarker in urine from DEHP exposure'],
  ARRAY['ingestion', 'dermal'],
  'not regulated directly',
  'not regulated directly',
  'not regulated directly',
  ARRAY[],
  ARRAY[],
  NULL,
  FALSE,
  TRUE,
  ARRAY['DEHP'],
  ARRAY[],
  'Oxidative metabolism of MEHP'
),

-- 9. MECPP
(
  'MECPP',
  ARRAY['Mono(2-ethyl-5-carboxypentyl) phthalate'],
  NULL,
  ARRAY['mono-2-ethyl-5-carboxypentyl phthalate'],
  'phthalate',
  ARRAY['endocrine disruptor', 'reproductive toxin'],
  ARRAY['reproductive toxicity'],
  'DEHP metabolite, comprises 87% of DEHP metabolites in urine',
  ARRAY['pregnant women', 'children'],
  ARRAY['biomarker in urine from DEHP exposure'],
  ARRAY['ingestion', 'dermal'],
  'not regulated directly',
  'not regulated directly',
  'not regulated directly',
  ARRAY[],
  ARRAY[],
  NULL,
  FALSE,
  TRUE,
  ARRAY['DEHP'],
  ARRAY[],
  'Oxidative metabolism of MEHP (most abundant metabolite)'
),

-- Bisphenols

-- 10. BPA
(
  'BPA',
  ARRAY['Bisphenol A'],
  '80-05-7',
  ARRAY['4,4''-isopropylidenediphenol', '2,2-bis(4-hydroxyphenyl)propane'],
  'bisphenol',
  ARRAY['endocrine disruptor', 'reproductive toxin'],
  ARRAY['reproductive effects', 'developmental effects', 'obesity', 'cardiovascular effects', 'cancer'],
  'Estrogenic endocrine disruptor, reproductive toxicity, neurodevelopmental effects, metabolic disruption',
  ARRAY['pregnant women', 'children', 'infants'],
  ARRAY['food can linings', 'thermal paper receipts', 'polycarbonate plastics', 'water bottles', 'dental sealants'],
  ARRAY['ingestion', 'dermal'],
  'restricted',
  'restricted',
  'banned',
  ARRAY['baby bottles (Canada, USA, EU)', 'infant formula cans (EU 2024)', 'thermal paper >0.02% (EU)'],
  ARRAY['some food cans', 'dental materials', 'industrial'],
  '{"baby_products": "0%", "thermal_paper_EU": "0.02%", "food_contact": "migration limit 0.6mg/kg"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY['BPA-glucuronide', 'BPA-sulfate'],
  NULL
),

-- 11. BPS
(
  'BPS',
  ARRAY['Bisphenol S'],
  '80-09-1',
  ARRAY['4,4''-sulfonyldiphenol', 'bis(4-hydroxyphenyl) sulfone'],
  'bisphenol',
  ARRAY['endocrine disruptor', 'reproductive toxin'],
  ARRAY['reproductive effects', 'developmental effects', 'thyroid disruption'],
  'BPA replacement with equal or worse endocrine disrupting effects',
  ARRAY['pregnant women', 'children'],
  ARRAY['thermal paper receipts', 'BPA-free plastics', 'food packaging'],
  ARRAY['dermal', 'ingestion'],
  'restricted',
  'under review',
  'restricted',
  ARRAY['thermal paper >0.02% (EU)'],
  ARRAY['some plastics', 'food packaging'],
  '{"thermal_paper_EU": "0.02%"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 12. BPF
(
  'BPF',
  ARRAY['Bisphenol F'],
  '620-92-8',
  ARRAY['4,4''-dihydroxydiphenylmethane', 'bis(4-hydroxyphenyl)methane'],
  'bisphenol',
  ARRAY['endocrine disruptor'],
  ARRAY['reproductive effects', 'developmental effects'],
  'BPA alternative with similar endocrine disrupting properties',
  ARRAY['pregnant women', 'children'],
  ARRAY['epoxy resins', 'food can linings', 'dental materials', 'plastics'],
  ARRAY['ingestion', 'dermal'],
  'restricted',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY['epoxy resins', 'coatings'],
  '{"food_contact": "under review"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 13. BPAF
(
  'BPAF',
  ARRAY['Bisphenol AF'],
  '1478-61-1',
  ARRAY['4,4''-(hexafluoroisopropylidene)diphenol'],
  'bisphenol',
  ARRAY['endocrine disruptor'],
  ARRAY['reproductive effects', 'developmental effects'],
  'Fluorinated bisphenol, more potent than BPA',
  ARRAY['pregnant women', 'children'],
  ARRAY['specialty plastics', 'electronics', 'fluoropolymer production'],
  ARRAY['dermal', 'ingestion'],
  'under assessment',
  'under review',
  'restricted',
  ARRAY[],
  ARRAY['industrial specialty applications'],
  NULL,
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- Bisphenol Derivatives

-- 14. BADGE
(
  'BADGE',
  ARRAY['Bisphenol A diglycidyl ether'],
  '1675-54-3',
  ARRAY['DGEBA', 'diglycidyl ether of bisphenol A'],
  'bisphenol',
  ARRAY['endocrine disruptor', 'allergen'],
  ARRAY['reproductive effects', 'allergic reactions', 'sensitization'],
  'Epoxy resin from BPA, used in food can coatings, hydrolyzes to BPA',
  ARRAY['pregnant women', 'workers'],
  ARRAY['food can linings', 'epoxy resins', 'adhesives', 'coatings'],
  ARRAY['ingestion', 'dermal'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY['food can linings', 'industrial coatings'],
  '{"food_contact_migration": "9 mg/kg", "infant_formula_EU": "1 mg/kg"}',
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['BADGE·H2O', 'BADGE·2H2O', 'BPA'],
  'Reaction of BPA with epichlorohydrin; hydrolyzes to BPA in acidic conditions'
),

-- 15. BADGE·H2O
(
  'BADGE·H2O',
  ARRAY['Bisphenol A diglycidyl ether monohydrate'],
  '76002-91-0',
  ARRAY['BADGE monohydrate', 'BADGE·1H2O'],
  'bisphenol',
  ARRAY['endocrine disruptor'],
  ARRAY['reproductive effects'],
  'Hydrolysis product of BADGE, found in canned foods',
  ARRAY['pregnant women'],
  ARRAY['canned foods', 'food packaging'],
  ARRAY['ingestion'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY[],
  '{"food_contact_migration": "1 mg/kg"}',
  FALSE,
  TRUE,
  ARRAY['BADGE'],
  ARRAY['BADGE·2H2O', 'BPA'],
  'Hydrolysis of one epoxy group of BADGE'
),

-- 16. BADGE·2H2O
(
  'BADGE·2H2O',
  ARRAY['Bisphenol A diglycidyl ether dihydrate'],
  '5581-32-8',
  ARRAY['BADGE dihydrate', 'BADGE·2H2O'],
  'bisphenol',
  ARRAY['endocrine disruptor'],
  ARRAY['reproductive effects'],
  'Hydrolysis product of BADGE, found in canned foods',
  ARRAY['pregnant women'],
  ARRAY['canned foods', 'food packaging'],
  ARRAY['ingestion'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY[],
  '{"food_contact_migration": "1 mg/kg"}',
  FALSE,
  TRUE,
  ARRAY['BADGE'],
  ARRAY['BPA'],
  'Complete hydrolysis of both epoxy groups of BADGE'
),

-- 17. BFDGE
(
  'BFDGE',
  ARRAY['Bisphenol F diglycidyl ether'],
  '2095-03-6',
  ARRAY['diglycidyl ether of bisphenol F'],
  'bisphenol',
  ARRAY['endocrine disruptor'],
  ARRAY['reproductive effects', 'sensitization'],
  'Epoxy resin from BPF, used in food can coatings',
  ARRAY['pregnant women', 'workers'],
  ARRAY['food can linings', 'epoxy resins', 'coatings'],
  ARRAY['ingestion', 'dermal'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY['food can linings', 'industrial coatings'],
  '{"food_contact_migration": "1 mg/kg"}',
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['BPF'],
  'Reaction of BPF with epichlorohydrin; hydrolyzes to BPF'
),

-- Heavy Metals

-- 18. Lead
(
  'Lead',
  ARRAY['Pb'],
  '7439-92-1',
  ARRAY['lead metal', 'plumbum'],
  'heavy_metal',
  ARRAY['neurotoxin', 'reproductive toxin', 'carcinogen'],
  ARRAY['neurodevelopmental damage', 'IQ reduction', 'behavioral problems', 'kidney damage', 'reproductive effects'],
  'Neurotoxin with no safe level, particularly harmful to children. Accumulates in bones.',
  ARRAY['children', 'pregnant women', 'workers'],
  ARRAY['old paint', 'cosmetics', 'jewelry', 'toys', 'ceramics', 'pipes'],
  ARRAY['ingestion', 'inhalation', 'dermal'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['paint', 'gasoline', 'children''s products >100 ppm', 'cosmetics >10 ppm'],
  ARRAY['batteries (controlled)', 'industrial applications'],
  '{"cosmetics_Canada": "10 ppm", "children_products_USA": "100 ppm", "drinking_water": "5 ppb (Canada)", "toys_EU": "0.05 mg/kg"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 19. Cadmium
(
  'Cadmium',
  ARRAY['Cd'],
  '7440-43-9',
  ARRAY['cadmium metal'],
  'heavy_metal',
  ARRAY['carcinogen', 'reproductive toxin', 'kidney toxin'],
  ARRAY['kidney damage', 'bone damage', 'lung cancer', 'prostate cancer'],
  'Accumulates in kidneys and liver, 10-30 year half-life in body. Group 1 carcinogen.',
  ARRAY['workers', 'smokers', 'children'],
  ARRAY['batteries', 'pigments', 'jewelry', 'plastics', 'electronics'],
  ARRAY['inhalation', 'ingestion'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['jewelry', 'children''s products >75 ppm'],
  ARRAY['batteries (controlled)', 'industrial pigments'],
  '{"children_products_USA": "75 ppm", "jewelry_EU": "0.01%", "toys_EU": "0.01%"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 20. Mercury
(
  'Mercury',
  ARRAY['Hg'],
  '7439-97-6',
  ARRAY['quicksilver', 'hydrargyrum'],
  'heavy_metal',
  ARRAY['neurotoxin', 'reproductive toxin'],
  ARRAY['neurodevelopmental damage', 'kidney damage', 'immune system effects'],
  'Neurotoxin, particularly harmful as methylmercury. Bioaccumulates in fish.',
  ARRAY['pregnant women', 'children', 'workers'],
  ARRAY['fish', 'dental amalgam', 'thermometers', 'batteries', 'cosmetics (skin lightening)'],
  ARRAY['ingestion', 'inhalation', 'dermal'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['cosmetics >1 mg/kg except eye area preservative', 'thermometers', 'batteries'],
  ARRAY['dental amalgam (controlled)', 'industrial applications'],
  '{"cosmetics": "1 mg/kg", "fish_consumption_advisory": "varies by species"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY['methylmercury'],
  NULL
),

-- 21. Arsenic
(
  'Arsenic',
  ARRAY['As'],
  '7440-38-2',
  ARRAY['arsenic metal'],
  'heavy_metal',
  ARRAY['carcinogen', 'neurotoxin'],
  ARRAY['skin cancer', 'lung cancer', 'bladder cancer', 'cardiovascular disease', 'diabetes'],
  'Group 1 carcinogen, causes skin, lung, and bladder cancer. Contaminates groundwater.',
  ARRAY['children', 'pregnant women'],
  ARRAY['contaminated water', 'rice', 'pressure-treated wood', 'pesticides (legacy)'],
  ARRAY['ingestion', 'inhalation', 'dermal'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['pesticides', 'pressure-treated wood (consumer)', 'children''s products'],
  ARRAY['industrial applications (controlled)'],
  '{"drinking_water_WHO": "10 ppb", "rice_infant_EU": "0.1 mg/kg"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 22. Chromium VI
(
  'Chromium VI',
  ARRAY['Hexavalent chromium', 'Cr(VI)'],
  '18540-29-9',
  ARRAY['chromate', 'dichromate', 'chromium(6+)'],
  'heavy_metal',
  ARRAY['carcinogen', 'allergen', 'respiratory toxin'],
  ARRAY['lung cancer', 'nasal cancer', 'allergic dermatitis', 'respiratory damage'],
  'Group 1 carcinogen, causes lung and nasal cancer. Strong allergen and skin sensitizer.',
  ARRAY['workers', 'children'],
  ARRAY['stainless steel', 'chrome plating', 'leather tanning', 'pigments', 'wood preservatives'],
  ARRAY['inhalation', 'dermal', 'ingestion'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['leather products in direct skin contact >3 ppm (EU)', 'toys'],
  ARRAY['industrial chrome plating (controlled)', 'pigments (limited)'],
  '{"leather_EU": "3 ppm", "drinking_water_USA": "0.1 mg/L"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 23. Nickel
(
  'Nickel',
  ARRAY['Ni'],
  '7440-02-0',
  ARRAY['nickel metal'],
  'heavy_metal',
  ARRAY['carcinogen', 'allergen'],
  ARRAY['allergic contact dermatitis', 'respiratory cancer', 'asthma'],
  'Most common metal allergen (15% of population). Group 2B carcinogen (nickel compounds).',
  ARRAY['workers'],
  ARRAY['jewelry', 'coins', 'zippers', 'eyeglasses', 'medical devices', 'stainless steel'],
  ARRAY['dermal', 'inhalation'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['jewelry >0.5 μg/cm²/week nickel release (EU)'],
  ARRAY['stainless steel', 'industrial alloys', 'batteries'],
  '{"jewelry_nickel_release_EU": "0.5 μg/cm²/week", "post_assemblies_EU": "0.2 μg/cm²/week"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- VOCs

-- 24. Formaldehyde
(
  'Formaldehyde',
  ARRAY['Methanal'],
  '50-00-0',
  ARRAY['methylene oxide', 'formalin (aqueous)', 'CH2O'],
  'voc',
  ARRAY['carcinogen', 'respiratory toxin', 'allergen'],
  ARRAY['nasopharyngeal cancer', 'leukemia', 'respiratory irritation', 'asthma', 'allergic sensitization'],
  'Group 1 carcinogen. EPA determined unreasonable risk. Emitted from wood products, released by preservatives.',
  ARRAY['workers', 'children', 'asthmatics'],
  ARRAY['pressed wood products', 'cosmetic preservatives', 'textiles', 'insulation', 'embalming'],
  ARRAY['inhalation', 'dermal'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['cosmetics as formaldehyde >0.2% (Canada)', 'cosmetics >0.05% (EU unless preservative)'],
  ARRAY['preservative in cosmetics <0.2%', 'pressed wood (emission limits)', 'industrial'],
  '{"cosmetics_Canada": "0.2%", "cosmetics_EU_preservative": "0.2%", "pressed_wood_emission_USA": "0.09 ppm (plywood)"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 25. Vinyl Chloride
(
  'Vinyl Chloride',
  ARRAY['Chloroethylene'],
  '75-01-4',
  ARRAY['chloroethene', 'VCM'],
  'voc',
  ARRAY['carcinogen'],
  ARRAY['liver cancer (angiosarcoma)', 'brain cancer', 'lung cancer', 'lymphoma'],
  'Group 1 carcinogen. No safe level of exposure. Causes rare liver angiosarcoma.',
  ARRAY['workers', 'residents near plants'],
  ARRAY['PVC plastic production', 'industrial emissions', 'contaminated groundwater'],
  ARRAY['inhalation', 'ingestion'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['consumer products', 'food contact (as residual monomer)'],
  ARRAY['industrial PVC production (controlled)'],
  '{"drinking_water_USA": "2 ppb", "occupational_USA": "1 ppm", "PVC_residual": "<1 ppm"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- Formaldehyde Releasers

-- 26. Quaternium-15
(
  'Quaternium-15',
  ARRAY['Dowicil 200'],
  '4080-31-3',
  ARRAY['1-(3-chloroallyl)-3,5,7-triaza-1-azoniaadamantane chloride'],
  'preservative',
  ARRAY['allergen', 'formaldehyde releaser'],
  ARRAY['allergic contact dermatitis', 'respiratory irritation', 'asthma'],
  'Releases formaldehyde continuously. Most common cosmetic allergen in North America.',
  ARRAY['workers', 'asthmatics', 'formaldehyde-sensitive'],
  ARRAY['shampoos', 'lotions', 'cosmetics', 'cleaning products'],
  ARRAY['dermal', 'inhalation'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['cosmetics >0.2% (Canada)', 'leave-on products >0.1% (EU)'],
  ARRAY['rinse-off cosmetics <0.2% (EU)'],
  '{"cosmetics_Canada": "0.2%", "leave_on_EU": "0.1%", "rinse_off_EU": "0.2%"}',
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['Formaldehyde'],
  'Decomposes in aqueous solution releasing formaldehyde continuously'
),

-- 27. DMDM Hydantoin
(
  'DMDM Hydantoin',
  ARRAY['1,3-dimethylol-5,5-dimethylhydantoin'],
  '6440-58-0',
  ARRAY['dimethylol dimethyl hydantoin', 'Glydant'],
  'preservative',
  ARRAY['allergen', 'formaldehyde releaser'],
  ARRAY['allergic contact dermatitis', 'respiratory irritation'],
  'Releases formaldehyde. Common preservative in personal care products.',
  ARRAY['workers', 'formaldehyde-sensitive'],
  ARRAY['shampoos', 'conditioners', 'lotions', 'cosmetics'],
  ARRAY['dermal', 'inhalation'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['cosmetics releasing >0.2% formaldehyde (Canada)'],
  ARRAY['cosmetics <0.6% (EU)'],
  '{"cosmetics_formaldehyde_release": "0.2%", "cosmetics_EU": "0.6%"}',
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['Formaldehyde'],
  'Hydrolyzes releasing formaldehyde'
),

-- 28. Bronopol
(
  'Bronopol',
  ARRAY['2-bromo-2-nitropropane-1,3-diol'],
  '52-51-7',
  ARRAY['2-bromo-2-nitro-1,3-propanediol', 'Lexgard'],
  'preservative',
  ARRAY['allergen', 'formaldehyde releaser'],
  ARRAY['allergic contact dermatitis', 'irritation'],
  'Releases formaldehyde, especially at elevated pH. Also releases nitrosamines.',
  ARRAY['workers'],
  ARRAY['cosmetics', 'shampoos', 'industrial water treatment'],
  ARRAY['dermal', 'inhalation'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['cosmetics with nitrosating agents'],
  ARRAY['cosmetics <0.1% (EU)'],
  '{"cosmetics_EU": "0.1%", "no_nitrosating_agents": "required"}',
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['Formaldehyde'],
  'Decomposes releasing formaldehyde, especially in alkaline conditions'
),

-- Surfactants

-- 29. Nonylphenol
(
  'Nonylphenol',
  ARRAY['NP', '4-nonylphenol'],
  '25154-52-3',
  ARRAY['para-nonylphenol', 'p-nonylphenol'],
  'surfactant',
  ARRAY['endocrine disruptor'],
  ARRAY['reproductive effects', 'estrogenic effects', 'developmental effects', 'aquatic toxicity'],
  'Potent endocrine disruptor with estrogenic activity. Highly toxic to aquatic life. Bioaccumulative.',
  ARRAY['aquatic organisms', 'workers'],
  ARRAY['detergents', 'industrial cleaners', 'pesticide formulations', 'textiles'],
  ARRAY['dermal', 'ingestion', 'environmental'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['cosmetics (EU)', 'detergents (EU)', 'textiles (restricted)'],
  ARRAY['industrial applications (time-limited)'],
  '{"cosmetics_EU": "banned", "detergents_EU": "banned", "textiles": "restricted"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 30. Triclosan
(
  'Triclosan',
  ARRAY['5-chloro-2-(2,4-dichlorophenoxy)phenol'],
  '3380-34-5',
  ARRAY['Irgasan', 'Microban'],
  'surfactant',
  ARRAY['endocrine disruptor', 'antimicrobial resistance'],
  ARRAY['endocrine disruption', 'thyroid effects', 'antimicrobial resistance', 'skin irritation'],
  'Antimicrobial banned in hand soaps 2016. Disrupts thyroid hormones, contributes to antibiotic resistance.',
  ARRAY['children', 'pregnant women'],
  ARRAY['toothpaste', 'deodorants', 'cosmetics', 'cleaning products', 'textiles'],
  ARRAY['dermal', 'ingestion'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['hand soaps (USA 2016)', 'hand sanitizers', 'cosmetics (EU)'],
  ARRAY['toothpaste <0.3% (USA, Canada)', 'deodorant <0.3%'],
  '{"hand_soap_USA": "banned 2016", "toothpaste": "0.3%", "cosmetics_EU": "0.3%"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- Additional Phthalate Metabolites

-- 31. MBP
(
  'MBP',
  ARRAY['Monobutyl phthalate'],
  '131-70-4',
  ARRAY['mono-n-butyl phthalate'],
  'phthalate',
  ARRAY['endocrine disruptor', 'reproductive toxin'],
  ARRAY['reproductive toxicity', 'anti-androgenic effects'],
  'Primary metabolite of DBP, biomarker of DBP exposure',
  ARRAY['pregnant women', 'children'],
  ARRAY['biomarker in urine from DBP exposure'],
  ARRAY['ingestion', 'dermal'],
  'not regulated directly',
  'not regulated directly',
  'not regulated directly',
  ARRAY[],
  ARRAY[],
  NULL,
  FALSE,
  TRUE,
  ARRAY['DBP'],
  ARRAY[],
  'Hydrolysis of DBP by intestinal lipases'
),

-- 32. MBzP
(
  'MBzP',
  ARRAY['Monobenzyl phthalate'],
  '2528-16-7',
  ARRAY['mono-benzyl phthalate'],
  'phthalate',
  ARRAY['endocrine disruptor', 'reproductive toxin'],
  ARRAY['reproductive toxicity'],
  'Primary metabolite of BBP, biomarker of BBP exposure',
  ARRAY['pregnant women', 'children'],
  ARRAY['biomarker in urine from BBP exposure'],
  ARRAY['ingestion', 'dermal'],
  'not regulated directly',
  'not regulated directly',
  'not regulated directly',
  ARRAY[],
  ARRAY[],
  NULL,
  FALSE,
  TRUE,
  ARRAY['BBP'],
  ARRAY[],
  'Hydrolysis of BBP'
),

-- 33. MEP
(
  'MEP',
  ARRAY['Monoethyl phthalate'],
  '2306-33-4',
  ARRAY['mono-ethyl phthalate'],
  'phthalate',
  ARRAY['endocrine disruptor'],
  ARRAY['developmental effects', 'reproductive effects'],
  'Primary metabolite of DEP, most abundant urinary phthalate metabolite',
  ARRAY['pregnant women'],
  ARRAY['biomarker in urine from DEP exposure'],
  ARRAY['dermal', 'inhalation'],
  'not regulated directly',
  'not regulated directly',
  'not regulated directly',
  ARRAY[],
  ARRAY[],
  NULL,
  FALSE,
  TRUE,
  ARRAY['DEP'],
  ARRAY[],
  'Hydrolysis of DEP by esterases'
),

-- 34. MiBP
(
  'MiBP',
  ARRAY['Mono-isobutyl phthalate'],
  '30833-53-5',
  ARRAY['mono-iso-butyl phthalate'],
  'phthalate',
  ARRAY['endocrine disruptor', 'reproductive toxin'],
  ARRAY['reproductive toxicity', 'anti-androgenic effects'],
  'Metabolite of DiBP (di-isobutyl phthalate), biomarker of exposure',
  ARRAY['pregnant women', 'children'],
  ARRAY['biomarker in urine from DiBP exposure'],
  ARRAY['ingestion', 'dermal'],
  'not regulated directly',
  'not regulated directly',
  'not regulated directly',
  ARRAY[],
  ARRAY[],
  NULL,
  FALSE,
  TRUE,
  ARRAY['DiBP'],
  ARRAY[],
  'Hydrolysis of DiBP'
),

-- 35. MINP
(
  'MINP',
  ARRAY['Mono-isononyl phthalate'],
  NULL,
  ARRAY['mono-iso-nonyl phthalate'],
  'phthalate',
  ARRAY['endocrine disruptor'],
  ARRAY['reproductive effects', 'liver toxicity'],
  'Metabolite of DINP, biomarker of DINP exposure',
  ARRAY['children'],
  ARRAY['biomarker in urine from DINP exposure'],
  ARRAY['ingestion', 'dermal'],
  'not regulated directly',
  'not regulated directly',
  'not regulated directly',
  ARRAY[],
  ARRAY[],
  NULL,
  FALSE,
  TRUE,
  ARRAY['DINP'],
  ARRAY[],
  'Hydrolysis of DINP'
),

-- BADGE Chlorohydrin Derivatives

-- 36. BADGE·HCl
(
  'BADGE·HCl',
  ARRAY['Bisphenol A diglycidyl ether monochlorohydrin'],
  '13836-48-1',
  ARRAY['BADGE chlorohydrin', 'BADGE·1HCl'],
  'bisphenol',
  ARRAY['endocrine disruptor'],
  ARRAY['reproductive effects', 'genotoxicity'],
  'Reaction product of BADGE with HCl, found in canned foods, genotoxic',
  ARRAY['pregnant women'],
  ARRAY['canned foods', 'food packaging'],
  ARRAY['ingestion'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY[],
  '{"food_contact_migration": "1 mg/kg"}',
  FALSE,
  TRUE,
  ARRAY['BADGE'],
  ARRAY[],
  'Reaction of BADGE with HCl during food processing/storage'
),

-- 37. BADGE·2HCl
(
  'BADGE·2HCl',
  ARRAY['Bisphenol A diglycidyl ether dichlorohydrin'],
  '4809-35-2',
  ARRAY['BADGE dichlorohydrin', 'BADGE·2HCl'],
  'bisphenol',
  ARRAY['endocrine disruptor', 'genotoxin'],
  ARRAY['reproductive effects', 'genotoxicity'],
  'Reaction product of BADGE with HCl, found in canned foods, genotoxic',
  ARRAY['pregnant women'],
  ARRAY['canned foods', 'food packaging'],
  ARRAY['ingestion'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY[],
  '{"food_contact_migration": "1 mg/kg"}',
  FALSE,
  TRUE,
  ARRAY['BADGE'],
  ARRAY[],
  'Reaction of both epoxy groups of BADGE with HCl'
),

-- BFDGE Derivatives

-- 38. BFDGE·H2O
(
  'BFDGE·H2O',
  ARRAY['Bisphenol F diglycidyl ether monohydrate'],
  NULL,
  ARRAY['BFDGE monohydrate', 'BFDGE·1H2O'],
  'bisphenol',
  ARRAY['endocrine disruptor'],
  ARRAY['reproductive effects'],
  'Hydrolysis product of BFDGE, found in canned foods',
  ARRAY['pregnant women'],
  ARRAY['canned foods', 'food packaging'],
  ARRAY['ingestion'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY[],
  '{"food_contact_migration": "1 mg/kg"}',
  FALSE,
  TRUE,
  ARRAY['BFDGE'],
  ARRAY['BFDGE·2H2O'],
  'Hydrolysis of one epoxy group of BFDGE'
),

-- 39. BFDGE·2H2O
(
  'BFDGE·2H2O',
  ARRAY['Bisphenol F diglycidyl ether dihydrate'],
  NULL,
  ARRAY['BFDGE dihydrate'],
  'bisphenol',
  ARRAY['endocrine disruptor'],
  ARRAY['reproductive effects'],
  'Hydrolysis product of BFDGE, found in canned foods',
  ARRAY['pregnant women'],
  ARRAY['canned foods', 'food packaging'],
  ARRAY['ingestion'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY[],
  '{"food_contact_migration": "1 mg/kg"}',
  FALSE,
  TRUE,
  ARRAY['BFDGE'],
  ARRAY['BPF'],
  'Complete hydrolysis of both epoxy groups of BFDGE'
),

-- Additional Formaldehyde Releasers

-- 40. Imidazolidinyl Urea
(
  'Imidazolidinyl Urea',
  ARRAY['Imidurea'],
  '39236-46-9',
  ARRAY['Germall 115', '1,3-bis(hydroxymethyl)-5,5-dimethylimidazolidine-2,4-dione'],
  'preservative',
  ARRAY['allergen', 'formaldehyde releaser'],
  ARRAY['allergic contact dermatitis', 'respiratory irritation'],
  'Releases formaldehyde, second most common cosmetic allergen after quaternium-15',
  ARRAY['workers', 'formaldehyde-sensitive'],
  ARRAY['cosmetics', 'lotions', 'shampoos'],
  ARRAY['dermal', 'inhalation'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['cosmetics releasing >0.2% formaldehyde (Canada)'],
  ARRAY['cosmetics <0.6% (EU)'],
  '{"cosmetics_formaldehyde_release": "0.2%", "cosmetics_EU": "0.6%"}',
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['Formaldehyde'],
  'Slow release of formaldehyde in aqueous solution'
),

-- 41. Diazolidinyl Urea
(
  'Diazolidinyl Urea',
  ARRAY['Germall II'],
  '78491-02-8',
  ARRAY['1,3-bis(hydroxymethyl)-5,5-dimethyl-2,4-imidazolidinedione'],
  'preservative',
  ARRAY['allergen', 'formaldehyde releaser'],
  ARRAY['allergic contact dermatitis', 'respiratory irritation'],
  'Releases formaldehyde, common preservative in cosmetics',
  ARRAY['workers', 'formaldehyde-sensitive'],
  ARRAY['cosmetics', 'shampoos', 'lotions'],
  ARRAY['dermal', 'inhalation'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['cosmetics releasing >0.2% formaldehyde (Canada)'],
  ARRAY['cosmetics <0.5% (EU)'],
  '{"cosmetics_formaldehyde_release": "0.2%", "cosmetics_EU": "0.5%"}',
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['Formaldehyde'],
  'Releases formaldehyde via hydrolysis'
),

-- 42. Sodium Hydroxymethylglycinate
(
  'Sodium Hydroxymethylglycinate',
  ARRAY['SHMG'],
  '70161-44-3',
  ARRAY['sodium hydroxymethyl glycinate', 'Suttocide A'],
  'preservative',
  ARRAY['allergen', 'formaldehyde releaser'],
  ARRAY['allergic contact dermatitis', 'formaldehyde release'],
  'Releases formaldehyde at elevated pH, used in cosmetics',
  ARRAY['workers', 'formaldehyde-sensitive'],
  ARRAY['cosmetics', 'wet wipes', 'personal care products'],
  ARRAY['dermal'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['cosmetics releasing >0.2% formaldehyde (Canada)'],
  ARRAY['cosmetics <0.5% (EU, not authorized as preservative)'],
  '{"cosmetics_formaldehyde_release": "0.2%", "cosmetics_EU": "not authorized"}',
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['Formaldehyde'],
  'Releases formaldehyde, especially at pH >6'
),

-- Paraben Metabolites

-- 43. p-Hydroxybenzoic acid
(
  'p-Hydroxybenzoic acid',
  ARRAY['PHBA', '4-hydroxybenzoic acid'],
  '99-96-7',
  ARRAY['para-hydroxybenzoic acid', 'PHB'],
  'preservative',
  ARRAY['endocrine disruptor'],
  ARRAY['estrogenic effects'],
  'Common metabolite of all parabens, biomarker of paraben exposure',
  ARRAY['pregnant women'],
  ARRAY['biomarker in urine from paraben exposure'],
  ARRAY['ingestion', 'dermal'],
  'not regulated directly',
  'not regulated directly',
  'not regulated directly',
  ARRAY[],
  ARRAY[],
  NULL,
  FALSE,
  TRUE,
  ARRAY['methylparaben', 'ethylparaben', 'propylparaben', 'butylparaben'],
  ARRAY['p-hydroxyhippuric acid'],
  'Hydrolysis of all parabens to PHBA'
),

-- 44. p-Hydroxyhippuric acid
(
  'p-Hydroxyhippuric acid',
  ARRAY['PHHA'],
  NULL,
  ARRAY['4-hydroxyhippuric acid'],
  'preservative',
  ARRAY['endocrine disruptor'],
  ARRAY['estrogenic effects'],
  'Secondary metabolite of parabens via PHBA conjugation',
  ARRAY['pregnant women'],
  ARRAY['biomarker in urine from paraben exposure'],
  ARRAY['ingestion', 'dermal'],
  'not regulated directly',
  'not regulated directly',
  'not regulated directly',
  ARRAY[],
  ARRAY[],
  NULL,
  FALSE,
  TRUE,
  ARRAY['p-Hydroxybenzoic acid'],
  ARRAY[],
  'Conjugation of PHBA with glycine'
),

-- Additional Surfactants

-- 45. Nonylphenol Ethoxylates
(
  'Nonylphenol Ethoxylates',
  ARRAY['NPEs', 'NPE'],
  NULL,
  ARRAY['nonylphenol polyethoxylate', 'NP ethoxylates'],
  'surfactant',
  ARRAY['endocrine disruptor'],
  ARRAY['estrogenic effects', 'reproductive toxicity', 'aquatic toxicity'],
  'Breaks down to nonylphenol (potent endocrine disruptor), banned in many regions',
  ARRAY['aquatic organisms', 'workers'],
  ARRAY['detergents', 'industrial cleaners', 'textiles', 'pesticide formulations'],
  ARRAY['dermal', 'environmental'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['detergents (EU)', 'textiles (EU)'],
  ARRAY['industrial applications (time-limited)'],
  '{"detergents_EU": "banned", "textiles_EU": "restricted"}',
  TRUE,
  FALSE,
  ARRAY[],
  ARRAY['Nonylphenol'],
  'Biodegradation of ethoxylate chain releases nonylphenol'
),

-- 46. Triclocarban
(
  'Triclocarban',
  ARRAY['TCC'],
  '101-20-2',
  ARRAY['3,4,4''-trichlorocarbanilide'],
  'surfactant',
  ARRAY['endocrine disruptor', 'antimicrobial resistance'],
  ARRAY['endocrine disruption', 'amplifies hormones', 'antimicrobial resistance'],
  'Antimicrobial banned in hand soaps 2016. Amplifies testosterone and estrogen effects.',
  ARRAY['children', 'pregnant women'],
  ARRAY['hand soaps (banned)', 'bar soaps', 'deodorants'],
  ARRAY['dermal'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['hand soaps (USA 2016)', 'body washes'],
  ARRAY['some bar soaps <0.1%'],
  '{"hand_soap_USA": "banned 2016", "body_wash_USA": "banned 2016"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- Additional Heavy Metals

-- 47. Cobalt Metal
(
  'Cobalt Metal',
  ARRAY['Co'],
  '7440-48-4',
  ARRAY['elemental cobalt'],
  'heavy_metal',
  ARRAY['carcinogen', 'allergen', 'respiratory toxin'],
  ARRAY['lung cancer', 'asthma', 'allergic contact dermatitis', 'cardiomyopathy'],
  'Group 2B carcinogen (cobalt metal with tungsten carbide). Common allergen, often co-sensitized with nickel.',
  ARRAY['workers', 'nickel-allergic individuals'],
  ARRAY['jewelry', 'metal alloys', 'cement', 'pigments', 'batteries'],
  ARRAY['inhalation', 'dermal'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['jewelry (restricted release)', 'toys'],
  ARRAY['industrial alloys', 'batteries (controlled)'],
  '{"jewelry_release": "under development", "toys": "restricted"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 48. Methylmercury
(
  'Methylmercury',
  ARRAY['MeHg', 'CH3Hg'],
  '22967-92-6',
  ARRAY['methyl mercury', 'monomethylmercury'],
  'heavy_metal',
  ARRAY['neurotoxin', 'reproductive toxin'],
  ARRAY['neurodevelopmental damage', 'cognitive impairment', 'motor dysfunction'],
  'Most toxic form of mercury, bioaccumulates in fish. Crosses placenta and blood-brain barrier.',
  ARRAY['pregnant women', 'children', 'fetuses'],
  ARRAY['fish (especially large predatory fish)', 'seafood'],
  ARRAY['ingestion'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY[],
  '{"fish_consumption_advisory": "varies by species and size", "pregnant_women": "avoid high-Hg fish"}',
  FALSE,
  TRUE,
  ARRAY['Mercury'],
  ARRAY[],
  'Methylation of inorganic mercury by bacteria in aquatic environments'
),

-- Additional VOC/Preservatives

-- 49. Benzyl Alcohol
(
  'Benzyl Alcohol',
  ARRAY['Phenylmethanol'],
  '100-51-6',
  ARRAY['benzenemethanol', 'phenylcarbinol'],
  'preservative',
  ARRAY['allergen', 'irritant'],
  ARRAY['allergic contact dermatitis', 'respiratory irritation', 'neurotoxicity (neonates)'],
  'Preservative and solvent, allergen in Balsam of Peru. Can cause gasping syndrome in neonates.',
  ARRAY['neonates', 'infants', 'workers'],
  ARRAY['cosmetics', 'pharmaceuticals', 'food flavorings', 'injectable medications'],
  ARRAY['dermal', 'inhalation', 'injection'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY['injectable medications for neonates >99 mg/kg/day'],
  ARRAY['cosmetics <1%', 'pharmaceuticals (controlled use)'],
  '{"cosmetics": "1%", "neonatal_injectable": "restricted to <99 mg/kg/day"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
),

-- 50. Phenoxyethanol
(
  'Phenoxyethanol',
  ARRAY['2-phenoxyethanol'],
  '122-99-6',
  ARRAY['ethylene glycol monophenyl ether', 'phenoxetol'],
  'preservative',
  ARRAY['allergen', 'irritant'],
  ARRAY['allergic contact dermatitis', 'respiratory irritation', 'neurotoxicity (infants)'],
  'Formaldehyde-free preservative alternative, but causes eczema and irritation. Neurotoxic at high doses.',
  ARRAY['infants', 'workers'],
  ARRAY['cosmetics', 'wet wipes', 'sunscreens', 'vaccines'],
  ARRAY['dermal', 'inhalation'],
  'restricted',
  'restricted',
  'restricted',
  ARRAY[],
  ARRAY['cosmetics <1% (EU, Canada)', 'vaccines (trace amounts)'],
  '{"cosmetics_EU": "1%", "cosmetics_Canada": "1%", "leave_on_infant_products": "caution advised"}',
  FALSE,
  FALSE,
  ARRAY[],
  ARRAY[],
  NULL
)

ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- PART 4: SEARCH FUNCTIONS
-- ============================================================================

-- Enhanced allergen search
CREATE OR REPLACE FUNCTION search_allergen(search_term TEXT)
RETURNS TABLE(allergen_id UUID, allergen_name TEXT, severity INTEGER, allergen_type TEXT) AS $$
BEGIN
  RETURN QUERY
  SELECT id, name, severity_default, allergen_type
  FROM allergens
  WHERE
    LOWER(name) = LOWER(search_term) OR
    LOWER(search_term) = ANY(SELECT LOWER(unnest(synonyms))) OR
    LOWER(search_term) = ANY(SELECT LOWER(unnest(alternative_names)));
END;
$$ LANGUAGE plpgsql;

-- Enhanced PFAS search
CREATE OR REPLACE FUNCTION search_pfas(search_term TEXT)
RETURNS TABLE(
  pfas_id UUID,
  pfas_name TEXT,
  cas TEXT,
  effects TEXT,
  regulatory_status TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT id, name, cas_number, body_effects, regulatory_status_canada
  FROM pfas_compounds
  WHERE
    LOWER(name) LIKE '%' || LOWER(search_term) || '%' OR
    cas_number = search_term OR
    LOWER(search_term) = ANY(SELECT LOWER(unnest(synonyms)));
END;
$$ LANGUAGE plpgsql;

-- New: Search toxic substances
CREATE OR REPLACE FUNCTION search_toxic_substance(search_term TEXT)
RETURNS TABLE(
  substance_id UUID,
  substance_name TEXT,
  cas TEXT,
  category TEXT,
  effects TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT id, name, cas_number, substance_category, body_effects
  FROM toxic_substances
  WHERE
    LOWER(name) LIKE '%' || LOWER(search_term) || '%' OR
    cas_number = search_term OR
    LOWER(search_term) = ANY(SELECT LOWER(unnest(synonyms))) OR
    LOWER(search_term) = ANY(SELECT LOWER(unnest(common_names)));
END;
$$ LANGUAGE plpgsql;

-- New: Find precursors for a substance
CREATE OR REPLACE FUNCTION find_precursors(substance_name TEXT)
RETURNS TABLE(
  precursor_name TEXT,
  transformation_pathway TEXT,
  source_table TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT name, transformation_pathway, 'pfas_compounds'::TEXT
  FROM pfas_compounds
  WHERE substance_name = ANY(metabolites) AND is_precursor = TRUE
  UNION
  SELECT name, transformation_pathway, 'toxic_substances'::TEXT
  FROM toxic_substances
  WHERE substance_name = ANY(metabolites) AND is_precursor = TRUE;
END;
$$ LANGUAGE plpgsql;

-- New: Find metabolites of a substance
CREATE OR REPLACE FUNCTION find_metabolites(substance_name TEXT)
RETURNS TABLE(
  metabolite_name TEXT,
  transformation_pathway TEXT,
  source_table TEXT
) AS $$
BEGIN
  RETURN QUERY
  SELECT name, transformation_pathway, 'pfas_compounds'::TEXT
  FROM pfas_compounds
  WHERE substance_name = ANY(parent_compounds) AND is_metabolite = TRUE
  UNION
  SELECT name, transformation_pathway, 'toxic_substances'::TEXT
  FROM toxic_substances
  WHERE substance_name = ANY(parent_compounds) AND is_metabolite = TRUE;
END;
$$ LANGUAGE plpgsql;

-- Comments
COMMENT ON FUNCTION search_allergen IS 'Search allergens by name, synonym, or alternative name';
COMMENT ON FUNCTION search_pfas IS 'Search PFAS compounds by name, CAS number, or synonym with regulatory status';
COMMENT ON FUNCTION search_toxic_substance IS 'Search non-PFAS toxic substances by name, CAS, or category';
COMMENT ON FUNCTION find_precursors IS 'Find all precursor compounds that transform into the specified substance';
COMMENT ON FUNCTION find_metabolites IS 'Find all metabolites/breakdown products of the specified substance';
