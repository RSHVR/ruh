# Eject - Product Safety Intelligence Chrome Extension

## Project Vision

Eject is a Chrome extension that empowers consumers to make safer purchasing decisions by providing real-time, AI-powered analysis of products for harmful substances including allergens and PFAS (forever chemicals). When users browse products online, Eject automatically analyzes the product, scores its safety level, and recommends safer alternatives - monetized through affiliate links.

## Core Value Proposition

1. **Immediate Safety Intelligence**: AI agent analyzes products in real-time as users shop
2. **Clear Harm Scoring**: Simple visual indicators show how harmful a product is
3. **Actionable Alternatives**: Curated recommendations for safer products with lower/no risk
4. **Transparent Monetization**: Free for users, monetized through affiliate links on alternatives
5. **Evidence-Based**: AI provides sources and reasoning for safety assessments

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│              Chrome Extension (Frontend)             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │  Content    │  │    Popup     │  │ Background │ │
│  │   Script    │  │      UI      │  │  Service   │ │
│  │  (Detector) │  │  (Results)   │  │  Worker    │ │
│  └─────────────┘  └──────────────┘  └────────────┘ │
└─────────────────────────────────────────────────────┘
                          │
                          ▼ (API calls)
┌─────────────────────────────────────────────────────┐
│          Claude Agent Backend (Node.js)              │
│  ┌──────────────────────────────────────────────┐  │
│  │         Agent SDK Core                       │  │
│  │  • WebFetch (scrape product pages)           │  │
│  │  • WebSearch (find alternatives)             │  │
│  │  • Harm Analysis (allergens + PFAS)          │  │
│  │  • Alternative Ranking                       │  │
│  │  • Affiliate Link Injection                  │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
                          │
                          ▼ (Stores results)
┌─────────────────────────────────────────────────────┐
│              Database (SQLite/PostgreSQL)            │
│  • Product analysis cache                           │
│  • User preferences (allergen profiles)             │
│  • Affiliate tracking                               │
└─────────────────────────────────────────────────────┘
```

## Technology Stack

### Chrome Extension (Frontend)
- **Manifest Version**: V3 (latest Chrome standard)
- **UI Framework**: React with TypeScript (for popup and options page)
- **Styling**: Tailwind CSS (utility-first, fast development)
- **Build Tool**: Vite (fast builds, HMR for development)
- **State Management**: Zustand (lightweight, simple)
- **Icons**: Lucide React (consistent, modern icons)

### Backend Agent (Node.js)
- **Runtime**: Node.js 20+ with TypeScript
- **Agent Framework**: Claude Agent SDK (@anthropic-ai/sdk)
- **Web Scraping**: Playwright (for dynamic content) + Cheerio (for parsing)
- **API Framework**: Express.js (REST API for extension)
- **Database**: PostgreSQL (production) / SQLite (development)
- **Caching**: Redis (for product analysis cache)
- **Environment**: Docker for containerization

### AI/ML Components
- **LLM**: Claude 3.5 Sonnet (via Anthropic API)
- **Tools**: WebFetch, WebSearch, custom harm analysis
- **Prompt Engineering**: Structured prompts for safety analysis
- **Knowledge Base**: Curated lists of allergens, PFAS compounds, safe alternatives

## Component Breakdown

### 1. Chrome Extension Components

#### A. Content Script (`content.js`)
**Purpose**: Detect product pages and extract product information

**Responsibilities**:
- Detect when user is on a product page (Amazon, Target, Walmart, etc.)
- Extract product data: name, description, ingredients, brand, URL
- Inject floating "Analyze Safety" button on product pages
- Send product data to background service worker
- Display analysis badge/overlay on product images

**Technical Details**:
```typescript
interface ProductData {
  url: string;
  name: string;
  brand?: string;
  description?: string;
  ingredients?: string[];
  images?: string[];
  price?: number;
  retailer: string;
}
```

#### B. Popup UI (`popup.tsx`)
**Purpose**: Display analysis results and alternatives

**Features**:
- **Safety Score Display**: Visual gauge (0-100, red → yellow → green)
- **Detected Hazards List**:
  - Allergens found (with severity)
  - PFAS compounds detected
  - Other concerning ingredients
- **Alternative Products**:
  - 3-5 safer alternatives with comparison scores
  - Affiliate links (clearly marked)
  - Price comparison
- **Source Citations**: Links to research/databases used
- **User Settings**: Custom allergen profile

**UI States**:
- Loading (analyzing product)
- Analysis complete (show results)
- No analysis available (product not supported)
- Error state (API failure)

#### C. Background Service Worker (`background.js`)
**Purpose**: Coordinate between content script and backend agent

**Responsibilities**:
- Listen for messages from content scripts
- Make API calls to backend agent
- Manage analysis queue (rate limiting)
- Cache analysis results locally (IndexedDB)
- Handle extension icon badge updates
- Track user events for analytics

#### D. Options Page (`options.tsx`)
**Purpose**: User configuration and preferences

**Features**:
- Allergen profile setup (what to watch for)
- Sensitivity settings (strict vs. moderate)
- Retailer preferences (which sites to analyze)
- Privacy settings (data sharing preferences)
- API key configuration (if self-hosting)

### 2. Backend Agent Components

#### A. Agent Core (`agent/core.ts`)
**Purpose**: Claude Agent SDK implementation for product analysis

**Main Agent Loop**:
1. Receive product data from extension
2. Use WebFetch to scrape full product page (if needed)
3. Extract and parse ingredient lists
4. Search knowledge bases for harmful substances
5. Calculate harm score using weighted algorithm
6. Use WebSearch to find safer alternatives
7. Rank alternatives by safety + price + availability
8. Inject affiliate links
9. Return structured analysis to extension

**Prompt Structure**:
```
You are a product safety expert. Analyze this product for harmful substances.

Product Information:
- Name: {product.name}
- Ingredients: {product.ingredients}
- Description: {product.description}

Your Tasks:
1. Identify all allergens (milk, eggs, nuts, soy, wheat, shellfish, fish, sesame)
2. Detect PFAS compounds (PTFE, PFOA, PFOS, GenX, etc.)
3. Flag other concerning chemicals (parabens, phthalates, BPA, etc.)
4. Assign severity scores (1-10) for each concern
5. Calculate overall safety score (0-100)
6. Provide scientific reasoning with sources

Output as JSON: {schema}
```

#### B. Harm Analysis Engine (`agent/harm-analyzer.ts`)
**Purpose**: Score products based on detected hazards

**Algorithm**:
```typescript
interface HarmScore {
  overall: number; // 0-100 (0 = very harmful, 100 = safe)
  allergens: AllergenRisk[];
  pfas: PFASRisk[];
  otherConcerns: ChemicalRisk[];
  confidence: number; // 0-100 (how confident in analysis)
}

interface AllergenRisk {
  name: string; // e.g., "Peanuts"
  severity: number; // 1-10
  source: string; // where detected in ingredients
  crossContamination: boolean;
}

interface PFASRisk {
  compound: string; // e.g., "PFOA"
  concentration?: string; // if known
  healthImpact: string; // brief description
  evidence: string[]; // research links
}

// Scoring formula:
// overall_score = 100 - (sum of weighted penalties)
// penalties = (allergen_severity * allergen_weight) + (pfas_severity * pfas_weight)
```

**Weighting**:
- PFAS compounds: High weight (major penalty)
- Major allergens (peanuts, shellfish): Medium-high weight
- Minor allergens (soy): Medium weight
- Other concerns: Variable based on research

#### C. Alternative Finder (`agent/alternative-finder.ts`)
**Purpose**: Search for and rank safer alternatives

**Process**:
1. Use WebSearch to find similar products
2. Filter by category/use case
3. Analyze each alternative with same harm scoring
4. Rank by: (safety_score * 0.6) + (price_competitiveness * 0.2) + (availability * 0.2)
5. Select top 3-5 alternatives
6. Convert product links to affiliate links

**Affiliate Integration**:
- Amazon Associates API
- ShareASale
- CJ Affiliate
- Impact
- Direct brand partnerships

#### D. Knowledge Base (`agent/knowledge/`)
**Purpose**: Reference data for harm analysis

**Data Sources**:
- `allergens.json`: Comprehensive allergen list with synonyms
- `pfas-compounds.json`: Known PFAS chemicals with CAS numbers
- `safe-certifications.json`: Trusted certifications (USDA Organic, NSF, etc.)
- `ingredient-database.json`: Common ingredients with safety profiles
- `research-sources.json`: Peer-reviewed research links

**Update Strategy**:
- Weekly automated scraping of EPA PFAS list
- Monthly review of new allergen research
- Community contributions via GitHub PRs

### 3. API Layer

#### REST API Endpoints (`api/routes.ts`)

```typescript
POST /api/analyze
Request: {
  product: ProductData,
  userProfile?: AllergenProfile
}
Response: {
  score: HarmScore,
  alternatives: AlternativeProduct[],
  analysisId: string,
  timestamp: string
}

GET /api/analysis/:id
// Retrieve cached analysis

POST /api/feedback
Request: {
  analysisId: string,
  helpful: boolean,
  comment?: string
}
// User feedback for improving accuracy

GET /api/health
// Service health check
```

#### Rate Limiting
- 10 requests/minute per user (free tier)
- 100 requests/minute (premium tier - future)
- Aggressive caching (7-day TTL for product analyses)

## Guiding Principles

### 1. User Privacy First
- **No tracking without consent**: Users opt-in to analytics
- **Local-first processing**: Cache analyses locally when possible
- **Minimal data collection**: Only collect what's necessary for analysis
- **Transparent data usage**: Clear privacy policy, open-source code

### 2. Scientific Accuracy
- **Evidence-based**: Every claim backed by research
- **Source citations**: Always provide links to studies/databases
- **Confidence scoring**: Be honest about uncertainty
- **Expert review**: Periodic audits by toxicologists/allergists

### 3. User Empowerment
- **Education over fear**: Explain WHY something is harmful
- **Customizable sensitivity**: Users choose their risk tolerance
- **No false alarms**: Minimize false positives to maintain trust
- **Actionable alternatives**: Never just warn, always provide solutions

### 4. Sustainable Monetization
- **Value alignment**: Only promote genuinely safer products
- **Disclosure transparency**: Clearly mark affiliate links
- **No pay-to-rank**: Alternatives ranked by safety, not commission rates
- **Free core features**: Never paywall safety information

### 5. Technical Excellence
- **Performance**: Analysis results in < 3 seconds
- **Reliability**: 99.9% uptime target
- **Scalability**: Architecture supports millions of users
- **Maintainability**: Clean code, comprehensive tests, good documentation

## Implementation Phases

### Phase 1: MVP (Weeks 1-4)
**Goal**: Prove the concept with basic functionality

- [x] Project setup and architecture design (this document)
- [ ] Chrome extension scaffold (manifest.json, basic popup)
- [ ] Content script for Amazon product detection only
- [ ] Backend agent with Claude SDK integration
- [ ] Basic harm analysis (allergens only, no PFAS yet)
- [ ] Simple popup UI showing safety score
- [ ] Manual alternative input (no auto-search yet)
- [ ] Local testing with 10-20 sample products

**Success Criteria**:
- Extension detects Amazon products correctly
- Agent analyzes ingredients and finds allergens
- Popup displays results in < 5 seconds
- Safety scores are reasonable and consistent

### Phase 2: Core Features (Weeks 5-8)
**Goal**: Build out full feature set

- [ ] Add PFAS detection to harm analysis
- [ ] Implement WebSearch-based alternative finder
- [ ] Affiliate link integration (Amazon Associates)
- [ ] Support 5 major retailers (Amazon, Walmart, Target, CVS, Walgreens)
- [ ] Build knowledge base with 100+ allergens, 50+ PFAS compounds
- [ ] Add user allergen profiles in options page
- [ ] Implement caching layer (Redis)
- [ ] Create analysis history view
- [ ] Write comprehensive test suite

**Success Criteria**:
- Supports multiple retailers correctly
- PFAS detection works accurately
- Alternative finder returns relevant products
- Extension performs well under normal usage

### Phase 3: Polish & Launch (Weeks 9-12)
**Goal**: Prepare for public release

- [ ] UI/UX refinement based on beta testing
- [ ] Performance optimization (< 2s analysis time)
- [ ] Error handling and edge cases
- [ ] Chrome Web Store listing (screenshots, description, video)
- [ ] Landing page development (SvelteKit or Next.js)
- [ ] Documentation (user guide, FAQ, API docs)
- [ ] Beta testing with 50-100 users
- [ ] Security audit
- [ ] Privacy policy and terms of service
- [ ] Submit to Chrome Web Store

**Success Criteria**:
- Chrome Web Store approval
- 100+ active beta users
- < 5% error rate
- Positive user feedback (4+ stars)

### Phase 4: Growth & Iteration (Post-Launch)
**Goal**: Scale and improve based on user feedback

- [ ] Add support for more retailers (international markets)
- [ ] Expand to Firefox and Edge
- [ ] Build mobile app (React Native)
- [ ] Add more harm categories (microplastics, heavy metals)
- [ ] Implement ML models for ingredient extraction
- [ ] Partnership with health organizations
- [ ] Premium features (custom reports, bulk analysis)
- [ ] API for third-party integrations

## Monetization Strategy

### Revenue Streams

1. **Affiliate Commissions** (Primary - 80% of revenue)
   - Amazon Associates: 1-10% commission per sale
   - Other affiliate networks: 5-15% commission
   - Direct brand partnerships: Negotiated rates

2. **Premium Subscription** (Secondary - 15% of revenue)
   - $4.99/month or $49/year
   - Features:
     - Custom allergen profiles (unlimited)
     - Bulk product analysis (upload spreadsheet)
     - Export reports (PDF)
     - Priority support
     - Ad-free experience

3. **API Access** (Future - 5% of revenue)
   - For health apps, meal planning services, etc.
   - Pricing: $0.01 per analysis (volume discounts)

### Affiliate Strategy

**Product Selection Criteria**:
1. **Safety first**: Must score 20+ points higher than original
2. **Availability**: In stock and shippable to user's location
3. **Price competitiveness**: Within 20% of original product price
4. **Commission rate**: Secondary factor (never override safety)

**Disclosure**:
- Clear "Affiliate Link" badge on all recommendations
- Explanation in first-time user onboarding
- Full transparency in privacy policy

**Ethics**:
- Never recommend products we wouldn't use ourselves
- Regular audits of alternative quality
- User feedback loop to remove poor recommendations
- Option to disable affiliate links (in premium tier)

## Technical Specifications

### Performance Targets

- **Extension bundle size**: < 500KB (optimized for fast install)
- **Popup load time**: < 100ms (instant UI)
- **Analysis time**: < 3s (from request to result)
- **Memory usage**: < 50MB (lightweight on browser)
- **API response time**: < 1s (p95)
- **Cache hit rate**: > 60% (reduce API calls)

### Browser Compatibility

- Chrome: 120+ (Manifest V3 fully supported)
- Edge: 120+ (Chromium-based)
- Brave: Latest version
- Opera: Latest version
- Firefox: Phase 4 (requires manifest adaptation)
- Safari: Phase 4 (requires different extension format)

### Data Privacy Compliance

- **GDPR**: Full compliance (EU users)
- **CCPA**: Full compliance (California users)
- **Cookie consent**: Not needed (no cookies used)
- **Data retention**: Analyses cached 7 days, then deleted
- **User data**: Encrypted at rest and in transit
- **Third-party sharing**: Only with explicit consent

### Security Measures

- **Content Security Policy**: Strict CSP in manifest
- **HTTPS only**: All API calls encrypted
- **No eval()**: No dynamic code execution
- **Input sanitization**: Prevent XSS attacks
- **API authentication**: JWT tokens for backend
- **Rate limiting**: Prevent abuse
- **Regular updates**: Security patches within 48h

## Success Metrics

### Key Performance Indicators (KPIs)

**User Acquisition**:
- Installs per week
- Activation rate (% who use it within 7 days)
- Retention (D1, D7, D30)
- Referral rate

**Engagement**:
- Products analyzed per user per week
- Popup open rate (when on product pages)
- Alternative click-through rate
- User settings customization rate

**Revenue**:
- Affiliate click-through rate
- Conversion rate (clicks → purchases)
- Revenue per user per month
- Premium subscription conversion rate

**Quality**:
- Analysis accuracy (manual review sample)
- User feedback score (helpful vs. not helpful)
- Error rate
- Support ticket volume

### Target Goals (6 months post-launch)

- 10,000+ active users
- 50,000+ products analyzed
- 5% affiliate conversion rate
- $10,000+ monthly revenue
- 4.5+ star average rating
- < 2% error rate

## Open Questions & Future Research

1. **Medical liability**: Do we need disclaimers from lawyers about health advice?
2. **Data sourcing**: Should we partner with organizations like EWG or FDA?
3. **Internationalization**: How to handle different regulations (EU vs. US)?
4. **Offline mode**: Cache common analyses for offline browsing?
5. **Social features**: Should users be able to share analyses or contribute to knowledge base?
6. **Brand partnerships**: Could "safe" brands sponsor their placement in alternatives?
7. **Insurance integration**: Could health insurers subsidize premium subscriptions?

## Contributing

This project will be open-source (MIT license) with community contributions welcome:
- Report bugs and issues
- Suggest new features
- Add to knowledge base (allergens, PFAS compounds)
- Improve documentation
- Submit code improvements

Core maintainers: Arshveer Gahir, Kaustubh KC

---

**Document Version**: 1.0
**Last Updated**: 2025-11-10
**Status**: Active Development - Phase 1
