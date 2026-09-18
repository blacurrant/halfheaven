export const runtime = "nodejs";

/**
 * Stream media via halfhell with Range support.
 * Must proxy bytes + headers, not buffer whole file (videos are large).
 */
import { halfhellFetch } from "@/lib/halfhell";

export async function GET(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const which = new URL(req.url).searchParams.get("v") ?? "after";
  const q = `?v=${encodeURIComponent(which)}`;

  // Proxy streaming: we use rawResponse so we can pipe body directly
  try {
    const res = await halfhellFetch(`/v1/jobs/${encodeURIComponent(id)}/media${q}`, {
      method: "GET",
      timeoutMs: 60_000,
      rawResponse: true,
      forwardFrom: req,
    });

    // Mirror halfhell headers that matter for seek
    const headers = new Headers();
    for (const [k, v] of res.headers.entries()) {
      if (["content-type", "content-length", "content-range", "accept-ranges", "cache-control", "x-request-id", "etag"].includes(k.toLowerCase())) {
        headers.set(k, v);
      }
    }
    // Fallback content type
    if (!headers.has("Content-Type")) headers.set("Content-Type", "video/mp4");

    return new Response(res.body as unknown as BodyInit, {
      status: res.status,
      headers,
    });
  } catch (e) {
    const err = e as Error & { status?: number; message: string };
    const status = err.status || 404;
    return new Response(err.message || "Not ready.", { status });
  }
}
