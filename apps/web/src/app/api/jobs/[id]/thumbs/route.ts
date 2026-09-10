import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { jobPaths } from "@/lib/pipeline";

export const runtime = "nodejs";

const FFMPEG = process.env.FFMPEG ?? "/opt/homebrew/bin/ffmpeg";
const FFPROBE = process.env.FFPROBE ?? "/opt/homebrew/bin/ffprobe";
export const THUMB_W = 48;

const run = (bin: string, args: string[]) =>
  new Promise<string>((resolve, reject) => {
    const c = spawn(bin, args);
    let out = "";
    c.stdout.on("data", (b) => (out += b.toString()));
    c.on("close", (code) => (code === 0 ? resolve(out) : reject(new Error(`${bin} ${code}`))));
  });

/** One frame per second, tiled into a single strip. A sprite sheet keeps the
 *  timeline to one request no matter how long the video is. */
export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const { out, work } = jobPaths(id);
  if (!fs.existsSync(out)) return new Response("Not ready.", { status: 404 });

  const sheet = path.join(work, "timeline_strip.jpg");
  const fresh =
    fs.existsSync(sheet) && fs.statSync(sheet).mtimeMs > fs.statSync(out).mtimeMs;

  if (!fresh) {
    const duration = Number(
      (await run(FFPROBE, ["-v", "error", "-show_entries", "format=duration",
                           "-of", "csv=p=0", out])).trim()
    );
    const count = Math.max(1, Math.ceil(duration));
    await run(FFMPEG, ["-v", "error", "-y", "-i", out,
      "-vf", `fps=1,scale=${THUMB_W}:-2,tile=${count}x1`, "-frames:v", "1", "-q:v", "5", sheet]);
  }

  return new Response(fs.readFileSync(sheet) as unknown as BodyInit, {
    headers: { "Content-Type": "image/jpeg", "Cache-Control": "no-store" },
  });
}
