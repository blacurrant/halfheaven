import { BUSY, runRecut } from "@/lib/pipeline";

export const runtime = "nodejs";
export const maxDuration = 300; // Vercel Hobby's ceiling; Next does not enforce it locally

const MODES = ["off", "around", "behind"] as const;

/** How captions relate to the speaker, and what stands behind them. The speaker
 *  was separated when the edit was made, so either change is a render, not a re-run.
 *  Body: { mode?: "off" | "around" | "behind", background?: "#RRGGBB" | null }. */
export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const body = await req.json();
  const args: string[] = [];
  if (body.mode !== undefined) {
    if (!MODES.includes(body.mode)) {
      return Response.json({ error: "Unknown caption mode." }, { status: 400 });
    }
    args.push("--subject-captions", body.mode);
  }
  if (body.background !== undefined) {
    if (body.background !== null && !/^#[0-9a-fA-F]{6}$/.test(String(body.background))) {
      return Response.json({ error: "Pick a colour." }, { status: 400 });
    }
    args.push("--background", body.background ?? "none");
  }
  if (!args.length) return Response.json({ error: "Nothing to change." }, { status: 400 });

  const { code, err } = await runRecut(id, args);
  if (code === BUSY) return Response.json({ error: err }, { status: 409 });
  if (code === 3) {
    return Response.json(
      { error: "This edit was made before speaker separation. Make it again to use this." },
      { status: 409 });
  }
  return code === 0
    ? Response.json({ ok: true, at: Date.now() })
    : Response.json({ error: "That didn't apply. Try again." }, { status: 500 });
}
