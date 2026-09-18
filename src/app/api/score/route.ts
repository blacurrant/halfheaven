import { halfhellJSON } from "@/lib/halfhell";

export const runtime = "nodejs";
export const maxDuration = 300;

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const jobId = String(body?.jobId ?? body?.job_id ?? "").trim();
  if (!jobId) return Response.json({ error: "No jobId" }, { status: 400 });
  try {
    const data = await halfhellJSON("/v1/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jobId }),
      timeoutMs: 120_000,
    });
    return Response.json(data);
  } catch (e) {
    const err = e as Error & { status?: number; message: string };
    const status = err.status && err.status >= 400 ? err.status : 500;
    // halfhell already envelopes errors; try to preserve message
    let msg = err.message || "Scoring failed";
    // If backend returned JSON error, unwrap
    try {
      const j = JSON.parse(msg);
      if (j?.error?.message) msg = j.error.message;
    } catch {}
    return Response.json({ error: msg }, { status });
  }
}
