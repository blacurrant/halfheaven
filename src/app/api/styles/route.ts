import { halfhellJSON } from "@/lib/halfhell";

export const runtime = "nodejs";

export async function GET() {
  try {
    const data = await halfhellJSON<{ styles: unknown }>("/v1/styles", { timeoutMs: 8000 });
    return Response.json(data);
  } catch (e) {
    const err = e as Error & { status?: number; code?: string };
    // Fallback: empty list rather than hard failure
    return Response.json({ styles: [] }, { status: err.status === 401 ? 502 : 200, headers: { "X-Halfhell-Error": err.code || "proxy_error" } });
  }
}
