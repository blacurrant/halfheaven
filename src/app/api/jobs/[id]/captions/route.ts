import { halfhellFetch, halfhellJSON } from "@/lib/halfhell";

export const runtime = "nodejs";
export const maxDuration = 300;

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  try {
    const data = await halfhellJSON(`/v1/jobs/${encodeURIComponent(id)}/captions`, { timeoutMs: 8000 });
    return Response.json(data);
  } catch (e) {
    const err = e as Error & { status?: number; message: string };
    const status = err.status || 404;
    return Response.json({ error: err.message || "No edit" }, { status });
  }
}

export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const body = await req.json().catch(() => ({}));
  const edits = body?.edits;
  if (!Array.isArray(edits) || edits.length === 0) {
    return Response.json({ error: "Nothing to change." }, { status: 400 });
  }
  try {
    const res = await halfhellFetch(`/v1/jobs/${encodeURIComponent(id)}/captions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ edits }),
      timeoutMs: 120_000,
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch (e) {
    const err = e as Error & { status?: number; message: string };
    const status = err.status || 500;
    return Response.json({ error: err.message || "Recut failed" }, { status });
  }
}
