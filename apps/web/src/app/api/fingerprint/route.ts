import { startRead, stageFile } from "@/lib/fingerprint";

export const runtime = "nodejs";
export const maxDuration = 600;

export async function POST(req: Request) {
  const form = await req.formData();
  const file = form.get("reference");
  if (!(file instanceof File)) {
    return Response.json({ error: "No video supplied." }, { status: 400 });
  }
  // Subject segmentation loads a model and takes minutes, so it is asked for
  // rather than assumed.
  const depth = String(form.get("depth") ?? "") === "1";

  const at = stageFile(file.name, Buffer.from(await file.arrayBuffer()));
  const job = startRead({ videoPath: at, name: file.name, depth });
  return Response.json({ id: job.id });
}
