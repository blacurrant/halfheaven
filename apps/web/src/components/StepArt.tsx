/** The pictures beside "How it works": 1 - the things Halfheaven reads, with
 *  the reference selected and a few reels fanned beside it; 2 - everything
 *  you can drop in, orbiting an upload target; 3 - the finished edit, ready
 *  to download. Each has a handwritten note in the margin.
 *
 *  Everything is sized in --u, 1/560th of the picture's width, so a scene
 *  scales as one piece. Decorative, so aria-hidden; the step text says it all. */

import Image from "next/image";

import s from "@/app/landing.module.css";

const u = (n: number) => `calc(${n} * var(--u))`;

// Lucide-style 24px line icons
const PATHS = {
  scissors: <><circle cx="6" cy="6" r="3" /><circle cx="6" cy="18" r="3" /><path d="M20 4 8.12 15.88M14.47 14.48 20 20M8.12 8.12 12 12" /></>,
  type: <path d="M4 7V4h16v3M9 20h6M12 4v16" />,
  colour: <><circle cx="12" cy="8.5" r="5" /><circle cx="8.5" cy="14.5" r="5" /><circle cx="15.5" cy="14.5" r="5" /></>,
  pace: <path d="M2 10v3M6 6v11M10 3v18M14 8v7M18 5v13M22 10v3" />,
  music: <><path d="M9 18V5l12-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" /></>,
  palette: <><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.93 0 1.65-.75 1.65-1.69 0-.44-.18-.84-.44-1.13-.29-.29-.44-.65-.44-1.13a1.64 1.64 0 0 1 1.67-1.67h2c3.05 0 5.55-2.5 5.55-5.55C21.97 6.01 17.46 2 12 2z" /><circle cx="13.5" cy="6.5" r=".6" fill="currentColor" /><circle cx="17.5" cy="10.5" r=".6" fill="currentColor" /><circle cx="8.5" cy="7.5" r=".6" fill="currentColor" /><circle cx="6.5" cy="12.5" r=".6" fill="currentColor" /></>,
  ratio: <><path d="M3 7V5a2 2 0 0 1 2-2h2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M7 21H5a2 2 0 0 1-2-2v-2" /><rect x="7" y="8" width="10" height="8" rx="1" /></>,
  image: <><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="9" cy="9" r="2" /><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21" /></>,
  video: <><path d="m16 13 5.2 3.5a.5.5 0 0 0 .8-.4V7.9a.5.5 0 0 0-.8-.4L16 10.5" /><rect x="2" y="6" width="14" height="12" rx="2" /></>,
  mic: <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3ZM19 10v2a7 7 0 0 1-14 0v-2M12 19v3" />,
  folder: <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />,
  monitor: <><rect x="2" y="3" width="20" height="14" rx="2" /><path d="M8 21h8M12 17v4" /></>,
  film: <><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M7 3v18M17 3v18M3 7.5h4M3 12h18M3 16.5h4M17 7.5h4M17 16.5h4" /></>,
  up: <path d="M12 19V5M5 12l7-7 7 7" />,
  download: <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />,
};
type IconName = keyof typeof PATHS;

const Icon = ({ name, className }: { name: IconName; className?: string }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.6"
       strokeLinecap="round" strokeLinejoin="round">{PATHS[name]}</svg>
);

const Play = () => (
  <span className={s.playDot}><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z" fill="currentColor" /></svg></span>
);

// a photo card: a generated still standing in for a reel, tilted, with an optional duration
function Snap({ src, x, y, w, h, turn, len, z }: {
  src: string; x: number; y: number; w: number; h: number; turn: number; len?: string; z?: number;
}) {
  return (
    <span className={s.snap} style={{ left: u(x), top: u(y), width: u(w), height: u(h), transform: `rotate(${turn}deg)`, zIndex: z }}>
      <Image src={src} alt="" fill sizes="160px" className={s.snapImg} />
      <Play />
      {len && <b>{len}</b>}
    </span>
  );
}

// handwritten note with a curved arrow; the arrow is drawn in a 90×60 box
function Note({ text, x, y, turn, arrow, ax, ay }: {
  text: [string, string]; x: number; y: number; turn: number; arrow: string; ax: number; ay: number;
}) {
  return (
    <span className={s.handNote}
          style={{ left: u(x), top: u(y), transform: `rotate(${turn}deg)` }}>
      {text[0]}<br />{text[1]}
      <svg viewBox="0 0 90 60" style={{ left: u(ax), top: u(ay), width: u(90), height: u(60) }} fill="none"
           stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d={arrow} /></svg>
    </span>
  );
}

// three short ink strokes, the kind of flourish you'd scribble by a corner
const Flourish = ({ x, y, turn }: { x: number; y: number; turn: number }) => (
  <svg className={s.flourish} viewBox="0 0 30 30" fill="none" stroke="currentColor"
       strokeWidth="2" strokeLinecap="round" style={{ left: u(x), top: u(y), width: u(30), height: u(30), transform: `rotate(${turn}deg)` }}>
    <path d="M6 4l3 9M15 2v10M24 6l-5 8" />
  </svg>
);

// 1 - what Halfheaven reads
const READS: { icon: IconName | "ring"; label: string }[] = [
  { icon: "scissors", label: "Cuts" }, { icon: "type", label: "Captions" }, { icon: "colour", label: "Colour" },
  { icon: "pace", label: "Pace" }, { icon: "music", label: "Music" }, { icon: "ring", label: "Reference" },
  { icon: "palette", label: "Look & Feel" }, { icon: "ratio", label: "Aspect Ratio" },
];

function Read() {
  return (
    <div className={`${s.art} ${s.art1}`} aria-hidden>
      <div className={s.card} style={{ left: 0, top: 0, width: u(490), height: u(300) }}>
        <div className={s.readGrid}>
          {READS.map((r) => (
            <span key={r.label} className={`${s.readTile} ${r.icon === "ring" ? s.readOn : ""}`}>
              {r.icon === "ring" ? <span className={s.bigRing} /> : <Icon name={r.icon} className={s.readIcon} />}
              {r.label}
            </span>
          ))}
        </div>
      </div>
      <Snap src="/landing/reel.jpg" x={466} y={-16} w={86} h={124} turn={8} z={3} />
      <Snap src="/landing/thumb-plant.jpg" x={484} y={92} w={86} h={124} turn={6} z={2} />
      <Snap src="/landing/thumb-sunset.jpg" x={458} y={196} w={86} h={112} turn={-9} z={4} />
      <Note text={["Choose what", "you like"]} x={-150} y={-6} turn={-14} ax={40} ay={46}
            arrow="M8 6C10 30 30 46 62 50M52 42l10 8-12 4" />
      <Flourish x={560} y={-44} turn={20} />
    </div>
  );
}

// 2 - everything you can drop in, around the upload target
const SOURCES: { icon: IconName; label: string; x: number; y: number }[] = [
  { icon: "image", label: "Clips", x: -108, y: -118 },
  { icon: "video", label: "Screen recordings", x: 150, y: -92 },
  { icon: "mic", label: "Voice", x: 160, y: 40 },
  { icon: "folder", label: "Anything you have", x: 22, y: 112 },
  { icon: "image", label: "Photos", x: -118, y: 72 },
];

function Upload() {
  return (
    <div className={`${s.art} ${s.art2}`} aria-hidden>
      <div className={s.card} style={{ left: u(40), top: 0, width: u(520), height: u(400) }}>
        <svg className={s.rings} viewBox="0 0 520 400" fill="none">
          <circle cx="300" cy="200" r="110" /><circle cx="300" cy="200" r="190" />
        </svg>
        <span className={s.upCore} style={{ left: u(232), top: u(132) }}>
          <span><Icon name="up" className={s.upIcon} /></span>
        </span>
        {SOURCES.map((src) => (
          <span key={src.label} className={s.source} style={{ left: u(300 + src.x - 40), top: u(200 + src.y - 40) }}>
            <span className={s.sourceDot}><Icon name={src.icon} className={s.sourceIcon} /></span>
            {src.label}
          </span>
        ))}
      </div>
      <Snap src="/landing/thumb-plant.jpg" x={200} y={230} w={112} h={140} turn={0} z={2} />
      <Snap src="/landing/reel.jpg" x={112} y={214} w={118} h={168} turn={5} len="0:31" z={3} />
      <Snap src="/landing/thumb-sunset.jpg" x={0} y={196} w={124} h={176} turn={-7} len="0:12" z={4} />
      <Note text={["Just drop", "everything"]} x={-90} y={40} turn={-14} ax={30} ay={46}
            arrow="M6 6C8 28 26 42 56 44M46 36l10 8-12 4" />
      <Flourish x={532} y={28} turn={30} />
    </div>
  );
}

// 3 - the finished edit
function Result() {
  return (
    <div className={`${s.art} ${s.art3}`} aria-hidden>
      <div className={s.card} style={{ left: 0, top: 0, width: u(560), height: u(290) }}>
        <div className={s.editFrame}>
          <span className={s.editThumb}>
            <Image src="/landing/thumb-sunset.jpg" alt="" fill sizes="160px" className={s.snapImg} />
            <Play /><b>0:31</b>
          </span>
          <span className={s.editCard}>
            <span className={s.wordmark}>halfheaven</span>
            <span className={s.smallRing} />
            <strong>Your edit</strong>
            <span className={s.mono}><Icon name="film" className={s.monoIcon} /> reel_012 · 0:31 · 17 cuts</span>
          </span>
        </div>
        <span className={s.stem} />
        <span className={s.downTile}><Icon name="download" className={s.downIcon} /></span>
      </div>
      <Note text={["Same look,", "new edit"]} x={-150} y={276} turn={-14} ax={96} ay={-44}
            arrow="M6 54C22 30 44 16 78 14M68 8l10 6-10 8" />
      <Flourish x={-44} y={36} turn={-50} />
    </div>
  );
}

const SCENES = [Read, Upload, Result];

export default function StepArt({ step }: { step: number }) {
  const Scene = SCENES[step];
  return <Scene />;
}

// the step-2 chips under the text: what you can drop in
const CHIPS: { icon: IconName; label: string }[] = [
  { icon: "film", label: "Clips" }, { icon: "mic", label: "Voice" }, { icon: "monitor", label: "Screen recordings" },
  { icon: "image", label: "Photos" }, { icon: "folder", label: "Anything you have" },
];

export function SourceChips() {
  return (
    <ul className={s.sourceChips}>
      {CHIPS.map((c) => <li key={c.label}><Icon name={c.icon} className={s.chipIcon} />{c.label}</li>)}
    </ul>
  );
}
