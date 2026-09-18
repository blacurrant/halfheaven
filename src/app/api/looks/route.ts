import { halfhellJSON } from "@/lib/halfhell";

export const runtime = "nodejs";

export async function GET() {
  try {
    const data = await halfhellJSON<{ looks: unknown }>("/v1/looks", { timeoutMs: 8000 });
    return Response.json(data);
  } catch (e) {
    const err = e as { code?: string; status?: number };
    return Response.json({ looks: [] }, { status: 200, headers: { "X-Halfhell-Error": err.code || "proxy_error" } });
  }
}
