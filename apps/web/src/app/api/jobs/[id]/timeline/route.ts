import fs from "node:fs";
import { jobPaths } from "@/lib/pipeline";

export const runtime = "nodejs";

/** What sits where on the finished cut: shots, caption cards, and the pushes.
 *  Times are on the program clock, which is what the player uses. */
export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const { program } = jobPaths(id);
  if (!fs.existsSync(program)) return Response.json({ error: "No edit yet." }, { status: 404 });

  const prog = JSON.parse(fs.readFileSync(program, "utf8"));
  let elapsed = 0;
  const shots = prog.video.map((c: { start: number; end: number; scale_to?: number }) => {
    const at = elapsed;
    elapsed += c.end - c.start;
    return { at, length: c.end - c.start, punched: !!c.scale_to && c.scale_to > 1.02 };
  });

  return Response.json({
    duration: elapsed,
    shots,
    captions: prog.captions.map((c: { t: number; duration: number; runs: { text: string; style: string }[] }) => ({
      at: c.t,
      length: c.duration,
      text: c.runs.map((r) => r.text).join(" "),
      stressed: c.runs.some((r) => r.style === "emphasis"),
    })),
  });
}
