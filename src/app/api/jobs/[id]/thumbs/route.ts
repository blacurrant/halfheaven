import { halfhellFetch } from "@/lib/halfhell";

export const runtime = "nodejs";

export async function GET(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  try {
    const res = await halfhellFetch(`/v1/jobs/${encodeURIComponent(id)}/thumbs`, {
      method: "GET",
      timeoutMs: 30_000,
      rawResponse: true,
      forwardFrom: req,
    });
    if (!res.ok) {
      const msg = await res.text().catch(() => "Not ready.");
      return new Response(msg, { status: res.status });
    }
    const buf = await res.arrayBuffer();
    return new Response(buf as unknown as BodyInit, {
      headers: {
        "Content-Type": res.headers.get("Content-Type") || "image/jpeg",
        "Cache-Control": res.headers.get("Cache-Control") || "no-store",
        "X-Request-Id": res.headers.get("X-Request-Id") || "",
      },
    });
  } catch (e) {
    const err = e as Error & { status?: number; message: string };
    return new Response(err.message || "Not ready.", { status: err.status || 404 });
  }
}
