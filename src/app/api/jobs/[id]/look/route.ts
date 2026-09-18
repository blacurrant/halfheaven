import { halfhellFetch } from "@/lib/halfhell";

export const runtime = "nodejs";
export const maxDuration = 300;

export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const { preset } = await req.json().catch(() => ({}));
  if (!preset) return Response.json({ error: "Missing preset" }, { status: 400 });
  try {
    const res = await halfhellFetch(`/v1/jobs/${encodeURIComponent(id)}/look`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ preset: String(preset) }),
      timeoutMs: 120_000,
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch (e) {
    const err = e as Error & { status?: number; message: string };
    const status = err.status || 500;
    return Response.json({ error: err.message || "That look didn't apply. Try another." }, { status });
  }
}
