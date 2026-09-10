import fs from "node:fs";
import path from "node:path";
import { listJobs, startJob, workDir } from "@/lib/pipeline";

export const runtime = "nodejs";
export const maxDuration = 600;

export async function GET() {
  return Response.json({ jobs: listJobs().map(({ log, ...j }) => j) });
}

export async function POST(req: Request) {
  const form = await req.formData();
  const file = form.get("target");
  const styleId = String(form.get("styleId") ?? "");
  const overrides = JSON.parse(String(form.get("overrides") ?? "{}"));
  if (!(file instanceof File)) {
    return Response.json({ error: "No video supplied." }, { status: 400 });
  }

  // Stage the upload where the pipeline can reach it before the job exists,
  // then move it into the job's own directory once we have an id.
  const staging = path.join(workDir("staging"), `${Date.now()}-${file.name}`);
  fs.mkdirSync(path.dirname(staging), { recursive: true });
  fs.writeFileSync(staging, Buffer.from(await file.arrayBuffer()));

  const job = await startJob({ styleId, targetPath: staging, targetName: file.name, overrides });
  return Response.json({ id: job.id });
}
