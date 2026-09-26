import { budgetsOf, BY_ID, type Copy, FIELD_HINTS, fieldsOf, LAYOUTS } from "@/lib/layouts";
import { chatJSON } from "@/lib/openrouter";

export const runtime = "nodejs";

type Msg = { role: "user" | "assistant"; text: string };

/** Jev picks the layout; this writes the words that go in it. */
const SYSTEM = `You are the creative director inside an ad layout tool. The user describes the
ad they want in chat. A separate model has already chosen a wireframe layout for it; you are
told which one and which copy slots it has. You write the copy for those slots and reply.

Reply with JSON only: {"reply": string, "copy": object}

"reply": one or two short sentences, first person, plain words, no emoji, no markdown. Say
what you set up in terms of the ad, not the wireframe mechanics. If one detail that matters is
missing (brand name, the offer, the date), end with one short question asking for it.

"copy": values for the layout's slots. Keep everything in "current copy" unless the user asked
to change it. Write believable, specific copy from what the user said; invent the rest in the
same voice, but keep it short: this is an ad, not a paragraph. Written slots have hard
character limits for this layout; when current copy is over one, rewrite it shorter. Match
the user's language and currency; if no currency is given use ₹. Never name a real
competitor unless the user did.

Slots that exist (use only these keys):
${Object.entries(FIELD_HINTS).map(([k, v]) => `  ${k}: ${v}`).join("\n")}`;

const clip = (v: unknown, n: number) => (typeof v === "string" && v.trim() ? v.trim().slice(0, n) : undefined);

/** Keep only the slots that exist, in the shapes the renderer draws. */
function clean(raw: unknown): Copy {
  if (!raw || typeof raw !== "object") return {};
  const r = raw as Record<string, unknown>;
  const out: Copy = {};
  for (const k of ["brand", "headline", "subhead", "body", "cta", "offer", "price", "was", "code", "badge",
    "quote", "author", "role", "rating", "rival", "date", "time", "place"] as const) {
    const v = clip(r[k], k === "quote" ? 200 : 90);
    if (v) out[k] = v;
  }
  const list = (v: unknown) => (Array.isArray(v) ? v : []);
  const stats = list(r.stats).map((s) => ({ value: clip(s?.value, 12), label: clip(s?.label, 40) }))
    .filter((s): s is { value: string; label: string } => !!s.value && !!s.label).slice(0, 3);
  if (stats.length) out.stats = stats;
  const steps = list(r.steps).map((s) => clip(s, 60)).filter((s): s is string => !!s).slice(0, 3);
  if (steps.length) out.steps = steps;
  const points = list(r.points).map((s) => clip(s, 60)).filter((s): s is string => !!s).slice(0, 5);
  if (points.length) out.points = points;
  const items = list(r.items).map((s) => ({ name: clip(s?.name, 40), price: clip(s?.price, 20) }))
    .filter((s): s is { name: string; price: string | undefined } => !!s.name).slice(0, 4);
  if (items.length) out.items = items;
  const chat = list(r.chat).map((s) => ({ me: !!s?.me, text: clip(s?.text, 120) }))
    .filter((s): s is { me: boolean; text: string } => !!s.text).slice(0, 5);
  if (chat.length) out.chat = chat;
  return out;
}

export async function POST(req: Request) {
  const { messages, copy, layout } = (await req.json()) as { messages?: Msg[]; copy?: Copy; layout?: string };
  const chosen = BY_ID[layout ?? ""] ?? LAYOUTS[0];
  const convo = (messages ?? []).slice(-16)
    .map((m) => `${m.role === "user" ? "User" : "You"}: ${String(m.text).slice(0, 800)}`).join("\n");

  const t0 = Date.now();
  try {
    const { out, model, cost } = await chatJSON(
      SYSTEM,
      `Layout chosen: ${chosen.name} (${chosen.format}). ${chosen.when}\n` +
      `Its slots: ${fieldsOf(chosen).join(", ")}\n` +
      `Hard character limits in this layout (for arrays, per item): ${Object.entries(budgetsOf(chosen)).map(([k, v]) => `${k} ${v}`).join(", ")}\n\n` +
      `Current copy: ${JSON.stringify(copy ?? {})}\n\nConversation:\n${convo}`,
    );
    return Response.json({
      reply: clip(out.reply, 400) ?? "Done.",
      copy: clean(out.copy),
      model, cost, ms: Date.now() - t0,
    });
  } catch {
    return Response.json({ reply: "I couldn't reach the model just then. Try that again.", copy: {} });
  }
}
