import { spawn } from "node:child_process";
import path from "node:path";
import { REPO, jobPaths } from "@/lib/pipeline";

export const runtime = "nodejs";
export const maxDuration = 300; // Vercel Hobby's ceiling; Next does not enforce it locally

/** Switching a caption look only changes captions, so it is a restyle and a
 *  render - the transcript and the cut are already decided. */
export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const { preset } = await req.json();
  const { program, out, work } = jobPaths(id);

  const code = await new Promise<number>((resolve) => {
    const child = spawn(
      path.join(REPO, ".venv", "bin", "python"),
      ["-u", "-m", "halfheaven.recut", "--program", program, "--out", out,
       "--work", work, "--preset", String(preset ?? "")],
      { cwd: REPO, env: { ...process.env, PYTHONUNBUFFERED: "1",
                          PYTHONPATH: path.join(REPO, "packages", "pipeline") } }
    );
    child.on("close", (c) => resolve(c ?? 1));
  });

  return code === 0
    ? Response.json({ ok: true, at: Date.now() })
    : Response.json({ error: "That look didn't apply. Try another." }, { status: 500 });
}
