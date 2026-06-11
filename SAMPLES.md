# SAMPLES.md — live scraper outputs per retailer

Real product pages captured via chrome-devtools and run through the actual scraper (`process_client_html`). Each block is **what Claude receives** for analysis — links included so you can compare against the live page. Sections are capped for readability; `structured_data` is raw JSON-LD (Claude parses it).

_Generated 2026-06-03._

---

## Amazon

**Product:** [https://www.amazon.ca/Roche-Posay-Anthelios-Mineral-50mL/dp/B00OZNRV00/](https://www.amazon.ca/Roche-Posay-Anthelios-Mineral-50mL/dp/B00OZNRV00/)
**Scraper:** `AmazonScraper` · **raw DOM** 2374 KB → **extracted** 6.9 KB

```text
=== title ===
La Roche-Posay Mineral Sunscreen, Anthelios Tinted Mineral Face Ultra-Fluid SPF 50 Lotion & Mineral Body SPF 50 Lotion with UVA-UVB Sun Protection, Titanium Dioxide, Fragrance Free & Water Resistant

=== price ===
$39.95

=== availability ===
In Stock In Stock

=== product_attributes ===
Scent: Unscented
Product benefits: Ultra Fluid Mineral Tinted SPF 50 is a 100% mineral filter sunscreen with titanium dioxide. It is water resistant, fragrance-free, paraben-free, oil-free and non-comedogenic. It is suitable for all skin types, including sensitive skinUltra Fluid Mineral Tinted SPF 50 is a 100% mineral filter sunscreen with titanium dioxide. It is water resistant, fragrance-free, paraben-free, oil-free and non-comedogenic. It is suitable for all skin types, including sensitive skin
Sun Protection Factor: 50 Sun Protection Factor (SPF)
Item weight: 50 Grams
Number of Items: 1
Unit count: 50.0 Milliliters
Skin type: All, Combin  …(+142 chars)

=== aplus_content ===
From the manufacturer Previous page Next page 1 KEY INGREDIENTS 2 PRODUCT SAFETY 3 BENEFITS APPLICATION COMPLETE THE ROUTINE DISCOVER ANTHELIOS SUNCARE Mineral Tinted Face Ultra Invisible Face Age Correct Buying Options Mattifying Face Sunscreen Body Sunscreen Lotion Buying Options Customer Reviews 4.3 out of 5 stars 3,697 4.5 out of 5 stars 6,487 4.0 out of 5 stars 24 4.3 out of 5 stars 1,442 4.6 out of 5 stars 1,287 Price $39.95 $ 39 . 95 $35.95 $ 35 . 95 — $35.95 $ 35 . 95 — PRODUCT TYPE Face sunscreen, sun protection Face sunscreen, sun protection Face sunscreen, sun protection Face sunscreen, sun protection Sunscreen, sun protection PROT  …(+4925 chars)

=== detail_bullets ===
Product Dimensions ‏ : ‎ 13.97 x 5.21 x 30.99 cm; 50 g Date First Available ‏ : ‎ Oct. 29 2014 Manufacturer ‏ : ‎ L'Oréal Place of Business ‏ : ‎ New York, NY 10001 ASIN ‏ : ‎ B00OZNRV00 Country of origin ‏ : ‎ France Best Sellers Rank: #45 in Beauty & Personal Care ( See Top 100 in Beauty & Personal Care ) #1 in Facial Sunsceen Customer Reviews: 4.3 4.3 out of 5 stars (3,697)
```

---

## Sephora

**Product:** [https://www.sephora.com/ca/en/product/phantom-smoothing-blur-lip-balm-P524770](https://www.sephora.com/ca/en/product/phantom-smoothing-blur-lip-balm-P524770)
**Scraper:** `SephoraScraper` · **raw DOM** 1323 KB → **extracted** 11.4 KB

```text
=== structured_data ===
{"@type":"ItemList","@context":"http://schema.org","itemListElement":[{"url":"https://www.sephora.com/ca/en/shop/makeup-cosmetics","name":"Makeup","@type":"SiteNavigationElement","position":1,"description":"Shop the best makeup now at Sephora and earn points with every purchase! Not yet a Beauty Insider? Join now for FREE!"},{"url":"https://www.sephora.com/ca/en/shop/skincare","name":"Skincare","@type":"SiteNavigatio  …(+10030 chars)

=== title ===
Hourglass Phantom Smoothing Blur Lip Balm

=== ingredients ===
Ingredients -Conditioning Complex: A blend of emollients and oils that nourishes, smooths, and softens. -Smoothing Gel-Base and Hyaluronic Acid: Blurs the appearance of lips. -Emollient and Oil Blend: Nourishes the skin barrier for up to 12 hours. Dimethicone, Phenyl Trimethicone, Tridecyl Trimellitate, Dimethicone Crosspolymer, Synthetic Wax, Tribehenin, Polyglyceryl-2 Triisostearate, Diisostearyl Malate, Polyhydroxystearic Acid, Synthetic Fluorphlogopite, Polysilicone-11, Fragrance/Parfum, Caprylyl Glycol, 1,2-Hexanediol, Propanediol, Aluminum Hydroxide, Vanillin, Illicium Verum (Anise) Fruit Extract, Argania Spinosa Kernel Oil, Mangifera I  …(+464 chars)

=== product_details ===
About the Product
```

---

## IKEA

**Product:** [https://www.ikea.com/us/en/p/hemnes-8-drawer-dresser-white-stain-10576191/](https://www.ikea.com/us/en/p/hemnes-8-drawer-dresser-white-stain-10576191/)
**Scraper:** `IkeaScraper` · **raw DOM** 442 KB → **extracted** 27.8 KB

```text
=== structured_data ===
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Products","item":"https://www.ikea.com/us/en/cat/products-products/"},{"@type":"ListItem","position":2,"name":"Storage & organization","item":"https://www.ikea.com/us/en/cat/storage-organization-st001/"},{"@type":"ListItem","position":3,"name":"Dressers & storage drawers","item":"https://www.ikea.com/  …(+13134 chars)

=== title ===
HEMNES 8-drawer dresser, white stain, 63x37 3/4 "

=== product_details ===
Product details This chest of drawers has a drawer interlock, which means that only one drawer per column can be opened at a time. When combined with wall-anchoring, this solution helps reduce the risk of tip-over. Of course your home should be a safe place for the entire family. That’s why hardware is included so that you can attach the chest of drawers to the wall. Made of solid wood, which is a durable and warm natural material. A wide chest of drawers gives you plenty of storage space as well as room for lamps or other items you want to display on top. Smooth running drawers with pull-out stop. Use smaller boxes to organize the inside of  …(+4812 chars)

=== description ===
A classic chest of drawers in solid wood, with a traditional look and modern functions like quiet, smooth-running drawers. The drawer interlock reduce the tip-over risk when combined with wall-anchoring. Article Number 105.761.91 A classic chest of drawers in solid wood, with a traditional look and modern functions like quiet, smooth-running drawers. The drawer interlock reduce the tip-over risk when combined with wall-anchoring. A classic chest of drawers in solid wood, with a traditional look and modern functions like quiet, smooth-running drawers. The drawer interlock reduce the tip-over risk when combined with wall-anchoring. Article Numb  …(+13 chars)

=== questions_answers ===
Review: 4 out of 5 stars. Total reviews: 77 (77) | Q&A (180) Q&A (180)

=== reviews ===
Reviews Beautiful dresser but LOUD Anonymous reviewer Dresser was quick to assemble and looks beautiful. The downside is that the drawers are incredibly LOUD when closing. It routinely wakes up the sleeping person in the room when one of us gets up earlier than the other and needs clothes. There is no way to close the dresser drawers quietly due to the locking mechanism. 2 Nice dresser Jennifer Dresser was easy to put together, only a few minor issues. It looks great and is functional. The only issue is the drawers are very loud when opening and closing. Otherwise, a great dresser. 4 Longest lasting dresser Jen We bought this dresser for our  …(+6214 chars)

=== materials_breakdown ===
Main parts: Solid pine, Adhesive, Stain, Clear acrylic lacquer
Inner side panel: Particleboard
Plinth back/ Drawer sides/ Drawer back: Solid pine, Adhesive
Back: Fiberboard
Drawer bottom: Fiberboard, Acrylic paint

=== care ===
Wipe clean with a damp cloth.
Wipe dry with a clean cloth.
Disassembly & Recycling (For industry professionals)

=== safety_and_compliance ===
WARNING! Tipping hazard – this product must be securely anchored. Use suitable screws and plugs for your home. If you are uncertain, seek professional advice.

=== certifications ===
The drawer interlock in this chest of drawers means that only one drawer can be opened at a time.
The small drawer holds about 5 pairs of folded pants or 10 T-shirts.
The medium drawer holds about 10 pairs of folded pants or 20 T-shirts.
The big drawer holds about 15 pairs of folded pants or 30 T-shirts.
Coordinates with other products in the HEMNES series.
WARNING! Tipping hazard – this product must be securely anchored. Use suitable screws and plugs for your home. If you are uncertain, seek professional advice.

=== good_to_know ===
The drawer interlock in this chest of drawers means that only one drawer can be opened at a time.
The small drawer holds about 5 pairs of folded pants or 10 T-shirts.
The medium drawer holds about 10 pairs of folded pants or 20 T-shirts.
The big drawer holds about 15 pairs of folded pants or 30 T-shirts.
Coordinates with other products in the HEMNES series.
WARNING! Tipping hazard – this product must be securely anchored. Use suitable screws and plugs for your home. If you are uncertain, seek professional advice.
```

---

## Garage

**Product:** [https://www.garageclothing.com/us/p/low-rise-baggy-jeans/10010171607H.html](https://www.garageclothing.com/us/p/low-rise-baggy-jeans/10010171607H.html)
**Scraper:** `GarageScraper` · **raw DOM** 858 KB → **extracted** 3.9 KB

```text
=== structured_data ===
{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"Clothing","item":"/us/g/clothing/"},{"@type":"ListItem","position":2,"name":"Denim","item":"/us/g/clothing/denim/"},{"@type":"ListItem","position":3,"name":"Jeans","item":"/us/g/clothing/denim/jeans/"}]} {"@context":"http://schema.org/","@type":"Product","@id":"https://www.garageclothing.com/us/p/low-  …(+1308 chars)

=== title ===
Low Rise Baggy Jeans DENIM

=== product_details ===
Clothing > Denim > Jeans EXTENDED LENGTH ( 2 ) 86 Low Rise Baggy Jeans $74.95 Lina Blue Amber Blue Brenna Blue Bright White Carden Blue Icy Grey Lina Blue Tori Blue Washed Black Length Short Regular Long Size 00 0 1 3 5 7 9 11 13 15 Size Chart Add to Bag Wishlist Product Details These baggy-fit jeans sit low on the hips and come with a bigger, full-length leg that bunches at the bottom. Perfect for your biggest sweater or your tiniest shirt. Low rise and loving it. Features Five-pocket styling Zip-fly with tonal button closure Size & Fit Fit: Relaxed Rise: 11." Inseam: 32" Model is wearing size 3 Materials & Care Content: 85% cotton, 15% recy  …(+1571 chars)
```

---

## Uniqlo

**Product:** [https://www.uniqlo.com/us/en/products/E422992-000/00](https://www.uniqlo.com/us/en/products/E422992-000/00)
**Scraper:** `UniqloScraper` · **raw DOM** 1301 KB → **extracted** 16.6 KB

```text
=== structured_data ===
{"@context":"https://schema.org/","@graph":[{"@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,"name":"MEN","item":"https://www.uniqlo.com/us/en/men"},{"@type":"ListItem","position":2,"name":"T-Shirts & Sweats","item":"https://www.uniqlo.com/us/en/men/tops"},{"@type":"ListItem","position":3,"name":"T-Shirts","item":"https://www.uniqlo.com/us/en/men/tops/t-shirts"},{"@type":"ListItem","posit  …(+5582 chars)

=== title ===
Crew Neck T-Shirt

=== product_details ===
Crew Neck T-Shirt Bestseller Color: 32 BEIGE Size: MEN S XXS XS S M L XL XXL 3XL Size Guide Get help with finding your size. Get help with finding your size. $24.90 4.6 (999+) UNISEX, New color 1 Add to cart In stock Add to wish list SHIPS FREE: $99+ orders and in-store pickups Store availability You can check store stock status here. Select a store Check additional stores No store results match your current search criteria. Find in store Description Product ID: 485563 Features A heavyweight cotton jersey fabric with a smooth texture and rugged look. Durable fabric built to last. Binding at the collar helps the neckline keep its shape. Neckli  …(+10257 chars)
```

---

## Instacart

**Product:** [https://www.instacart.com/products/80314-greek-gods-honey-vanilla-greek-style-yogurt-24-oz?retailerSlug=safeway](https://www.instacart.com/products/80314-greek-gods-honey-vanilla-greek-style-yogurt-24-oz?retailerSlug=safeway)
**Scraper:** `InstacartScraper` · **raw DOM** 752 KB → **extracted** 1.2 KB

```text
=== structured_data ===
{"@context":"https://schema.org","@graph":[{"@type":"Product","name":"Greek Gods Greek Style Honey Vanilla Yogurt","image":["https://d2lnr5mha7bycj.cloudfront.net/product-image/file/large_707e2bcf-ea1c-48b0-898d-9f3012ffd77c.png"],"category":"Greek &amp; Icelandic Yogurt","description":"The Greek Gods Greek Style Honey Vanilla Yogurt 24 oz","brand":{"@type":"Brand","name":"Greek Gods"},"size":"24 oz","offers":{"@type  …(+264 chars)

=== title ===
Greek Gods Greek Style Honey Vanilla Yogurt

=== nutrition_facts ===
% Daily Value* Total Fat 7g 9% daily value Saturated Fat 4g 20% daily value Trans Fat 0g Total Fat Polyunsaturated Fat 0g Total Fat Monounsaturated Fat 0g Cholesterol 25mg 8% daily value Sodium 110mg 5% daily value Total Carbohydrate 25g 9% daily value Total Carbohydrate Dietary Fiber 0g 0% daily value Total Carbohydrate Total Sugars 23g Total Sugars Includes 15g Added Sugars 30% daily value Protein 7g
```

---

## Not capturable via automation (runtime-only)

These bot-wall or login-gate the automated browser, so no live sample here. They run at runtime via the user's real session (INV-1); see `AUDIT.md` for status.

- **Walmart** — `https://www.walmart.com/ip/…`
- **H&M** — `https://www2.hm.com/.../productpage.<id>.html`
- **Costco** — `https://www.costco.com/….product.<id>.html`
- **SHEIN** — `https://us.shein.com/…-p-<id>.html`
- **Temu** — `https://www.temu.com/…-g-<id>.html`
- **Aritzia** — `https://www.aritzia.com/…/product/…/<id>.html (Cloudflare)`
