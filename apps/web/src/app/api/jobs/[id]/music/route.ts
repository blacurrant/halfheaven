import fs from "node:fs";
import path from "node:path";
import { BUSY, jobPaths, runRecut } from "@/lib/pipeline";

export const runtime = "nodejs";
export const maxDuration = 300; // Vercel Hobby's ceiling; Next does not enforce it locally

/** A bed is mixed in the finish pass, so adding or removing one is a render
 *  rather than a re-run: the cut and the transcript are already decided. */
export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const { work } = jobPaths(id);
  const form = await req.formData();
  const file = form.get("track");
  const remove = String(form.get("remove") ?? "") === "1";

  let args: string[];
  if (remove) {
    args = ["--no-music"];
  } else if (file instanceof File) {
    const dest = path.join(work, `music-${file.name.replace(/[^\w.-]/g, "_")}`);
    fs.mkdirSync(work, { recursive: true });
    fs.writeFileSync(dest, Buffer.from(await file.arrayBuffer()));
    args = ["--music", dest];
  } else {
    return Response.json({ error: "No track supplied." }, { status: 400 });
  }

  const { code, err } = await runRecut(id, args);
  if (code === BUSY) return Response.json({ error: err }, { status: 409 });
  return code === 0
    ? Response.json({ ok: true, at: Date.now() })
    : Response.json({ error: "That track didn't mix. Try an mp3 or m4a." }, { status: 500 });
}
