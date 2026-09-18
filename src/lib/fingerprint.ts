/**
 * fingerprint.ts — types only, post-split.
 *
 * Measurement now runs inside halfhell (POST /v1/fingerprint). The Next.js
 * api routes proxy there via @/lib/halfhell. This file keeps the
 * Fingerprint/Reading types that Readout.tsx imports for display.
 */

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
  videoPath: string;
  fingerprint?: Fingerprint;
};

/** @deprecated - staging now happens in halfhell via multipart upload */
export function stageFile(): string {
  throw new Error("stageFile() is deprecated: upload directly to halfhell");
}
export function readJob(): ReadJob | undefined {
  return undefined;
}
export function startRead(): ReadJob {
  throw new Error("startRead() is deprecated: POST /api/fingerprint proxies to halfhell");
}
