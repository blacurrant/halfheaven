import { BUSY, runRecut } from "@/lib/pipeline";

export const runtime = "nodejs";
export const maxDuration = 300; // Vercel Hobby's ceiling; Next does not enforce it locally

/** Switching a caption look only changes captions, so it is a restyle and a
 *  render - the transcript and the cut are already decided. "matched" puts
 *  back the look the edit was first made with. */
export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const { preset } = await req.json();
  const { code, err } = await runRecut(id, ["--preset", String(preset ?? "")]);
  if (code === BUSY) return Response.json({ error: err }, { status: 409 });
  return code === 0
    ? Response.json({ ok: true, at: Date.now() })
    : Response.json({ error: "That look didn't apply. Try another." }, { status: 500 });
}
