# ruh Brand Guide

## Brand Overview
**ruh** is a Chrome extension that protects users from harmful chemicals in everyday products. It detects PFAS and allergens, explains their effects, provides harm scores, and suggests safer alternatives.

**Target Audience:** Women aged 20-40, wellness-conscious, non-technical  
**Brand Essence:** Soul protection through informed choices  
**Tone:** Gentle, trustworthy, empowering, warm

---

## Color Palette

### Primary Colors
- **Apricot Cream** `#FFD7C4` - Main brand color, warm and inviting
- **Soft Terracotta** `#E8B4A0` - Secondary, grounding and earthy
- **Warm Sage** `#C8D5B9` - Accent, natural and calming

### Supporting Colors
- **Powder Peach** `#FFDFD3` - Light backgrounds, soft alerts
- **Dusty Rose** `#E5C3C6` - Medium emphasis, gentle warnings
- **Cream** `#FFF8F0` - Canvas/background color
- **Warm Gray** `#9D9D9C` - Text, subtle elements

### Semantic Colors
- **Safe Green** `#B8D4C6` - Products with low harm scores
- **Caution Peach** `#FFB8A0` - Medium harm scores
- **Alert Coral** `#E89B8C` - High harm scores (still warm, not alarming red)

### Usage Guidelines
- Use Apricot Cream as the primary brand color for logo, buttons, and key UI elements
- Cream serves as the main background for extension interface
- Warm Sage for secondary actions and success states
- Keep contrast ratios accessible (minimum 4.5:1 for body text)

---

## Typography

### Logo Font
**Primary: Cormorant (Google Font)**
- Weight: Medium (500) or Semi Bold (600)
- Style: Elegant serif with personality, slightly condensed, stylistic terminals
- Alternative: Spectral Medium (more contemporary feel) or Fraunces (variable font with character)
- Logo treatment: "ruh" in lowercase, generous letter spacing (+75 to +100 tracking)

**Why this works:** Cormorant is a display serif with beautiful, distinctive letterforms that feel elegant and intentional. The slightly condensed proportions and stylistic details give it personality while remaining readable. It has that sophisticated warmth perfect for a wellness brand without feeling corporate or generic.

### Heading Fonts
**Primary: Inter**
- Weights: Semi Bold (600) for H1/H2, Medium (500) for H3/H4
- Style: Clean, modern, highly legible
- Usage: Extension headings, product names, harm scores

**Secondary: DM Sans**
- Weights: Medium (500) for larger headings
- Style: Geometric, friendly, contemporary
- Usage: Alternative for web presence, marketing materials

### Body Text Font
**Primary: Inter**
- Weights: Regular (400) for body, Medium (500) for emphasis
- Line height: 1.6 for readability
- Usage: Product descriptions, chemical explanations, ingredient lists

**Secondary: Source Sans Pro**
- Weight: Regular (400)
- Style: Clean, neutral, highly legible at small sizes
- Usage: Labels, metadata, fine print

### Font Pairing Rules
- Use Inter for both headings and body for maximum consistency in the extension
- Keep font sizes between 14-16px for body text (accessibility)
- Use font weight variations rather than different fonts for hierarchy
- Maintain generous spacing (1.5-2em between sections)

---

## Logo Design

### Primary Logo
```
ruh
```
- Font: Cormorant Medium (500) or Semi Bold (600)
- All lowercase
- Color: Apricot Cream (#FFD7C4) on dark backgrounds
- Color: Soft Terracotta (#E8B4A0) on light backgrounds
- Letter spacing: +75 to +100 tracking

### Logo Icon (Browser Extension)
**Concept:** Minimalist shield with organic curves

Visual description:
- Rounded shield shape (soft, not angular)
- Single color: Apricot Cream
- Could incorporate a subtle leaf or droplet motif inside
- 16x16px, 32x32px, 48x48px versions needed
- Should work in monochrome for toolbar states

### Logo Variations
1. **Full wordmark:** "ruh" (primary use)
2. **Icon only:** Shield icon (browser toolbar)
3. **Icon + wordmark:** For splash screens, onboarding
4. **Monochrome:** For print, limited color contexts

### Clear Space
Maintain clear space around logo equal to the height of lowercase "r" on all sides.

---

## Visual Style

### Design Principles
1. **Soft over sharp:** Rounded corners (8-12px border radius), gentle shadows
2. **Space over clutter:** Generous white space, breathing room between elements
3. **Warmth over clinical:** Warm tones, friendly language, approachable data visualization
4. **Clarity over complexity:** Simple layouts, clear hierarchy, scannable information

### UI Elements
- **Buttons:** Rounded (8px), Apricot Cream fill, Warm Gray text, subtle hover states
- **Cards:** Light backgrounds (Cream), soft shadows (0 2px 8px rgba(0,0,0,0.08))
- **Input fields:** Minimal borders, Warm Gray outlines, focus state in Apricot Cream
- **Harm score:** Circular progress indicator, color-coded (Safe Green to Alert Coral)
- **Icons:** Line-style, 2px stroke weight, rounded caps

---

## Component Design Principles

### Buttons
**Philosophy:** Inviting, not demanding. Every button should feel like a gentle suggestion rather than a command.

**Primary Buttons (CTAs):**
- Filled with Apricot Cream background
- Text in deep Warm Gray or white (test for contrast)
- 12px padding vertical, 24px horizontal (generous breathing room)
- 8px border radius (soft corners, never sharp)
- Hover state: Slightly deeper Soft Terracotta, subtle lift with shadow
- Active state: Very slight scale down (0.98), feels responsive
- Font: Inter Medium, 15-16px size
- Never use ALL CAPS (lowercase or sentence case only)

**Secondary Buttons:**
- Outlined style with 2px Soft Terracotta border
- Transparent or Cream background
- Same padding and radius as primary
- Hover: Fill with Powder Peach, border stays
- Text matches border color

**Tertiary/Ghost Buttons:**
- No border, no background
- Text in Soft Terracotta or Warm Sage
- Underline on hover (1px, subtle)
- Use for "Learn more" or dismissible actions

### Cards & Containers
**Philosophy:** Create sanctuary spaces. Each card is a safe zone for information.

**Product Cards:**
- Background: Cream with very soft shadow (never harsh drop shadows)
- Border: Optional 1px in Powder Peach (only if needed for definition)
- Padding: 20-24px (never cramped)
- Border radius: 12px (more rounded than buttons for hierarchy)
- Space between cards: 16px minimum
- Hover state: Lift slightly with enhanced shadow, no color change
- Never stack information densely. One idea per visual section.

**Information Cards:**
- Similar to product cards but can use color-coded left borders
- Safe products: 3px left border in Safe Green
- Caution products: 3px left border in Caution Peach
- Alert products: 3px left border in Alert Coral
- Keep content inside card spacious and scannable

**Chemical Detail Cards:**
- Nested inside main product cards (card within card)
- Slightly darker background (Powder Peach) for visual hierarchy
- 8px border radius (smaller than parent)
- Include small icon (molecule, warning, info) in Warm Sage
- Expandable/collapsible with smooth animation (200-300ms ease)

### Input Fields & Forms
**Philosophy:** Welcoming and clear. Never intimidating.

**Text Inputs:**
- Height: 44px minimum (thumb-friendly)
- Padding: 12px horizontal
- Background: White or very light Cream
- Border: 1.5px solid Warm Gray (subtle, not harsh)
- Border radius: 6px (slightly less rounded than buttons)
- Focus state: Border becomes Apricot Cream, add soft glow shadow in same color
- Placeholder text: Warm Gray at 70% opacity
- Error state: Border becomes Alert Coral, never shake animation (too aggressive)
- Success state: Border becomes Safe Green with checkmark icon inside

**Search Bars:**
- Same as text inputs but with search icon inside (left side)
- Icon in Warm Gray, 20px size
- Clear button appears on right when text entered (small X in circle)
- Wider than regular inputs (full width or 60% of container)

**Dropdowns/Selects:**
- Match text input styling exactly
- Chevron icon (down arrow) on right, 16px, Warm Gray
- Dropdown menu: Card styling with Cream background
- Options have 12px padding, hover with Powder Peach background
- Selected option shows checkmark in Warm Sage

### Progress Indicators & Scores
**Philosophy:** Visual feedback should inform without alarming. Even bad scores are presented with care.

**Harm Score Circle:**
- Large (120-140px diameter for main score)
- Circular progress ring, 8-10px thickness
- Background ring: Light gray at 20% opacity
- Progress ring: Color-coded gradient
  - 0-30: Safe Green
  - 31-60: Warm Sage to Caution Peach gradient
  - 61-80: Caution Peach to Alert Coral gradient
  - 81-100: Alert Coral (but never harsh red)
- Number in center: Large (32-36px), Inter Semi Bold
- Label underneath: Small (12px), Inter Regular, "Harm Score"
- Smooth animation on load (1 second ease-out)

**Loading States:**
- Soft pulsing animation (never harsh spinning)
- Skeleton screens in Powder Peach (not gray)
- Shimmer effect that moves slowly (2-3 seconds per cycle)
- Text: "Finding safer options..." not "Loading..."

**Progress Bars (Linear):**
- Height: 8px
- Border radius: 4px (fully rounded ends)
- Background: Powder Peach
- Progress fill: Apricot Cream
- Smooth animation, never jumpy

### Alerts & Notifications
**Philosophy:** Inform with empathy. Never panic the user.

**Toast Notifications:**
- Slide in from top-right
- Width: 320-360px
- Padding: 16px
- Border radius: 10px
- Auto-dismiss after 4-5 seconds (or manual close)
- Close icon: Small X in top-right corner

**Success Toast:**
- Background: Safe Green at 90% opacity
- Text: Deep gray (for contrast)
- Icon: Checkmark circle, same green but solid
- Message: "Saved" or "Found 3 cleaner alternatives"

**Warning Toast:**
- Background: Caution Peach at 90% opacity
- Text: Deep gray
- Icon: Info circle in Soft Terracotta
- Message: "This product contains 2 allergens you've flagged"

**Error Toast:**
- Background: Alert Coral at 90% opacity (not bright red)
- Text: Deep gray or white (test contrast)
- Icon: Gentle exclamation circle
- Message: Never blame user. "We couldn't load that product. Try again?"

**Inline Alerts:**
- Appear within the flow of content (not overlays)
- Bordered card style with colored left border (4px)
- Same color coding as toasts
- Include dismiss option if appropriate

### Lists & Tables
**Philosophy:** Breathe. Information density must serve clarity, not overwhelm.

**Ingredient Lists:**
- Each item: 48-52px height minimum
- 16px padding vertical, 20px horizontal
- Subtle divider lines (1px Powder Peach, not harsh gray)
- Hover state: Very light Powder Peach background
- Expandable items show chevron icon on right
- When expanded, nested content indents 20px with slightly darker background

**Alternative Product Lists:**
- Card-based layout, not table
- Each alternative: Own card with product image, name, score
- 3 alternatives shown, "See more" button for additional
- Score badge in top-right corner of card (small circular indicator)
- Product image: 80x80px, rounded 8px
- Name: Inter Medium, 16px
- Price: Below name, smaller (14px), Warm Gray

**Chemical Comparison Tables:**
- Only use tables when comparing multiple products side-by-side
- Header row: Powder Peach background, Inter Semi Bold
- Cell padding: 12px vertical, 16px horizontal
- Zebra striping: Alternating Cream and White rows
- Border radius on outer corners of entire table (12px)
- Never use internal vertical lines (columns separated by spacing only)

### Icons & Illustrations
**Philosophy:** Friendly, not technical. Approachable, not childish.

**Icon Style:**
- Line icons only (no filled solid icons except for active states)
- 2px stroke weight consistently
- Rounded line caps and joins (never sharp)
- 24x24px default size (scale proportionally)
- Color: Warm Gray for inactive, Apricot Cream or Warm Sage for active
- Never use stark black icons

**Icon Usage:**
- Chemical molecule: Abstract 3-circle connection (not literal benzene ring)
- Shield: Rounded shield shape, gentle curves
- Check: Rounded checkmark, friendly angle
- Warning: Circle with exclamation, not triangle
- Info: Lowercase 'i' in circle
- Alternatives: Horizontal arrows or shuffle symbol
- Heart: For favorites/saved items

**Illustrations (if used):**
- Line-art style matching icon stroke weight
- Limited color palette (2-3 colors from brand palette)
- Abstract and friendly (avoid clinical/medical imagery)
- Use for empty states, onboarding, or feature explanations
- Never use stock illustration styles that feel corporate

### Spacing & Layout
**Philosophy:** White space is active design, not empty space. Respect the breath between elements.

**Spacing Scale:**
- Use 4px base unit system
- Extra small: 4px (tight groupings)
- Small: 8px (related items)
- Medium: 16px (section spacing)
- Large: 24px (major sections)
- Extra large: 32px+ (page sections)

**Layout Grid:**
- 12-column grid for desktop
- 16px gutters between columns
- 24px margins on outer edges
- Single column for mobile (full width minus 16px margins)
- Never center-align body text (left-align for readability)
- Headings can be left or center aligned depending on context

**Content Width:**
- Maximum content width: 720px for reading comfort
- Extension popup: 380px fixed width
- Modals: 480-560px depending on content
- Never stretch content edge-to-edge on wide screens

### Typography Hierarchy (Applied)
**Philosophy:** Guide the eye naturally. Hierarchy through size, weight, and spacing, not color.

**H1 (Page Titles):**
- Inter Semi Bold, 28-32px
- Letter spacing: -0.5px (tighter for large text)
- Line height: 1.2
- Margin bottom: 24px
- Color: Deep gray/black, never pure black (#2D2D2D)

**H2 (Section Headings):**
- Inter Semi Bold, 22-24px
- Letter spacing: -0.25px
- Line height: 1.3
- Margin bottom: 16px
- Can use Soft Terracotta for emphasis in some contexts

**H3 (Subsections):**
- Inter Medium, 18-20px
- Letter spacing: 0
- Line height: 1.4
- Margin bottom: 12px

**Body Text:**
- Inter Regular, 15-16px
- Letter spacing: 0
- Line height: 1.6 (generous for readability)
- Color: Warm Gray (#2D2D2D)
- Paragraph spacing: 16px between paragraphs

**Small Text (Labels, Captions):**
- Inter Regular, 13-14px
- Line height: 1.5
- Color: Warm Gray at 80% opacity
- Use sparingly (most text should be body size)

**Links:**
- Same size as surrounding text
- Color: Soft Terracotta
- Underline on hover only
- Never open links in new tabs without warning

### Microinteractions
**Philosophy:** Delight in the details. Every interaction should feel responsive and thoughtful.

**Hover States:**
- Timing: 150-200ms transition
- Easing: ease-in-out (smooth both ways)
- Changes: Subtle color shifts, slight elevation, underlines
- Never change size dramatically (max 1.02 scale)

**Click/Tap Feedback:**
- Brief scale down (0.98) on active state
- 100ms duration
- Returns to normal immediately on release
- Helps user feel in control

**Expand/Collapse:**
- Smooth height animation: 300ms ease-out
- Chevron rotates 180° at same timing
- Content fades in slightly (opacity 0 to 1 over 200ms)
- Never instant (jarring)

**Loading Animations:**
- Gentle pulsing or slow shimmer
- 2-3 second cycles (not frantic)
- If longer than 3 seconds, show progress indicator
- Replace with content smoothly (fade transition)

**Success Feedback:**
- Brief color change (to Safe Green tint)
- Small checkmark animation or icon scale
- Revert to normal after 1 second
- Optional haptic feedback on mobile

### Accessibility Reminders
**Must-haves for all components:**
- Minimum 4.5:1 contrast ratio for text
- 3:1 for UI components and graphics
- Focus states visible for keyboard navigation (Apricot Cream outline, 2px)
- Touch targets minimum 44x44px
- Alt text for all images and icons
- Labels for all form inputs
- Avoid color as only means of conveying information
- Test with screen readers regularly

---

## Component Combinations

### Example: Product Detection Card
When you combine multiple components, maintain hierarchy and breathing room:

1. **Card Container** (Cream background, 12px radius, soft shadow)
2. **Product Header** (Name in H2, brand in small text)
3. **Harm Score Circle** (Centered, prominent)
4. **Chemical List** (Expandable items below score)
5. **Alternative Products** (Smaller cards within main card, or separate section)
6. **Action Buttons** (Bottom of card, properly spaced)

Each section separated by 20-24px vertical spacing. Never cramped.

### Example: Onboarding Flow
1. **Welcome Screen** (Large logo at top, friendly intro text, single primary CTA)
2. **Permission Request** (Clear explanation, two buttons: primary "Allow" and ghost "Skip")
3. **Feature Highlights** (Cards with icons, concise copy, dots indicator for progress)
4. **Setup Complete** (Success message with checkmark, CTA to start using)

Maintain consistent padding throughout (32px on all sides). Each screen stands alone but flows naturally into next.

---

### Photography/Imagery Style
- Natural lighting, warm tones
- Lifestyle shots over clinical product photos
- Authentic, unposed moments
- Inclusive representation of target demographic
- Soft focus, shallow depth of field when appropriate

---

## Voice & Tone

### Brand Voice
- **Caring:** Like a knowledgeable friend looking out for you
- **Clear:** No jargon, plain language explanations
- **Empowering:** You're in control of your choices
- **Honest:** Direct about risks without fear-mongering

### Tone Examples

**Good:**
"This product contains PFAS, which can accumulate in your body over time. Here are three cleaner alternatives we found."

**Avoid:**
"DANGER: Toxic chemicals detected! This product will harm you!"

**Good:**
"We found 3 allergens in this moisturizer. Tap to learn what they do."

**Avoid:**
"WARNING: Multiple allergen detection. Chemical analysis complete."

---

## Extension UI Mockup Guidelines

### Popup Interface
1. **Header:** "ruh" logo, settings icon
2. **Product Detection:** Auto-detect current product being viewed
3. **Harm Score:** Large circular indicator (0-100)
4. **Chemical List:** Expandable accordion with explanations
5. **Alternatives:** 3-5 suggested products with better scores
6. **Footer:** Quick links to settings, feedback

### Information Hierarchy
1. Harm score (most prominent)
2. Product name
3. Detected chemicals count
4. Individual chemical details (expandable)
5. Suggested alternatives

### Color Usage in UI
- Green zone (0-30): Safe, mostly clean products
- Yellow zone (31-60): Some concerns, moderate chemicals
- Orange zone (61-80): Notable concerns, consider alternatives
- Red zone (81-100): High concern, strongly suggest alternatives

---

## Brand Applications

### Chrome Web Store Listing
- **Icon:** 128x128px ruh shield icon in Apricot Cream
- **Screenshots:** Light Cream backgrounds, warm interface examples
- **Banner:** Apricot Cream gradient with "ruh" wordmark

### Website
- **Hero section:** Cream background, Apricot Cream CTAs
- **Features:** Card-based layout with Powder Peach accents
- **Footer:** Warm Sage with white text

### Social Media
- **Profile image:** Shield icon on Apricot Cream background
- **Cover images:** Warm pastel gradients
- **Post templates:** Cream backgrounds with Apricot Cream accents

---

## Technical Specifications

### CSS Variables
```css
:root {
  /* Primary Colors */
  --color-primary: #FFD7C4;
  --color-secondary: #E8B4A0;
  --color-accent: #C8D5B9;
  
  /* Backgrounds */
  --color-bg-primary: #FFF8F0;
  --color-bg-secondary: #FFDFD3;
  
  /* Semantic */
  --color-safe: #B8D4C6;
  --color-caution: #FFB8A0;
  --color-alert: #E89B8C;
  
  /* Neutrals */
  --color-text: #2D2D2D;
  --color-text-light: #9D9D9C;
  
  /* Typography */
  --font-logo: 'Cormorant', serif;
  --font-primary: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-heading: 'Inter', sans-serif;
  
  /* Spacing */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;
  
  /* Border Radius */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-full: 9999px;
}
```

### Font Loading
```html
<!-- Google Fonts -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant:wght@500;600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
```

---

## Design Checklist

Before launching any ruh branded material:

- [ ] Colors match the approved palette
- [ ] Fonts are Inter (or approved alternatives)
- [ ] Logo has proper clear space
- [ ] Tone is warm and empowering (not fear-based)
- [ ] UI elements have rounded corners
- [ ] Contrast ratios meet WCAG AA standards
- [ ] Mobile/extension responsive design tested
- [ ] Brand feels cohesive with existing materials

---

## Contact & Resources

**Brand Assets Location:** [Add your Figma/Drive link]  
**Questions:** [Your email]  
**Last Updated:** November 2025

---

*Remember: ruh protects the soul. Every design decision should reflect care, clarity, and empowerment.*
