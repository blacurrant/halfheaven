/**
 * score.ts — deprecated on frontend.
 * Scoring runs in halfhell via POST /v1/score (which spawns halfheaven.analyze.compare).
 * Keep types for Scorecard.tsx.
 */

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

/** @deprecated - call /api/score which proxies to halfhell */
export async function scoreAgainst(): Promise<never> {
  throw new Error("scoreAgainst is deprecated: use halfhell /v1/score via Next.js /api/score");
}
