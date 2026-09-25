import fs from "node:fs";
import path from "node:path";
import { jobPaths } from "@/lib/pipeline";

export const runtime = "nodejs";

/** One look's preview still. The name comes from the URL, so it is held to the
 *  shape the previews module writes before it touches the disk. */
export async function GET(_req: Request, ctx: { params: Promise<{ id: string; file: string }> }) {
  const { id, file } = await ctx.params;
  if (!/^[\w-]+\.jpg$/.test(file)) return new Response("Not found.", { status: 404 });
  const at = path.join(jobPaths(id).work, "previews", file);
  if (!fs.existsSync(at)) return new Response("Not found.", { status: 404 });
  return new Response(fs.readFileSync(at) as unknown as BodyInit, {
    headers: { "Content-Type": "image/jpeg", "Cache-Control": "private, max-age=31536000, immutable" },
  });
}
