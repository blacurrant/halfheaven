// The picture. seek(t) sets every element from the clock alone - no CSS
// transitions, no timers - so frame 412 comes out the same on every render and
// render.mjs can step through it one frame at a time.

import {
  BEAT, FPS, M, PROMPT, CHAT_TYPE_START, CHAT_TYPE_PER, HOURS_PER_REEL, reelAt, reelTime,
} from "./cues.mjs";

const PAPER = "#EFE5D2";
const THEATRE = "#2E2630";
const CREAM = "#EFE5D2";
const INK = "#574B55";

// ---- motion helpers ---------------------------------------------------------------

const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, k) => a + (b - a) * k;
const E = {
  lin: (x) => x,
  out: (x) => 1 - (1 - x) ** 3,
  in: (x) => x ** 3,
  io: (x) => (x < 0.5 ? 4 * x ** 3 : 1 - (-2 * x + 2) ** 3 / 2),
  back: (x) => 1 + 2.70158 * (x - 1) ** 3 + 1.70158 * (x - 1) ** 2,
  expo: (x) => (x === 1 ? 1 : 1 - 2 ** (-10 * x)),
};
// progress of a move starting at t0 lasting d, eased
const P = (t, t0, d, e = E.out) => e(clamp((t - t0) / d));

function put(el, { x = 0, y = 0, s = 1, sx, sy, r = 0, o = 1, blur = 0, skew = 0 } = {}) {
  el.style.transform = `translate(${x}px,${y}px) rotate(${r}deg) skewX(${skew}deg) scale(${sx ?? s},${sy ?? s})`;
  el.style.opacity = o;
  el.style.filter = blur > 0.05 ? `blur(${blur}px)` : "none";
}

const hash = (a, b) => {
  let h = (a * 374761393 + b * 668265263) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return (h ^ (h >>> 16)) >>> 0;
};

// a word landing hard: big, blurred, then set
const slam = (t, t0, from = 1.4) => {
  const k = P(t, t0, 0.22);
  return { s: lerp(from, 1, k), o: clamp((t - t0) / 0.05), blur: lerp(16, 0, k) };
};
// a word rising into place
const rise = (t, t0, dy = 50, d = 0.35) => {
  const k = P(t, t0, d);
  return { y: lerp(dy, 0, k), o: clamp((t - t0) / (d * 0.6)) };
};

// ---- elements ----------------------------------------------------------------------

const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
let el;

export async function ready() {
  await document.fonts.ready;
  await Promise.all([
    '800 150px "Bricolage Grotesque"', '700 140px "Bricolage Grotesque"',
    '600 40px "Plus Jakarta Sans"', '700 40px "Plus Jakarta Sans"', '800 40px "Plus Jakarta Sans"',
  ].map((f) => document.fonts.load(f, "Halfheaven ₹10–30k ’")));

  // the wordmark, one span per letter
  const word = $("#logo .word");
  word.innerHTML = [...word.textContent].map((c) => `<span class="w">${c}</span>`).join("");

  // film grain: a few noise tiles, cycled per frame
  const tiles = [];
  for (let n = 0; n < 6; n++) {
    const c = document.createElement("canvas");
    c.width = c.height = 256;
    const g = c.getContext("2d");
    const img = g.createImageData(256, 256);
    for (let i = 0; i < img.data.length; i += 4) {
      const v = hash(i, n + 1) & 255;
      img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
      img.data[i + 3] = 255;
    }
    g.putImageData(img, 0, 0);
    tiles.push(`url(${c.toDataURL()})`);
  }

  el = {
    bgBase: $("#bgBase"), bgWipe: $("#bgWipe"), world: $("#world"),
    s: [1, 2, 3, 4, 5, 6].map((n) => $(`#s${n}`)),
    payHead1: $$("#payHead1 .w"), payHead2: $$("#payHead2 .w"), phL: $("#phL"), phR: $("#phR"),
    phRstyled: $("#phRstyled"), payEdge: $("#phR .wipeEdge"), payScan: $("#phL .scanline"),
    payWash: $("#phL .scanwash"), payCaps: $$("#phR .caps .w"), payArrow: $("#payArrow"),
    labL: $("#labL"), labR1: $("#labR1"), labR2: $("#labR2"),
    loopHead1: $("#loopHead1"), loopHead2: $("#loopHead2"), card: $("#card"), cardStyled: $("#cardStyled"),
    cardDrain: $("#cardDrain"), reelNo: $(".reelNo"), tallyTime: $("#tallyTime"), tallyMoney: $("#tallyMoney"),
    tallyReels: $("#tallyReels"), tallyReelsLabel: $("#tallyTime p"), tallyHours: $("#tallyHours"),
    loopSub1: $("#loopSub1"), loopSub2: $("#loopSub2"), onceBox: $(".once"), once: $$(".once .w"),
    logo: $("#logo .in"), mark: $("#logo .mark"), word, letters: $$("#logo .word .w"),
    ring: $("#ring"), tagline: $("#tagline"),
    steps: $$(".step"), phone: $("#phone"), screen: $("#phone .screen"),
    ref: $("#ref"), refBars: $$("#ref .bars b"), refCapWord: $("#ref .cap b"),
    scanline: $("#ref .scanline"), scanwash: $("#ref .scanwash"),
    raw: $("#raw"), styled: $("#styled"), frame: $("#styled .frame"), edge: $("#phone .wipeEdge"),
    styledBars: $$("#styled .bars b"), flash: $("#styled .flash"), toast: $(".toast"),
    caps: $("#styled .caps"), capWords: $$("#styled .caps .w"),
    chips: [$("#chipCuts"), $("#chipType"), $("#chipColour")], rhythm: $$(".rhythm i"), swatches: $$(".swatches i"),
    strip: $("#strip"), stripFill: $("#strip .fill"), stripCuts: $$("#strip .cut"),
    chat: $("#chat"), chatPh: $("#chat .ph"), chatText: $("#chat .text"), chatCaret: $("#chat .caret"),
    send: $("#chat .send"), bubble: $("#bubble"), touch: $("#touch"),
    end1: $(".end1 .w"), end2: $(".end2 .w"), price: $(".price .w"), btn: $(".btn"), bio: $(".bio"),
    grain: $("#grain"), tiles,
    logoSize: [$("#logo .in").offsetWidth, $("#logo .in").offsetHeight],
  };
  el.stripCuts.forEach((c, i) => { c.style.left = `${((i ? M.cut2 : M.cut1) - M.step3) / 3 * 470 - 3}px`; });
}

// ---- the background, which changes colour through wipes ---------------------------------

const WIPES = [
  { t: -1, color: THEATRE },
  { t: M.loop, color: PAPER, kind: "circle", x: 540, y: 960, dur: 0.42 },
  { t: M.once, color: THEATRE, kind: "circle", x: 540, y: 900, dur: 0.35 },
  { t: M.logo, color: PAPER, kind: "circle", x: 540, y: 880, dur: 0.32 },
  { t: M.end, color: THEATRE, kind: "up", dur: 0.45 },
];

function background(t) {
  let i = WIPES.findLastIndex((w) => t >= w.t);
  const w = WIPES[i];
  const k = w.dur ? P(t, w.t, w.dur, E.io) : 1;
  el.bgBase.style.background = i > 0 ? WIPES[i - 1].color : w.color;
  el.bgWipe.style.background = w.color;
  el.bgWipe.style.clipPath =
    w.kind === "circle" ? `circle(${k * 1300}px at ${w.x}px ${w.y}px)`
    : w.kind === "up" ? `inset(${(1 - k) * 100}% 0 0 0)` : "none";
}

// ---- camera shake, from the heavy hits ----------------------------------------------------

const HITS = [
  [M.payoff, 12], [M.payoff + BEAT, 8], [M.now, 8], [M.once, 18], [M.logo, 22],
  [M.step2 + 0.2, 7], [M.end + BEAT / 2, 10],
];
function shake(t) {
  let x = 0, y = 0;
  HITS.forEach(([h, a], i) => {
    if (t < h) return;
    const d = t - h, k = a * Math.exp(-d * 16);
    x += k * Math.sin(d * 75 + i);
    y += k * Math.cos(d * 63 + i * 2);
  });
  // the riser tightens the frame
  if (t > M.riser && t < M.gap) {
    const k = ((t - M.riser) / (M.gap - M.riser)) ** 2 * 5;
    x += k * Math.sin(t * 97);
    y += k * Math.cos(t * 83);
  }
  el.world.style.transform = `translate(${x}px,${y}px)`;
}

// ---- scenes -------------------------------------------------------------------------------

const show = (node, on) => { node.style.display = on ? "" : "none"; };

function payoff(t) {
  show(el.s[0], t < M.loop + 0.1);
  const out = P(t, M.payOut, 0.45, E.in);

  // the question lands word by word, then lifts away for the answer
  const lift = P(t, M.now - 0.12, 0.2, E.in);
  el.payHead1.forEach((w, i) => {
    const s = slam(t, M.payoff + i * 0.15, 1.3);
    put(w, { ...s, y: -lift * 40, o: s.o * (1 - lift) });
  });
  el.payHead2.forEach((w, i) => {
    const r = rise(t, M.now + i * 0.08, 50, 0.3);
    put(w, { y: r.y - out * 60, o: r.o * (1 - out) });
  });

  // two phones: the reel you love, and your raw clip
  const inL = P(t, M.payoff, 0.5), inR = P(t, M.payoff + 0.1, 0.5);
  const push = 1 + 0.04 * P(t, M.restyle, 1.2, E.io);
  put(el.phL, { x: lerp(-700, 0, inL), y: out * 1400, r: -3 });
  put(el.phR, { x: lerp(700, 0, inR), y: out * 1500, r: 3, s: push });

  // the reference is read...
  const sk = clamp((t - M.read) / 0.35);
  const scanning = t >= M.read && t < M.read + 0.5;
  el.payScan.style.transform = `translateY(${sk * 691}px)`;
  el.payScan.style.opacity = scanning ? 1 - P(t, M.read + 0.35, 0.15) : 0;
  el.payWash.style.height = `${sk * 691}px`;
  el.payWash.style.opacity = scanning ? 1 - P(t, M.read + 0.35, 0.15) : 0;
  const a = P(t, M.read + 0.1, 0.35, E.back);
  const beat = t > M.read ? 1 + 0.06 * Math.exp(-(((t - M.read) % BEAT) * 8)) : 1;
  put(el.payArrow, { s: a * beat, o: clamp((t - M.read - 0.1) / 0.05) * (1 - out), y: out * 1400 });

  // ...and the raw clip takes the style
  const wk = P(t, M.restyle, 0.45, E.io);
  const xt = lerp(-35, 135, wk), xb = xt - 30;
  el.phRstyled.style.clipPath = `polygon(0 0,${xt}% 0,${xb}% 100%,0 100%)`;
  el.payEdge.style.display = wk > 0 && wk < 1 ? "" : "none";
  el.payEdge.style.left = `${((xt + xb) / 2 / 100) * 380 - 4}px`;
  el.payEdge.style.transform = `rotate(${(Math.atan2(0.3 * 380, 691) * 180) / Math.PI}deg)`;
  el.payCaps.forEach((w, i) => {
    const t0 = M.payWords + i * BEAT / 2;
    put(w, { s: lerp(0.3, 1, P(t, t0, 0.3, E.back)), o: clamp((t - t0) / 0.06) });
  });

  const lab = (node, t0, t1 = Infinity) => {
    const r = rise(t, t0, 24, 0.3), x = P(t, t1, 0.2, E.in);
    put(node, { y: r.y + out * 200, o: r.o * (1 - x) * (1 - out) });
  };
  lab(el.labL, M.payoff + 0.3);
  lab(el.labR1, M.payoff + 0.4, M.restyle + 0.2);
  lab(el.labR2, M.restyle + 0.35);
}

function loop(t) {
  show(el.s[1], t >= M.loop && t < M.once + 0.3);
  if (t < M.loop) return;
  const out = P(t, M.once - 0.05, 0.2, E.in);

  const h1 = rise(t, M.loop + 0.05, 50, 0.3), h1x = P(t, M.editor - 0.12, 0.2, E.in);
  put(el.loopHead1, { y: h1.y - h1x * 40, o: h1.o * (1 - h1x) });
  const h2 = rise(t, M.editor + 0.05, 50, 0.3);
  put(el.loopHead2, { y: h2.y, o: h2.o * (1 - out) });

  // one card, the same edit redone on it reel after reel, faster and faster
  const n = reelAt(t);
  const self = t < M.editor;
  const t0 = reelTime(n);
  const frac = self ? clamp(((t - t0) / Math.max(0.05, reelTime(n + 1) - t0)) * 1.15) : 1;
  const kick = self ? Math.exp(-(t - t0) * 22) : 0;
  const cin = P(t, M.loop, 0.45, E.back);
  put(el.card, { y: lerp(1100, 0, cin) - kick * 18 + out * 60, s: 1 + kick * 0.03, o: 1 - out });
  el.cardStyled.style.clipPath = `inset(0 ${(1 - frac) * 100}% 0 0)`;
  el.cardDrain.style.opacity = P(t, M.leave, 0.45, E.io);
  el.reelNo.textContent = self ? `Reel #${n}` : t < M.leave ? `Reel #${n + 1}` : "Reel #1, again";

  // what it adds up to
  const tt = rise(t, M.loop + 0.15, 40, 0.3), ttx = P(t, M.editor - 0.12, 0.2, E.in);
  put(el.tallyTime, { y: tt.y, o: tt.o * (1 - ttx) });
  el.tallyReels.textContent = `#${n}`;
  el.tallyReelsLabel.textContent = n > 1 ? "reels, same edit" : "reel, same edit";
  el.tallyHours.textContent = `${n * HOURS_PER_REEL} hrs`;
  const tm = rise(t, M.editor + 0.12, 40, 0.3);
  put(el.tallyMoney, { y: tm.y, o: tm.o * (1 - out) });

  const s1 = P(t, M.everyReel, 0.35, E.back), s1x = P(t, M.editor - 0.12, 0.2, E.in);
  put(el.loopSub1, { s: lerp(0.6, 1, s1), o: clamp((t - M.everyReel) / 0.06) * (1 - s1x) });
  const s2 = slam(t, M.leave, 1.3);
  put(el.loopSub2, { ...s2, o: s2.o * (1 - out) });
}

function once(t) {
  show(el.s[2], t >= M.once && t < M.gap);
  el.once.forEach((w, i) => put(w, slam(t, M.once + i * 0.15, 1.5)));
  put(el.onceBox, { s: 1 + P(t, M.riser, M.gap - M.riser, E.in) * 0.08 });
}

function logo(t) {
  const on = t >= M.logo;
  el.logo.parentElement.style.display = on ? "" : "none";
  show(el.s[3], on && t < M.phone + 0.6);
  if (!on) return;

  // centre stage, then up into the header when the phone arrives
  const [w, h] = el.logoSize;
  const k = P(t, M.phone - 0.25, 0.4, E.io);
  const s = lerp(1, 0.4, k);
  const cy = lerp(880, 160, k);
  el.logo.style.transform = `translate(${540 - (w * s) / 2}px,${cy - (h * s) / 2}px) scale(${s})`;

  const m = P(t, M.logo, 0.45, E.back);
  const pulse = t > M.final ? 1 + 0.08 * Math.exp(-(t - M.final) * 5) * Math.sin((t - M.final) * 14 + 1.6) : 1;
  put(el.mark, { s: m * pulse, r: lerp(-25, 0, m), o: clamp((t - M.logo) / 0.05) });
  el.letters.forEach((c, i) => put(c, rise(t, M.logo + 0.06 + i * 0.025, 70, 0.4)));
  // it turns cream once the dark end card has risen past it
  el.word.style.color = t >= M.end + 0.4 ? CREAM : INK;

  const r = P(t, M.logo, 0.9, E.expo);
  el.ring.style.transform = `translate(-50%,-50%) translate(${-5}px,${-20}px)`;
  el.ring.style.width = el.ring.style.height = `${60 + r * 1500}px`;
  el.ring.style.borderWidth = `${lerp(24, 1, r)}px`;
  el.ring.style.opacity = 1 - r;
  el.ring.style.left = "540px";
  el.ring.style.top = "900px";

  const tg = rise(t, M.logo + 0.45, 30);
  const out = P(t, M.phone - 0.35, 0.2);
  put(el.tagline, { y: tg.y - out * 30, o: tg.o * (1 - out) });
}

const PHONE_C = [540, 818]; // centre of the phone on stage
const CHIP_C = [[210, 555], [870, 615], [210, 945]]; // centre of each chip

function demo(t) {
  show(el.s[4], t >= M.phone && t < M.end + 0.5);
  if (t < M.phone) return;
  const leave = P(t, M.end, 0.35, E.in);

  // step labels
  const STEPS = [[M.phone + 0.3, M.step2], [M.step2, M.step3], [M.step3, M.chat], [M.chat, M.end]];
  el.steps.forEach((st, i) => {
    const [a, b] = STEPS[i];
    const r = rise(t, a, 34, 0.3);
    const x = P(t, b - 0.05, 0.2, E.in);
    put(st, { y: r.y - x * 34, o: r.o * (1 - x) });
  });

  // the phone rises, flinches at the tap, then leaves with the rest
  const up = P(t, M.phone, 0.6, E.back);
  const tap = t > M.tap ? 1 - 0.03 * Math.sin(clamp((t - M.tap) / 0.2) * Math.PI) : 1;
  put(el.phone, { y: lerp(1300, 0, up) - leave * 120, s: tap, o: 1 - leave });

  // reference: story bars run, the scan reads it
  el.refBars.forEach((b, i) => put(b, { sx: i === 0 ? 1 : i === 1 ? clamp((t - M.phone) / 2.4) : 0, sy: 1 }));
  const sk = clamp((t - M.scan) / 1.1);
  const scanning = t >= M.scan && t < M.scan + 1.25;
  el.scanline.style.transform = `translateY(${sk * 812}px)`;
  el.scanline.style.opacity = scanning ? 1 - P(t, M.scan + 1.1, 0.15) : 0;
  el.scanwash.style.height = `${sk * 812}px`;
  el.scanwash.style.opacity = scanning ? 1 - P(t, M.scan + 1.1, 0.15) : 0;
  el.refCapWord.style.opacity = 1 - 0.6 * P(t, M.scan + 0.7, 0.2);

  // raw footage falls in on top
  const fall = P(t, M.step2, 0.2, E.in);
  const land = t > M.step2 + 0.2 ? Math.exp(-(t - M.step2 - 0.2) * 14) * Math.sin((t - M.step2 - 0.2) * 40) : 0;
  el.raw.style.display = t >= M.step2 ? "" : "none";
  put(el.raw, { y: lerp(-900, 0, fall), sy: 1 - land * 0.04, sx: 1 + land * 0.03 });

  // the style washes across it
  const wk = P(t, M.step3 + 0.3, 0.55, E.io);
  const xt = lerp(-35, 135, wk), xb = xt - 30;
  el.styled.style.display = t >= M.step3 + 0.3 ? "" : "none";
  el.styled.style.clipPath = `polygon(0 0,${xt}% 0,${xb}% 100%,0 100%)`;
  el.edge.style.display = wk > 0 && wk < 1 ? "" : "none";
  el.edge.style.left = `${((xt + xb) / 2 / 100) * 446 - 4}px`;
  el.edge.style.transform = `rotate(${(Math.atan2(0.3 * 446, 812) * 180) / Math.PI}deg)`;

  // two cuts: punch in, then back out
  const zoom = t < M.cut1 ? 1 : t < M.cut2 ? 1.24 : 1.08;
  put(el.frame, { s: zoom, x: t >= M.cut2 ? -14 : 0 });
  const fl = Math.max(0, 0.55 - (t - M.cut1) * 6) * (t >= M.cut1 ? 1 : 0) +
             Math.max(0, 0.45 - (t - M.cut2) * 6) * (t >= M.cut2 ? 1 : 0);
  el.flash.style.opacity = Math.min(fl, 0.6);
  el.styledBars.forEach((b, i) => put(b, { sx: i === 0 ? clamp((t - M.step3) / 3) : 0, sy: 1 }));

  // captions, word by word, then bigger when asked
  el.capWords.forEach((w, i) => {
    const t0 = M.words + i * BEAT / 2;
    const k = P(t, t0, 0.3, E.back);
    put(w, { s: lerp(0.3, 1, k), o: clamp((t - t0) / 0.06) });
  });
  const g = P(t, M.grow, 0.45, E.back);
  put(el.caps, { s: lerp(1, 1.28, g) });
  const ts = rise(t, M.grow + 0.5, -24, 0.3);
  el.toast.style.transform = `translateX(-50%) translateY(${ts.y}px)`;
  el.toast.style.opacity = ts.o;

  // what it read off the reference, flying out to the sides and back in
  const outAt = [M.scan + 0.35, M.scan + 0.7, M.scan + 0.95];
  el.chips.forEach((c, i) => {
    const k = P(t, outAt[i], 0.45, E.back);
    const back = P(t, M.step3, 0.32, E.in);
    const dx = PHONE_C[0] - CHIP_C[i][0], dy = PHONE_C[1] - CHIP_C[i][1];
    const pos = t < M.step3 ? 1 - k : back;
    put(c, {
      x: dx * pos, y: dy * pos, s: lerp(1, 0.25, pos),
      o: t < outAt[i] ? 0 : t < M.step3 ? clamp((t - outAt[i]) / 0.08) : 1 - back,
      r: (i % 2 ? 4 : -4) * (1 - pos),
    });
  });
  el.rhythm.forEach((b, i) => {
    const base = [0.5, 0.9, 0.35, 0.75, 0.6, 1][i];
    const beatPhase = ((t - i * 0.07) % BEAT) / BEAT;
    put(b, { sy: base * (0.55 + 0.45 * Math.exp(-beatPhase * 6)), sx: 1 });
  });
  el.swatches.forEach((sw, i) => put(sw, { s: P(t, M.scan + 0.95 + i * 0.15, 0.3, E.back) }));

  // the edit timeline under the phone
  const stripOn = t >= M.step3 && t < M.chat + 0.3;
  el.strip.style.display = stripOn ? "" : "none";
  put(el.strip, { o: clamp((t - M.step3) / 0.2) * (1 - P(t, M.chat, 0.25)) });
  put(el.stripFill, { sx: clamp((t - M.step3) / 3), sy: 1 });
  el.stripCuts.forEach((c, i) => put(c, { s: P(t, i ? M.cut2 : M.cut1, 0.25, E.back) }));

  // asking for a change
  el.chat.style.display = t >= M.chat ? "" : "none";
  put(el.chat, { ...rise(t, M.chat, 60, 0.35), s: t > M.send ? 1 - 0.02 * Math.sin(clamp((t - M.send) / 0.2) * Math.PI) : 1 });
  const n = t >= M.send ? 0 : clamp(Math.floor((t - CHAT_TYPE_START) / CHAT_TYPE_PER) + 1, 0, PROMPT.length);
  el.chatText.textContent = PROMPT.slice(0, n);
  el.chatPh.style.display = n ? "none" : "";
  el.chatCaret.style.display = n ? "" : "none";
  put(el.send, { s: t > M.send ? 1 + 0.25 * Math.exp(-(t - M.send) * 10) : 1 });
  const fly = P(t, M.send, 0.4, E.io);
  el.bubble.style.display = t >= M.send && fly < 1 ? "" : "none";
  put(el.bubble, { x: lerp(-370, -190, fly), y: lerp(10, -520, fly), s: lerp(1, 0.55, fly), o: 1 - P(t, M.send + 0.25, 0.15) });
}

function touches(t) {
  const EVENTS = [[M.tap, 565, 810], [M.press, 560, 1220]];
  const ev = EVENTS.find(([at]) => t >= at - 0.2 && t < at + 0.45);
  el.touch.style.display = ev ? "" : "none";
  if (!ev) return;
  const [at, x, y] = ev;
  el.touch.style.left = `${x}px`;
  el.touch.style.top = `${y}px`;
  const inK = P(t, at - 0.2, 0.18);
  const press = t >= at ? 1 - 0.18 * Math.sin(clamp((t - at) / 0.12) * Math.PI) : 1;
  const away = P(t, at + 0.12, 0.33);
  put(el.touch, { s: lerp(1.4, 1, inK) * press * lerp(1, 1.7, away), o: inK * (1 - away) });
}

function endCard(t) {
  show(el.s[5], t >= M.end);
  if (t < M.end) return;
  put(el.end1, rise(t, M.end + 0.15, 60, 0.4));
  put(el.end2, slam(t, M.end + BEAT / 2, 1.3));
  put(el.price, rise(t, M.price, 30));
  const b = P(t, M.button, 0.45, E.back);
  const press = t > M.press ? 1 - 0.06 * Math.sin(clamp((t - M.press) / 0.18) * Math.PI) : 1;
  const glow = t > M.press ? Math.exp(-(t - M.press) * 3) : 0;
  put(el.btn, { s: b * press, o: clamp((t - M.button) / 0.06) });
  el.btn.style.boxShadow = `0 0 0 ${glow * 28}px rgba(195,211,226,${glow * 0.35}), 0 30px 60px -30px rgba(0,0,0,.6)`;
  put(el.bio, rise(t, M.press + 0.35, 20));
}

export function seek(t) {
  background(t);
  shake(t);
  payoff(t);
  loop(t);
  once(t);
  logo(t);
  demo(t);
  touches(t);
  endCard(t);
  el.grain.style.backgroundImage = el.tiles[Math.floor(t * FPS) % el.tiles.length];
}
