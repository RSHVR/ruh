# Ruh Website — Migration to trellisstudio.co + Landing Build-out Plan

> **Author:** recon + plan, 2026-08-03 (Veer's request). Goal: move the Ruh marketing site onto
> **`ruh.trellisstudio.co`** and build a proper landing page with subscription pricing.
> **Status:** Part 1 (port) awaits a hosting-model decision; Part 2 (build-out) is planned.
> Companion: [`KB-OPTIMIZATION-PLAN.md`](./KB-OPTIMIZATION-PLAN.md) §M (cost model → pricing floors),
> [`FLEET-AUDIT-2026-08-01.md`](./FLEET-AUDIT-2026-08-01.md).

## 0. Current state (verified 2026-08-03)

| Thing | Where | Notes |
|---|---|---|
| Current Ruh landing | `personal-site` repo → `src/routes/ruh/+page.svelte` (1627 lines) | Serves `rshvr.com/ruh` + `ruh.rshvr.com`. Self-contained (no separate ruh component/data dir). |
| Ruh privacy policy | `personal-site` → `src/routes/ruh/privacy/+page.svelte` (275 lines) | **Referenced by the CWS store listing** ("Honest Fine Print" → `rshvr.com/ruh/privacy`). |
| Waitlist backend | `personal-site` → `src/routes/api/waitlist` + DB | First-party API + DB. Landing posts here. |
| Target site | `trellis/trellis-studio/web` | SvelteKit 5 + Tailwind v4 + GSAP on **CF Pages** (`pages_build_output_dir=.svelte-kit/cloudflare`, project `trellis-studio`). Agency one-pager + blog/work/tools; D1+R2 for photo-booth. |
| Ruh brand | `ruh-development/ruh-brand-guide.md` | Ruh has its own identity — distinct from Trellis's "Quiet Authority" agency brand. |
| DNS / hosting | Cloudflare, RSHVR account `c4cfa96…` (login `arshveer@trellisstudio.co`) | Subdomain = a CF Pages custom-domain step. |
| Stripe (test) | `~/.config/ruh/env` + `backend/.env` (chmod 600) | Test keys staged 2026-08-03; integration not built. |

Same framework on both sides (SvelteKit/CF Pages) → **framework-compatible port, not a rewrite.**

---

## Part 1 — Port the current pages (do now, once hosting model is chosen)

### 1a. Hosting-model decision (GATES everything — Veer's call)
`ruh.trellisstudio.co` is a **subdomain**, which is not a plain SvelteKit route. Options:

| Option | What | Pros | Cons |
|---|---|---|---|
| **A — separate CF Pages project** (recommended) | New small SvelteKit app (e.g. `trellis/ruh-web` or `trellis-studio/ruh-web`), its own Pages project, `ruh.trellisstudio.co` as its custom domain | Clean separation; Ruh keeps its own brand; independent deploy; no bloat/risk to the live agency build | A new project + deploy pipeline to stand up |
| **B — same project, host-routed** | Add `ruh.trellisstudio.co` as a 2nd custom domain on `trellis-studio`, reroute by hostname in `hooks.server.ts` → `/ruh/*` | One repo/deploy | Couples Ruh to the agency build; host-routing complexity; a Ruh bug can break the agency site |
| **C — path, not subdomain** | `trellisstudio.co/ruh` route in the agency site | Trivial | Not what was asked (`ruh.` subdomain); mixes product into agency IA |

**Recommendation: A.** Ruh is a distinct product with its own brand; a dedicated Pages project on the
subdomain is the clean separation, and it borrows Trellis's SEO/deploy patterns without entangling the
two builds. (Decide before any files move.)

### 1b. What to port
- `ruh/+page.svelte` (1627 lines) + `ruh/privacy/+page.svelte` (275 lines) → target routes.
- Associated **static assets** (images/og) the landing references from `personal-site/static`.
- Adapt personal-site-specific imports/aliases/layout to the target app's conventions (its own
  `+layout.svelte`, `lib/seo.ts`/`<Seo>` pattern, Tailwind config).
- **Waitlist:** do NOT blindly port the waitlist DB. Since Part 2 adds real signup + pricing, replace
  the waitlist CTA with an **install/signup CTA** (or keep a thin waitlist only if we still want one).
  → decision below.

### 1c. Downstream references to update when the site moves (don't miss these)
- **CWS store listing** privacy URL (`rshvr.com/ruh/privacy`) → new URL, OR keep `rshvr.com/ruh/privacy`
  alive as a redirect so the published listing doesn't break. (Ties to the extension-submission call.)
- Supabase Auth **Site URL** is `ruh.rshvr.com` + the `chrome-extension://…/auth-callback.html` redirect
  — moving the marketing site does NOT require changing auth (auth redirects to the extension, not the
  site), but the canonical/marketing URLs and any in-app links to the site do.
- SEO: canonical URLs, sitemap, OG. Decide whether `rshvr.com/ruh` **redirects** to
  `ruh.trellisstudio.co` (preserves the CWS link + link equity) or both stay live (needs canonical to
  avoid duplicate-content).

### 1d. Steps (after Option A is chosen)
1. Scaffold `ruh-web` (SvelteKit + CF Pages adapter), mirror Trellis's `<Seo>`/layout patterns + Ruh brand.
2. Port the two routes + assets; swap waitlist CTA per 1b.
3. Local build + preview (`pnpm build`, `wrangler pages dev`).
4. Create the Pages project + add `ruh.trellisstudio.co` custom domain (CF dashboard/API) — **Veer or with explicit go-ahead**.
5. Redirect/canonical decision for `rshvr.com/ruh` (1c).
6. Update the CWS listing privacy URL if the privacy page moved.

---

## Part 2 — Build the proper landing + subscription pricing (planned)

The ported page gets Ruh live under the new domain; then we build the real thing.

### 2a. Landing structure (a "proper" product landing)
Hero (what Ruh does + install CTA) → How it works (scan → score → sources) → Trust/accuracy block
(the confirmed-vs-category-typical honesty, disclaimer — a shipped invariant, not fine print) →
**Pricing** (2b) → Social proof / examples → FAQ → final CTA (install + sign up). Reuse Trellis's
motion/design-system tokens where they fit Ruh's brand; keep Ruh's identity.

### 2b. Subscription pricing (Stripe)
- Tiers today (CLAUDE.md tier matrix): **Free 5 / Basic 15 / Middle 30 / Unlimited** analyses-or-unlocks
  per month. Post-beta free tier = **5** (per §M).
- **Pricing floor is set by the cost model** — `KB-OPTIMIZATION-PLAN.md` §M: marginal ≈ **$0.28/analysis**
  pre-levers, target **≤$0.052** post-levers at scale. Paid tiers must price above marginal-after-levers;
  the free-tier size is gated by the <$300/mo cap at 1000 users. **Decide the analysis-vs-unlock cap
  model first** (the §M2 load-bearing decision) — it determines whether pricing is per-analysis or
  per-unlock, and the tier limits.
- **Stripe integration** (not yet built): test keys staged. Needs — products/prices in Stripe (test),
  Checkout or Payment Element, a `/api/webhooks/stripe` handler to sync subscription state → Supabase
  `user_tiers`/`credit_ledger`, and the extension reading tier from the backend (already does via
  `/api/credits/me`). Sequence Stripe **after** the security launch-blockers (FLEET-AUDIT §7) — billing
  on top of the current client-side paywall (S3) would be exploitable.
- Billing surface: on the marketing site (Checkout) vs in the extension side-panel (upgrade CTA) —
  decision below. Likely both: site for acquisition, in-panel upgrade for conversion.

### 2c. Open decisions (Veer)
1. **Hosting model** — A (separate Pages project, recommended) / B / C. *(gates Part 1)*
2. **Waitlist** — replace with install+signup CTA (recommended, since real signup is coming) / keep a waitlist.
3. **rshvr.com/ruh** — redirect to the new subdomain (recommended; preserves CWS link) / keep both live.
4. **Cap model** (from §M2) — per-analysis cap vs per-unlock cap; sets the pricing structure.
5. **Where billing lives** — marketing-site Checkout, in-extension upgrade, or both.

### 2d. Dependencies / sequencing
- Part 1 (port) can proceed immediately once (1) is chosen — independent of the backend fix queue.
- Part 2 pricing/Stripe should follow the security launch-blockers (S1/S3 esp.) so billing isn't built
  on the bypassable paywall. It also wants the §M2 cap decision.
