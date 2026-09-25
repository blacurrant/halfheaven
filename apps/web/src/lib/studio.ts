/** What the studio says while it works, and the small sums behind it.
 *
 *  Everything a creator is told comes from something the pipeline reported
 *  (lib/pipeline Facts) or measured (the reel's fingerprint). The one estimate,
 *  how long an edit usually takes, is always worded as "usually" or "about".
 */
import type { Fingerprint, Reading } from "@/lib/fingerprint";
import type { Facts } from "@/lib/pipeline";
import { gradeGroup } from "@/lib/readout";

export const clock = (s: number) =>
  `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

const val = <T,>(r: Reading | undefined, fallback: T): T =>
  r && r.confidence !== "absent" && r.value !== null && r.value !== undefined ? (r.value as T) : fallback;

/** CIELAB (D65) to an sRGB hex, for showing a measured grade as a colour. */
export function labToHex([L, a, b]: number[]): string {
  const fy = (L + 16) / 116, fx = a / 500 + fy, fz = fy - b / 200;
  const f = (t: number) => (t ** 3 > 0.008856 ? t ** 3 : (t - 16 / 116) / 7.787);
  const x = 0.95047 * f(fx), y = f(fy), z = 1.08883 * f(fz);
  const lin = [x * 3.2406 - y * 1.5372 - z * 0.4986, -x * 0.9689 + y * 1.8758 + z * 0.0415,
               x * 0.0557 - y * 0.204 + z * 1.057];
  const byte = (c: number) => {
    const g = c > 0.0031308 ? 1.055 * c ** (1 / 2.4) - 0.055 : 12.92 * c;
    return Math.round(Math.max(0, Math.min(1, g)) * 255).toString(16).padStart(2, "0");
  };
  return `#${lin.map(byte).join("")}`;
}

// ---- how long ------------------------------------------------------------

/** Measured on this machine: 56s for a 12s clip, 111s for 61s, 124s for 106s.
 *  A fixed start-up plus a little under real time. */
export const editSeconds = (sourceSeconds: number) => 45 + 0.9 * sourceSeconds;

export function about(seconds: number): string {
  if (seconds < 50) return "under a minute";
  const minutes = Math.round(seconds / 60);
  return minutes <= 1 ? "about a minute" : `about ${minutes} min`;
}

// ---- what we read ----------------------------------------------------------

export type Chip = { key: string; text: string; icon?: "pace" | "type"; swatch?: string };

/** The reel in three chips: its pace, its type, its colour. Each is left out
 *  when it could not be measured rather than guessed. */
export function readChips(fp: Fingerprint): Chip[] {
  const chips: Chip[] = [];
  const median = val(fp.rhythm.median_shot, 0);
  if (val<string>(fp.rhythm.driver, "") === "beat") chips.push({ key: "pace", icon: "pace", text: "Cuts on the beat" });
  else if (median > 0) chips.push({ key: "pace", icon: "pace", text: `A cut every ${median < 10 ? median.toFixed(1) : Math.round(median)}s` });

  const face = val<string | null>(fp.text.typeface, null);
  const accent = val<string | null>(fp.text.accent_hex, null);
  if (face) chips.push({ key: "type", icon: "type", text: `Set in ${face}`, swatch: accent ?? undefined });
  else if (val(fp.text.duty_cycle, 0) === 0) chips.push({ key: "type", icon: "type", text: "No captions" });

  const grade = gradeGroup(fp);
  const lab = val<number[] | null>(fp.grade.lab_mean, null);
  if (grade.headline && lab) chips.push({ key: "grade", text: grade.headline, swatch: labToHex(lab) });
  return chips;
}

/** How the reel sets its words, so the studio can speak in the same voice. */
export type Voice = { face: string | null; stressFace: string | null; stress: string | null; caps: boolean };
export function voiceOf(fp: Fingerprint | undefined): Voice {
  if (!fp) return { face: null, stressFace: null, stress: null, caps: false };
  return {
    face: val<string | null>(fp.text.typeface, null),
    stressFace: val<string | null>(fp.text.emphasis_face, null),
    stress: val<string | null>(fp.text.accent_hex, null),
    caps: val(fp.text.all_caps, false),
  };
}

// ---- while it edits --------------------------------------------------------

/** One narration line: `lead`, then the stressed word, then `tail`. */
export type Line = { key: string; lead: string; stress: string; tail: string };

export const STAGE_NAMES = ["Studying the reel", "Listening", "Cutting", "Framing and colour", "Putting it together"];

/** Every line the edit has earned so far, in the order the pipeline earned
 *  them. A line exists only once its stage has started or its fact printed. */
export function narrate(stage: number, facts: Facts | undefined, uploading: boolean): Line[] {
  if (uploading) return [{ key: "up", lead: "Sending your ", stress: "footage", tail: "" }];
  const f = facts ?? {};
  const lines: Line[] = [{ key: "s0", lead: "Studying the ", stress: "reel", tail: "" }];
  if (stage >= 1) lines.push({ key: "s1", lead: "Listening to ", stress: "you", tail: "" });
  if (f.words !== undefined) lines.push({ key: "words", lead: "", stress: `${f.words}`, tail: " words, heard" });
  if (stage >= 2) lines.push({ key: "s2", lead: "Cutting the ", stress: "stumbles", tail: "" });
  if (f.wordsCut !== undefined) {
    lines.push(f.wordsCut > 0
      ? { key: "cut", lead: "", stress: `${f.wordsCut}`, tail: f.wordsCut === 1 ? " stumble gone" : " stumbles gone" }
      : { key: "cut", lead: "Clean take, ", stress: "nothing", tail: " to cut" });
  }
  if (stage >= 3) {
    if (f.reframed) lines.push({ key: "frame", lead: "Following ", stress: "you", tail: " in the frame" });
    if (f.gradeFrom) lines.push({ key: "grade", lead: "Your light, ", stress: "their", tail: " grade" });
    if (f.subjectSeconds !== undefined) lines.push({ key: "you", lead: "Found ", stress: "you", tail: " in the frame" });
    if (f.captions !== undefined) lines.push({ key: "caps", lead: "", stress: `${f.captions}`, tail: " captions, set" });
  }
  if (stage >= 4) lines.push({ key: "s4", lead: "Putting it ", stress: "together", tail: "" });
  return lines;
}

/** A stretch of what was said around the first cut, with the cut words marked.
 *  Cuts are [start, stop) word ranges. */
export function snippet(words: string[], cuts: [number, number][], reach = 9) {
  if (!words.length) return null;
  const first = cuts[0];
  const from = first ? Math.max(0, first[0] - reach) : 0;
  const to = Math.min(words.length, first ? first[1] + reach * 2 : reach * 2);
  const cut = (i: number) => cuts.some(([a, b]) => i >= a && i < b);
  return {
    before: from > 0,
    after: to < words.length,
    words: words.slice(from, to).map((text, k) => ({ text, cut: cut(from + k) })),
  };
}
