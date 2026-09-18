import { halfhellJSON } from "@/lib/halfhell";

export const runtime = "nodejs";

export async function POST(req: Request) {
  const { message, profile } = await req.json().catch(() => ({}));
  if (!String(message || "").trim()) {
    return Response.json({ reply: "Say something and I'll try to translate it.", overrides: {}, changed: [] });
  }
  try {
    const out = await halfhellJSON<{ reply: string; overrides: Record<string, unknown>; changed: string[] }>(
      "/v1/chat",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, profile }),
        timeoutMs: 15_000,
      }
    );
    return Response.json({
      reply: String(out.reply ?? "Done."),
      overrides: out.overrides && typeof out.overrides === "object" ? out.overrides : {},
      changed: Array.isArray(out.changed) ? out.changed : [],
    });
  } catch {
    return Response.json(
      { reply: "I couldn't reach the model just then — try that again.", overrides: {}, changed: [] },
      { status: 200 }
    );
  }
}
