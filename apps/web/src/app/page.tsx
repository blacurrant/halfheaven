"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type Style = { id: string; name: string; file: string; hint: string };
type Receipt = {
  clips: number; captions: number; emphasised: number; punches: number;
  wordsCut: number; sourceSeconds: number; outputSeconds: number; emphasisWords: string[];
};
type Job = {
  id: string; status: "running" | "done" | "error"; stageIndex: number; progress: number;
  styleId: string; targetName: string; error?: string; tail?: string[];
  profile?: any; receipt?: Receipt; segments?: number; punchAt?: number[];
  clips?: { start: number; end: number }[];
};

const STAGES = [
  "Reading the reference",
  "Transcribing",
  "Editorial pass",
  "Planning the cut",
  "Rendering",
];

const secs = (n?: number) => (n == null ? "—" : `${n.toFixed(1)}s`);

export default function Workspace() {
  const [styles, setStyles] = useState<Style[]>([]);
  const [styleId, setStyleId] = useState("night-interview");
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [over, setOver] = useState(false);
  const [split, setSplit] = useState(50);
  const [uploaded, setUploaded] = useState(1);
  const inputRef = useRef<HTMLInputElement>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const beforeRef = useRef<HTMLVideoElement>(null);
  const afterRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    fetch("/api/demo").then((r) => r.json()).then((d) => { if (d.job) setJob(d.job); });
  }, []);

  useEffect(() => {
    fetch("/api/styles").then((r) => r.json()).then((d) => {
      setStyles(d.styles);
      if (d.styles[0]) setStyleId((s) => d.styles.some((x: Style) => x.id === s) ? s : d.styles[0].id);
    });
  }, []);

  /* poll while a job is in flight */
  useEffect(() => {
    if (!job || job.status !== "running") return;
    const t = setInterval(async () => {
      const r = await fetch(`/api/jobs/${job.id}`);
      if (r.ok) setJob(await r.json());
    }, 700);
    return () => clearInterval(t);
  }, [job?.id, job?.status]);

  const run = useCallback(async () => {
    if (!file) { inputRef.current?.click(); return; }
    const fd = new FormData();
    fd.set("target", file);
    fd.set("styleId", styleId);
    setUploaded(0);
    setJob({ id: "…", status: "running", stageIndex: -1, progress: 0.02, styleId, targetName: file.name });
    const d = await new Promise<{ id?: string; error?: string }>((resolve) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", "/api/jobs");
      xhr.upload.onprogress = (e) => e.lengthComputable && setUploaded(e.loaded / e.total);
      xhr.onload = () => resolve(JSON.parse(xhr.responseText || "{}"));
      xhr.onerror = () => resolve({ error: "Upload failed. Check the connection and try again." });
      xhr.send(fd);
    });
    if (d.id) setJob({ id: d.id, status: "running", stageIndex: 0, progress: 0.08, styleId, targetName: file.name });
    else setJob({ id: "—", status: "error", stageIndex: 0, progress: 0, styleId, targetName: file.name, error: d.error });
  }, [file, styleId]);

  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); run(); }
    };
    addEventListener("keydown", k);
    return () => removeEventListener("keydown", k);
  }, [run]);

  /* The styled cut has material removed, so its clock runs ahead of the
     source's. Matching the two on raw currentTime would compare unrelated
     moments; this walks the clip list to turn program time back into source
     time, the same mapping the pipeline uses to place captions. */
  const sync = () => {
    const b = beforeRef.current, a = afterRef.current;
    if (!b || !a) return;
    const clips = job?.clips;
    let want = a.currentTime;
    if (clips?.length) {
      let elapsed = 0;
      want = clips[clips.length - 1].end;
      for (const c of clips) {
        const d = c.end - c.start;
        if (a.currentTime < elapsed + d) { want = c.start + (a.currentTime - elapsed); break; }
        elapsed += d;
      }
    }
    if (Math.abs(b.currentTime - want) > 0.12) b.currentTime = want;
  };

  const drag = (e: React.PointerEvent) => {
    if (e.buttons === 0 && e.type !== "pointerdown") return;
    const r = frameRef.current?.getBoundingClientRect();
    if (!r) return;
    setSplit(Math.max(2, Math.min(98, ((e.clientX - r.left) / r.width) * 100)));
  };

  const running = job?.status === "running";
  const done = job?.status === "done";
  const style = styles.find((s) => s.id === styleId);
  const p = job?.profile;
  const segCount = job?.segments ?? 16;

  return (
    <div className="app">
      {/* ---------------- top bar ---------------- */}
      <header className="top">
        <span className="brand"><span className="glyph">H</span>Halfheaven</span>
        <span className="sep" />
        <span className="mono" style={{ fontSize: 11.5, color: "var(--muted)" }}>
          {file ? file.name : "no source"}
        </span>
        {job && (
          <span className={`pill ${running ? "live" : done ? "ok" : "err"}`}>
            <span className="dot" />
            {running
              ? job.stageIndex < 0
                ? `Uploading ${Math.round(uploaded * 100)}%`
                : STAGES[job.stageIndex]
              : done ? "Complete" : "Failed"}
          </span>
        )}
        {running && (
          <div className="plane"><i style={{ width: `${((job!.stageIndex < 0 ? 0.02 + uploaded * 0.06 : job!.progress) * 100).toFixed(0)}%` }} /></div>
        )}
        <span className="spacer" />
        {done && (
          <a className="btn sm" href={`/api/jobs/${job!.id}/media?v=after`} download={`styled-${job!.id}.mp4`}>
            Download
          </a>
        )}
        <button className="btn primary sm" onClick={run} disabled={running}>
          {running ? "Working…" : "Run"} <span className="kbd" style={{ marginLeft: 2 }}>⌘↵</span>
        </button>
      </header>

      <div className="body">
        {/* ---------------- left rail ---------------- */}
        <aside className="rail">
          <div className="sec">
            <div className="sec-head"><span className="lbl">Source</span></div>
            <input ref={inputRef} type="file" accept="video/*" hidden
              onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            {file ? (
              <div className="file">
                <div>
                  <div className="n">{file.name}</div>
                  <div className="m mono">{(file.size / 1e6).toFixed(1)} MB</div>
                </div>
                <button className="btn quiet sm" onClick={() => setFile(null)}>Clear</button>
              </div>
            ) : (
              <button
                className={`drop${over ? " over" : ""}`}
                onClick={() => inputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setOver(true); }}
                onDragLeave={() => setOver(false)}
                onDrop={(e) => { e.preventDefault(); setOver(false); setFile(e.dataTransfer.files?.[0] ?? null); }}
              >
                <span className="t">Drop a take</span>
                <span className="d">Ums and all. Needs an audio track.</span>
              </button>
            )}
          </div>

          <div className="sec">
            <div className="sec-head">
              <span className="lbl">Reference style</span>
              <span className="mono" style={{ fontSize: 10, color: "var(--dim)" }}>{styles.length}</span>
            </div>
            <div className="styles">
              {styles.map((s) => (
                <button key={s.id} className="srow" aria-pressed={s.id === styleId}
                  onClick={() => setStyleId(s.id)}
                  style={{ ["--f" as string]: s.id === "night-interview" ? "#A4A848" : "#FFE94A" }}>
                  <span className="chip" />
                  <span>
                    <span className="nm">{s.name}</span>
                    <span className="sub mono" style={{ display: "block" }}>{s.hint}</span>
                  </span>
                  <span className="tick">✓</span>
                </button>
              ))}
            </div>
          </div>

          <div style={{ flex: 1 }} />
          <div className="sec">
            <span className="lbl">Local pipeline</span>
            <span className="mono" style={{ fontSize: 11, color: "var(--dim)", lineHeight: 1.7 }}>
              groq whisper-large-v3-turbo<br />gpt-oss-120b · qwen3.8-27b<br />ffmpeg 9.0.1 · lut3d
            </span>
          </div>
        </aside>

        {/* ---------------- viewport ---------------- */}
        <main className="center">
          <div className="viewport">
            <div className={`frame${done ? "" : " idle"}`} ref={frameRef}
              style={{ ["--split" as string]: `${split}%` }}>
              {done ? (
                <>
                  <video ref={beforeRef} src={`/api/jobs/${job!.id}/media?v=before`}
                    muted loop playsInline autoPlay />
                  <video ref={afterRef} className="after" src={`/api/jobs/${job!.id}/media?v=after`}
                    muted loop playsInline autoPlay onTimeUpdate={sync} />
                  <span className="seam" />
                  <span className="grab" onPointerDown={drag} onPointerMove={drag} />
                  <span className="tagl">source</span>
                  <span className="tagr">styled</span>
                </>
              ) : (
                <div className="empty">
                  <span style={{ fontSize: 12.5 }}>
                    {running ? (job!.stageIndex < 0 ? "Uploading…" : STAGES[job!.stageIndex] + "…") : "Nothing rendered yet"}
                  </span>
                  <span className="mono" style={{ fontSize: 11 }}>
                    {running ? `job ${job!.id}` : "Pick a style, drop a take, press ⌘↵"}
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* ---------------- timeline ---------------- */}
          <div className="timeline">
            <div className="tl-head">
              <span className="lbl">Timeline</span>
              <span className="mono" style={{ fontSize: 11, color: "var(--dim)" }}>
                {done ? `${job!.receipt!.clips} segments · ${secs(job!.receipt!.outputSeconds)}` : `${segCount} segments`}
              </span>
              <span className="spacer" />
              {done && (
                <span className="mono" style={{ fontSize: 11, color: "var(--dim)" }}>
                  {secs(job!.receipt!.sourceSeconds)} → {secs(job!.receipt!.outputSeconds)}
                </span>
              )}
            </div>
            <div className="segs">
              {Array.from({ length: segCount }).map((_, i) => {
                const filled = done || (running && job!.stageIndex >= 4 &&
                  i < Math.round(((job!.progress - 0.8) / 0.2) * segCount));
                return (
                  <span key={i}
                    className={`s${filled ? "" : " pending"}${job?.punchAt?.includes(i) ? " punch" : ""}`} />
                );
              })}
            </div>
          </div>
        </main>

        {/* ---------------- inspector ---------------- */}
        <aside className="inspector">
          {job?.status === "error" && (
            <div className="sec">
              <div className="banner">
                <span className="t">That take didn&apos;t go through.</span>
                <span className="d">{job.error || "The pipeline stopped before it produced a program."}</span>
              </div>
            </div>
          )}

          {running && (
            <div className="sec">
              <span className="lbl">Progress</span>
              <div className="stages">
                {STAGES.map((s, i) => (
                  <div key={s} className={`stage ${i === job!.stageIndex ? "active" : i < job!.stageIndex ? "done" : ""}`}>
                    <span className="ix mono">{String(i + 1).padStart(2, "0")}</span>
                    <span>{s}</span>
                    <span className="out mono">{i < job!.stageIndex ? "done" : ""}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {p && (
            <div className="sec">
              <span className="lbl">Extracted from {style?.name}</span>
              <div>
                <div className="kv"><span className="k">Median shot</span><span className="v mono">{p.pacing.median_shot.toFixed(2)}s</span></div>
                <div className="kv"><span className="k">Cut rhythm</span><span className="v mono">{p.pacing.cuts_per_min.toFixed(1)}/min</span></div>
                <div className="kv"><span className="k">Longest pause</span><span className="v mono">{p.trim.max_silence.toFixed(2)}s</span></div>
                <div className="kv"><span className="k">Body face</span><span className="v mono">{p.captions.font_category}</span></div>
                <div className="kv"><span className="k">Emphasis face</span><span className="v mono">{p.emphasis.font_category}</span></div>
                <div className="kv"><span className="k">Caption fill</span>
                  <span className="v swatch mono"><i style={{ background: p.captions.fill_hex }} />{p.captions.fill_hex}</span></div>
                <div className="kv"><span className="k">Caption band</span><span className="v mono">{Math.round(p.captions.anchor[1] * 100)}% height</span></div>
                <div className="kv"><span className="k">Grade (LAB L)</span><span className="v mono">{p.grade.lab_mean[0].toFixed(1)}</span></div>
              </div>
            </div>
          )}

          {done && job!.receipt && (
            <div className="sec">
              <span className="lbl">What changed</span>
              <div>
                <div className="kv"><span className="k">Filler words removed</span><span className="v mono">{job!.receipt.wordsCut}</span></div>
                <div className="kv"><span className="k">Caption cards</span><span className="v mono">{job!.receipt.captions}</span></div>
                <div className="kv"><span className="k">Words emphasised</span><span className="v mono">{job!.receipt.emphasised}</span></div>
                <div className="kv"><span className="k">Push-ins</span><span className="v mono">{job!.receipt.punches}</span></div>
                <div className="kv"><span className="k">Runtime</span>
                  <span className="v mono">{secs(job!.receipt.sourceSeconds)} → {secs(job!.receipt.outputSeconds)}</span></div>
              </div>
              {job!.receipt.emphasisWords.length > 0 && (
                <>
                  <span className="lbl" style={{ marginTop: 4 }}>Stressed</span>
                  <span className="mono" style={{ fontSize: 11.5, color: "var(--muted)", lineHeight: 1.8 }}>
                    {job!.receipt.emphasisWords.join(" · ")}
                  </span>
                </>
              )}
            </div>
          )}

          {!job && (
            <div className="sec">
              <span className="lbl">How it works</span>
              <span style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.65 }}>
                The reference is measured, not guessed: shot lengths, caption band and fill,
                type category, and the colour statistics of its graded frames.
                Your take keeps its own words — only the treatment is transferred.
              </span>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
