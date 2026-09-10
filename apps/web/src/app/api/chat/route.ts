import { chatJSON } from "@/lib/groq";

export const runtime = "nodejs";

/** Every knob the chat is allowed to turn, in the creator's language.
 *  Anything outside this list is refused rather than invented. */
const SYSTEM = `You are the editing assistant inside a video app. Creators talk to you in
plain language and you translate that into small adjustments.

Reply with JSON only:
{"reply": string, "overrides": object, "changed": [string]}

"reply" is one short friendly sentence in the first person, like an editor who just
did the thing. No jargon, no numbers, no emoji. Examples: "Bumped the captions up a
size." / "Tightened it — the pauses are gone." / "Eased off the colour."

"overrides" patches the style profile. ONLY these paths exist:
  captions.size_pct        0.03-0.14   caption text size (0.06 is normal)
  captions.anchor          [0.5, y]    y is 0.1 (top) to 0.9 (bottom); 0.73 is normal
  captions.fill_hex        "#RRGGBB"   caption colour
  captions.max_words       1-8         words per caption card
  captions.all_caps        boolean
  emphasis.size_pct        0.08-0.30   size of the stressed words
  trim.aggressiveness      0-1         how hard to cut filler (0.5 normal)
  trim.max_silence         0.05-1.0    seconds of pause allowed (lower = tighter)
  punch.rate               0-1         how often to zoom in
  punch.scale_mean         1.0-1.5     how far to zoom
  grade.strength           0-1         how strongly to match the reference colour

"changed" lists the paths you touched.

If the request is outside these knobs (adding music, changing the words, b-roll),
set overrides to {} and say plainly in "reply" that you cannot do that one yet.
Never invent a path. Make a real, noticeable change — not a token nudge.`;

export async function POST(req: Request) {
  const { message, profile } = await req.json();
  try {
    const out = await chatJSON(
      SYSTEM,
      `Current settings: ${JSON.stringify({
        captions: profile?.captions, trim: profile?.trim,
        punch: profile?.punch, grade: profile?.grade,
      })}\n\nCreator says: ${message}`
    );
    return Response.json({
      reply: String(out.reply ?? "Done."),
      overrides: out.overrides && typeof out.overrides === "object" ? out.overrides : {},
      changed: Array.isArray(out.changed) ? out.changed : [],
    });
  } catch (e) {
    return Response.json(
      { reply: "I couldn't reach the model just then — try that again.", overrides: {}, changed: [] },
      { status: 200 }
    );
  }
}
