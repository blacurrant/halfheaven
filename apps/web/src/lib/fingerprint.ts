import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { REPO, workDir } from "@/lib/pipeline";

const PYTHON = path.join(REPO, ".venv", "bin", "python");

/** Every reading carries how much of it to believe, and why. */
export type Reading = {
  value: unknown;
  confidence: "measured" | "inferred" | "absent";
  note: string;
};

export type Fingerprint = {
  source: string;
  duration: number;
  width: number;
  height: number;
  rhythm: Record<string, Reading>;
  structure: Record<string, Reading>;
  text: Record<string, Reading>;
  grade: Record<string, Reading>;
  depth?: Record<string, Reading> | null;
};

export type ReadJob = {
  id: string;
  status: "running" | "done" | "error";
  name: string;
  startedAt: number;
  finishedAt?: number;
  error?: string;
  /** Where the upload is staged. The render step copies this same file, so it
   *  outlives the reading rather than being cleaned up after it. */
  videoPath: string;
  fingerprint?: Fingerprint;
};

const reads = new Map<string, ReadJob>();

export function readJob(id: string) {
  return reads.get(id);
}

/**
 * Measure an uploaded reference.
 *
 * The scan is a couple of times faster than real time, which is too long to
 * hold a request open but far too short to deserve a queue. So it runs as a
 * job the page polls, exactly like a render does - one pattern for both rather
 * than a second kind of waiting for the reader to learn.
 */
export function startRead(opts: { videoPath: string; name: string; depth: boolean }): ReadJob {
  const id = randomUUID().slice(0, 8);
  const job: ReadJob = {
    id, status: "running", name: opts.name,
    videoPath: opts.videoPath, startedAt: Date.now(),
  };
  reads.set(id, job);

  const args = [
    "-W", "ignore",
    "-m", "halfheaven.analyze.fingerprint",
    opts.videoPath,
    "--json",
    // Every third frame. Nothing measured changes inside a tenth of a second,
    // and it is the difference between waiting and giving up.
    "--stride", "3",
  ];
  if (opts.depth) args.push("--depth");

  const child = spawn(PYTHON, args, { cwd: REPO });
  let out = "";
  let err = "";
  child.stdout.on("data", (chunk) => (out += chunk));
  child.stderr.on("data", (chunk) => (err += chunk));
  // A spawn that never starts (no .venv) emits only "error", never "close",
  // so without this the reading would sit at "running" forever.
  child.on("error", (e) => {
    const done = reads.get(id);
    if (!done) return;
    done.finishedAt = Date.now();
    done.status = "error";
    done.error = `Could not start the analyzer: ${e.message}`;
  });

  child.on("close", (code) => {
    const done = reads.get(id);
    if (!done) return;
    done.finishedAt = Date.now();
    if (code === 0) {
      try {
        done.fingerprint = JSON.parse(out) as Fingerprint;
        // Kept beside the reference so the render reads exactly what the user
        // was shown, instead of measuring the same reel a second time.
        fs.writeFileSync(`${opts.videoPath}.fingerprint.json`, out);
        done.status = "done";
      } catch {
        done.status = "error";
        done.error = "The measurement finished but its output could not be read.";
      }
    } else {
      done.status = "error";
      // The last line of a traceback is the part worth showing.
      done.error = err.trim().split("\n").pop() || "The measurement failed.";
    }
  });

  return job;
}

export function stageFile(name: string, bytes: Buffer): string {
  const at = path.join(workDir("references"), `${Date.now()}-${name}`);
  fs.mkdirSync(path.dirname(at), { recursive: true });
  fs.writeFileSync(at, bytes);
  return at;
}
