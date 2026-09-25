import fs from "node:fs";
import path from "node:path";
import { jobPaths } from "@/lib/pipeline";

export const runtime = "nodejs";

const read = (file: string) => {
  try { return JSON.parse(fs.readFileSync(file, "utf8")); } catch { return null; }
};

/** What the edit heard and what it decided to cut, as soon as each exists.
 *  The pipeline writes transcript.json after listening and decisions.json after
 *  the editorial pass; before then the answer is simply shorter. */
export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const { work } = jobPaths(id);
  const heard = read(path.join(work, "transcript.json"));
  const decided = read(path.join(work, "decisions.json"));
  return Response.json({
    words: heard?.words?.map((w: { text: string }) => w.text) ?? null,
    cuts: decided?.cuts ?? null,
    emphasis: decided?.emphasis ?? null,
  });
}
