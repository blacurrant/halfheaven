import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { REPO, getJob, workDir } from "@/lib/pipeline";

export const runtime = "nodejs";

const FFMPEG = process.env.FFMPEG ?? "/opt/homebrew/bin/ffmpeg";

/** Serves the rendered output (v=after), the untouched footage (v=before), the
 *  reel it was copying (v=reference) or the speaker's matte (v=matte), with
 *  range support so the player can seek and several stay in step. */
export async function GET(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const which = new URL(req.url).searchParams.get("v") ?? "after";
  if (id === "demo") {
    return serve(path.join(REPO, which === "before" ? "noedit.mp4" : "styled.mp4"), req);
  }
  const job = getJob(id);
  if (!job) return new Response("No such job.", { status: 404 });

  const dir = workDir(id);
  if (which === "before") return serve(inside(job.targetPaths?.[0]), req);
  if (which === "reference") return serve(inside(job.referencePath), req);
  if (which === "matte") return serve(await webMatte(dir, job.targetPaths?.[0]), req);
  return serve(path.join(dir, "out.mp4"), req);
}

/** Paths come from the job record, but a file outside the repo is never served. */
function inside(file: string | undefined): string {
  return file && path.resolve(file).startsWith(REPO + path.sep) ? file : "";
}

/**
 * The first take's subject matte, re-encoded so a browser can play it.
 *
 * The pipeline writes mattes as H.264 in grey (4:0:0), which is compact and
 * exactly what the renderer wants, but which browsers will not decode. A 4:2:0
 * copy is made once, the first time the studio asks, and kept beside it.
 */
async function webMatte(dir: string, take: string | undefined): Promise<string> {
  const listing = path.join(dir, "mattes", "mattes.json");
  if (!take || !fs.existsSync(listing)) return "";
  const subject: string | undefined = JSON.parse(fs.readFileSync(listing, "utf8"))[take]?.subject;
  if (!subject || !fs.existsSync(subject)) return "";
  const web = path.join(dir, "mattes", "web.subject.mp4");
  if (fs.existsSync(web)) return web;
  const partial = `${web}.part.mp4`;
  const ok = await new Promise<boolean>((resolve) => {
    const child = spawn(FFMPEG, ["-v", "error", "-y", "-i", subject, "-vf", "scale=-2:640,format=yuv420p",
      "-c:v", "libx264", "-preset", "ultrafast", "-crf", "32", "-an", "-movflags", "+faststart", partial]);
    child.on("close", (code) => resolve(code === 0));
    child.on("error", () => resolve(false));
  });
  if (!ok) return "";
  fs.renameSync(partial, web);
  return web;
}

function serve(file: string, req: Request) {
  if (!file || !fs.existsSync(file)) return new Response("Not ready.", { status: 404 });

  const size = fs.statSync(file).size;
  const range = req.headers.get("range");
  const headers: Record<string, string> = {
    "Content-Type": "video/mp4",
    "Accept-Ranges": "bytes",
    "Cache-Control": "no-store",
  };

  if (range) {
    const [s, e] = range.replace("bytes=", "").split("-");
    const start = Number(s);
    const end = e ? Number(e) : Math.min(start + 1_000_000, size - 1);
    headers["Content-Range"] = `bytes ${start}-${end}/${size}`;
    headers["Content-Length"] = String(end - start + 1);
    return new Response(
      fs.createReadStream(file, { start, end }) as unknown as ReadableStream,
      { status: 206, headers }
    );
  }
  headers["Content-Length"] = String(size);
  return new Response(fs.createReadStream(file) as unknown as ReadableStream, { headers });
}
