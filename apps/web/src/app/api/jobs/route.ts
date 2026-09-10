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
  // Several takes are treated as one, in the order they were chosen.
  const files = form.getAll("target").filter((f): f is File => f instanceof File);
  const file = files[0];
  const styleId = String(form.get("styleId") ?? "");
  const overrides = JSON.parse(String(form.get("overrides") ?? "{}"));
  if (!file) {
    return Response.json({ error: "No video supplied." }, { status: 400 });
  }

  // Stage the upload where the pipeline can reach it before the job exists,
  // then move it into the job's own directory once we have an id.
  const stamp = Date.now();
  const staged: string[] = [];
  for (const [index, item] of files.entries()) {
    const at = path.join(workDir("staging"), `${stamp}-${index}-${item.name}`);
    fs.mkdirSync(path.dirname(at), { recursive: true });
    fs.writeFileSync(at, Buffer.from(await item.arrayBuffer()));
    staged.push(at);
  }

  const name = files.length === 1 ? file.name : `${files.length} takes`;
  const job = await startJob({ styleId, targetPaths: staged, targetName: name, overrides });
  return Response.json({ id: job.id });
}
