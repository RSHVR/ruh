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
};
