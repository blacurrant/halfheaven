import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { REPO, jobPaths } from "@/lib/pipeline";

export const runtime = "nodejs";
export const maxDuration = 600;

/** A bed is mixed in the finish pass, so adding or removing one is a render
 *  rather than a re-run: the cut and the transcript are already decided. */
export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const { program, out, work } = jobPaths(id);
  const form = await req.formData();
  const file = form.get("track");
  const remove = String(form.get("remove") ?? "") === "1";

  const args = ["-u", "-m", "halfheaven.recut", "--program", program,
                "--out", out, "--work", work];

  if (remove) {
    args.push("--no-music");
  } else if (file instanceof File) {
    const dest = path.join(work, `music-${file.name.replace(/[^\w.-]/g, "_")}`);
    fs.mkdirSync(work, { recursive: true });
    fs.writeFileSync(dest, Buffer.from(await file.arrayBuffer()));
    args.push("--music", dest);
  } else {
    return Response.json({ error: "No track supplied." }, { status: 400 });
  }

  const code = await new Promise<number>((resolve) => {
    const child = spawn(path.join(REPO, ".venv", "bin", "python"), args, {
      cwd: REPO,
      env: { ...process.env, PYTHONUNBUFFERED: "1",
             PYTHONPATH: path.join(REPO, "packages", "pipeline") },
    });
    child.on("close", (c) => resolve(c ?? 1));
  });

  return code === 0
    ? Response.json({ ok: true, at: Date.now() })
    : Response.json({ error: "That track didn't mix. Try an mp3 or m4a." }, { status: 500 });
}
