import { halfhellJSON } from "@/lib/halfhell";

export const runtime = "nodejs";

export async function POST(req: Request) {
  const body = await req.json().catch(() => null);
  if (!body) return Response.json({ error: "Invalid JSON" }, { status: 400 });
  try {
    const data = await halfhellJSON("/v1/waitlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      timeoutMs: 8000,
    });
    return Response.json(data);
  } catch (e) {
    const err = e as Error & { status?: number; message: string };
    const status = err.status && err.status >= 400 && err.status < 600 ? err.status : 502;
    // Surface halfhell envelope if present
    try {
      const parsed = JSON.parse(err.message);
      if (parsed?.error) return Response.json(parsed, { status });
    } catch {}
    return Response.json({ error: err.message || "Waitlist failed" }, { status });
  }
}
