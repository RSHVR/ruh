# Ruh Adversarial Security Audit — 2026-08-07

**Target:** `https://api.rshvr.com` (FastAPI on Cloudflare Containers, Supabase Postgres backend)
**Window:** Scheduled Friday-evening authorized pentest routine
**Run time:** 2026-08-07 19:12 EDT / 23:12 UTC (gate check passed: Friday, after 19:00 America/Toronto)
**Status: BLOCKED — no attack traffic was sent.** This is a report of why the audit could not run, plus a static-analysis pre-read of the codebase to hand off for the next attempt.

---

## TL;DR

The Step 0 self-gate (Friday, after 7pm Toronto, target = api.rshvr.com) **passed**. But the very first live request — a plain `GET /api/health` — was rejected by this session's own outbound network proxy with a **policy-level 403** before it ever left the sandbox:

```
$ curl -sS -o /tmp/h1.json -w "\nHTTP %{http_code}\n" https://api.rshvr.com/api/health
curl: (56) CONNECT tunnel failed, response 403
```

```
$ curl -sS "$HTTPS_PROXY/__agentproxy/status"
"recentRelayFailures": [
  {
    "ts": "2026-08-07T23:11:49.733Z",
    "kind": "connect_rejected",
    "detail": "gateway answered 403 to CONNECT (policy denial or upstream failure)",
    "host": "api.rshvr.com:443"
  }
]
```

The proxy's own operating instructions (`/root/.ccr/README.md`) are explicit: *"403/407 from the proxy: the destination host is not allowed by your organization's egress policy for this session. Do not retry or route around it — report the blocked host."* I followed that instruction and stopped rather than trying to tunnel around the sandbox's egress controls, since bypassing a security boundary to reach the test target would itself be the kind of thing this audit is supposed to catch, not do.

**No requests beyond the single blocked `CONNECT` reached api.rshvr.com.** Zero probes, zero auth attempts, zero data touched.

---

## Why this happened (likely cause)

This session's execution environment has an egress allowlist that `api.rshvr.com` is not on. This is almost certainly independent of the Friday-night trigger gate — the gate logic (time + hostname match) is inside the agent's own prompt-level check, not the infra-level proxy policy, so passing the gate doesn't imply the sandbox is allowed to reach the host.

## What needs to change before this routine can do its job

One of the following, from Veer:

1. **Add `api.rshvr.com` to the egress allowlist** for whatever environment this scheduled routine runs in (check environment config under Claude Code on the web — environments have a network policy setting chosen at creation time), or
2. **Move this routine to an environment provisioned with broader/custom egress** that includes the production API host, or
3. Confirm this restriction is intentional (e.g., prod is deliberately unreachable from this sandbox class for safety) — in which case the adversarial-pass concept needs a different execution venue entirely (e.g., a session with a network policy scoped explicitly to `api.rshvr.com` only, which would also be the *tighter* and more defensible setup for a scheduled prod-attacking routine than a general allowlist).

---

## What I did instead (read-only, local repo only)

Since I could not send live traffic, I used the time to read the checked-out `github.com/RSHVR/ruh` repo (already cloned in this session) to pre-stage the next attempt, so a future run with network access can go straight to targeted requests instead of re-deriving the attack surface. This is static-analysis only — **nothing below is a confirmed live finding**; all of it is CODE READING and needs to be verified against the running service before it counts as a vuln.

### Attack surface identified (for next run)

| Area | File | Notes |
|---|---|---|
| Dual-mode auth | `backend/src/api/auth.py` | JWT-first (HS256, explicit `algorithms=["HS256"]`, `audience="authenticated"` — alg-confusion looks closed on read), falls back to constant-time static API key compare. |
| Analyze | `backend/src/api/routes/analyze.py` | `POST /api/analyze`, `GET /api/analyze/{url_hash}/reviews`, `POST /api/reviews/search`, `GET /api/reviews/{url_hash}/summary`. Rate limited 30/min (analyze) and 60/min (search) per IP via slowapi. |
| Credits | `backend/src/api/routes/credits.py` | `GET /api/credits/me`, `POST /api/credits/deduct`, `GET /api/credits/check/{url_hash}` — all call `_require_jwt_user`, reject `is_api_key` callers with 401. `deduct_credit` always uses `auth.user_id` from the verified JWT, never a client-supplied user id, so a body-based IDOR on deduct looks closed on read. Atomicity is delegated to a Postgres RPC (`deduct_credit`, migration 013) with a `UNIQUE(user_id, url_hash)` constraint on `unlocked_analyses` — worth a live replay test (rapid-fire concurrent deducts) to confirm the row lock actually prevents a double-spend race, since that can't be verified from source alone. |
| User | `backend/src/api/routes/user.py` | `GET /api/user/me`, auto-creates user row on first JWT. |
| Admin | `backend/src/api/routes/admin.py` | Validation-log/stats endpoints gated on the same static `verify_api_key`, not JWT/tier. Read-only (SQL via parameterized Supabase RPCs / query builder, not string concatenation — injection looks closed on read). |
| Unauthenticated | `backend/src/api/main.py` | `GET /` and `GET /api/health` require no auth (by design, low sensitivity). |

### Things worth targeted live testing next time (not yet tested)

- **Static API key exposure**: `VITE_API_KEY` is baked into the published Chrome extension's JS bundle at build time (per `CLAUDE.md`), meaning it is effectively public to anyone who unpacks the extension. On the live API this key grants `AuthContext(is_api_key=True)` with **`credits_remaining` defaulting to `-1`** (the dataclass default, which elsewhere in the code means "unlimited") — though `_auth_fields()` special-cases `is_api_key` callers to omit tier/credit fields from the response, so this may be inert. Needs a live check: does a request authenticated with the static key get treated as unlimited-tier anywhere, or is it purely used for the free/anonymous `/api/analyze` path? This is the single highest-value live test for the "static API key path granting more than intended" item in scope.
- **JWT edge cases against the live secret**: expired token, `alg: none`, wrong audience, token signed with a garbage/empty secret, token with a `sub` claim for a UUID that doesn't exist in `users` (does auto-create silently mint a full account?).
- **`deduct_credit` race/replay**: fire ~5 concurrent deduct calls for the same fresh `url_hash` on a test account and confirm exactly one deduction lands (requires a live JWT — see credentials gap below).
- **CORS reflection**: `CORSMiddleware` origins come from `ALLOWED_ORIGINS` env var; worth confirming production isn't accidentally wildcarded or reflecting arbitrary `Origin` headers with `allow_credentials=True` (a real cross-origin credential-leak pattern if misconfigured).
- **Debug-mode error verbosity**: `_safe_error_detail()` in `analyze.py` returns raw `str(exception)` when `settings.debug` is `True`. Need to confirm prod `DEBUG` is false (a 500 with a stack-trace-flavored detail string would confirm it's on).
- **`/docs` and `/openapi.json` exposure**: not blocked by any auth in `main.py`; worth checking if reachable in prod (informational at most, but shows full endpoint/schema map to anyone).

### Credentials gap

No backend route exposes signup — account creation happens client-side directly against Supabase Auth, which is out of scope per the rules of engagement ("do not attack Supabase or any other host directly"). **Synthetic test accounts cannot be created within the stated rules of engagement using only `api.rshvr.com`.** Cross-account IDOR testing (credits, unlock state) needs Veer to either pre-provision two test JWTs/accounts, or explicitly widen scope to include the Supabase Auth signup endpoint for account creation only (not general Supabase probing).

---

## Findings

**CONFIRMED:** none — no live requests were made.
**SUSPECTED:** none — nothing above rises past "worth checking," everything is gated on actually reaching the host.

## Could not test without Veer provisioning / fixing

1. **Network egress to `api.rshvr.com` from this session's environment** — the actual blocker, see top of report.
2. Two synthetic test-account JWTs for cross-account IDOR/credit tests (or explicit scope to hit Supabase Auth signup only).
3. Confirmation of whether `DEBUG=true` in the Cloud Run/Cloudflare Container prod env (can be checked live once network access is fixed, by triggering a 500 and inspecting the `detail` field).

---

*No commits or PR were made — there are no code changes to propose; this is an audit-status report. Re-run this routine once egress is fixed to actually execute the probes listed above.*
