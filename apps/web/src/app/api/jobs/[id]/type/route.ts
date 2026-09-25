import fs from "node:fs";
import { BUSY, jobPaths, runRecut } from "@/lib/pipeline";

export const runtime = "nodejs";
export const maxDuration = 300; // Vercel Hobby's ceiling; Next does not enforce it locally

const FIELDS = ["fill_hex", "size_pct", "font_file", "font_weight", "all_caps",
                "decor", "stroke_hex", "shadow_hex", "box_hex"] as const;

/** The type as the edit currently draws it: normal words and pop words. */
export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const { program } = jobPaths(id);
  if (!fs.existsSync(program)) return Response.json({ error: "No such edit." }, { status: 404 });
  const styles = JSON.parse(fs.readFileSync(program, "utf8")).styles ?? {};
  const pick = (style: Record<string, unknown> = {}) =>
    Object.fromEntries(FIELDS.map((f) => [f, style[f] ?? null]));
  return Response.json({ body: pick(styles.default), pop: pick(styles.emphasis) });
}

/** Restyle the captions. Only how cards are drawn changes, so it is a render. */
export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const patch = await req.json();
  const { code, err } = await runRecut(id, ["--type", JSON.stringify(patch)]);
  if (code === BUSY) return Response.json({ error: err }, { status: 409 });
  if (code === 4) {
    const why = /type not applied: (.*)/.exec(err)?.[1] ?? "That setting isn't allowed.";
    return Response.json({ error: why }, { status: 400 });
  }
  return code === 0
    ? Response.json({ ok: true, at: Date.now() })
    : Response.json({ error: "That didn't apply. Try again." }, { status: 500 });
}
