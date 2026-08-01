import { Container, getContainer } from "@cloudflare/containers";

export class RuhApi extends Container {
  defaultPort = 8080;
  sleepAfter = "15m";

  constructor(ctx, env) {
    super(ctx, env);
    // Secrets live on the Worker (wrangler secret); forward them into the container.
    this.envVars = {
      ANTHROPIC_API_KEY: env.ANTHROPIC_API_KEY ?? "",
      API_KEY: env.API_KEY ?? "",
      SUPABASE_URL: env.SUPABASE_URL ?? "",
      SUPABASE_KEY: env.SUPABASE_KEY ?? "",
      SUPABASE_JWT_SECRET: env.SUPABASE_JWT_SECRET ?? "",
      TAVILY_API_KEY: env.TAVILY_API_KEY ?? "",
      SERPER_API_KEY: env.SERPER_API_KEY ?? "",
      COHERE_API_KEY: env.COHERE_API_KEY ?? "",
      ALLOWED_ORIGINS: env.ALLOWED_ORIGINS ?? "",
      DEBUG: "false",
      LOG_LEVEL: "INFO",
    };
  }
}

export default {
  async fetch(request, env) {
    return getContainer(env.RUH_API).fetch(request);
  },

  // Scheduled sweep: re-analyze inconclusive cached analyses (empty/garbage
  // results). The analyze route itself treats inconclusive cache entries as
  // stale (should_rescan, capped at MAX_RESCANS), so the cron only needs to
  // CALL analyze on candidates — there is no second analysis pathway.
  // Note: cron rescans have no client-captured DOM, so bot-hostile retailers
  // may stay inconclusive until a user visit provides the page HTML.
  async scheduled(event, env, ctx) {
    ctx.waitUntil(
      (async () => {
        const container = getContainer(env.RUH_API);
        const auth = { Authorization: `Bearer ${env.API_KEY}` };
        const res = await container.fetch(
          new Request("https://api.rshvr.com/api/admin/rescan-candidates", {
            headers: auth,
          }),
        );
        if (!res.ok) {
          console.log("rescan sweep: candidates fetch failed", res.status);
          return;
        }
        const { candidates = [] } = await res.json();
        console.log(`rescan sweep: ${candidates.length} candidate(s)`);
        for (const product_url of candidates) {
          try {
            const r = await container.fetch(
              new Request("https://api.rshvr.com/api/analyze", {
                method: "POST",
                headers: { ...auth, "Content-Type": "application/json" },
                body: JSON.stringify({ product_url }),
              }),
            );
            console.log(`rescan sweep: ${product_url} -> ${r.status}`);
          } catch (e) {
            console.log(`rescan sweep: ${product_url} failed: ${e}`);
          }
        }
      })(),
    );
  },
};
