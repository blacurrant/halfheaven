import fs from "node:fs";
import path from "node:path";
import { REPO } from "@/lib/pipeline";

export const runtime = "nodejs";

const FONTS = path.join(REPO, "packages", "pipeline", "halfheaven", "assets", "fonts");

/** One shipped face, so the picker can show each name in its own letters. */
export async function GET(_req: Request, ctx: { params: Promise<{ file: string }> }) {
  const { file } = await ctx.params;
  // A bare file name and nothing else: this route reads from disk.
  if (!/^[A-Za-z0-9_-]+\.ttf$/.test(file)) return new Response("Not found", { status: 404 });
  const at = path.join(FONTS, file);
  if (!fs.existsSync(at)) return new Response("Not found", { status: 404 });
  return new Response(fs.readFileSync(at), {
    headers: { "content-type": "font/ttf", "cache-control": "public, max-age=86400" },
  });
}
