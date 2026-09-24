import { execFile } from "node:child_process";
import path from "node:path";
import { REPO } from "@/lib/pipeline";

export const runtime = "nodejs";

type Face = { file: string; family: string; genre: string; italic: boolean;
              caps_only: boolean; weights: [number, number] | null };
let faces: Promise<Face[]> | null = null;

/** The shipped faces. Read once per server: they only change with a deploy. */
function catalogue(): Promise<Face[]> {
  faces ??= new Promise((resolve, reject) => {
    execFile(path.join(REPO, ".venv", "bin", "python"), ["-m", "halfheaven.render.fonts"],
      { cwd: REPO, env: { ...process.env, PYTHONPATH: path.join(REPO, "packages", "pipeline") } },
      (error, stdout) => (error ? reject(error) : resolve(JSON.parse(stdout))));
  });
  faces.catch(() => { faces = null; });
  return faces;
}

export async function GET() {
  try {
    return Response.json({ faces: await catalogue() });
  } catch {
    return Response.json({ error: "Couldn't list the fonts." }, { status: 500 });
  }
}
