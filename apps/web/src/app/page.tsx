"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { capPlace, capSize, faceFamily, mood, pace, silence } from "@/lib/plain";

type Style = { id: string; name: string; file: string; hint: string };
type Receipt = {
  clips: number; captions: number; emphasised: number; punches: number;
  wordsCut: number; sourceSeconds: number; outputSeconds: number; emphasisWords: string[];
};
type Job = {
  id: string; status: "running" | "done" | "error"; stageIndex: number; progress: number;
  styleId: string; targetName: string; error?: string;
  profile?: any; receipt?: Receipt; segments?: number; punchAt?: number[];
  clips?: { start: number; end: number }[];
};
type Msg = { who: "me" | "bot"; text: string; changed?: string[] };

/* What the app is doing, said the way a person would say it. */
const DOING = [
  "Studying the look you picked",
  "Listening to your video",
  "Deciding what to cut",
  "Laying out the captions",
  "Putting it together",
];

const SUGGESTIONS = [
  "Bigger captions",
  "Cut it tighter",
  "Less zooming",
  "Warmer colour",
  "Move captions up",
  "Fewer words per line",
  "Punch more words",
  "Keep more pauses",
  "All caps captions",
];

const LOOK_ART: Record<string, { g: string; f: string; tag: string; blurb: string }> = {
  "night-interview": { g: "linear-gradient(160deg,#2A2418,#0E0C08)", f: "#E4D97A", tag: "Aa",
    blurb: "Moody street interview. Small gold captions, big word punches." },
  "street-montage": { g: "linear-gradient(160deg,#3A4A5E,#141A22)", f: "#FFE94A", tag: "Aa",
    blurb: "Fast travel montage. Bold type over scenery." },
};

export default function Studio() {
  const [styles, setStyles] = useState<Style[]>([]);
  const [styleId, setStyleId] = useState("night-interview");
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [over, setOver] = useState(false);
  const [split, setSplit] = useState(50);
  const [uploaded, setUploaded] = useState(1);
  const [msgs, setMsgs] = useState<Msg[]>([
    { who: "bot", text: "Pick a look and drop a video in. Once it's done, tell me what to change — plain words are fine." },
  ]);
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, unknown>>({});

  const fileInput = useRef<HTMLInputElement>(null);
  const screenRef = useRef<HTMLDivElement>(null);
  const beforeRef = useRef<HTMLVideoElement>(null);
  const afterRef = useRef<HTMLVideoElement>(null);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => { fetch("/api/demo").then(r => r.json()).then(d => d.job && setJob(d.job)); }, []);
  useEffect(() => { fetch("/api/styles").then(r => r.json()).then(d => setStyles(d.styles)); }, []);
  useEffect(() => { logRef.current?.scrollTo({ top: 1e6, behavior: "smooth" }); }, [msgs, thinking]);

  useEffect(() => {
    if (!job || job.status !== "running") return;
    const t = setInterval(async () => {
      const r = await fetch(`/api/jobs/${job.id}`);
      if (r.ok) setJob(await r.json());
    }, 700);
    return () => clearInterval(t);
  }, [job?.id, job?.status]);

  const start = useCallback(async (patch: Record<string, unknown> = overrides) => {
    if (!file) { fileInput.current?.click(); return; }
    const fd = new FormData();
    fd.set("target", file); fd.set("styleId", styleId);
    fd.set("overrides", JSON.stringify(patch));
    setUploaded(0);
    setJob({ id: "…", status: "running", stageIndex: -1, progress: 0.02, styleId, targetName: file.name });
    const d = await new Promise<{ id?: string; error?: string }>(res => {
      const x = new XMLHttpRequest();
      x.open("POST", "/api/jobs");
      x.upload.onprogress = e => e.lengthComputable && setUploaded(e.loaded / e.total);
      x.onload = () => res(JSON.parse(x.responseText || "{}"));
      x.onerror = () => res({ error: "The upload didn't go through. Give it another go." });
      x.send(fd);
    });
    setJob(d.id
      ? { id: d.id, status: "running", stageIndex: 0, progress: 0.08, styleId, targetName: file.name }
      : { id: "—", status: "error", stageIndex: 0, progress: 0, styleId, targetName: file.name, error: d.error });
  }, [file, styleId, overrides]);

  const say = useCallback(async (text: string) => {
    if (!text.trim() || thinking) return;
    setMsgs(m => [...m, { who: "me", text }]); setDraft(""); setThinking(true);
    try {
      const r = await fetch("/api/chat", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ message: text, profile: job?.profile }),
      });
      const d = await r.json();
      const merged = { ...overrides, ...d.overrides };
      setOverrides(merged);
      setMsgs(m => [...m, { who: "bot", text: d.reply, changed: d.changed }]);
      if (Object.keys(d.overrides ?? {}).length && file) start(merged);
    } finally { setThinking(false); }
  }, [thinking, job, overrides, file, start]);

  /* the styled cut runs ahead of the source, so map program time back */
  const sync = () => {
    const b = beforeRef.current, a = afterRef.current;
    if (!b || !a) return;
    let want = a.currentTime;
    const clips = job?.clips;
    if (clips?.length) {
      let elapsed = 0; want = clips[clips.length - 1].end;
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
    const r = screenRef.current?.getBoundingClientRect(); if (!r) return;
    setSplit(Math.max(2, Math.min(98, ((e.clientX - r.left) / r.width) * 100)));
  };

  const running = job?.status === "running";
  const done = job?.status === "done";
  const p = job?.profile;
  const r = job?.receipt;
  const saved = r ? Math.max(0, r.sourceSeconds - r.outputSeconds) : 0;

  return (
    <div className="app">
      <header className="top">
        <span className="logo"><span className="dot">H</span><span className="name">Halfheaven</span></span>
        <span className="spacer" />
        {job && (
          <span className={`badge ${running ? "busy" : done ? "ok" : ""}`}>
            <span className="dot" />
            {running
              ? job.stageIndex < 0 ? `Uploading ${Math.round(uploaded * 100)}%` : DOING[job.stageIndex]
              : done ? "Ready" : "Didn't work"}
          </span>
        )}
        {done && (
          <a className="btn sm" href={`/api/jobs/${job!.id}/media?v=after`} download={`edit-${job!.id}.mp4`}>
            Save video
          </a>
        )}
        <button className="btn primary sm" onClick={() => start()} disabled={running}>
          {running ? "Working…" : file ? "Make my edit" : "Add a video"}
        </button>
      </header>

      <div className="body">
        {/* ---------------- left: what goes in ---------------- */}
        <aside className="left">
          <div className="block">
            <span className="eyebrow">Your video</span>
            <input ref={fileInput} type="file" accept="video/*" hidden
              onChange={e => setFile(e.target.files?.[0] ?? null)} />
            {file ? (
              <div className="loaded">
                <span className="thumb">▸</span>
                <span style={{ flex: 1 }}>
                  <span className="nm" style={{ display: "block" }}>{file.name}</span>
                  <span className="tiny">{(file.size / 1e6).toFixed(0)} MB</span>
                </span>
                <button className="btn ghost sm" onClick={() => setFile(null)}>Change</button>
              </div>
            ) : (
              <button className={`drop${over ? " over" : ""}`} onClick={() => fileInput.current?.click()}
                onDragOver={e => { e.preventDefault(); setOver(true); }}
                onDragLeave={() => setOver(false)}
                onDrop={e => { e.preventDefault(); setOver(false); setFile(e.dataTransfer.files?.[0] ?? null); }}>
                <span className="big">Drop your video here</span>
                <span className="sub">Talk to camera, ums and all. It needs sound.</span>
              </button>
            )}
          </div>

          <div className="block">
            <span className="eyebrow">Pick a look</span>
            <div className="looks">
              {styles.map(s => {
                const art = LOOK_ART[s.id] ?? LOOK_ART["night-interview"];
                return (
                  <button key={s.id} className="look" aria-pressed={s.id === styleId}
                    onClick={() => setStyleId(s.id)}
                    style={{ ["--g" as string]: art.g, ["--f" as string]: art.f }}>
                    <span className="swatch"><b>{art.tag}</b></span>
                    <span>
                      <span className="t" style={{ display: "block" }}>{s.name}</span>
                      <span className="d">{art.blurb}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </aside>

        {/* ---------------- middle: the video ---------------- */}
        <main className="middle">
          <div className="theatre">
            <div className="screen" ref={screenRef} style={{ ["--split" as string]: `${split}%` }}>
              {done ? (
                <>
                  <video ref={beforeRef} src={`/api/jobs/${job!.id}/media?v=before`} muted loop playsInline autoPlay />
                  <video ref={afterRef} className="after" src={`/api/jobs/${job!.id}/media?v=after`}
                    muted loop playsInline autoPlay onTimeUpdate={sync} />
                  <span className="seam" /><span className="grip">↔</span>
                  <span className="handle" onPointerDown={drag} onPointerMove={drag} />
                  <span className="tag l">Yours</span>
                  <span className="tag r">Edited</span>
                </>
              ) : (
                <div className="waiting">
                  {running && <span className="ring" />}
                  <span style={{ fontWeight: 650 }}>
                    {running
                      ? job!.stageIndex < 0 ? "Uploading your video…" : DOING[job!.stageIndex] + "…"
                      : job?.status === "error" ? "That didn't work" : "Your edit will show up here"}
                  </span>
                  <span style={{ fontSize: 13, opacity: .65, maxWidth: 260 }}>
                    {running ? "Usually about half a minute."
                      : job?.status === "error" ? (job.error || "Try a different video.")
                      : "Drop a video on the left and hit Make my edit."}
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="strip">
            {done && r ? (
              <>
                <span className="fact"><b>{saved.toFixed(0)}s</b> shorter</span>
                <span className="fact">Cut <b>{r.wordsCut}</b> stumbles</span>
                <span className="fact"><b>{r.captions}</b> captions, one word at a time</span>
                <span className="fact"><b>{r.emphasised}</b> words punched</span>
                <span className="fact"><b>{r.punches}</b> zoom-ins</span>
              </>
            ) : (
              <span className="tiny">
                Everything you see here was measured from the look you picked — nothing invented.
              </span>
            )}
          </div>
        </main>

        {/* ---------------- right: chat ---------------- */}
        <aside className="chat">
          <div className="chat-head">
            <h2 style={{ fontSize: 16 }}>Tell me what to change</h2>
            <span className="tiny">Plain words. I'll redo the edit each time.</span>
          </div>

          <div className="chat-log" ref={logRef}>
            {p && (
              <div className="reads" style={{ marginBottom: 4 }}>
                <span className="eyebrow">What this look does</span>
                {(() => {
                  const pc = pace(p.pacing.cuts_per_min, p.pacing.median_shot);
                  const si = silence(p.trim.max_silence);
                  const md = mood(p.grade.lab_mean[0]);
                  return (
                    <>
                      <div className="read"><span className="sw">✂</span>
                        <span><span className="t">{pc.t}</span><span className="d" style={{ display: "block" }}>{pc.d}</span></span></div>
                      <div className="read"><span className="sw">⏱</span>
                        <span><span className="t">{si.t}</span><span className="d" style={{ display: "block" }}>{si.d}</span></span></div>
                      <div className="read">
                        <span className="sw" style={{ fontFamily: faceFamily(p.captions.font_category), color: p.captions.fill_hex, background: "var(--theatre)" }}>Aa</span>
                        <span><span className="t">{capSize(p.captions.size_pct)} captions, {capPlace(p.captions.anchor[1])}</span>
                          <span className="d" style={{ display: "block" }}>Up to {p.captions.max_words} words at a time</span></span></div>
                      <div className="read">
                        <span className="sw" style={{ fontFamily: faceFamily(p.emphasis.font_category), color: p.captions.fill_hex, background: "var(--theatre)", fontWeight: 900 }}>A</span>
                        <span><span className="t">Big word punches</span>
                          <span className="d" style={{ display: "block" }}>Key words jump out in a different font</span></span></div>
                      <div className="read"><span className="sw">◐</span>
                        <span><span className="t">{md.t} colour</span><span className="d" style={{ display: "block" }}>{md.d}</span></span></div>
                    </>
                  );
                })()}
              </div>
            )}

            {msgs.map((m, i) => (
              <div key={i} className={`msg ${m.who}`}>
                <span className="av">{m.who === "me" ? "You" : "H"}</span>
                <span>
                  <span className="bubble" style={{ display: "block" }}>{m.text}</span>
                  {m.changed && m.changed.length > 0 && (
                    <span className="did">{m.changed.map(c => <span key={c}>{label(c)}</span>)}</span>
                  )}
                </span>
              </div>
            ))}
            {thinking && (
              <div className="msg bot"><span className="av">H</span>
                <span className="bubble thinking"><i /><i /><i /></span></div>
            )}
          </div>

          <div className="chat-foot">
            <div className="suggest">
              {SUGGESTIONS.map(s => (
                <button key={s} className="chip" onClick={() => say(s)} disabled={thinking}>{s}</button>
              ))}
            </div>
            <div className="composer">
              <textarea rows={1} placeholder="Make the captions pop more…" value={draft}
                onChange={e => setDraft(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); say(draft); } }} />
              <button className="send" onClick={() => say(draft)} disabled={!draft.trim() || thinking}>↑</button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

/** Turn a settings path into something a creator recognises. */
function label(path: string) {
  const map: Record<string, string> = {
    "captions.size_pct": "caption size",
    "captions.anchor": "caption position",
    "captions.fill_hex": "caption colour",
    "captions.max_words": "words per line",
    "captions.all_caps": "capitals",
    "emphasis.size_pct": "punch size",
    "trim.aggressiveness": "how much is cut",
    "trim.max_silence": "pauses",
    "punch.rate": "how often it zooms",
    "punch.scale_mean": "zoom amount",
    "grade.strength": "colour",
  };
  return map[path] ?? path.split(".").pop()!;
}
