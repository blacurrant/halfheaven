import { halfhellJSON } from "@/lib/halfhell";

export const runtime = "nodejs";

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  try {
    const data = await halfhellJSON(`/v1/jobs/${encodeURIComponent(id)}`, { timeoutMs: 8000 });
    return Response.json(data);
  } catch (e) {
    const err = e as Error & { status?: number; message: string };
    const status = err.status || 404;
    let msg = err.message || "No such job.";
    try {
      const j = JSON.parse(msg);
      if (j?.error?.message) msg = j.error.message;
    } catch {}
    return Response.json({ error: msg }, { status });
  }
}
