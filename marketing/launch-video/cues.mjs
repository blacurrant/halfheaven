// The one clock the picture and the sound both read.
//
// 100 BPM, so a beat is 0.6s and a bar is 2.4s. Scene marks sit on beats and
// every sound effect is named against a mark, so moving a mark moves the
// picture and its sound together.
//
// v3 story: the payoff first (a reel you love, your raw clip, your clip in that
// style), then the loop that costs you (the same edit, reel after reel; an
// editor who takes the look with them), then "Do it once." into the logo.

export const BPM = 100;
export const BEAT = 60 / BPM;
export const FPS = 30;
export const W = 1080;
export const H = 1920;

const b = (n) => +(n * BEAT).toFixed(4); // beats -> seconds

export const M = {
  payoff: 0,          // "Love how that reel looks?" over two phones
  read: b(3),         // the reference is read
  restyle: b(3.5),    // the raw clip takes the style
  now: b(4),          // "Now yours does too."
  payWords: b(4.5),   // its captions, one per half-beat
  payOut: b(7.5),
  loop: b(8),         // "Editing it yourself?" reel #1, #2 ... #37
  everyReel: b(10),   // "3 hours. Every reel."
  editor: b(12),      // "Paying an editor?"
  leave: b(13),       // "Until they leave." the look drains away
  once: b(14),        // "Do it once."
  riser: b(14.25),
  gap: b(15.5),       // a half-beat of silence before the drop
  logo: b(16),        // the drop
  phone: b(18),       // demo: the phone rises
  tap: b(19),         // step 1, reference is tapped
  scan: b(19.5),
  step2: b(22),       // raw footage drops in
  step3: b(24),       // it comes back styled
  cut1: b(25),
  cut2: b(25.5),
  words: b(26),       // captions, one per half-beat
  chat: b(29),        // "bigger captions"
  send: b(31),
  grow: b(31.6),
  end: b(34),         // end card
  price: b(36),
  button: b(37),
  press: b(38),
  final: b(40),       // last chord
};

export const DURATION = b(42.5);
export const TOTAL_FRAMES = Math.round(DURATION * FPS);

export const CAPTION = ["bhai,", "yeh", "game-changer", "hai"];
export const PROMPT = "bigger captions";

// the loop: reel #1 to #37, speeding up, across four beats
export const LOOP_REELS = 37;
export const HOURS_PER_REEL = 3;
export const reelAt = (t) =>
  t < M.loop ? 1 : 1 + Math.floor((LOOP_REELS - 1) * clamp01((t - M.loop) / (M.editor - M.loop)) ** 1.7);
export const reelTime = (n) => M.loop + (M.editor - M.loop) * ((n - 1) / (LOOP_REELS - 1)) ** (1 / 1.7);
function clamp01(x) { return Math.min(1, Math.max(0, x)); }

const keys = (t0, text, per) =>
  [...text].map((ch, i) => ({ t: t0 + i * per, s: ch === " " ? "space" : "key", v: 0.8, seed: i }));

export const CHAT_TYPE_START = M.chat + b(0.5);
export const CHAT_TYPE_PER = 0.055;

export const SFX = [
  // payoff
  { t: M.payoff, s: "whoosh", v: 0.7, dir: 1 },
  { t: M.payoff + 0.02, s: "thud", v: 1 },
  { t: M.payoff + b(1), s: "thud", v: 0.7 },
  { t: M.read, s: "scan", v: 0.6, dur: 0.35 },
  { t: M.read + 0.2, s: "pop", v: 0.6, pitch: 1.3 },
  { t: M.restyle, s: "shimmer", v: 0.9 },
  { t: M.now, s: "thud", v: 0.7 },
  ...CAPTION.map((_, i) => ({ t: M.payWords + b(i * 0.5), s: "pop", v: 0.85, pitch: 1 + i * 0.12 })),
  { t: M.payOut, s: "whoosh", v: 0.7, dir: -1 },

  // the loop: a tick per reel, a snip on every beat, getting frantic
  { t: M.loop, s: "click", v: 1 },
  ...Array.from({ length: LOOP_REELS - 1 }, (_, i) => ({ t: reelTime(i + 2), s: "tick", v: 0.6 })),
  ...[0, 1, 2, 3].map((n) => ({ t: M.loop + b(n), s: "snip", v: 0.55 + n * 0.1 })),
  { t: M.everyReel, s: "pop", v: 0.8, pitch: 0.9 },
  { t: M.editor - 0.05, s: "whoosh", v: 0.6, dir: 1 },
  { t: M.editor + 0.05, s: "pop", v: 0.7 },
  { t: M.leave, s: "drain", v: 0.9 },

  // the loop stops
  { t: M.once, s: "stop", v: 1 },
  { t: M.once + 0.02, s: "thud", v: 1 },
  { t: M.riser, s: "riser", v: 0.9, dur: M.gap - M.riser },
  { t: M.logo, s: "impact", v: 1 },

  // demo
  { t: M.phone, s: "whoosh", v: 0.8, dir: 1 },
  { t: M.tap, s: "click", v: 1 },
  { t: M.scan, s: "scan", v: 0.7, dur: 1.1 },
  { t: M.scan + 0.35, s: "pop", v: 0.7, pitch: 1 },
  { t: M.scan + 0.7, s: "pop", v: 0.7, pitch: 1.2 },
  { t: M.scan + 0.95, s: "pop", v: 0.6, pitch: 1.4 },
  { t: M.scan + 1.1, s: "pop", v: 0.6, pitch: 1.6 },
  { t: M.scan + 1.25, s: "pop", v: 0.6, pitch: 1.8 },

  { t: M.step2 - 0.15, s: "whoosh", v: 0.6, dir: -1 },
  { t: M.step2 + 0.2, s: "drop", v: 1 },

  { t: M.step3, s: "suck", v: 0.7 },
  { t: M.step3 + 0.3, s: "shimmer", v: 0.8 },
  { t: M.cut1, s: "snip", v: 1 },
  { t: M.cut2, s: "snip", v: 0.9 },
  ...CAPTION.map((_, i) => ({ t: M.words + b(i * 0.5), s: "pop", v: 0.9, pitch: 1 + i * 0.12 })),

  { t: M.chat, s: "pop", v: 0.6, pitch: 0.8 },
  ...keys(CHAT_TYPE_START, PROMPT, CHAT_TYPE_PER),
  { t: M.send, s: "send", v: 0.9 },
  { t: M.grow, s: "grow", v: 0.9 },
  { t: M.grow + 0.5, s: "click", v: 0.5 },

  // end card
  { t: M.end - 0.1, s: "whoosh", v: 0.9, dir: 1 },
  { t: M.end + b(0.5), s: "thud", v: 0.6 },
  { t: M.price, s: "pop", v: 0.7 },
  { t: M.button, s: "pop", v: 0.8, pitch: 0.9 },
  { t: M.press, s: "click", v: 1 },
  { t: M.press + 0.02, s: "chime", v: 0.8 },
];
