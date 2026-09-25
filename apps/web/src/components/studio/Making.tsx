"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { Facts } from "@/lib/pipeline";
import { about, clock, editSeconds, labToHex, narrate, snippet, STAGE_NAMES, type Voice } from "@/lib/studio";

import { Arrow } from "./icons";
import s from "./studio.module.css";

type Run = {
  id: string; status: "running" | "done" | "error"; stageIndex: number;
  startedAt?: number; error?: string; facts?: Facts;
};
type Words = { words: string[] | null; cuts: [number, number][] | null };

/** Faces the renderer ships, loaded into the page on demand. */
type Face = { file: string; family: string; italic: boolean; weights: [number, number] | null };
let catalogue: Promise<Face[]> | null = null;
const loaded = new Map<string, Promise<string>>();

/** The reel's own typeface, by family name, as a CSS family. Null until loaded
 *  or when the renderer has no such face. */
function useFace(family: string | null): string | null {
  const [css, setCss] = useState<string | null>(null);
  useEffect(() => {
    if (!family) return;
    catalogue ??= fetch("/api/fonts").then(r => r.json()).then(d => d.faces ?? []).catch(() => []);
    let live = true;
    catalogue.then(faces => {
      const want = family.toLowerCase();
      const face = faces.find(f => want === `${f.family}${f.italic ? " italic" : ""}`.toLowerCase())
        ?? faces.find(f => want.startsWith(f.family.toLowerCase()));
      if (!face) return;
      if (!loaded.has(face.file)) {
        const name = `hh-${face.file.replace(/\W/g, "-")}`;
        const font = new FontFace(name, `url(/api/fonts/${face.file})`,
          face.weights ? { weight: `${face.weights[0]} ${face.weights[1]}` } : {});
        loaded.set(face.file, font.load().then(f => { document.fonts.add(f); return name; }));
      }
      loaded.get(face.file)!.then(name => { if (live) setCss(`"${name}"`); }, () => {});
    });
    return () => { live = false; };
  }, [family]);
  return css;
}

/**
 * While the edit is being made: the creator's own footage keeps playing
 * (the Player underneath), and this says what is happening to it.
 *
 * Each bar is one stage the pipeline reports. The lines are written in the
 * reel's own caption voice and each one exists only once the pipeline has
 * printed the fact behind it. A line holds long enough to be read, so a burst
 * of facts plays out in order rather than flickering past.
 */
export default function Making({
  run, uploaded, voice, reelLab, sourceSeconds, time, matte, onRetry, onStartOver,
}: {
  run: Run;
  /** Upload progress 0..1 while the footage is still being sent, else null. */
  uploaded: number | null;
  voice: Voice;
  reelLab: number[] | null;
  sourceSeconds: number | null;
  time: number;
  matte: string | null;
  onRetry: () => void;
  onStartOver: () => void;
}) {
  const uploading = uploaded !== null;
  const stage = uploading ? -1 : run.stageIndex;
  const lines = useMemo(() => narrate(stage, run.facts, uploading), [stage, run.facts, uploading]);
  const [shown, setShown] = useState(() => Math.max(0, lines.length - 1));
  const [now, setNow] = useState(() => Date.now());
  const [words, setWords] = useState<Words | null>(null);
  const count = useRef(lines.length);
  const shownAt = useRef(0);
  useEffect(() => { count.current = lines.length; }, [lines.length]);

  // A burst of facts plays out in order, each held long enough to read and
  // faster the further behind it is. A new fact never restarts the wait.
  useEffect(() => {
    const t = window.setInterval(() => {
      setNow(Date.now());
      setShown(i => {
        const behind = count.current - 1 - i;
        if (behind <= 0 || Date.now() - shownAt.current < Math.max(900, 1800 - 250 * behind)) return i;
        shownAt.current = Date.now();
        return i + 1;
      });
    }, 250);
    return () => window.clearInterval(t);
  }, []);
  const line = lines[Math.min(shown, lines.length - 1)];

  // What was said and what was cut, once the pipeline has written them.
  const id = run.id;
  const needWords = !uploading && stage >= 2 && !words?.cuts;
  useEffect(() => {
    if (!needWords || id === "…") return;
    let live = true;
    const get = () => fetch(`/api/jobs/${id}/words`).then(r => r.json()).then((d: Words) => { if (live) setWords(d); }).catch(() => {});
    get();
    const t = window.setInterval(get, 1500);
    return () => { live = false; window.clearInterval(t); };
  }, [needWords, id]);

  const face = useFace(voice.face);
  const stressFace = useFace(voice.stressFace);
  const voiceStyle: React.CSSProperties = {
    fontFamily: face ?? undefined,
    textTransform: voice.caps ? "uppercase" : undefined,
  };
  const stressStyle: React.CSSProperties = {
    fontFamily: stressFace ?? face ?? undefined,
    color: voice.stress ?? "var(--accent)",
  };

  const said = line.key === "s2" || line.key === "cut"
    ? snippet(words?.words ?? [], line.key === "cut" ? words?.cuts ?? [] : []) : null;
  const facts = run.facts ?? {};
  const theirs = facts.gradeTo ?? reelLab;

  // The one estimate on this screen, worded as one.
  const seconds = sourceSeconds ?? facts.sourceSeconds ?? null;
  const elapsed = run.startedAt ? Math.max(0, (now - run.startedAt) / 1000) : 0;

  if (run.status === "error") {
    return (
      <div className={s.failed}>
        <h2>That didn&apos;t work</h2>
        <p>{run.error || "Something went wrong making the edit. Your footage is still here."}</p>
        <div className={s.failedRow}>
          <button className={s.btnLight} onClick={onRetry}>Try again</button>
          <button className={s.btnGhost} onClick={onStartOver}>Start over</button>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className={s.shade} />
      <div className={s.bars} role="progressbar" aria-label="Making your edit"
           aria-valuemin={0} aria-valuemax={5} aria-valuenow={Math.max(0, stage)}>
        {STAGE_NAMES.map((name, i) => (
          <b key={name} title={name}
             className={i < stage ? s.on : i === stage ? s.now : undefined}>
            {i === 0 && uploading && <i style={{ width: `${Math.round((uploaded ?? 0) * 100)}%` }} />}
          </b>
        ))}
      </div>

      {matte && line.key === "you" && (
        <MatteGlow src={matte} time={time} />
      )}

      <p key={line.key} className={s.say} style={voiceStyle} aria-live="polite">
        {line.lead}<b style={stressStyle}>{line.stress}</b>{line.tail}
      </p>

      {said && said.words.length > 0 && (
        <div className={s.tx} key={`tx-${line.key}`}>
          <small>What you said</small>
          {said.before && "… "}
          {said.words.map((w, i) => {
            const k = said.words.slice(0, i).filter(x => x.cut).length;
            return w.cut
              ? <span key={i}><span className={s.x} style={{ ["--k" as string]: `${0.35 + k * 0.3}s` }}>{w.text}</span>{" "}</span>
              : <span key={i}>{w.text} </span>;
          })}
          {said.after && "…"}
        </div>
      )}

      {line.key === "grade" && facts.gradeFrom && theirs && (
        <div className={s.swap}>
          <figure><span style={{ background: labToHex(facts.gradeFrom) }} />Yours</figure>
          <Arrow size={22} />
          <figure><span style={{ background: labToHex(theirs) }} />The reel&apos;s</figure>
        </div>
      )}

      <div className={s.status}>
        {uploading
          ? <>Sending your footage · <span className={s.mono}>{Math.round((uploaded ?? 0) * 100)}%</span></>
          : <>{seconds ? `Usually ${about(editSeconds(seconds))} for ${clock(seconds)} of video · ` : ""}
              <span className={s.mono}>{clock(elapsed)}</span></>}
        <small>You can leave this screen. It keeps going.</small>
      </div>
    </>
  );
}

/** The speaker's matte, lit in the accent and laid over their own footage:
 *  the moment separation finds them, shown rather than said. */
function MatteGlow({ src, time }: { src: string; time: number }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const v = ref.current;
    if (v && Math.abs(v.currentTime - time) > 0.2) v.currentTime = time;
  }, [time]);
  return (
    <div className={s.glow} aria-hidden>
      <video ref={ref} src={src} muted playsInline autoPlay loop />
    </div>
  );
}
