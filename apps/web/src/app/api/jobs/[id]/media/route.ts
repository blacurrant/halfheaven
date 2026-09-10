import fs from "node:fs";
import path from "node:path";
import { REPO, getJob, workDir } from "@/lib/pipeline";

export const runtime = "nodejs";

/** Serves the rendered output, or the untouched source, with range support so
 *  the player can seek and the two sides of the comparison stay in step. */
export async function GET(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const which = new URL(req.url).searchParams.get("v") ?? "after";
  if (id === "demo") {
    return serve(path.join(REPO, which === "before" ? "noedit.mp4" : "styled.mp4"), req);
  }
  const job = getJob(id);
  if (!job) return new Response("No such job.", { status: 404 });

  const dir = workDir(id);
  const file =
    which === "before"
      ? fs.readdirSync(path.join(REPO, ".web-work", "staging"))
          .map((f) => path.join(REPO, ".web-work", "staging", f))
          .sort()
          .find((f) => f.endsWith(job.targetName) || job.targetName.endsWith("takes")) ?? ""
      : path.join(dir, "out.mp4");

  return serve(file, req);
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
