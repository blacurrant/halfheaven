import fs from "node:fs";
import { getJob, jobPaths, lookPreviews } from "@/lib/pipeline";

export const runtime = "nodejs";
export const maxDuration = 60;

/** Every caption look, drawn on this edit by the real renderer. The images are
 *  served from ./[file]; `version` changes whenever the edit does. */
export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  if (!getJob(id) || !fs.existsSync(jobPaths(id).program)) {
    return Response.json({ error: "No edit yet." }, { status: 404 });
  }
  try {
    return Response.json(await lookPreviews(id));
  } catch (e) {
    return Response.json({ error: (e as Error).message }, { status: 500 });
  }
}
