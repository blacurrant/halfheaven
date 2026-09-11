import { spawn } from "node:child_process";
import path from "node:path";

import { REPO } from "@/lib/pipeline";

const PYTHON = path.join(REPO, ".venv", "bin", "python");

export type ScoreRow = {
  group: string;
  field: string;
  label: string;
  verdict: "match" | "near" | "miss" | "unscored";
  ours: unknown;
  theirs: unknown;
  gap: number | null;
  why: string;
};

export type Score = { score: number; rows: ScoreRow[] };

/**
 * How close the render landed to the reel it was copying.
 *
 * Worth showing rather than keeping to ourselves: it is the only honest answer
 * to "did that work", and a user who can see which traits we missed is being
 * told where not to trust us. It measures resemblance, not quality - a page
 * showing it should say so.
 */
export function scoreAgainst(output: string, reference: string): Promise<Score> {
  return new Promise((resolve, reject) => {
    const child = spawn(
      PYTHON,
      ["-W", "ignore", "-m", "halfheaven.analyze.compare", output, reference, "--json", "--stride", "3"],
      { cwd: REPO },
    );
    let out = "";
    let err = "";
    child.stdout.on("data", (c) => (out += c));
    child.stderr.on("data", (c) => (err += c));
    child.on("close", (code) => {
      if (code !== 0) return reject(new Error(err.trim().split("\n").pop() || "scoring failed"));
      try {
        resolve(JSON.parse(out) as Score);
      } catch {
        reject(new Error("could not read the scorecard"));
      }
    });
  });
}
