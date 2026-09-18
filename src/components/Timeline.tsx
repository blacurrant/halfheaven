"use client";

import { useEffect, useRef, useState } from "react";

type Shot = { at: number; length: number; punched: boolean };
type Card = { at: number; length: number; text: string; stressed: boolean };
type Data = { duration: number; shots: Shot[]; captions: Card[] };

const clock = (s: number) =>
  `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

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
    <div className="border-t border-[var(--line)] bg-[var(--card)] py-2.5 px-4 pb-3.5 flex flex-col gap-2">
      <div className="flex items-center gap-3">
        <span className="text-[11.5px] font-semibold tracking-[0.04em] uppercase text-[var(--faint)]">Timeline</span>
        <span className="text-xs text-[var(--muted)] font-mono">{clock(at)} / {clock(data.duration)}</span>
        <span className="ml-auto flex items-center gap-1.5 text-[11.5px] text-[var(--faint)]">
          <i className="w-2 h-2 rounded-sm inline-block ml-2 bg-[#6B5F69]" /> shot
          <i className="w-2 h-2 rounded-sm inline-block ml-2 bg-[#C3D3E2]" /> pushed in
          <i className="w-2 h-2 rounded-sm inline-block ml-2 bg-[#E3C47A]" /> caption
        </span>
      </div>

      <div className="relative cursor-pointer select-none border border-[var(--line)] rounded-lg overflow-hidden bg-[var(--theatre)] touch-manipulation" ref={strip} onPointerDown={scrub} onPointerMove={scrub}>
        <div className="h-[46px] bg-no-repeat bg-auto opacity-85" style={{ backgroundImage: `url(/api/jobs/${jobId}/thumbs?v=${version})`, backgroundSize:"auto 100%" }} />

        <div className="relative h-[9px] my-1">
          {data.shots.map((s, i) => (
            <span key={i} className={`absolute top-0 h-full rounded-sm bg-[#6B5F69] border-r border-[var(--theatre)] ${s.punched ? "bg-[#C3D3E2] opacity-90" : ""}`}
              style={{ left: pct(s.at), width: pct(s.length) }}
              title={`Shot ${i + 1} — ${s.length.toFixed(1)}s${s.punched ? ", pushed in" : ""}`} />
          ))}
        </div>

        <div className="relative h-[9px] my-1">
          {data.captions.map((c, i) => (
            <span key={i} className={`absolute rounded-[3px] bg-[#E3C47A] opacity-55 ${c.stressed ? "opacity-100 h-[9px] top-0" : "top-0.5 h-[5px]"}`}
              style={{ left: pct(c.at), width: pct(Math.max(c.length, 0.12)) }}
              title={c.text} />
          ))}
        </div>

        <span className="absolute top-0 bottom-0 w-0.5 bg-white pointer-events-none shadow-[0_0_6px_rgba(0,0,0,0.7)]" style={{ left: pct(at) }} />
      </div>
    </div>
  );
}
