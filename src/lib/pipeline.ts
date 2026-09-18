/**
 * pipeline.ts — frontend types & constants ONLY.
 *
 * The heavy lifting now lives in halfhell (FastAPI backend). This file no
 * longer spawns Python; it just re-exports the Job/Receipt types and stage
 * table that the UI consumes. API routes forward to halfhell via
 * @/lib/halfhell instead of spawning `python -m halfheaven.cli`.
 *
 * Kept for backwards-compat: the studio page imports `STAGES` and `Job`.
 */

export type StageKey = "analyse" | "transcribe" | "edit" | "plan" | "render";

export const STAGES: { key: StageKey; label: string }[] = [
  { key: "analyse", label: "Reading the reference" },
  { key: "transcribe", label: "Transcribing" },
  { key: "edit", label: "Editorial pass" },
  { key: "plan", label: "Planning the cut" },
  { key: "render", label: "Rendering" },
];

export type Job = {
  id: string;
  status: "running" | "done" | "error";
  stageIndex: number;
  progress: number;
  styleId: string;
  referenceName?: string;
  referencePath?: string;
  targetName: string;
  startedAt: number;
  finishedAt?: number;
  error?: string;
  log?: string[];
  tail?: string[];
  profile?: Record<string, unknown>;
  receipt?: Receipt;
  segments?: number;
  punchAt?: number[];
  clips?: { start: number; end: number }[];
};

export type Receipt = {
  clips: number;
  captions: number;
  emphasised: number;
  punches: number;
  wordsCut: number;
  sourceSeconds: number;
  outputSeconds: number;
  emphasisWords: string[];
};

export type Style = { id: string; name: string; file: string; hint: string };

/** @deprecated - backend now owns storage; kept for any leftover imports. */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function workDir(id: string): string {
  throw new Error("workDir() is deprecated: storage lives in halfhell backend");
}

/** @deprecated - use halfhell API via /api/styles instead */
export function availableStyles(): Style[] {
  return [];
}

/** @deprecated - jobs are now in halfhell; use GET /api/jobs/[id] which proxies */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function getJob(_id: string): Job | undefined {
  return undefined;
}
export function listJobs(): Job[] {
  return [];
}
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function jobPaths(_id: string): { program: string; out: string; work: string } {
  throw new Error("jobPaths() is deprecated: use halfhell backend");
}
export async function startJob(): Promise<never> {
  throw new Error("startJob() is deprecated: POST /api/jobs proxies to halfhell");
}
export async function recut(): Promise<never> {
  throw new Error("recut() is deprecated: use POST /api/jobs/[id]/captions|look|music");
}

// Keep REPO export for any stray import, but mark deprecated
export const REPO = process.cwd();
