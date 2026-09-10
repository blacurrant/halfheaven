"use client";

import { useEffect, useRef, useState } from "react";

type Shot = { at: number; length: number; punched: boolean };
type Card = { at: number; length: number; text: string; stressed: boolean };
type Data = { duration: number; shots: Shot[]; captions: Card[] };

const clock = (s: number) =>
  `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** The cut, laid out. Frames along the top so you can find a moment by eye,
 *  then two lanes: where the shots change, and where each caption sits. */
export default function Timeline({
  jobId, at, onSeek, version,
}: { jobId: string; at: number; onSeek: (t: number) => void; version: number }) {
  const [data, setData] = useState<Data | null>(null);
  const strip = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch(`/api/jobs/${jobId}/timeline`).then(r => r.json())
      .then(d => { if (!d.error) setData(d); });
  }, [jobId, version]);

  if (!data) return null;
  const pct = (t: number) => `${(t / data.duration) * 100}%`;

  const scrub = (e: React.PointerEvent) => {
    if (e.buttons === 0 && e.type !== "pointerdown") return;
    const r = strip.current?.getBoundingClientRect();
    if (!r) return;
    onSeek(Math.max(0, Math.min(data.duration, ((e.clientX - r.left) / r.width) * data.duration)));
  };

  return (
    <div className="tl">
      <div className="tl-head">
        <span className="eyebrow">Timeline</span>
        <span className="tiny mono">{clock(at)} / {clock(data.duration)}</span>
        <span className="tl-legend">
          <i className="k-shot" /> shot
          <i className="k-punch" /> pushed in
          <i className="k-cap" /> caption
        </span>
      </div>

      <div className="tl-strip" ref={strip} onPointerDown={scrub} onPointerMove={scrub}>
        <div className="frames"
          style={{ backgroundImage: `url(/api/jobs/${jobId}/thumbs?v=${version})` }} />

        <div className="lane shots">
          {data.shots.map((s, i) => (
            <span key={i} className={`shot${s.punched ? " punched" : ""}`}
              style={{ left: pct(s.at), width: pct(s.length) }}
              title={`Shot ${i + 1} — ${s.length.toFixed(1)}s${s.punched ? ", pushed in" : ""}`} />
          ))}
        </div>

        <div className="lane caps">
          {data.captions.map((c, i) => (
            <span key={i} className={`cap${c.stressed ? " stressed" : ""}`}
              style={{ left: pct(c.at), width: pct(Math.max(c.length, 0.12)) }}
              title={c.text} />
          ))}
        </div>

        <span className="head" style={{ left: pct(at) }} />
      </div>
    </div>
  );
}
