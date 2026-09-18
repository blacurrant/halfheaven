/** Turning measurements into the words a creator would use.
 *  Nobody making Reels wants to read "Grade (LAB L) 20.9". */

export function pace(cutsPerMin: number, medianShot: number) {
  const s = Math.round(medianShot);
  if (cutsPerMin >= 20) return { t: "Rapid fire", d: `A new shot about every ${s} seconds` };
  if (cutsPerMin >= 11) return { t: "Snappy", d: `Cuts roughly every ${s} seconds` };
  if (cutsPerMin >= 6) return { t: "Steady", d: `Cuts roughly every ${s} seconds` };
  return { t: "Slow and calm", d: `Long takes — about ${s} seconds each` };
}

export function silence(maxSilence: number) {
  if (maxSilence <= 0.15) return { t: "Tight", d: "Almost no dead air between words" };
  if (maxSilence <= 0.35) return { t: "Natural", d: "Keeps a beat between thoughts" };
  return { t: "Roomy", d: "Lets pauses breathe" };
}

export function mood(labL: number) {
  if (labL < 25) return { t: "Moody", d: "Dark, cinematic, low light" };
  if (labL < 40) return { t: "Warm", d: "Soft and golden" };
  if (labL < 55) return { t: "Natural", d: "True to how it was shot" };
  return { t: "Bright", d: "Light and airy" };
}

export function capSize(sizePct: number) {
  if (sizePct >= 0.09) return "Big";
  if (sizePct >= 0.055) return "Medium";
  return "Small";
}

export function capPlace(y: number) {
  if (y <= 0.35) return "near the top";
  if (y <= 0.62) return "in the middle";
  if (y <= 0.8) return "low on screen";
  return "at the bottom";
}

/** CSS family for a detected type category, so we can show the face itself. */
export function faceFamily(category: string) {
  if (category === "mono") return "var(--font-geist-mono), ui-monospace, monospace";
  if (category === "didone" || category === "slab") return "var(--font-didone), Georgia, serif";
  return "var(--font-ui), system-ui, sans-serif";
}
