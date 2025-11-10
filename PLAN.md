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

## Agent Model & Request Flow

### Key Architecture Decisions

**Q: Does each user get their own agent?**
**A: No. Agents are ephemeral and request-scoped, not user-scoped.**

Agents work like serverless functions:
- **Created on-demand** for each analysis request
- **Stateless** - no persistent connection to users
- **Single-purpose** - handle one analysis, then complete
- **Pooled/reused** - to avoid cold starts, but not tied to specific users

### Agent Capacity Model

**One agent instance handles one analysis request at a time** (~3-10 seconds per analysis)

**Capacity breakdown**:
```
1 agent instance    = 1 concurrent analysis
1 Cloud Run pod     = 10 concurrent agent instances (configurable)
1 pod               ≈ 6-20 analyses/minute (depending on complexity)

With auto-scaling:
- Start: 0 pods (scale to zero when idle)
- Moderate load (10 users): 1-2 pods
- High load (100 concurrent): 10 pods
- Max scale: 1000 pods (Cloud Run limit)
```

**Critical optimization: Caching prevents most requests from needing agents**

### Request Routing & Flow

**End-to-End User Flow**:

```
┌─────────────────────────────────────────────────────────┐
│ 1. USER BROWSES PRODUCT                                 │
│    User lands on Amazon product page                    │
│    Extension content script detects product             │
│    "Analyze Safety" button appears                      │
└────────────────────┬────────────────────────────────────┘
                     │ User clicks "Analyze"
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 2. EXTENSION CHECKS LOCAL CACHE                         │
│    Check IndexedDB for cached analysis (30-day TTL)     │
│    ├─ Cache HIT: Display results immediately (< 50ms)   │
│    └─ Cache MISS: Send request to backend →             │
└────────────────────┬────────────────────────────────────┘
                     │ POST /api/analyze
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 3. BACKEND API GATEWAY                                  │
│    Express.js endpoint receives request                 │
│    - Validate product data (Zod schema)                 │
│    - Rate limit check (10 req/min per user)             │
│    - Extract product URL hash                           │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 4. CHECK REDIS CACHE (1-hour TTL)                       │
│    ├─ Cache HIT: Return cached analysis (< 100ms) →    │
│    └─ Cache MISS: Check database ↓                      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 5. CHECK DATABASE CACHE (7-day TTL)                     │
│    Query product_analyses by URL hash                   │
│    ├─ Cache HIT: Promote to Redis, return (< 500ms) →  │
│    └─ Cache MISS: Need fresh analysis ↓                 │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 6. ENQUEUE ANALYSIS JOB (BullMQ)                        │
│    Add job to "product-analysis" queue                  │
│    - Priority: premium > free users (future)            │
│    - Return job ID to client immediately                │
│    - Client polls for results or uses WebSocket         │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 7. WORKER PICKS UP JOB                                  │
│    BullMQ worker (10 concurrent per pod) grabs job      │
│    Creates new Claude Agent instance                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 8. AGENT ANALYZES PRODUCT                               │
│    Agent execution (~3-10 seconds):                     │
│    ├─ WebFetch: Scrape full product page (if needed)   │
│    ├─ Extract ingredients & product details             │
│    ├─ Search knowledge base for allergens/PFAS          │
│    ├─ Calculate harm score (0-100)                      │
│    ├─ WebSearch: Find safer alternatives                │
│    ├─ Analyze alternatives (parallel)                   │
│    ├─ Rank by safety improvement + price                │
│    └─ Inject affiliate links                            │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 9. STORE RESULTS                                        │
│    - Save to PostgreSQL (product_analyses table)        │
│    - Cache in Redis (1 hour)                            │
│    - Mark job as complete                               │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│ 10. RETURN TO EXTENSION                                 │
│     - Extension receives analysis via polling/WebSocket │
│     - Store in local IndexedDB (30 days)                │
│     - Display in popup UI                               │
│     - Track user interaction (DB: user_searches)        │
└─────────────────────────────────────────────────────────┘
```

**Request latency breakdown**:
- Cache hit (local): ~50ms
- Cache hit (Redis): ~100ms
- Cache hit (DB): ~500ms
- Cache miss (new analysis): ~3-10 seconds

**Target cache hit rate: 60%+**
- Most popular products will be cached
- Reduces costs by 60% (avoid Claude API calls)
- Dramatically improves UX (instant results)

### Database Choice: PostgreSQL (No Vector Search Needed for MVP)

**Q: Do we need vector search?**
**A: Not for Phase 1. PostgreSQL is sufficient.**

**Why PostgreSQL is fine**:
- **Ingredient matching**: Exact string matching with arrays (`ingredients: text[]`)
- **Allergen detection**: Keyword search with synonyms (e.g., "milk" OR "dairy" OR "lactose")
- **PFAS matching**: Exact compound names or CAS numbers
- **Alternative search**: Claude's WebSearch tool handles semantic similarity
- **Fast enough**: Index on `product_url_hash` makes lookups < 50ms

**When we'd need vector search** (Phase 3+):
- Semantic ingredient similarity ("whey protein isolate" ≈ "whey protein concentrate")
- Finding similar products without relying on Claude API
- Clustering products by ingredient profiles
- Recommendation engine based on user preferences

**If we add vector search later**:
- **pgvector** extension for PostgreSQL (Supabase supports this)
- Embed ingredients with Claude embeddings or OpenAI embeddings
- Still use same Postgres database, just add vector columns

**Decision: Start with PostgreSQL, add pgvector only if needed in Phase 3+**

### Why This Architecture Works

**Advantages**:
1. **Cost-efficient**: Caching reduces Claude API costs by 60%+
2. **Scalable**: Cloud Run auto-scales from 0 to 1000s of instances
3. **Fast UX**: Cached responses in < 500ms, fresh analysis < 10s
4. **Resilient**: Job queue handles failures with retries
5. **No websockets needed initially**: Simple polling is fine for MVP

**Potential bottlenecks** (and mitigations):
- **Anthropic API rate limits**: 50 req/min (request increase to 500 req/min)
- **Redis memory**: 1GB free tier (50K cached analyses) → upgrade to $50/mo for 5GB
- **Cold starts**: Agent pooling reduces this to ~100-200ms

## Infrastructure & Hosting Strategy

### Backend API Hosting

**Recommended: Google Cloud Platform (GCP)**

**Rationale**:
- **Chrome Extension Integration**: Better ecosystem alignment (Google Cloud + Chrome)
- **Free Tier**: $300 credit for 90 days, then generous always-free tier
  - Cloud Run: 2 million requests/month free
  - Cloud Functions: 2 million invocations/month free
  - Firestore: 1GB storage, 50K reads/day, 20K writes/day free
- **Auto-scaling**: Cloud Run scales to zero (pay only for usage)
- **Serverless**: No infrastructure management required
- **Global CDN**: Low latency worldwide
- **Cost Efficiency**: ~$20-50/month at 10K users (vs Vercel ~$40-80/month)

**Landing Page Hosting: Cloudflare Pages**
- **Decision**: Landing page hosted at `eject.rshvr.com` via Cloudflare Pages
- **Rationale**:
  - Already using Cloudflare for www.rshvr.com (easy subdomain setup)
  - Free tier: Unlimited bandwidth, unlimited requests
  - Global CDN (300+ locations)
  - Automatic HTTPS
  - Git integration (deploy on push)
  - Perfect for static sites (Svelte/Next.js/React)
- **Cost**: $0/month (free tier sufficient)
- **Build time**: < 1 minute per deploy

**Alternative Considered: Vercel**
- **Pros**: Excellent DX, easy deployment, good for Next.js
- **Cons**: Function timeout (10s free tier), more expensive at scale
- **Verdict**: Cloudflare Pages better for landing page (free + already using Cloudflare). GCP Cloud Run better for backend API (long-running agent tasks).

**Deployment Architecture (GCP)**:
```
┌──────────────────────────────────────────────────────┐
│               Chrome Extension                        │
└────────────────────┬─────────────────────────────────┘
                     │ HTTPS
                     ▼
┌──────────────────────────────────────────────────────┐
│           Cloud Load Balancer (HTTPS)                │
│                 (Global, Auto-SSL)                    │
└────────────────────┬─────────────────────────────────┘
                     ▼
┌──────────────────────────────────────────────────────┐
│         Cloud Run (Containerized API)                │
│  • Node.js + Express + TypeScript                    │
│  • Claude Agent SDK                                  │
│  • Auto-scales 0-1000 instances                      │
│  • Max concurrency: 80 requests/instance             │
│  • Timeout: 60s (configurable up to 60min)           │
└────────┬────────────────────────┬────────────────────┘
         │                        │
         ▼                        ▼
┌──────────────────┐    ┌──────────────────────┐
│  Cloud Firestore │    │   Cloud Memorystore  │
│   (Database)     │    │      (Redis)         │
└──────────────────┘    └──────────────────────┘
```

**Cost Estimates (GCP)**:
- **0-1K users**: $0/month (free tier)
- **1K-10K users**: $20-50/month (Cloud Run + Firestore)
- **10K-100K users**: $200-500/month (need Memorystore Redis ~$50/month)
- **Anthropic API costs**: Variable (~$0.01-0.05 per analysis)

### Database Architecture

**Recommended: Supabase (PostgreSQL + Realtime)**

**Rationale**:
- **No Auth Required**: Can use anonymous sessions with UUID tracking
- **PostgreSQL**: Full-featured relational database
- **Free Tier**: 500MB database, 1GB file storage, 2GB bandwidth
- **Real-time**: WebSocket subscriptions (for future features)
- **Edge Functions**: Deno-based serverless functions
- **Cost**: $0/month (free tier) → $25/month (Pro with 8GB database)
- **Backup**: Automated daily backups on paid tier
- **REST API**: Auto-generated from schema (optional, we'll use direct connection)

**Alternative: GCP Firestore (NoSQL)**
- **Pros**:
  - Same ecosystem as Cloud Run (easier integration)
  - Generous free tier (1GB storage, 50K reads/day, 20K writes/day)
  - Real-time listeners built-in
  - No server management
  - Scales automatically
- **Cons**:
  - NoSQL (less flexible for complex queries)
  - More expensive at scale ($0.06/100K reads)
- **Verdict**: Great for MVP, but PostgreSQL better for complex analytics later

**Alternative: Prisma + PostgreSQL (Self-hosted or Railway)**
- **Prisma**: ORM for type-safe database access (can use with Supabase)
- **Railway**: $5/month PostgreSQL, easy deployment
- **Verdict**: Prisma is great as ORM layer on top of Supabase

**Decision: Supabase (PostgreSQL) + Prisma ORM**

### Database Schema

**User Tracking (Anonymous, No Auth)**:

```typescript
// Users table - anonymous tracking via UUID
table users {
  id: uuid PRIMARY KEY DEFAULT gen_random_uuid()
  created_at: timestamp DEFAULT now()
  last_active: timestamp
  extension_version: string

  // Optional preferences (stored locally, synced if user opts-in)
  allergen_profile: jsonb // ["peanuts", "dairy", ...]
  sensitivity_level: enum("strict", "moderate", "relaxed")

  // Privacy: no PII, no email, no accounts
}

// Product Analyses - cache of AI analysis results
table product_analyses {
  id: uuid PRIMARY KEY DEFAULT gen_random_uuid()
  product_url: text NOT NULL
  product_url_hash: text UNIQUE NOT NULL // hash for fast lookup

  // Product data
  product_name: text
  brand: text
  retailer: text
  ingredients: text[]

  // Analysis results
  overall_score: integer // 0-100
  allergens_detected: jsonb // [{name, severity, source}]
  pfas_detected: jsonb
  other_concerns: jsonb
  confidence: integer // 0-100

  // Metadata
  analyzed_at: timestamp DEFAULT now()
  analysis_version: string // track prompt versions
  claude_model: string // "claude-3-5-sonnet-20241022"

  // Cache TTL
  expires_at: timestamp // 7 days from analysis

  // Index for fast lookup
  INDEX idx_url_hash (product_url_hash)
  INDEX idx_expires (expires_at)
}

// User Searches - track what users searched (privacy-respecting)
table user_searches {
  id: uuid PRIMARY KEY DEFAULT gen_random_uuid()
  user_id: uuid REFERENCES users(id) ON DELETE CASCADE

  product_url: text NOT NULL
  product_url_hash: text NOT NULL
  analysis_id: uuid REFERENCES product_analyses(id)

  // Timestamps
  searched_at: timestamp DEFAULT now()

  // Index
  INDEX idx_user_searches (user_id, searched_at DESC)
  INDEX idx_url_hash (product_url_hash)
}

// Alternative Recommendations - track what AI recommended
table alternative_recommendations {
  id: uuid PRIMARY KEY DEFAULT gen_random_uuid()

  original_analysis_id: uuid REFERENCES product_analyses(id)
  alternative_product_url: text NOT NULL
  alternative_product_name: text

  // Scores
  safety_score: integer // 0-100
  safety_improvement: integer // delta from original
  price: decimal(10,2)
  price_difference: decimal(10,2) // delta from original

  // Ranking
  rank: integer // 1-5 (display order)

  // Affiliate
  affiliate_link: text
  affiliate_network: text // "amazon-associates", "shareasale", etc.

  // Metadata
  recommended_at: timestamp DEFAULT now()

  INDEX idx_original_analysis (original_analysis_id)
}

// User Interactions - track clicks and purchases (for optimization)
table user_interactions {
  id: uuid PRIMARY KEY DEFAULT gen_random_uuid()
  user_id: uuid REFERENCES users(id) ON DELETE CASCADE

  search_id: uuid REFERENCES user_searches(id)
  alternative_id: uuid REFERENCES alternative_recommendations(id)

  // Interaction type
  action: enum("viewed_alternatives", "clicked_alternative", "purchased")

  // Metadata
  occurred_at: timestamp DEFAULT now()

  // Revenue tracking (optional, privacy-respecting)
  purchase_amount: decimal(10,2) // if action=purchased
  commission_earned: decimal(10,2) // if action=purchased

  INDEX idx_user_interactions (user_id, occurred_at DESC)
  INDEX idx_alternative_interactions (alternative_id, action)
}

// Feedback - user ratings on analysis quality
table analysis_feedback {
  id: uuid PRIMARY KEY DEFAULT gen_random_uuid()

  analysis_id: uuid REFERENCES product_analyses(id)
  user_id: uuid REFERENCES users(id)

  helpful: boolean NOT NULL // thumbs up/down
  comment: text // optional feedback

  submitted_at: timestamp DEFAULT now()

  UNIQUE(analysis_id, user_id) // one feedback per user per analysis
  INDEX idx_analysis_feedback (analysis_id)
}

// Knowledge Base - allergens and PFAS compounds
table allergens {
  id: uuid PRIMARY KEY
  name: text NOT NULL UNIQUE
  synonyms: text[] // ["milk", "dairy", "lactose"]
  severity_default: integer // 1-10
  common_sources: text[]
  updated_at: timestamp
}

table pfas_compounds {
  id: uuid PRIMARY KEY
  name: text NOT NULL UNIQUE
  cas_number: text UNIQUE // Chemical Abstracts Service number
  synonyms: text[]
  health_impacts: text[]
  sources: text[] // research paper URLs
  updated_at: timestamp
}
```

**Privacy-First Design**:
- **No PII**: No emails, names, or identifying information
- **Anonymous UUIDs**: Extension generates UUID on install, stored locally
- **Opt-in sync**: Users can choose to sync allergen profiles (default: local only)
- **Aggregate analytics only**: Individual user data never exposed
- **GDPR compliant**: Right to deletion via UUID (users can reset extension)
- **Data retention**: Auto-delete searches older than 90 days

**Database Hosting Costs**:
- **Supabase Free Tier**: 500MB database (sufficient for 10K+ analyses)
- **Supabase Pro**: $25/month (8GB database, daily backups, 50GB bandwidth)
- **Estimated Scale**: 500MB ≈ 50K product analyses + 100K user searches

## Agent Parallelization & Scaling

### Concurrency Model

**Challenge**: Multiple users requesting analyses simultaneously requires parallel Claude agent instances.

**Solution: Stateless Agent Workers + Job Queue**

```typescript
┌─────────────────────────────────────────────────────┐
│              Incoming API Requests                   │
│          (from Chrome extension users)               │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│            API Gateway (Express.js)                  │
│  • Rate limiting (10 req/min per user)               │
│  • Request validation                                │
│  • Check analysis cache (Redis)                      │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────┐
│              Job Queue (BullMQ + Redis)              │
│  • Queue: "product-analysis"                         │
│  • Priority: premium users > free users              │
│  • Retry: 3 attempts with exponential backoff        │
│  • Timeout: 60s per job                              │
└────────────────────┬────────────────────────────────┘
                     │
                     ▼
        ┌────────────┴────────────┐
        │                         │
┌───────▼────────┐     ┌──────────▼─────────┐
│  Agent Worker  │ ... │   Agent Worker N   │
│    Instance 1  │     │                    │
│                │     │                    │
│ Claude SDK     │     │    Claude SDK      │
│ • WebFetch     │     │    • WebFetch      │
│ • WebSearch    │     │    • WebSearch     │
│ • Harm Analyze │     │    • Harm Analyze  │
└────────┬───────┘     └──────────┬─────────┘
         │                        │
         └────────────┬───────────┘
                      ▼
         ┌──────────────────────────┐
         │    Store in Database     │
         │   (Supabase PostgreSQL)  │
         └──────────────────────────┘
```

### Implementation Details

**BullMQ Job Queue (Redis-backed)**:

```typescript
// queue/analysis-queue.ts
import { Queue, Worker } from 'bullmq';
import IORedis from 'ioredis';

const connection = new IORedis({
  host: process.env.REDIS_HOST,
  port: 6379,
  maxRetriesPerRequest: null
});

// Analysis job queue
export const analysisQueue = new Queue('product-analysis', {
  connection,
  defaultJobOptions: {
    attempts: 3,
    backoff: {
      type: 'exponential',
      delay: 2000
    },
    timeout: 60000 // 60s
  }
});

// Worker pool - multiple instances processing in parallel
export function createWorker(concurrency: number = 10) {
  return new Worker(
    'product-analysis',
    async (job) => {
      const { productData, userId } = job.data;

      // Each job gets its own Claude agent instance
      const agent = new ProductSafetyAgent();
      const result = await agent.analyze(productData);

      // Store in database
      await storeAnalysis(result, userId);

      return result;
    },
    {
      connection,
      concurrency, // Process 10 jobs in parallel
      limiter: {
        max: 100, // Max 100 jobs
        duration: 60000 // per 60 seconds
      }
    }
  );
}
```

**Agent Instance Pooling**:

```typescript
// agent/agent-pool.ts
import { ProductSafetyAgent } from './product-safety-agent';

class AgentPool {
  private agents: ProductSafetyAgent[] = [];
  private maxSize: number = 20;

  async acquire(): Promise<ProductSafetyAgent> {
    // Reuse existing idle agent or create new one
    const agent = this.agents.pop() || new ProductSafetyAgent();
    return agent;
  }

  release(agent: ProductSafetyAgent): void {
    if (this.agents.length < this.maxSize) {
      this.agents.push(agent);
    }
    // Otherwise let it be garbage collected
  }
}

export const agentPool = new AgentPool();
```

**Scaling Characteristics**:
- **Horizontal scaling**: Cloud Run auto-scales instances (0-1000)
- **Per-instance concurrency**: 10 parallel agent executions
- **Queue throughput**: ~600 analyses/minute (10 workers × 60s)
- **Anthropic API rate limits**: 50 requests/minute (need to request increase)
- **Cost per 1000 analyses**: ~$10-50 (Claude API) + $1-2 (infrastructure)

### Caching Strategy

**Multi-layer caching to reduce API costs**:

```typescript
// Level 1: In-memory cache (Redis) - 1 hour TTL
// Level 2: Database cache - 7 days TTL
// Level 3: Extension local storage - 30 days TTL

async function getAnalysis(productUrl: string): Promise<Analysis | null> {
  const urlHash = hashUrl(productUrl);

  // Check Redis (fast, in-memory)
  const cached = await redis.get(`analysis:${urlHash}`);
  if (cached) return JSON.parse(cached);

  // Check database (slower, but cheaper than AI)
  const dbResult = await db.productAnalyses.findUnique({
    where: { product_url_hash: urlHash }
  });

  if (dbResult && !isExpired(dbResult.expires_at)) {
    // Promote to Redis
    await redis.setex(`analysis:${urlHash}`, 3600, JSON.stringify(dbResult));
    return dbResult;
  }

  // Not cached, needs new analysis
  return null;
}
```

**Cache Hit Rate Target**: 60%+ (reduces costs significantly)

## Separation of Concerns

### Clean Architecture Layers

```
┌─────────────────────────────────────────────────────┐
│              Presentation Layer                      │
│  • Express.js routes (REST API endpoints)            │
│  • Request validation (Zod schemas)                  │
│  • Response formatting                               │
│  • Error handling middleware                         │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│              Application Layer                       │
│  • Use cases / business logic                        │
│    - AnalyzeProductUseCase                           │
│    - FindAlternativesUseCase                         │
│    - TrackInteractionUseCase                         │
│  • Orchestration (queue jobs, combine results)       │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│              Domain Layer                            │
│  • Entities (Product, Analysis, Alternative)         │
│  • Value Objects (HarmScore, AllergenRisk)           │
│  • Domain services (HarmCalculator, RankingEngine)   │
│  • Interfaces (ports for external services)          │
└────────────────────┬────────────────────────────────┘
                     ▼
┌─────────────────────────────────────────────────────┐
│              Infrastructure Layer                    │
│  • Database (Prisma repositories)                    │
│  • External APIs (Claude SDK, affiliate APIs)        │
│  • Cache (Redis client)                              │
│  • Queue (BullMQ workers)                            │
│  • Logging (Winston/Pino)                            │
└─────────────────────────────────────────────────────┘
```

### Directory Structure

```
backend/
├── src/
│   ├── api/                    # Presentation Layer
│   │   ├── routes/
│   │   │   ├── analyze.route.ts
│   │   │   ├── alternatives.route.ts
│   │   │   └── health.route.ts
│   │   ├── middleware/
│   │   │   ├── rate-limit.ts
│   │   │   ├── validate.ts
│   │   │   └── error-handler.ts
│   │   └── schemas/
│   │       └── product.schema.ts   # Zod validation schemas
│   │
│   ├── application/            # Application Layer
│   │   ├── use-cases/
│   │   │   ├── analyze-product.usecase.ts
│   │   │   ├── find-alternatives.usecase.ts
│   │   │   └── track-interaction.usecase.ts
│   │   └── interfaces/         # Port definitions
│   │       ├── repository.interface.ts
│   │       └── ai-agent.interface.ts
│   │
│   ├── domain/                 # Domain Layer
│   │   ├── entities/
│   │   │   ├── product.entity.ts
│   │   │   ├── analysis.entity.ts
│   │   │   └── alternative.entity.ts
│   │   ├── value-objects/
│   │   │   ├── harm-score.vo.ts
│   │   │   └── allergen-risk.vo.ts
│   │   └── services/
│   │       ├── harm-calculator.service.ts
│   │       └── ranking-engine.service.ts
│   │
│   ├── infrastructure/         # Infrastructure Layer
│   │   ├── database/
│   │   │   ├── prisma/
│   │   │   │   └── schema.prisma
│   │   │   └── repositories/
│   │   │       ├── product.repository.ts
│   │   │       └── analysis.repository.ts
│   │   ├── ai/
│   │   │   ├── claude-agent.ts
│   │   │   ├── prompts/
│   │   │   │   ├── analyze.prompt.ts
│   │   │   │   └── alternatives.prompt.ts
│   │   │   └── tools/
│   │   │       ├── web-fetch.tool.ts
│   │   │       └── web-search.tool.ts
│   │   ├── cache/
│   │   │   └── redis.client.ts
│   │   ├── queue/
│   │   │   └── analysis.queue.ts
│   │   └── logging/
│   │       └── logger.ts
│   │
│   ├── shared/                 # Shared utilities
│   │   ├── types/
│   │   ├── utils/
│   │   └── constants/
│   │
│   └── index.ts               # Application entry point
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── prisma/
│   └── migrations/
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
└── package.json
```

### Key Principles

1. **Dependency Inversion**: Domain layer doesn't depend on infrastructure
2. **Single Responsibility**: Each module has one clear purpose
3. **Interface Segregation**: Small, focused interfaces
4. **Testability**: Easy to mock dependencies via interfaces
5. **Modularity**: Can swap implementations (e.g., different AI models, different databases)

## Logging & Monitoring

### Logging Strategy

**Structured Logging with Pino (High Performance)**

```typescript
// infrastructure/logging/logger.ts
import pino from 'pino';

export const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  formatters: {
    level: (label) => {
      return { level: label };
    }
  },
  timestamp: pino.stdTimeFunctions.isoTime,
  // GCP Cloud Logging compatible format
  messageKey: 'message',
  errorKey: 'error',
});

// Usage example
logger.info({ userId, productUrl, duration: 234 }, 'Product analysis completed');
logger.error({ userId, error, productUrl }, 'Analysis failed');
```

**Log Levels**:
- **ERROR**: Failures that need immediate attention (AI API errors, database failures)
- **WARN**: Degraded performance, rate limits, fallbacks used
- **INFO**: Key business events (analysis started, alternatives found, user clicked)
- **DEBUG**: Detailed execution flow (cache hit/miss, AI prompts, tool calls)

**What to Log**:

```typescript
// Analysis lifecycle
logger.info({
  event: 'analysis.started',
  userId,
  productUrl: hashUrl(url), // hash for privacy
  retailer,
  cached: false
});

logger.info({
  event: 'analysis.completed',
  userId,
  analysisId,
  duration: 2340, // ms
  cacheUsed: false,
  claudeTokens: 1234,
  harmScore: 67,
  alternativesFound: 4
});

// Errors
logger.error({
  event: 'analysis.failed',
  userId,
  error: err.message,
  stack: err.stack,
  productUrl: hashUrl(url),
  retryCount: 2
});

// User interactions
logger.info({
  event: 'alternative.clicked',
  userId,
  analysisId,
  alternativeId,
  alternativeRank: 1,
  affiliateNetwork: 'amazon-associates'
});

// Performance
logger.warn({
  event: 'slow.analysis',
  userId,
  duration: 8500, // ms (over threshold)
  productUrl: hashUrl(url)
});
```

### Monitoring Stack

**Recommended: Google Cloud Operations (formerly Stackdriver)**

**Why**:
- Native integration with Cloud Run
- Automatic log aggregation
- Built-in metrics and traces
- Free tier: 50GB logs/month
- Cost: ~$5-20/month at scale

**Components**:

1. **Cloud Logging**: Centralized log storage and search
2. **Cloud Monitoring**: Metrics dashboards and alerting
3. **Cloud Trace**: Distributed tracing (request flow)
4. **Cloud Profiler**: CPU/memory profiling

**Alternative: Sentry (Error Tracking)**
- Excellent for error monitoring and alerting
- Free tier: 5K errors/month
- Great user-friendly error grouping
- Source map support for stack traces
- Cost: $26/month (10K errors)

**Recommended Setup: GCP Logging + Sentry**

### Key Metrics to Monitor

```typescript
// Application metrics
metrics: {
  // Throughput
  'analyses.total': Counter,              // Total analyses requested
  'analyses.cached': Counter,             // Cache hits
  'analyses.successful': Counter,         // Successful completions
  'analyses.failed': Counter,             // Failures

  // Performance
  'analysis.duration': Histogram,         // p50, p95, p99 latency
  'claude.api.duration': Histogram,       // AI API call time
  'db.query.duration': Histogram,         // Database query time
  'cache.lookup.duration': Histogram,     // Cache lookup time

  // Business metrics
  'alternatives.found': Histogram,        // # of alternatives per analysis
  'alternatives.clicked': Counter,        // Click-through rate
  'purchases.tracked': Counter,           // Conversion events
  'revenue.commission': Gauge,            // Total commission earned

  // System health
  'queue.jobs.active': Gauge,             // Jobs in progress
  'queue.jobs.waiting': Gauge,            // Jobs in queue
  'queue.jobs.failed': Counter,           // Failed jobs
  'api.rate_limit.hit': Counter,          // Rate limit violations

  // Claude API
  'claude.tokens.used': Counter,          // Track API costs
  'claude.rate_limit.hit': Counter,       // API rate limits
}
```

### Alerting Rules

**Critical Alerts** (PagerDuty / Email / SMS):
- Error rate > 5% for 5 minutes
- API response time p95 > 10s
- Database connection failures
- Claude API failures > 10% of requests
- Queue backlog > 1000 jobs

**Warning Alerts** (Slack / Email):
- Error rate > 2% for 10 minutes
- Cache hit rate < 40%
- Analysis duration p95 > 5s
- Memory usage > 80%
- Disk usage > 90%

### Dashboards

**Main Operational Dashboard**:
- Requests per minute (RPM)
- Error rate (%)
- Average response time
- Cache hit rate
- Active users (last 5 min)
- Queue depth
- Cloud Run instance count

**Business Dashboard**:
- Analyses per day
- Alternative click-through rate
- Tracked purchases
- Commission earned (daily/weekly/monthly)
- User retention (D1, D7, D30)

**Cost Dashboard**:
- Claude API costs (tokens used)
- Infrastructure costs (Cloud Run, Firestore, Redis)
- Cost per analysis
- Revenue per user

## Test-Driven Development (TDD)

### Testing Philosophy

**Write tests BEFORE implementation** following Red-Green-Refactor cycle:

1. **Red**: Write failing test that defines desired behavior
2. **Green**: Write minimal code to make test pass
3. **Refactor**: Improve code while keeping tests passing

### Testing Pyramid

**For MVP (Phase 1)** - Start with essentials:
```
          ┌────────────┐
          │    E2E     │  ~3-5 tests (happy path + 1-2 error cases)
          └────────────┘
        ┌────────────────┐
        │  Integration   │  ~10-15 tests (main API endpoints)
        └────────────────┘
     ┌─────────────────────┐
     │   Unit Tests        │  ~30-50 tests (core business logic)
     └─────────────────────┘

     Total: ~50-70 tests for MVP
```

**For Production (Phase 2-3)** - Expand coverage:
```
          ┌────────────┐
          │    E2E     │  ~10-15 tests (all user flows + edge cases)
          └────────────┘
        ┌────────────────┐
        │  Integration   │  ~30-50 tests (all endpoints + error handling)
        └────────────────┘
     ┌─────────────────────┐
     │   Unit Tests        │  ~100-150 tests (all business logic + utils)
     └─────────────────────┘

     Total: ~150-200 tests at maturity
```

**Rationale for starting small**:
- MVP has limited scope (Amazon only, allergens only, basic UI)
- Write tests for code that exists, not code that might exist
- Grow test suite as features grow
- 500 tests is excessive for a product with < 5K LOC

### Testing Stack

```typescript
// package.json
{
  "devDependencies": {
    "vitest": "^1.0.0",           // Fast unit test runner (Vite-based)
    "supertest": "^6.3.0",         // HTTP assertions (integration tests)
    "@testcontainers/postgresql": "^10.0.0", // Real DB for integration tests
    "@testcontainers/redis": "^10.0.0",
    "playwright": "^1.40.0",       // E2E testing (Chrome extension)
    "msw": "^2.0.0",               // Mock Service Worker (API mocking)
    "@faker-js/faker": "^8.0.0",   // Generate test data
    "chai": "^4.3.0",              // Assertions
    "sinon": "^17.0.0"             // Spies, stubs, mocks
  }
}
```

### Unit Tests (Domain & Application Logic)

**Example: Harm Calculator Service**

```typescript
// tests/unit/domain/services/harm-calculator.test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { HarmCalculator } from '@/domain/services/harm-calculator.service';
import { AllergenRisk } from '@/domain/value-objects/allergen-risk.vo';
import { PFASRisk } from '@/domain/value-objects/pfas-risk.vo';

describe('HarmCalculator', () => {
  let calculator: HarmCalculator;

  beforeEach(() => {
    calculator = new HarmCalculator();
  });

  describe('calculateOverallScore', () => {
    it('should return 100 for product with no harmful substances', () => {
      const score = calculator.calculateOverallScore({
        allergens: [],
        pfas: [],
        otherConcerns: []
      });

      expect(score).toBe(100);
    });

    it('should penalize products with high-severity allergens', () => {
      const allergens = [
        new AllergenRisk({ name: 'peanuts', severity: 10 })
      ];

      const score = calculator.calculateOverallScore({
        allergens,
        pfas: [],
        otherConcerns: []
      });

      expect(score).toBeLessThan(50); // Severe penalty
    });

    it('should heavily penalize PFAS compounds', () => {
      const pfas = [
        new PFASRisk({ compound: 'PFOA', healthImpact: 'high' })
      ];

      const score = calculator.calculateOverallScore({
        allergens: [],
        pfas,
        otherConcerns: []
      });

      expect(score).toBeLessThan(30); // Very severe penalty
    });

    it('should combine penalties from multiple sources', () => {
      const allergens = [
        new AllergenRisk({ name: 'soy', severity: 3 })
      ];
      const pfas = [
        new PFASRisk({ compound: 'PFOS', healthImpact: 'moderate' })
      ];

      const score = calculator.calculateOverallScore({
        allergens,
        pfas,
        otherConcerns: []
      });

      expect(score).toBeGreaterThan(0);
      expect(score).toBeLessThan(70);
    });
  });
});
```

**Run unit tests**: `npm run test:unit` (should run in < 1s)

### Integration Tests (API + Database + External Services)

**Example: Analyze Product API Endpoint**

```typescript
// tests/integration/api/analyze.test.ts
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import supertest from 'supertest';
import { app } from '@/index';
import { PostgreSqlContainer } from '@testcontainers/postgresql';
import { RedisContainer } from '@testcontainers/redis';
import { PrismaClient } from '@prisma/client';

describe('POST /api/analyze', () => {
  let request: supertest.SuperTest<supertest.Test>;
  let db: PrismaClient;
  let postgresContainer;
  let redisContainer;

  beforeAll(async () => {
    // Start real PostgreSQL and Redis in Docker
    postgresContainer = await new PostgreSqlContainer().start();
    redisContainer = await new RedisContainer().start();

    // Configure app to use test containers
    process.env.DATABASE_URL = postgresContainer.getConnectionUri();
    process.env.REDIS_URL = redisContainer.getConnectionUri();

    db = new PrismaClient();
    await db.$connect();

    request = supertest(app);
  }, 30000); // 30s timeout for container startup

  afterAll(async () => {
    await db.$disconnect();
    await postgresContainer.stop();
    await redisContainer.stop();
  });

  beforeEach(async () => {
    // Clear database between tests
    await db.productAnalyses.deleteMany();
    await db.userSearches.deleteMany();
  });

  it('should analyze a product and return harm score', async () => {
    const productData = {
      url: 'https://amazon.com/product/B08XYZ',
      name: 'Test Protein Powder',
      ingredients: ['whey protein', 'peanuts', 'soy lecithin'],
      retailer: 'amazon'
    };

    const response = await request
      .post('/api/analyze')
      .send({ product: productData })
      .expect(200);

    expect(response.body).toMatchObject({
      score: expect.objectContaining({
        overall: expect.any(Number),
        allergens: expect.arrayContaining([
          expect.objectContaining({
            name: 'peanuts',
            severity: expect.any(Number)
          })
        ])
      }),
      alternatives: expect.any(Array),
      analysisId: expect.any(String)
    });

    // Verify stored in database
    const stored = await db.productAnalyses.findFirst({
      where: { product_name: 'Test Protein Powder' }
    });
    expect(stored).toBeTruthy();
  });

  it('should return cached result on second request', async () => {
    const productData = {
      url: 'https://amazon.com/product/B08XYZ',
      name: 'Test Product',
      ingredients: ['water'],
      retailer: 'amazon'
    };

    // First request (not cached)
    const first = await request
      .post('/api/analyze')
      .send({ product: productData });

    // Second request (should be cached)
    const second = await request
      .post('/api/analyze')
      .send({ product: productData });

    expect(first.body.analysisId).toBe(second.body.analysisId);
    // Second should be much faster (< 100ms vs > 1000ms)
  });

  it('should handle Claude API failures gracefully', async () => {
    // Mock Claude API to fail
    // (Implementation depends on how we mock external services)

    const response = await request
      .post('/api/analyze')
      .send({ product: { url: 'test', ingredients: ['unknown'] } })
      .expect(503); // Service unavailable

    expect(response.body).toMatchObject({
      error: 'Analysis service temporarily unavailable'
    });
  });
});
```

**Run integration tests**: `npm run test:integration` (should run in < 30s)

### E2E Tests (Full User Flow)

**Example: Chrome Extension → API → Results**

```typescript
// tests/e2e/extension-flow.test.ts
import { test, expect } from '@playwright/test';

test.describe('Product Analysis Flow', () => {
  test('should detect product, analyze, and show alternatives', async ({ page, context }) => {
    // Load Chrome extension
    const extensionPath = './dist/extension';
    const extensionContext = await context.newPage();

    // Navigate to Amazon product page
    await page.goto('https://www.amazon.com/dp/B08XYZ123');

    // Wait for content script to inject "Analyze Safety" button
    const analyzeButton = page.locator('[data-eject-analyze]');
    await expect(analyzeButton).toBeVisible({ timeout: 5000 });

    // Click analyze button
    await analyzeButton.click();

    // Wait for popup to show results
    const popup = page.locator('[data-eject-popup]');
    await expect(popup).toBeVisible({ timeout: 10000 });

    // Verify harm score displayed
    const harmScore = popup.locator('[data-harm-score]');
    await expect(harmScore).toContainText(/\d+/); // Contains a number

    // Verify alternatives shown
    const alternatives = popup.locator('[data-alternative]');
    await expect(alternatives).toHaveCount.greaterThanOrEqual(1);

    // Click first alternative (affiliate link)
    const firstAlternative = alternatives.first();
    await firstAlternative.click();

    // Verify tracking event sent to API
    // (Check network requests or database)
  });
});
```

**Run E2E tests**: `npm run test:e2e` (should run in < 2 minutes)

### Test Coverage Requirements

**MVP (Phase 1)**:
- **Unit tests**: 70%+ code coverage (focus on business logic, not boilerplate)
- **Integration tests**: Main API endpoints covered (analyze, alternatives, health check)
- **E2E tests**: Happy path covered (product detection → analysis → display results)

**Production (Phase 2+)**:
- **Unit tests**: 80%+ code coverage
- **Integration tests**: All API endpoints + error scenarios
- **E2E tests**: All critical user journeys + edge cases

**Philosophy**: Quality over quantity. One well-written test that catches real bugs is worth more than 10 tests that just boost coverage metrics.

### CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - run: npm run test:unit
      - run: npm run test:coverage

  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm ci
      - run: npm run test:integration

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm ci
      - run: npx playwright install
      - run: npm run test:e2e
```

### TDD Workflow Example

**Feature: Find safer alternatives**

1. **Write test first** (Red):
```typescript
it('should return alternatives safer than original product', async () => {
  const original = { harmScore: 45 };
  const alternatives = await findAlternatives(original);

  expect(alternatives.every(alt => alt.harmScore > 45)).toBe(true);
});
```

2. **Run test** → Fails (no implementation yet)

3. **Write minimal code** (Green):
```typescript
async function findAlternatives(original) {
  // Stub implementation
  return [{ harmScore: 80 }];
}
```

4. **Run test** → Passes

5. **Refactor** (implement real logic):
```typescript
async function findAlternatives(original) {
  const results = await webSearch(original.name + ' safe alternative');
  const analyzed = await Promise.all(results.map(analyzeProduct));
  return analyzed.filter(alt => alt.harmScore > original.harmScore);
}
```

6. **Run test** → Still passes

7. **Commit** → CI runs all tests → Deploy

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
