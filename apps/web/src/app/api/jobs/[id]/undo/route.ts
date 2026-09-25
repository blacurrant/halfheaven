import { undo } from "@/lib/pipeline";

export const runtime = "nodejs";

/** Put back the version before the last change. The previous render was kept,
 *  so this is a file copy - instant, and exactly what was there before. */
export async function POST(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const { ok, left, error } = undo(id);
  return ok
    ? Response.json({ ok, left, at: Date.now() })
    : Response.json({ error, left }, { status: 409 });
}
