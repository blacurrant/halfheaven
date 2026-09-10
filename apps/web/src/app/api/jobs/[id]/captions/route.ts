import fs from "node:fs";
import { jobPaths, recut } from "@/lib/pipeline";

export const runtime = "nodejs";
export const maxDuration = 600;

type Run = { text: string; style: string; t: number | null };
type Card = { t: number; duration: number; runs: Run[] };

function read(id: string): Card[] | null {
  const { program } = jobPaths(id);
  if (!fs.existsSync(program)) return null;
  return JSON.parse(fs.readFileSync(program, "utf8")).captions as Card[];
}

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const captions = read(id);
  if (!captions) return Response.json({ error: "No edit to fix yet." }, { status: 404 });
  return Response.json({
    captions: captions.map((c, index) => ({
      index,
      t: c.t,
      duration: c.duration,
      words: c.runs.map((r) => r.text),
      emphasis: c.runs.map((r, i) => (r.style === "emphasis" ? i : -1)).filter((i) => i >= 0),
    })),
  });
}

export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const { edits } = await req.json();
  if (!Array.isArray(edits) || edits.length === 0) {
    return Response.json({ error: "Nothing to change." }, { status: 400 });
  }
  try {
    await recut(id, edits);
    return Response.json({ ok: true, at: Date.now() });
  } catch (e) {
    return Response.json({ error: (e as Error).message }, { status: 500 });
  }
}
