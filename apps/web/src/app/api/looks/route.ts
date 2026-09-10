import { spawn } from "node:child_process";
import path from "node:path";
import { REPO } from "@/lib/pipeline";

/** The catalogue lives with the renderer, so it is read from there rather
 *  than duplicated here and left to drift. */
export async function GET() {
  const looks = await new Promise<unknown>((resolve) => {
    const child = spawn(
      path.join(REPO, ".venv", "bin", "python"),
      ["-c", "import json;from halfheaven.render.presets import catalogue;print(json.dumps(catalogue()))"],
      { cwd: REPO, env: { ...process.env, PYTHONPATH: path.join(REPO, "packages", "pipeline") } }
    );
    let out = "";
    child.stdout.on("data", (b) => (out += b.toString()));
    child.on("close", () => { try { resolve(JSON.parse(out)); } catch { resolve([]); } });
  });
  return Response.json({ looks });
}
