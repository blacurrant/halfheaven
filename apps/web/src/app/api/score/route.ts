import fs from "node:fs";
import path from "node:path";

import { getJob, workDir } from "@/lib/pipeline";
import { scoreAgainst } from "@/lib/score";

export const runtime = "nodejs";
export const maxDuration = 300; // Vercel Hobby's ceiling; Next does not enforce it locally

export async function POST(req: Request) {
  const { jobId } = await req.json();
  const job = getJob(String(jobId ?? ""));
  if (!job) return Response.json({ error: "No such job." }, { status: 404 });
  if (job.status !== "done") return Response.json({ error: "That render isn't finished." }, { status: 400 });

  const output = path.join(workDir(job.id), "out.mp4");
  if (!job.referencePath || !fs.existsSync(job.referencePath) || !fs.existsSync(output)) {
    return Response.json({ error: "The files to compare are no longer on disk." }, { status: 400 });
  }
  try {
    return Response.json(await scoreAgainst(output, job.referencePath));
  } catch (e) {
    return Response.json({ error: (e as Error).message }, { status: 500 });
  }
}
