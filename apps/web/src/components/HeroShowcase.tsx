/** The hero's picture of the product: a phone playing a reel you love, what
 *  Halfheaven reads from it on the left, what it makes from it on the right,
 *  wired together, with handwritten notes in the margins. The readings are an
 *  example, and the photos are generated stills, not a real creator's video.
 *  Decorative - the headline and lede carry the meaning - so it's hidden from
 *  screen readers.
 *
 *  Desktop tilts the glass panels toward the phone; below 1280px the notes and
 *  wires go and the panels become a swipeable row under the phone. */

import Image from "next/image";

import HeroWires from "@/components/HeroWires";
import s from "@/app/landing.module.css";

const READINGS = [
  ["Cuts", "A cut every 1.8s, landing on the beat"],
  ["Captions", "Bold, lower third, one keyword boxed"],
  ["Colour", "Warm, low contrast, lifted blacks"],
  ["Pace", "Fast open, no pause over 0.4s"],
];

const AFTER = [
  { src: "/landing/thumb-plant.jpg", line: "day 12 of posting", word: "daily" },
  { src: "/landing/thumb-coffee.jpg", line: "what nobody tells you about", word: "pricing" },
  { src: "/landing/thumb-sunset.jpg", line: "how I got my first", word: "client" },
];

// the reference's audio, one bar per ~0.5s; every fourth bar is a cut, on the beat
const AUDIO = [36, 30, 18, 26, 44, 24, 16, 28, 40, 20, 26, 18, 46, 22, 30, 16, 42, 24, 20, 28, 44, 18, 26, 22, 38, 20];
const STEP = 320 / AUDIO.length;

// cut ticks on the reel's progress bar: one every 1.8s of 31s
const TICKS = Array.from({ length: 17 }, (_, i) => ((i + 1) * 1.8 / 31) * 100);
const SWATCHES = ["#e6a15c", "#c46a3c", "#6b5a52"];

const Svg = ({ children, size = 14, fill = "none" }: { children: React.ReactNode; size?: number; fill?: string }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill={fill} stroke="currentColor" strokeWidth="2.2"
       strokeLinecap="round" strokeLinejoin="round">{children}</svg>
);
const Play = ({ size = 12 }: { size?: number }) => (
  <svg viewBox="0 0 24 24" width={size} height={size}><path d="M7 4.5v15l12-7.5z" fill="currentColor" /></svg>
);

// a hand-drawn arrow; `d` is the stroke, `head` the two-line tip
const Scribble = ({ d, head, className }: { d: string; head: string; className: string }) => (
  <svg className={className} viewBox="0 0 60 50" width="60" height="50" fill="none" stroke="currentColor"
       strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d={d} /><path d={head} /></svg>
);

function StatusBar() {
  return (
    <div className={s.status}>
      <span>9:41</span>
      <i className={s.island} />
      <span className={s.statusIcons}>
        <svg viewBox="0 0 18 12" width="17" height="11" fill="currentColor">
          <rect x="0" y="8" width="3" height="4" rx="1" /><rect x="5" y="5.5" width="3" height="6.5" rx="1" />
          <rect x="10" y="3" width="3" height="9" rx="1" /><rect x="15" y="0" width="3" height="12" rx="1" />
        </svg>
        <svg viewBox="0 0 16 12" width="15" height="11" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
          <path d="M1.5 4.5a9 9 0 0 1 13 0M4 7.2a5.5 5.5 0 0 1 8 0" /><circle cx="8" cy="10" r="1.2" fill="currentColor" stroke="none" />
        </svg>
        <svg viewBox="0 0 27 12" width="25" height="11" fill="none">
          <rect x=".5" y=".5" width="22" height="11" rx="3.5" stroke="currentColor" strokeOpacity=".5" />
          <rect x="2.5" y="2.5" width="18" height="7" rx="2" fill="currentColor" />
          <path d="M24.5 4v4" stroke="currentColor" strokeOpacity=".5" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </span>
    </div>
  );
}

export default function HeroShowcase() {
  return (
    <div className={s.showcase} aria-hidden>
      <HeroWires />

      <p className={`${s.note} ${s.noteBreakdown}`}>
        Clear breakdown<br />of what makes it work
        <Scribble className={s.scribbleDown} d="M6 6C28 4 44 14 50 36" head="M41 31l9 5 2-10" />
      </p>
      <p className={`${s.note} ${s.noteRhythm}`}>
        <Scribble className={s.scribbleUp} d="M10 44C10 26 20 12 40 6" head="M30 3l10 3-4 9" />
        See the rhythm<br />at a glance
      </p>
      <p className={`${s.note} ${s.noteAfter}`}>
        <Scribble className={s.scribbleBack} d="M54 8C36 6 20 16 12 40" head="M8 30l4 10 9-5" />
        Same look,<br />new ideas
      </p>
      <p className={`${s.note} ${s.noteAudience}`}>
        <Scribble className={s.scribbleBack} d="M54 44C36 44 20 34 12 10" head="M7 19l5-9 9 5" />
        Made for<br />your audience
      </p>
      <svg className={s.sparkle} viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor"
           strokeWidth="1.3" strokeLinecap="round"><path d="M12 1v22M1 12h22M4.5 4.5l15 15M19.5 4.5l-15 15" /></svg>

      <div className={s.device} data-wire-target>
        <div className={s.screen}>
          <StatusBar />
          <div className={s.appBar}>
            <span className={s.back}><Svg size={16}><path d="M19 12H5M11 18l-6-6 6-6" /></Svg></span>
            <div><strong>A reel you love</strong><small>Your reference · 0:31</small></div>
            <span className={`${s.tag} ${s.live}`}>Reading</span>
          </div>
          <div className={s.video}>
            <Image src="/landing/reel.jpg" alt="" fill sizes="300px" className={s.photo} priority />
            <span className={s.videoShade} />
            <span className={`${s.glass} ${s.cutChip}`}>Cut 3 of 17 · 0:05.4</span>
            <span className={`${s.glass} ${s.swatchChip}`}>
              {SWATCHES.map((c) => <i key={c} style={{ background: c }} />)}Colour
            </span>
            <span className={s.capBox}><em>Caption · bold, lower third</em></span>
            <p className={s.cap}>building a brand from<b>zero</b></p>
            <div className={s.controls}>
              <span className={s.track}><i />{TICKS.map((l) => <b key={l} style={{ left: `${l}%` }} />)}</span>
              <span className={s.playRow}><span><Play /> 0:08 / 0:31</span><span>17 cuts</span></span>
            </div>
          </div>
        </div>
      </div>

      <div className={s.panels}>
        <div className={s.left}>
          <div className={`${s.panel} ${s.breakdown}`} data-wire="left">
            <p className={s.panelNote}>
              <span className={s.panelIcon}><i /></span>Read cuts, captions, colour and pace · 4/4
            </p>
            <p className={s.panelTitle}>Style breakdown</p>
            <div className={s.rows}>
              {READINGS.map(([k, v], i) => (
                <div key={k} style={{ "--i": i } as React.CSSProperties}><b>{k}</b><span>{v}</span></div>
              ))}
            </div>
          </div>
          <div className={`${s.panel} ${s.rhythm}`} data-wire="left">
            <div className={s.panelHead}>
              <span>Cut rhythm</span>
              <span className={s.legend}><i className={s.legendCut} />Cut on the beat<i className={s.legendAudio} />Audio</span>
            </div>
            <svg viewBox="0 0 320 76" fill="none">
              {AUDIO.map((h, i) => (
                <rect key={i} x={i * STEP + 1.6} y={50 - h} width="9" height={h} rx="1.5"
                      className={i % 4 === 0 ? s.barCut : s.barAudio} />
              ))}
              {AUDIO.map((_, i) => i % 2 === 0 && (
                <circle key={i} cx={i * STEP + 6.1} cy="58" r="2" className={i % 4 === 0 ? s.beatCut : s.beat} />
              ))}
              <path d="M130 2V52" className={s.playhead} />
              <circle cx="130" cy="4" r="3.5" className={s.playheadKnob} />
              {([[0, "0s"], [96, "4s"], [192, "8s"], [300, "12s"]] as const).map(([x, t]) => (
                <text key={t} x={x} y="73" fontSize="10">{t}</text>
              ))}
            </svg>
          </div>
        </div>

        <div className={s.right}>
          <div className={`${s.panel} ${s.after}`} data-wire="right">
            <div className={s.panelHead}>
              <span>Every video after</span>
              <span className={s.samePill}>Same style <Svg size={13}><path d="M5 12h14M13 6l6 6-6 6" /></Svg></span>
            </div>
            <div className={s.thumbs}>
              {AFTER.map((a) => (
                <div key={a.word} className={s.thumb}>
                  <Image src={a.src} alt="" fill sizes="110px" className={s.photo} />
                  <span className={s.videoShade} />
                  <span className={s.thumbPlay}><Play size={14} /></span>
                  <p className={s.cap}>{a.line}<b>{a.word}</b></p>
                </div>
              ))}
            </div>
            <p className={s.panelFine}>Your new footage, cut and captioned in the saved look.</p>
          </div>
          <div className={`${s.panel} ${s.builtFor}`} data-wire="right">
            <div className={s.panelHead}><span>Built for how India posts</span></div>
            <div className={s.group}>
              <span>Captions</span>
              <p>{["Hinglish", "Hindi", "English"].map((c) => <i key={c}>{c}</i>)}</p>
            </div>
            <div className={s.group}>
              <span>Made for</span>
              <p>{["Instagram Reels", "YouTube Shorts", "9:16"].map((c) => <i key={c}>{c}</i>)}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
