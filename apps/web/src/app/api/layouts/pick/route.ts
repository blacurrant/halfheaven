import { LAYOUTS } from "@/lib/layouts";
import { type Choice, decide } from "@/lib/openrouter";

export const runtime = "nodejs";

type Msg = { role: "user" | "assistant"; text: string };

// Jev reads each layout's `when` as the criterion for choosing it; the format
// rides along so "make it vertical" or "for stories" can move the pick.
const CRITERIA = Object.fromEntries(LAYOUTS.map((l) => [l.id, `${l.name} (${l.format}). ${l.when}`]));

const INSTRUCTIONS = `The user is describing an ad creative they want to make. "conversation" is the chat so far;
"typing_now", when present, is a message they are still typing, may be unfinished, and is the newest
thing they have said. Which ad layout fits the ad they are describing best? If they ask for a
particular kind of layout or format, that request wins over the product category.`;

/** Called on every pause in typing, so it stays one small request: the last
 *  dozen turns, trimmed, and nothing else. */
export async function POST(req: Request) {
  const { messages, draft } = (await req.json()) as { messages?: Msg[]; draft?: string };
  const conversation = (messages ?? []).slice(-12).map((m) => ({
    from: m.role === "user" ? "user" : "assistant",
    text: String(m.text).slice(0, 600),
  }));
  const typing = String(draft ?? "").trim().slice(0, 600);
  if (!conversation.some((m) => m.from === "user") && !typing) {
    return Response.json({ error: "nothing to read yet" }, { status: 400 });
  }

  const t0 = Date.now();
  try {
    const { answers, model, cost } = await decide(
      { conversation, ...(typing ? { typing_now: typing } : {}) },
      { layout: { type: "choice", instructions: INSTRUCTIONS, criteria: CRITERIA } },
      req.signal,
    );
    const a = answers.layout as Choice;
    return Response.json({
      pick: a.choice,
      confidence: a.confidence,
      probabilities: a.probabilities,
      model, cost, ms: Date.now() - t0,
    });
  } catch (e) {
    if (req.signal.aborted) return new Response(null, { status: 499 });
    return Response.json({ error: String(e).slice(0, 300) }, { status: 502 });
  }
}
