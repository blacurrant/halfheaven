/** Turning a fingerprint into the sentences a creator would actually say.
 *
 *  The measurements are the evidence, not the message. Someone who points at a
 *  reel wants to hear "it cuts on the beat and the words are a composition,
 *  not subtitles" - the numbers behind that belong one fold down, for the
 *  person who wants to check our working.
 *
 *  Everything here degrades rather than invents: a reading we could not take
 *  produces a shorter sentence, never a confident wrong one.
 */
import type { Fingerprint, Reading } from "@/lib/fingerprint";

export type Group = {
  key: string;
  title: string;
  /** The one-line version. Null when nothing in the group was measurable. */
  headline: string | null;
  detail: string[];
  swatches?: { label: string; hex: string }[];
  readings: [string, Reading][];
};

const val = <T,>(r: Reading | undefined, fallback: T): T =>
  r && r.confidence !== "absent" && r.value !== null ? (r.value as T) : fallback;

const has = (r: Reading | undefined) => !!r && r.confidence !== "absent" && r.value !== null;

function seconds(n: number) {
  return n < 10 ? `${n.toFixed(1)}s` : `${Math.round(n)}s`;
}

export function rhythmGroup(fp: Fingerprint): Group {
  const r = fp.rhythm;
  const median = val(r.median_shot, 0);
  const onBeat = r.on_beat_share;
  const driver = val<string>(r.driver, "");
  const detail: string[] = [];

  let headline: string | null = null;
  if (median > 0) {
    const speed = median <= 1.2 ? "Very fast" : median <= 2.5 ? "Fast" : median <= 4 ? "Steady" : "Slow";
    headline = `${speed} — a new shot about every ${seconds(median)}`;
  }
  if (has(onBeat)) {
    const share = val(onBeat, 0);
    const bpm = val(r.tempo_bpm, 0);
    detail.push(
      share >= 0.8
        ? `Locked to the music — ${Math.round(share * 100)}% of cuts land on a beat${bpm ? ` at ${Math.round(bpm)} BPM` : ""}.`
        : share >= 0.4
          ? `Cut to the talking, but it takes the beat when it can (${Math.round(share * 100)}% of cuts).`
          : `Cut to the talking. The music is underneath, not driving it.`,
    );
  }
  if (driver === "beat") detail.push("This is a montage: the grid is the music, not the speech.");
  if (driver === "speech") detail.push("This is a talking piece: the words decide where it cuts.");

  return { key: "rhythm", title: "Pace", headline, detail, readings: Object.entries(r) };
}

export function textGroup(fp: Fingerprint): Group {
  const t = fp.text;
  const detail: string[] = [];
  const swatches: { label: string; hex: string }[] = [];

  if (!has(t.duty_cycle)) {
    return {
      key: "text",
      title: "Words on screen",
      headline: null,
      detail: ["We found no type in this reel."],
      readings: Object.entries(t),
    };
  }

  const placement = val<string>(t.placement, "");
  const headline =
    placement === "composed"
      ? "A typographic composition — the words move around the frame"
      : placement === "banded"
        ? "Captions that drift within a band"
        : "Captions pinned to one spot, like subtitles";

  const duty = val(t.duty_cycle, 0);
  detail.push(
    duty > 0.9
      ? "Type is on screen almost the whole time."
      : `Type is on screen about ${Math.round(duty * 100)}% of the time — the gaps are deliberate.`,
  );

  const size = val(t.size_pct, 0);
  const range = val<[number, number] | null>(t.size_range, null);
  const describe = (n: number) => (n >= 0.05 ? "large" : n >= 0.025 ? "middling" : "small");
  if (range && range[1] >= range[0] * 2.2) {
    // Two type systems, not one size. Saying "small" here because the median
    // sits between a headline and a sticker would be a confident wrong answer.
    detail.push(
      `Mixed sizes — ${describe(range[1])} type alongside ${describe(range[0])}, so there are two systems at work, not one.`,
    );
  } else if (size) {
    detail.push(`Set ${describe(size)}.`);
  }
  if (val(t.all_caps, false)) detail.push("All caps.");

  // Naming the face is the payoff of measuring character: "contrast 0.36 and
  // leaning" means nothing to anyone, "we'd set this in Playfair Display
  // Italic" is a claim a creator can look at and disagree with.
  const face = val<string | null>(t.typeface, null);
  if (face) {
    const leaning = val(t.italic, false);
    const partner = val<string | null>(t.emphasis_face, null);
    detail.push(
      `Set in something like ${face}${leaning ? " — it leans, so we'd keep the italic" : ""}` +
        (partner ? `, with ${partner} for a stressed word.` : "."),
    );
  }

  // The treatment is what most separates editorial type from burned-in
  // subtitles, so it is said out loud rather than left in the numbers.
  const treatment = val<string | null>(t.decor, null);
  const treatments: Record<string, string> = {
    stroke: "Outlined — a dark stroke round every letter.",
    shadow_soft: "A soft drop shadow, no outline.",
    shadow_hard: "A hard drop shadow, no outline.",
    none: "Bare type — no outline, no shadow.",
  };
  if (treatment && treatments[treatment]) detail.push(treatments[treatment]);

  if (has(t.accent_hex)) {
    const rate = val(t.accent_rate, 0);
    swatches.push({ label: "accent", hex: val<string>(t.accent_hex, "#FFFFFF") });
    detail.push(
      `One word in a different colour on roughly ${Math.round(rate * 100)}% of cards — that contrast is the signature.`,
    );
  } else if (t.accent_hex?.confidence === "absent") {
    detail.push("No deliberate accent colour: the type is one colour throughout.");
  }

  return { key: "text", title: "Words on screen", headline, detail, swatches, readings: Object.entries(t) };
}

export function structureGroup(fp: Fingerprint): Group {
  const s = fp.structure;
  const detail: string[] = [];
  const swatches: { label: string; hex: string }[] = [];

  const share = val(s.card_share, 0);
  const cadence = val(s.card_cadence, 0);
  let headline: string | null = null;

  if (share > 0.05) {
    headline = `${Math.round(share * 100)}% of this isn't footage — it's designed cards`;
    if (cadence > 0) detail.push(`It breaks away to one about every ${seconds(cadence)}.`);
  } else {
    headline = "Straight footage — no cutaway cards";
  }
  if (has(s.plate_hex)) {
    swatches.push({ label: "card", hex: val<string>(s.plate_hex, "#000000") });
    detail.push("That card colour is this creator's brand, not a style — you'd swap it for your own.");
  }

  const stat = val(s.static_share, 0);
  const push = val(s.push_share, 0);
  if (stat > 0.7) detail.push("The camera mostly sits still. The energy comes from cutting, not movement.");
  detail.push(
    push < 0.05
      ? "Effectively no zooms or push-ins."
      : `Push-ins on about ${Math.round(push * 100)}% of frames.`,
  );

  return { key: "structure", title: "Shape", headline, detail, swatches, readings: Object.entries(s) };
}

export function gradeGroup(fp: Fingerprint): Group {
  const g = fp.grade;
  if (!has(g.lab_mean)) {
    return {
      key: "grade",
      title: "Colour",
      headline: null,
      detail: ["Not enough photography here to read a grade."],
      readings: Object.entries(g),
    };
  }
  const [L, a, b] = val<number[]>(g.lab_mean, [50, 0, 0]);
  const light = L < 30 ? "Dark and moody" : L < 45 ? "Warm and low" : L < 60 ? "Natural" : "Bright and airy";
  const cast =
    Math.abs(a) < 3 && Math.abs(b) < 4
      ? "Neutral — barely any colour cast."
      : `Leans ${b < -3 ? "cool" : b > 4 ? "warm" : "neutral"}${a > 4 ? " and a touch magenta" : a < -4 ? " and a touch green" : ""}.`;

  const sampled = val(g.sampled_share, 1);
  const detail = [cast];
  if (sampled < 0.9) {
    detail.push(
      `Read from the ${Math.round(sampled * 100)}% of frames that are photography — the graphic cards are excluded, or their colour would end up on your skin.`,
    );
  }
  return { key: "grade", title: "Colour", headline: light, detail, readings: Object.entries(g) };
}

export function depthGroup(fp: Fingerprint): Group | null {
  if (!fp.depth) return null;
  const d = fp.depth;
  if (!has(d.behind_subject)) {
    return {
      key: "depth",
      title: "Depth",
      headline: null,
      detail: [d.behind_subject?.note ?? "Nothing to compare."],
      readings: Object.entries(d),
    };
  }
  const behind = val(d.behind_subject, false);
  return {
    key: "depth",
    title: "Depth",
    headline: behind ? "Type passes behind the subject" : "Type sits over the top",
    detail: [
      behind
        ? "At least one shot cuts the words off at the subject's outline — the text-behind effect."
        : "The words are drawn over everything, never occluded.",
    ],
    readings: Object.entries(d),
  };
}

export function groupsFor(fp: Fingerprint): Group[] {
  return [rhythmGroup(fp), textGroup(fp), structureGroup(fp), gradeGroup(fp), depthGroup(fp)].filter(
    (g): g is Group => g !== null,
  );
}

/** What we could not take a reading on, so the page can say so out loud. */
export function absences(fp: Fingerprint): string[] {
  const out: string[] = [];
  for (const section of [fp.rhythm, fp.structure, fp.text, fp.grade, fp.depth ?? {}]) {
    for (const [name, reading] of Object.entries(section)) {
      if (reading.confidence === "absent") out.push(`${name.replace(/_/g, " ")} — ${reading.note}`);
    }
  }
  return out;
}
