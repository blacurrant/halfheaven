// The soundtrack, synthesised - no samples, so nothing to license.
//
// Runs in the browser on an OfflineAudioContext: render.mjs calls it headless
// to bake a WAV, and index.html calls it to play along in preview. Music is a
// 100 BPM lo-fi groove in F that stays filtered and sparse under the hook,
// goes silent for half a beat, and drops in full on the logo. Sound effects are
// placed from cues.mjs, so each lands on the frame it belongs to.

import { BEAT, DURATION, M, SFX } from "./cues.mjs";

const BAR = BEAT * 4;
const S16 = BEAT / 4;
const mtof = (m) => 440 * 2 ** ((m - 69) / 12);

// bass note, pad voicing (MIDI)
const CH = {
  F: [41, [57, 60, 64, 67]],
  Dm: [38, [53, 57, 60, 64]],
  Bb: [46, [57, 60, 62, 65]],
  C: [36, [55, 60, 62, 67]],
};
// one chord per bar; bars 0-3 are the intro, the groove starts on the logo (bar 4)
// the payoff bar is bright, the loop darkens it, the stop leans into the drop
const BARS = ["F", "Dm", "Bb", "C", "F", "Dm", "Bb", "C", "Bb", "C"];

export async function renderSoundtrack(sampleRate = 48000) {
  const len = Math.ceil(DURATION * sampleRate);
  const ctx = new OfflineAudioContext(2, len, sampleRate);
  const noise = makeNoise(ctx);

  // ---- buses ----------------------------------------------------------------
  const master = ctx.createGain();
  master.gain.value = 0.9;
  const comp = ctx.createDynamicsCompressor();
  comp.threshold.value = -14;
  comp.ratio.value = 3.5;
  comp.attack.value = 0.004;
  comp.release.value = 0.18;
  // a brick wall after the glue, so nothing clips
  const limit = ctx.createDynamicsCompressor();
  limit.threshold.value = -4;
  limit.knee.value = 0;
  limit.ratio.value = 20;
  limit.attack.value = 0.001;
  limit.release.value = 0.08;
  const trim = ctx.createGain();
  trim.gain.value = 0.95;
  master.connect(comp).connect(limit).connect(trim).connect(ctx.destination);

  const reverb = ctx.createConvolver();
  reverb.buffer = makeImpulse(ctx, 2.4);
  const revOut = ctx.createGain();
  revOut.gain.value = 0.55;
  reverb.connect(revOut).connect(master);

  // music runs through one filter that opens across the intro, and one gain that
  // carves out the silence before the drop
  const music = ctx.createGain();
  const tone = ctx.createBiquadFilter();
  tone.type = "lowpass";
  tone.Q.value = 0.8;
  const f = tone.frequency;
  f.setValueAtTime(320, 0);
  f.exponentialRampToValueAtTime(900, M.payOut);
  f.exponentialRampToValueAtTime(600, M.loop + 0.3);
  f.exponentialRampToValueAtTime(1400, M.once);
  f.exponentialRampToValueAtTime(5000, M.gap);
  f.setValueAtTime(18000, M.logo);
  music.connect(tone);
  const musicGain = ctx.createGain();
  const g = musicGain.gain;
  g.setValueAtTime(0.0001, 0);
  g.exponentialRampToValueAtTime(0.8, 1.2);
  // the loop stops dead: music drops back under the riser, then out
  g.setValueAtTime(0.8, M.once);
  g.linearRampToValueAtTime(0.25, M.once + 0.08);
  g.setValueAtTime(0.25, M.gap - 0.03);
  g.linearRampToValueAtTime(0, M.gap);
  g.setValueAtTime(0, M.logo - 0.005);
  g.linearRampToValueAtTime(1, M.logo);
  g.setValueAtTime(1, DURATION - 1.2);
  g.linearRampToValueAtTime(0, DURATION);
  tone.connect(musicGain).connect(master);

  // pads duck under the kick for a bit of pump
  const padBus = ctx.createGain();
  padBus.connect(music);
  send(ctx, padBus, reverb, 0.5);

  const sfx = ctx.createGain();
  sfx.gain.value = 0.85;
  sfx.connect(master);
  send(ctx, sfx, reverb, 0.18);

  const env = { ctx, noise, reverb, music, padBus, sfx };

  // ---- music ------------------------------------------------------------------
  BARS.forEach((name, bar) => {
    const t0 = bar * BAR;
    const [bass, pad] = CH[name];
    const groove = bar >= 4;
    pad.forEach((m, i) => padVoice(env, mtof(m), t0, BAR + 0.15, groove ? 0.05 : 0.065, i));
    subBass(env, mtof(bass), t0, groove);

    if (bar === 2 || bar === 3) {
      [0, 8].forEach((s) => kick(env, t0 + s * S16, 0.55));
      for (let s = 2; s < 16; s += 4) hat(env, t0 + s * S16, 0.11);
    }
    if (bar === 1) kick(env, t0 + 8 * S16, 0.4);

    if (groove) {
      [0, 7, 10].forEach((s) => kick(env, t0 + s * S16, 0.95));
      [4, 12].forEach((s) => clap(env, t0 + s * S16));
      for (let s = 0; s < 16; s += 2) {
        const swing = s % 4 === 2 ? 0.028 : 0;
        hat(env, t0 + s * S16 + swing, s % 4 === 0 ? 0.12 : 0.2);
      }
      [3, 15].forEach((s) => hat(env, t0 + s * S16, 0.08));
      if (bar % 2 === 1) openHat(env, t0 + 14 * S16);
      pluckBar(env, pad, t0, bar);
      duck(padBus, t0, [0, 7, 10]);
    }
  });

  // last chord, left to ring
  const [fb, fp] = CH.F;
  fp.forEach((m, i) => padVoice(env, mtof(m), M.final, 1.6, 0.07, i));
  fp.forEach((m, i) => pluck(env, mtof(m + 12), M.final + i * 0.03, 0.18));
  subBass(env, mtof(fb), M.final, true, 1.4);
  kick(env, M.final, 1);

  // ---- sound effects ------------------------------------------------------------
  for (const c of SFX) FX[c.s]?.(env, c.t, c.v ?? 1, c);

  return ctx.startRendering();
}

// ---- instruments ------------------------------------------------------------------

function padVoice({ ctx, padBus }, freq, t, dur, level, i) {
  const out = ctx.createGain();
  const lp = ctx.createBiquadFilter();
  lp.type = "lowpass";
  lp.frequency.value = 1800;
  lp.connect(out).connect(padBus);
  for (const detune of [-7, 7]) {
    const o = ctx.createOscillator();
    o.type = "sawtooth";
    o.frequency.value = freq;
    o.detune.value = detune + (i % 2 ? 3 : -3);
    o.connect(lp);
    o.start(t);
    o.stop(t + dur + 0.6);
  }
  const g = out.gain;
  g.setValueAtTime(0, t);
  g.linearRampToValueAtTime(level, t + 0.25);
  g.setValueAtTime(level, t + dur - 0.1);
  g.linearRampToValueAtTime(0, t + dur + 0.5);
}

function subBass({ ctx, music }, freq, t0, groove, hold) {
  // root on 1, a push on the "and" of 2, the octave on 3 in the groove
  const hits = groove && !hold ? [[0, 0.55], [6, 0.3], [8, 0.45], [14, 0.25]] : [[0, hold || BAR * 0.95]];
  hits.forEach(([s, len], k) => {
    const t = t0 + s * S16;
    const o = ctx.createOscillator();
    o.type = "triangle";
    o.frequency.value = k === 2 ? freq * 2 : freq;
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 420;
    const g = ctx.createGain();
    const lvl = groove ? 0.3 : 0.2;
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(lvl, t + 0.012);
    g.gain.setValueAtTime(lvl, t + len * 0.7);
    g.gain.exponentialRampToValueAtTime(0.0001, t + len);
    o.connect(lp).connect(g).connect(music);
    o.start(t);
    o.stop(t + len + 0.05);
  });
}

function pluckBar(env, pad, t0, bar) {
  const pattern = bar % 2 ? [3, 1, 2, 0, 3, 2, 1, 2] : [0, 2, 1, 3, 2, 1, 3, 2];
  pattern.forEach((idx, k) => {
    if (bar >= 8 && k === 7) return;
    pluck(env, mtof(pad[idx] + 12), t0 + k * 2 * S16 + (k % 2 ? 0.025 : 0), k % 2 ? 0.075 : 0.1);
  });
}

function pluck({ ctx, music, reverb }, freq, t, level) {
  const o = ctx.createOscillator();
  o.type = "triangle";
  o.frequency.value = freq;
  const o2 = ctx.createOscillator();
  o2.type = "sine";
  o2.frequency.value = freq * 2;
  const lp = ctx.createBiquadFilter();
  lp.type = "lowpass";
  lp.frequency.setValueAtTime(4200, t);
  lp.frequency.exponentialRampToValueAtTime(600, t + 0.25);
  const g = ctx.createGain();
  g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(level, t + 0.004);
  g.gain.exponentialRampToValueAtTime(0.0001, t + 0.55);
  const g2 = ctx.createGain();
  g2.gain.value = 0.25;
  o.connect(lp);
  o2.connect(g2).connect(lp);
  lp.connect(g);
  g.connect(music);
  // a dotted-eighth echo, and some room
  const d = ctx.createDelay(1);
  d.delayTime.value = BEAT * 0.75;
  const fb = ctx.createGain();
  fb.gain.value = 0.28;
  const dOut = ctx.createGain();
  dOut.gain.value = 0.35;
  g.connect(d).connect(fb).connect(d);
  d.connect(dOut).connect(music);
  const rs = ctx.createGain();
  rs.gain.value = 0.3;
  g.connect(rs).connect(reverb);
  for (const x of [o, o2]) { x.start(t); x.stop(t + 0.6); }
}

function kick({ ctx, music }, t, v) {
  const o = ctx.createOscillator();
  o.type = "sine";
  o.frequency.setValueAtTime(150, t);
  o.frequency.exponentialRampToValueAtTime(44, t + 0.12);
  const g = ctx.createGain();
  g.gain.setValueAtTime(v, t);
  g.gain.exponentialRampToValueAtTime(0.0001, t + 0.42);
  o.connect(g).connect(music);
  o.start(t);
  o.stop(t + 0.45);
}

function clap(env, t) {
  const { ctx, music, reverb } = env;
  const bp = ctx.createBiquadFilter();
  bp.type = "bandpass";
  bp.frequency.value = 1300;
  bp.Q.value = 0.9;
  const g = ctx.createGain();
  [0, 0.011, 0.022].forEach((dt) => {
    g.gain.setValueAtTime(0.5, t + dt);
    g.gain.exponentialRampToValueAtTime(0.08, t + dt + 0.01);
  });
  g.gain.setValueAtTime(0.4, t + 0.033);
  g.gain.exponentialRampToValueAtTime(0.0001, t + 0.24);
  noiseSrc(env, t, 0.3).connect(bp).connect(g);
  g.connect(music);
  const rs = ctx.createGain();
  rs.gain.value = 0.35;
  g.connect(rs).connect(reverb);
}

function hat(env, t, v) {
  const { ctx, music } = env;
  const hp = ctx.createBiquadFilter();
  hp.type = "highpass";
  hp.frequency.value = 7500;
  const g = ctx.createGain();
  g.gain.setValueAtTime(v, t);
  g.gain.exponentialRampToValueAtTime(0.0001, t + 0.045);
  noiseSrc(env, t, 0.06).connect(hp).connect(g).connect(music);
}

function openHat(env, t) {
  const { ctx, music } = env;
  const hp = ctx.createBiquadFilter();
  hp.type = "highpass";
  hp.frequency.value = 6500;
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.13, t);
  g.gain.exponentialRampToValueAtTime(0.0001, t + 0.28);
  noiseSrc(env, t, 0.3).connect(hp).connect(g).connect(music);
}

function duck(bus, t0, steps) {
  for (const s of steps) {
    const t = t0 + s * S16;
    bus.gain.setValueAtTime(1, t);
    bus.gain.linearRampToValueAtTime(0.45, t + 0.01);
    bus.gain.linearRampToValueAtTime(1, t + 0.22);
  }
}

// ---- sound effects ------------------------------------------------------------------

const FX = {
  thud(env, t, v) {
    const { ctx, sfx, reverb } = env;
    const o = ctx.createOscillator();
    o.frequency.setValueAtTime(120, t);
    o.frequency.exponentialRampToValueAtTime(36, t + 0.28);
    const g = ctx.createGain();
    g.gain.setValueAtTime(v * 0.95, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.6);
    o.connect(g).connect(sfx);
    const rs = ctx.createGain();
    rs.gain.value = 0.25;
    g.connect(rs).connect(reverb);
    o.start(t); o.stop(t + 0.65);
    burst(env, t, "lowpass", 900, v * 0.5, 0.05);
  },
  tick(env, t, v) {
    tone(env, t, 2900, 2900, v * 0.18, 0.018, "square", 5000);
  },
  click(env, t, v) {
    burst(env, t, "bandpass", 3200, v * 0.8, 0.012, 1.2);
    tone(env, t, 1700, 900, v * 0.3, 0.035);
  },
  key(env, t, v, c) {
    const k = ((c.seed ?? 0) * 7919) % 5;
    burst(env, t, "bandpass", 2200 + k * 420, v * 0.55, 0.018, 1.5);
    tone(env, t, 210 + k * 12, 160, v * 0.22, 0.03);
  },
  space(env, t, v) {
    burst(env, t, "bandpass", 1500, v * 0.5, 0.03, 1.2);
    tone(env, t, 170, 120, v * 0.3, 0.05);
  },
  pop(env, t, v, c) {
    const p = c.pitch ?? 1;
    tone(env, t, 360 * p, 980 * p, v * 0.42, 0.11, "sine", 0, 0.045);
  },
  whoosh({ ctx, sfx, noise }, t, v, c) {
    const dir = c.dir ?? 1;
    const dur = 0.55;
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.Q.value = 1.4;
    const [a, b] = dir > 0 ? [350, 3200] : [3200, 350];
    bp.frequency.setValueAtTime(a, t);
    bp.frequency.exponentialRampToValueAtTime(b, t + dur);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(v * 0.9, t + dur * 0.55);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    const pan = ctx.createStereoPanner();
    pan.pan.setValueAtTime(-0.7 * dir, t);
    pan.pan.linearRampToValueAtTime(0.7 * dir, t + dur);
    const src = ctx.createBufferSource();
    src.buffer = noise;
    src.connect(bp).connect(g).connect(pan).connect(sfx);
    src.start(t, 0.3);
    src.stop(t + dur);
  },
  riser({ ctx, sfx, noise }, t, v, c) {
    const dur = c.dur;
    const end = t + dur;
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.Q.value = 2;
    bp.frequency.setValueAtTime(200, t);
    bp.frequency.exponentialRampToValueAtTime(7000, end);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.001, t);
    g.gain.exponentialRampToValueAtTime(v * 0.75, end - 0.01);
    g.gain.linearRampToValueAtTime(0, end);
    const src = ctx.createBufferSource();
    src.buffer = noise;
    src.loop = true;
    src.connect(bp).connect(g).connect(sfx);
    src.start(t);
    src.stop(end);
    // a saw climbing under the noise
    const o = ctx.createOscillator();
    o.type = "sawtooth";
    o.frequency.setValueAtTime(110, t);
    o.frequency.exponentialRampToValueAtTime(880, end);
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.setValueAtTime(300, t);
    lp.frequency.exponentialRampToValueAtTime(4000, end);
    const og = ctx.createGain();
    og.gain.setValueAtTime(0.001, t);
    og.gain.exponentialRampToValueAtTime(v * 0.18, end - 0.01);
    og.gain.linearRampToValueAtTime(0, end);
    o.connect(lp).connect(og).connect(sfx);
    o.start(t); o.stop(end);
  },
  impact(env, t, v) {
    const { ctx, sfx, reverb } = env;
    const o = ctx.createOscillator();
    o.frequency.setValueAtTime(78, t);
    o.frequency.exponentialRampToValueAtTime(30, t + 1.3);
    const g = ctx.createGain();
    g.gain.setValueAtTime(v * 1.1, t);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 1.6);
    o.connect(g).connect(sfx);
    o.start(t); o.stop(t + 1.7);
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.setValueAtTime(6000, t);
    lp.frequency.exponentialRampToValueAtTime(180, t + 0.9);
    const ng = ctx.createGain();
    ng.gain.setValueAtTime(v * 0.7, t);
    ng.gain.exponentialRampToValueAtTime(0.0001, t + 1.1);
    const n = noiseSrc(env, t, 1.2);
    n.connect(lp).connect(ng).connect(sfx);
    const rs = ctx.createGain();
    rs.gain.value = 0.8;
    ng.connect(rs).connect(reverb);
  },
  scan({ ctx, sfx }, t, v, c) {
    const dur = c.dur;
    const o = ctx.createOscillator();
    o.type = "sine";
    o.frequency.setValueAtTime(700, t);
    o.frequency.exponentialRampToValueAtTime(1500, t + dur);
    const lfo = ctx.createOscillator();
    lfo.frequency.value = 18;
    const lfoAmt = ctx.createGain();
    lfoAmt.gain.value = 0.5;
    const trem = ctx.createGain();
    trem.gain.value = 0.5;
    lfo.connect(lfoAmt).connect(trem.gain);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(v * 0.12, t + 0.1);
    g.gain.setValueAtTime(v * 0.12, t + dur - 0.15);
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(trem).connect(g).connect(sfx);
    o.start(t); o.stop(t + dur);
    lfo.start(t); lfo.stop(t + dur);
  },
  drop(env, t, v) {
    tone(env, t, 95, 34, v * 0.9, 0.45);
    burst(env, t, "lowpass", 1200, v * 0.45, 0.06);
    FX.tick(env, t + 0.012, v * 0.8);
  },
  // the look draining away: a falling tone under a closing filter
  drain(env, t, v) {
    tone(env, t, 620, 140, v * 0.3, 0.55, "triangle", 0, 0.5);
    FX.whoosh(env, t, v * 0.5, { dir: -1 });
  },
  // tape stop: everything winds down in pitch
  stop(env, t, v) {
    tone(env, t, 420, 45, v * 0.35, 0.4, "sawtooth", 0, 0.38);
    tone(env, t, 210, 30, v * 0.4, 0.42, "sine", 0, 0.4);
  },
  suck({ ctx, sfx, noise }, t, v) {
    const dur = 0.3;
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.Q.value = 2;
    bp.frequency.setValueAtTime(3500, t);
    bp.frequency.exponentialRampToValueAtTime(500, t + dur);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(v * 0.7, t + dur - 0.02);
    g.gain.linearRampToValueAtTime(0, t + dur);
    const src = ctx.createBufferSource();
    src.buffer = noise;
    src.connect(bp).connect(g).connect(sfx);
    src.start(t, 0.9);
    src.stop(t + dur);
  },
  shimmer({ ctx, sfx, reverb }, t, v) {
    [77, 81, 84, 88, 91, 93].forEach((m, i) => {
      const at = t + i * 0.045;
      const o = ctx.createOscillator();
      o.frequency.value = mtof(m);
      const g = ctx.createGain();
      g.gain.setValueAtTime(0, at);
      g.gain.linearRampToValueAtTime(v * 0.07, at + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, at + 0.9);
      o.connect(g).connect(sfx);
      const rs = ctx.createGain();
      rs.gain.value = 1;
      g.connect(rs).connect(reverb);
      o.start(at); o.stop(at + 0.95);
    });
  },
  snip(env, t, v) {
    burst(env, t, "highpass", 4500, v * 0.7, 0.01);
    burst(env, t + 0.035, "highpass", 5200, v * 0.55, 0.008);
    tone(env, t, 180, 90, v * 0.35, 0.06);
  },
  send(env, t, v) {
    tone(env, t, 480, 1150, v * 0.38, 0.16, "sine", 0, 0.1);
    FX.whoosh(env, t, v * 0.35, { dir: 1 });
  },
  grow(env, t, v) {
    tone(env, t, 280, 720, v * 0.3, 0.32, "triangle", 0, 0.25);
    tone(env, t + 0.02, 560, 1440, v * 0.08, 0.3, "sine", 0, 0.25);
  },
  chime({ ctx, sfx, reverb }, t, v) {
    [[88, 0.12], [93, 0.08], [100, 0.04]].forEach(([m, lvl]) => {
      const o = ctx.createOscillator();
      o.frequency.value = mtof(m);
      const g = ctx.createGain();
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(v * lvl, t + 0.005);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 1.4);
      o.connect(g).connect(sfx);
      const rs = ctx.createGain();
      rs.gain.value = 0.9;
      g.connect(rs).connect(reverb);
      o.start(t); o.stop(t + 1.5);
    });
  },
};

// ---- building blocks ------------------------------------------------------------------

function tone({ ctx, sfx }, t, f0, f1, level, dur, type = "sine", hp = 0, glide) {
  const o = ctx.createOscillator();
  o.type = type;
  o.frequency.setValueAtTime(f0, t);
  o.frequency.exponentialRampToValueAtTime(f1, t + (glide ?? dur));
  const g = ctx.createGain();
  g.gain.setValueAtTime(0, t);
  g.gain.linearRampToValueAtTime(level, t + 0.003);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  let node = o;
  if (hp) {
    const f = ctx.createBiquadFilter();
    f.type = "highpass";
    f.frequency.value = hp;
    node = o.connect(f);
  }
  node.connect(g).connect(sfx);
  o.start(t);
  o.stop(t + dur + 0.02);
}

function burst(env, t, type, freq, level, dur, q = 0.7) {
  const { ctx, sfx } = env;
  const f = ctx.createBiquadFilter();
  f.type = type;
  f.frequency.value = freq;
  f.Q.value = q;
  const g = ctx.createGain();
  g.gain.setValueAtTime(level, t);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  noiseSrc(env, t, dur + 0.02).connect(f).connect(g).connect(sfx);
}

function noiseSrc({ ctx, noise }, t, dur) {
  const src = ctx.createBufferSource();
  src.buffer = noise;
  src.loop = true;
  src.start(t, (t * 0.37) % 1.5);
  src.stop(t + dur);
  return src;
}

function send(ctx, from, to, amount) {
  const g = ctx.createGain();
  g.gain.value = amount;
  from.connect(g).connect(to);
  return g;
}

function makeNoise(ctx) {
  const buf = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate);
  const d = buf.getChannelData(0);
  let seed = 1;
  for (let i = 0; i < d.length; i++) {
    seed = (seed * 16807) % 2147483647; // seeded, so every render sounds the same
    d[i] = (seed / 2147483647) * 2 - 1;
  }
  return buf;
}

function makeImpulse(ctx, secs) {
  const n = Math.floor(ctx.sampleRate * secs);
  const buf = ctx.createBuffer(2, n, ctx.sampleRate);
  let seed = 7;
  for (let ch = 0; ch < 2; ch++) {
    const d = buf.getChannelData(ch);
    for (let i = 0; i < n; i++) {
      seed = (seed * 16807) % 2147483647;
      const r = (seed / 2147483647) * 2 - 1;
      d[i] = r * Math.pow(1 - i / n, 3.2) * 0.5;
    }
  }
  return buf;
}

// 16-bit PCM WAV, for render.mjs to hand to ffmpeg
export function toWav(buffer) {
  const ch = buffer.numberOfChannels;
  const n = buffer.length;
  const out = new DataView(new ArrayBuffer(44 + n * ch * 2));
  const str = (o, s) => [...s].forEach((c, i) => out.setUint8(o + i, c.charCodeAt(0)));
  str(0, "RIFF"); out.setUint32(4, 36 + n * ch * 2, true); str(8, "WAVE");
  str(12, "fmt "); out.setUint32(16, 16, true); out.setUint16(20, 1, true); out.setUint16(22, ch, true);
  out.setUint32(24, buffer.sampleRate, true); out.setUint32(28, buffer.sampleRate * ch * 2, true);
  out.setUint16(32, ch * 2, true); out.setUint16(34, 16, true);
  str(36, "data"); out.setUint32(40, n * ch * 2, true);
  const data = [...Array(ch)].map((_, c) => buffer.getChannelData(c));
  let o = 44;
  for (let i = 0; i < n; i++) {
    for (let c = 0; c < ch; c++) {
      const s = Math.max(-1, Math.min(1, data[c][i]));
      out.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      o += 2;
    }
  }
  return new Uint8Array(out.buffer);
}
