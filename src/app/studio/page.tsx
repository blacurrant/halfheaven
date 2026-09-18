"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import CaptionFixer from "@/components/CaptionFixer";
import Drop from "@/components/Drop";
import Readout from "@/components/Readout";
import Scorecard from "@/components/Scorecard";
import Timeline from "@/components/Timeline";
import type { Fingerprint } from "@/lib/fingerprint";
import type { Score } from "@/lib/score";

type Read = {
  id: string; status: "running" | "done" | "error"; name: string; videoPath: string;
  error?: string; fingerprint?: Fingerprint;
};
type Style = { id: string; name: string };
type Receipt = {
  clips: number; captions: number; emphasised: number; punches: number;
  wordsCut: number; sourceSeconds: number; outputSeconds: number;
};
type Job = {
  id: string; status: "running" | "done" | "error"; stageIndex: number; progress: number;
  targetName: string; error?: string;
  profile?: unknown; receipt?: Receipt; clips?: { start: number; end: number }[];
};
type Msg = { who: "me" | "bot"; text: string; changed?: string[] };
type Panel = "edit" | "read" | "score" | null;
type Tab = "ask" | "captions" | "style";

const DOING = [
  "Studying the look",
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

const HELLO: Msg = { who: "bot", text: "Tell me what to change — plain words are fine." };

const mb = (files: File[]) => `${(files.reduce((a, f) => a + f.size, 0) / 1e6).toFixed(1)} MB`;

// ── icons (rail) ─────────────────────────────────────────────────────────
const Icon = ({ children, size = 18 }: { children: React.ReactNode; size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} strokeLinecap="round" strokeLinejoin="round" aria-hidden>{children}</svg>
);
const LogoIcon = () => <Icon><circle cx={12} cy={12} r={9} /><path d="M12 8a4 4 0 0 1 4 4" /></Icon>;
const BotIcon = () => <Icon><rect x={4} y={6} width={16} height={12} rx={6} /><circle cx={9} cy={11} r={1.4} fill="currentColor" stroke="none" /><circle cx={15} cy={11} r={1.4} fill="currentColor" stroke="none" /><path d="M9 15c1.2 .9 3.8 .9 6 0" /></Icon>;
const KeyIcon = () => <Icon><path d="M14 7a3 3 0 1 1-4 4L6 15l-2 2 2 0 0-2 2-2" /><circle cx={14} cy={7} r={1} fill="currentColor" stroke="none" /></Icon>;
const ChartIcon = () => <Icon><path d="M4 19V9" /><path d="M10 19V5" /><path d="M16 19V12" /></Icon>;
const ChatIcon = () => <Icon><path d="M4 9a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v5a4 4 0 0 1-4 4H9l-5 3z" /><path d="M8 12h8M8 8h5" opacity={0} /></Icon>;
const GridIcon = () => <Icon><rect x={4} y={4} width={6} height={6} rx={1.5} /><rect x={14} y={4} width={6} height={6} rx={1.5} /><rect x={4} y={14} width={6} height={6} rx={1.5} /><rect x={14} y={14} width={6} height={6} rx={1.5} /></Icon>;
const BookIcon = () => <Icon><path d="M4 5a2 2 0 0 1 2-2h6v16H6a2 2 0 0 0-2 2z" /><path d="M12 3h6a2 2 0 0 1 2 2v12a2 2 0 0 0-2 2h-6z" /></Icon>;
const BagIcon = () => <Icon><path d="M6 7h12v10a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2z" /><path d="M9 7V5a3 3 0 0 1 6 0v2" /></Icon>;

function ColorWheel({ size = 22 }: { size?: number }) {
  return (
    <span aria-hidden style={{
      width: size, height: size, borderRadius: "50%",
      background: "conic-gradient(from 0deg, #ff3b30, #ffcc00, #4cd964, #5ac8fa, #007aff, #af52de, #ff2d55, #ff3b30)",
      display: "inline-block", border: "2px solid rgba(255,255,255,0.9)", boxShadow: "0 1px 6px rgba(0,0,0,0.4)"
    }} />
  );
}

export default function Studio() {
  const [refFile, setRefFile] = useState<File | null>(null);
  const [read, setRead] = useState<Read | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const readSeq = useRef(0);
  const [styles, setStyles] = useState<Style[]>([]);
  const [presets, setPresets] = useState(false);
  const [preset, setPreset] = useState<Style | null>(null);
  const [targets, setTargets] = useState<File[]>([]);
  const [previewUrls, setPreviewUrls] = useState<string[]>([]);
  const [localDurations, setLocalDurations] = useState<number[]>([]);

  const [job, setJob] = useState<Job | null>(null);
  const [uploaded, setUploaded] = useState(1);
  const lastGood = useRef<Job | null>(null);
  const [overrides, setOverrides] = useState<Record<string, unknown>>({});
  const [videoKey, setVideoKey] = useState(0);

  const [sound, setSound] = useState(false);
  const [compare, setCompare] = useState(false);
  const [split, setSplit] = useState(50);
  const [playhead, setPlayhead] = useState(0);
  const [menu, setMenu] = useState(false);
  const [panel, setPanel] = useState<Panel>(null);
  const [tab, setTab] = useState<Tab>("ask");

  const [msgs, setMsgs] = useState<Msg[]>([HELLO]);
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const [looks, setLooks] = useState<{ id: string; label: string; blurb: string }[]>([]);
  const looksAsked = useRef(false);
  const [look, setLook] = useState("");
  const [styling, setStyling] = useState(false);
  const [track, setTrack] = useState("");
  const [mixing, setMixing] = useState(false);
  const [score, setScore] = useState<Score | null>(null);
  const [scoring, setScoring] = useState(false);
  const [scoreError, setScoreError] = useState("");

  const screenRef = useRef<HTMLDivElement>(null);
  const beforeRef = useRef<HTMLVideoElement>(null);
  const afterRef = useRef<HTMLVideoElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const chatRailRef = useRef<HTMLDivElement>(null);
  const musicInput = useRef<HTMLInputElement>(null);

  useEffect(() => { fetch("/api/styles").then(r => r.json()).then(d => setStyles(d.styles ?? [])); }, []);

  useEffect(() => {
    if (panel !== "edit" || looksAsked.current) return;
    looksAsked.current = true;
    fetch("/api/looks").then(r => r.json()).then(d => setLooks(d.looks ?? []));
  }, [panel]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: 1e6, behavior: "smooth" });
    chatRailRef.current?.scrollTo({ top: 1e6, behavior: "smooth" });
  }, [msgs, thinking]);

  // Local previews for YOUR FOOTAGE — object URLs + durations for timeline
  useEffect(() => {
    const urls = targets.map((f) => URL.createObjectURL(f));
    setPreviewUrls(urls);
    setLocalDurations(new Array(targets.length).fill(0));
    return () => { urls.forEach((u) => URL.revokeObjectURL(u)); };
  }, [targets]);

  useEffect(() => {
    if (!menu) return;
    const close = (e: KeyboardEvent) => { if (e.key === "Escape") setMenu(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [menu]);

  const readId = read?.id;
  const readRunning = read?.status === "running";
  useEffect(() => {
    if (!readRunning || !readId) return;
    const tick = setInterval(() => setElapsed(e => e + 1), 1000);
    const poll = readId === "…" ? undefined : setInterval(async () => {
      const r = await fetch(`/api/fingerprint/${readId}`);
      if (!r.ok) return;
      const next: Read = await r.json();
      setRead(cur => (cur?.id === next.id ? next : cur));
    }, 1200);
    return () => { clearInterval(tick); clearInterval(poll); };
  }, [readId, readRunning]);

  useEffect(() => {
    if (job?.status !== "running" || job.id === "…") return;
    const t = setInterval(async () => {
      const r = await fetch(`/api/jobs/${job.id}`);
      if (!r.ok) return;
      const next: Job = await r.json();
      if (next.status === "done") lastGood.current = next;
      if (next.status === "error" && lastGood.current) {
        setJob(lastGood.current);
        setMsgs(m => [...m, { who: "bot", text: `That change didn't render, so I kept the last version. ${next.error ?? ""}`.trim() }]);
        return;
      }
      setJob(next);
    }, 900);
    return () => clearInterval(t);
  }, [job]);

  const readReference = useCallback(async (file: File) => {
    const mine = ++readSeq.current;
    setRefFile(file); setPreset(null); setPresets(false); setElapsed(0);
    setRead({ id: "…", status: "running", name: file.name, videoPath: "" });
    const form = new FormData();
    form.set("reference", file);
    try {
      const res = await fetch("/api/fingerprint", { method: "POST", body: form });
      const data = await res.json();
      if (mine !== readSeq.current) return;
      setRead(data.id
        ? { id: data.id, status: "running", name: file.name, videoPath: "" }
        : { id: "—", status: "error", name: file.name, videoPath: "", error: data.error });
    } catch {
      if (mine === readSeq.current) {
        setRead({ id: "—", status: "error", name: file.name, videoPath: "",
                  error: "The upload didn't go through. Give it another go." });
      }
    }
  }, []);

  const choosePreset = (s: Style) => {
    readSeq.current++;
    setPreset(s); setRead(null); setRefFile(null);
  };

  const start = useCallback(async (patch: Record<string, unknown>) => {
    if (!targets.length) return;
    const fd = new FormData();
    for (const f of targets) fd.append("target", f);
    if (read?.status === "done") {
      fd.set("fingerprint_id", read.id);
      fd.set("reference_id", read.id);
      fd.set("referencePath", read.videoPath);
      fd.set("referenceName", read.name);
    } else if (preset) {
      fd.set("styleId", preset.id);
    } else {
      // reel UI hidden for now — use default style, keep logic intact
      const fallback = styles[0]?.id || "night-interview";
      fd.set("styleId", fallback);
    }
    fd.set("overrides", JSON.stringify(patch));

    const name = targets.length > 1 ? `${targets.length} takes` : targets[0].name;
    setScore(null); setScoreError(""); setUploaded(0);
    setJob({ id: "…", status: "running", stageIndex: -1, progress: 0.02, targetName: name });
    const d = await new Promise<{ id?: string; error?: string }>(res => {
      const x = new XMLHttpRequest();
      x.open("POST", "/api/jobs");
      x.upload.onprogress = e => e.lengthComputable && setUploaded(e.loaded / e.total);
      x.onload = () => { try { res(JSON.parse(x.responseText || "{}")); } catch { res({ error: "The server didn't answer properly." }); } };
      x.onerror = () => res({ error: "The upload didn't go through. Give it another go." });
      x.send(fd);
    });
    if (d.id) {
      setJob({ id: d.id, status: "running", stageIndex: 0, progress: 0.08, targetName: name });
    } else if (lastGood.current) {
      setJob(lastGood.current);
      setMsgs(m => [...m, { who: "bot", text: d.error ?? "That didn't go through." }]);
    } else {
      setJob({ id: "—", status: "error", stageIndex: 0, progress: 0, targetName: name, error: d.error });
    }
  }, [targets, read, preset]);

  const startOver = () => {
    readSeq.current++;
    lastGood.current = null;
    setJob(null); setRead(null); setRefFile(null); setPreset(null); setPresets(false); setTargets([]);
    setOverrides({}); setMsgs([HELLO]); setPanel(null); setTab("ask"); setCompare(false);
    setScore(null); setScoreError(""); setTrack(""); setLook(""); setSound(false); setMenu(false);
  };

  const rerendered = () => { setVideoKey(k => k + 1); setScore(null); };

  const say = useCallback(async (text: string) => {
    if (!text.trim() || thinking || job?.status === "running") return;
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
      if (Object.keys(d.overrides ?? {}).length) start(merged);
    } finally { setThinking(false); }
  }, [thinking, job, overrides, start]);

  const chooseLook = async (id: string) => {
    if (!job) return;
    setLook(id); setStyling(true);
    try {
      await fetch(`/api/jobs/${job.id}/look`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ preset: id }),
      });
      rerendered();
    } finally { setStyling(false); }
  };

  const setMusic = async (file: File | null) => {
    if (!job) return;
    setMixing(true);
    try {
      const fd = new FormData();
      if (file) fd.set("track", file); else fd.set("remove", "1");
      const r = await fetch(`/api/jobs/${job.id}/music`, { method: "POST", body: fd });
      if ((await r.json()).ok) { setTrack(file ? file.name : ""); rerendered(); }
    } finally { setMixing(false); }
  };

  const runScore = async () => {
    setPanel("score");
    if (!job || job.status !== "done" || score || scoring) return;
    setScoring(true); setScoreError("");
    try {
      const res = await fetch("/api/score", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ jobId: job.id }),
      });
      const data = await res.json();
      if (data.error) setScoreError(data.error); else setScore(data);
    } catch {
      setScoreError("Couldn't reach the scorer. Try again in a moment.");
    } finally { setScoring(false); }
  };

  const sync = () => {
    const b = beforeRef.current, a = afterRef.current;
    if (!b || !a) return;
    let want = a.currentTime;
    const clips = job?.clips;
    if (clips?.length) {
      let at = 0; want = clips[clips.length - 1].end;
      for (const c of clips) {
        const d = c.end - c.start;
        if (a.currentTime < at + d) { want = c.start + (a.currentTime - at); break; }
        at += d;
      }
    }
    if (Math.abs(b.currentTime - want) > 0.12) b.currentTime = want;
  };

  const drag = (e: React.PointerEvent) => {
    if (e.buttons === 0 && e.type !== "pointerdown") return;
    const r = screenRef.current?.getBoundingClientRect(); if (!r) return;
    setSplit(Math.max(2, Math.min(98, ((e.clientX - r.left) / r.width) * 100)));
  };

  const fp = read?.status === "done" ? read.fingerprint : undefined;
  const lookReady = read?.status === "done" || !!preset;
  const lookName = preset?.name ?? read?.name ?? "";

  // ── rail helpers ─────────────────────────────────────────────────────
  const pick = (next: Panel) => { setPanel(p => (p === next ? null : next)); setMenu(false); };
  const isActive = (p: Panel, t?: Tab) => panel === p && (t ? tab === t : true);

  const toggleTheme = () => {
    const cur = document.documentElement.getAttribute("data-theme");
    document.documentElement.setAttribute("data-theme", cur === "dark" ? "light" : "dark");
    try { localStorage.setItem("theme", cur === "dark" ? "light" : "dark"); } catch {}
  };

  // ── shell: rail beyond left border, phone is light main with inner radius ───
  return (
    <div className="min-h-dvh h-dvh bg-black p-1 flex gap-1 overflow-hidden box-border">
      {/* ── dark rail beyond left border (as in Image 1) ── */}
      <nav className="w-12 bg-black shrink-0 flex flex-col justify-between items-center py-3 pb-2.5 rounded-[20px] border border-white/5" aria-label="Studio">
          <div className="flex flex-col items-center gap-2.5 w-full">
            <div className="w-9 h-9 rounded-full grid place-items-center text-[#e8e8ec] bg-transparent border-[1.5px] border-white/15 mb-1.5" aria-hidden><LogoIcon /></div>

            <button className={`w-[38px] h-[38px] rounded-xl grid place-items-center border transition-colors ${isActive("edit") ? "text-white bg-[#1c1c22] border-white/10 shadow-[0_1px_0_rgba(255,255,255,0.06)_inset,0_4px_12px_rgba(0,0,0,0.35)]" : "text-[#7a7a82] bg-transparent border-transparent hover:text-[#d6d6de] hover:bg-white/5"}`} aria-label="Assistant" title="Assistant" onClick={() => { setPanel("edit"); setTab("ask"); }}>
              <span className="grid place-items-center"><BotIcon /></span>
            </button>

            <button className={`w-[38px] h-[38px] rounded-xl grid place-items-center border transition-colors ${presets || isActive(null) && !panel ? "text-white bg-[#1c1c22] border-white/10" : "text-[#7a7a82] bg-transparent border-transparent hover:text-[#d6d6de] hover:bg-white/5"}`} aria-label="Reference" title="Reference" onClick={() => { setPanel(null); }}>
              <span className="grid place-items-center"><KeyIcon /></span>
            </button>

            <button className={`w-[38px] h-[38px] rounded-xl grid place-items-center border transition-colors ${isActive("score") ? "text-white bg-[#1c1c22] border-white/10 shadow-[0_1px_0_rgba(255,255,255,0.06)_inset,0_4px_12px_rgba(0,0,0,0.35)]" : "text-[#7a7a82] bg-transparent border-transparent hover:text-[#d6d6de] hover:bg-white/5"}`} aria-label="Score" title="How close" onClick={() => { if (job?.status === "done") runScore(); else pick("score"); }}>
              <span className="grid place-items-center"><ChartIcon /></span>
            </button>

            <button className={`w-[38px] h-[38px] rounded-xl grid place-items-center border transition-colors ${isActive("edit") && tab === "captions" ? "text-white bg-[#1c1c22] border-white/10" : "text-[#7a7a82] bg-transparent border-transparent hover:text-[#d6d6de] hover:bg-white/5"}`} aria-label="Captions" title="Captions" onClick={() => { setPanel("edit"); setTab("captions"); }}>
              <span className="grid place-items-center"><ChatIcon /></span>
            </button>

            <button className={`w-[38px] h-[38px] rounded-xl grid place-items-center border transition-colors ${isActive("edit") && tab === "style" ? "text-white bg-[#1c1c22] border-white/10" : "text-[#7a7a82] bg-transparent border-transparent hover:text-[#d6d6de] hover:bg-white/5"}`} aria-label="Looks" title="Looks" onClick={() => { setPanel("edit"); setTab("style"); }}>
              <span className="grid place-items-center"><GridIcon /></span>
            </button>
          </div>

          <div className="flex flex-col items-center gap-2.5 w-full">
            <button className={`w-[38px] h-[38px] rounded-xl grid place-items-center border transition-colors ${isActive("read") ? "text-white bg-[#1c1c22] border-white/10 shadow-[0_1px_0_rgba(255,255,255,0.06)_inset,0_4px_12px_rgba(0,0,0,0.35)]" : "text-[#7a7a82] bg-transparent border-transparent hover:text-[#d6d6de] hover:bg-white/5"}`} aria-label="What we read" title="What we read" onClick={() => pick("read")}>
              <span className="grid place-items-center"><BookIcon /></span>
            </button>
            <button className={`w-[38px] h-[38px] rounded-xl grid place-items-center border transition-colors ${compare ? "text-white bg-[#1c1c22] border-white/10" : "text-[#7a7a82] bg-transparent border-transparent hover:text-[#d6d6de] hover:bg-white/5"}`} aria-label="Compare" title="Compare" onClick={() => setCompare(v => !v)}>
              <span className="grid place-items-center"><BagIcon /></span>
            </button>
            <button className="w-9 h-9 rounded-full grid place-items-center bg-transparent border border-white/10 mt-1" aria-label="Toggle theme" title="Toggle theme" onClick={toggleTheme}>
              <ColorWheel />
            </button>
          </div>
        </nav>

        <div className="flex-1 min-w-0 h-full bg-[#cbd8db] rounded-[20px] overflow-hidden flex flex-col min-h-0 border border-white/10 shadow-[0_0_0_1px_rgba(255,255,255,0.06)_inset]">
          {/* ── main (light pixelated, inner rounded) ── */}
          <div className="flex-1 min-w-0 bg-[#d4e0e2] flex flex-col overflow-hidden relative">
          {!job ? (
            // SETUP — YOUR FOOTAGE fills entire border, pure white, no tray
            <div className="flex-1 min-h-0 flex flex-col overflow-hidden bg-white">
              <div className="flex-1 min-h-0 flex flex-col w-full h-full bg-white">
                <Drop
                  accept="video/*,image/*"
                  multiple
                  onFiles={setTargets}
                  className="flex-1 min-h-0 w-full h-full rounded-none border-2 border-dashed border-black/15 bg-white flex flex-col items-center justify-center gap-5 p-8 text-center hover:border-black/30 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <span className="w-14 h-14 rounded-2xl bg-[#0a0a0f] text-white grid place-items-center shadow-sm">
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="5" width="14" height="13" rx="2"/><path d="M17 8l4-2v10l-4-2z" fill="currentColor" stroke="none"/></svg>
                    </span>
                    <span className="w-14 h-14 rounded-2xl bg-[#e8f0ff] text-[#46607B] grid place-items-center border border-black/5 shadow-sm">
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="M14 15l3-3 3 3"/><path d="M3 17l5-5 4 4"/></svg>
                    </span>
                  </div>
                  <div>
                    <div className="text-[15px] font-bold tracking-[0.08em] uppercase text-[#0a0a0f]">YOUR FOOTAGE</div>
                    <div className="text-[13px] text-[#6b7280] mt-1">Drop video or image here</div>
                    {targets.length ? (
                      <div className="mt-2 inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#0a0a0f] text-white text-xs">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#6bff8a] animate-pulse" /> {targets.length} {targets.length === 1 ? "file" : "files"} • {mb(targets)} ready
                      </div>
                    ) : (
                      <div className="text-[11px] text-[#9aa0a6] mt-1">MP4, MOV, JPG, PNG — up to 50 MB each</div>
                    )}
                  </div>
                  {/* rounded padding border inside upload — previews + timeline */}
                  <div className="w-full max-w-[560px] rounded-[18px] border border-black/10 bg-[#fafafa] p-3 flex flex-col gap-3 text-left shadow-sm">
                    {targets.length === 0 ? (
                      <div className="py-4 text-center text-[12px] text-[#9aa0a6]">No video yet — drop to preview here</div>
                    ) : (
                      <>
                        {/* small rectangles — video / image previews */}
                        <div className="flex gap-2 overflow-x-auto pb-1">
                          {targets.map((f, i) => {
                            const url = previewUrls[i];
                            const isVideo = f.type.startsWith("video/") || /\.(mp4|mov|webm|m4a)$/i.test(f.name);
                            const isImage = f.type.startsWith("image/");
                            const dur = localDurations[i] || 0;
                            return (
                              <div key={`${f.name}-${i}`} className="relative w-36 shrink-0 rounded-xl overflow-hidden bg-black border border-black/10">
                                {isVideo && url ? (
                                  <video
                                    src={url}
                                    muted
                                    playsInline
                                    preload="metadata"
                                    className="w-full h-20 object-cover block"
                                    onLoadedMetadata={(e) => {
                                      const d = e.currentTarget.duration || 0;
                                      setLocalDurations((prev) => { const n = [...prev]; n[i] = d; return n; });
                                    }}
                                  />
                                ) : isImage && url ? (
                                  // eslint-disable-next-line @next/next/no-img-element
                                  <img src={url} alt={f.name} className="w-full h-20 object-cover block" />
                                ) : (
                                  <div className="w-full h-20 grid place-items-center text-white/70 text-[11px]">loading…</div>
                                )}
                                <span className="absolute left-1 bottom-1 px-1.5 py-0.5 rounded-md bg-black/70 text-white text-[10px] leading-none">
                                  {dur ? `${dur.toFixed(1)}s` : f.name.slice(-8)}
                                </span>
                                <button
                                  onClick={(e) => { e.stopPropagation(); setTargets((prev) => prev.filter((_, idx) => idx !== i)); }}
                                  className="absolute right-1 top-1 w-5 h-5 grid place-items-center rounded-full bg-black/70 text-white text-[10px] hover:bg-black"
                                  aria-label="Remove"
                                >✕</button>
                              </div>
                            );
                          })}
                        </div>
                        {/* file names */}
                        <div className="flex flex-col gap-1 max-h-[96px] overflow-auto">
                          {targets.map((f, i) => (
                            <div key={`${f.name}-${i}-name`} className="flex items-center gap-2 px-2 py-1 rounded-lg bg-white border border-black/5 text-[11px]">
                              <span className="truncate flex-1">{f.name}</span>
                              <span className="text-[#6b7280]">{(f.size / 1024).toFixed(0)} KB{localDurations[i] ? ` • ${localDurations[i].toFixed(1)}s` : ""}</span>
                            </div>
                          ))}
                        </div>
                        {/* timeline at bottom, adjacent to videos */}
                        <div className="rounded-xl bg-white border border-black/5 p-2">
                          <div className="flex items-center justify-between text-[10px] text-[#6b7280] mb-1.5">
                            <span className="font-semibold tracking-[0.06em] uppercase">Timeline</span>
                            <span>
                              {(() => {
                                const total = localDurations.reduce((a, b) => a + (b || 0), 0);
                                return total > 0 ? `${total.toFixed(1)}s total • ${targets.length} clip${targets.length > 1 ? "s" : ""}` : `${targets.length} clip${targets.length > 1 ? "s" : ""} • loading durations…`;
                              })()}
                            </span>
                          </div>
                          <div className="flex h-2.5 rounded-full overflow-hidden bg-black/5 gap-[2px]">
                            {(() => {
                              const total = localDurations.reduce((a, b) => a + (b || 0), 0);
                              return targets.map((f, i) => {
                                const w = total > 0 && localDurations[i] ? (localDurations[i] / total) * 100 : 100 / targets.length;
                                const palette = ["bg-[#0a0a0f]", "bg-[#46607B]", "bg-[#7E5C22]", "bg-[#37714F]", "bg-[#574B55]"];
                                return <div key={`${f.name}-${i}-bar`} className={`${palette[i % palette.length]} h-full rounded-full`} style={{ width: `${w}%` }} title={`${f.name}${localDurations[i] ? ` — ${localDurations[i].toFixed(1)}s` : ""}`} />;
                              });
                            })()}
                          </div>
                          <div className="mt-1.5 flex justify-between text-[10px] text-[#9aa0a6] tabular-nums">
                            <span>00:00</span>
                            <span>{(() => { const total = localDurations.reduce((a, b) => a + (b || 0), 0); const m = Math.floor(total / 60); const s = Math.floor(total % 60); return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`; })()}</span>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                  <div className="text-[11px] text-[#6b7280]">Click to browse</div>
                </Drop>

                {/* keep reel-to-copy logic hidden for now (required for start) */}
                <div className="hidden">
                  {presets ? (
                    <div>
                      {styles.map(s => (
                        <button key={s.id} onClick={() => choosePreset(s)}>{s.name}</button>
                      ))}
                    </div>
                  ) : (
                    <span>{refFile ? refFile.name : ""} {read?.status === "running" ? `Reading… ${elapsed}s` : read?.status === "done" ? "Read ✓" : read?.status === "error" ? read.error : ""}</span>
                  )}
                </div>

                <div className="shrink-0 bg-white px-6 pt-3 pb-4 flex flex-col items-center border-t border-black/5">
                  <button className="h-11 px-6 text-[15px] shadow-[0_8px_20px_rgba(0,0,0,0.14)] inline-flex items-center justify-center rounded-full font-semibold bg-[var(--accent)] border border-[var(--accent)] text-[var(--on-accent)] hover:bg-[var(--accent-press)] disabled:opacity-45" disabled={!targets.length} onClick={() => start({})}>Edit it like that</button>
                  <p className="mt-2 text-[12px] text-[var(--muted)] min-h-[16px] text-center">
                    {!targets.length ? "Drop your clips above to continue" : lookReady ? "Ready to edit" : "Need a reel style (using default)"}
                  </p>
                </div>
              </div>
            </div>
          ) : (
            // STUDIO — video + rail-driven panels
            <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
              <div className="h-[52px] shrink-0 flex items-center gap-2.5 px-4 bg-white/75 backdrop-blur border-b border-black/5">
                <span className="text-[13px] text-[#4a5558] overflow-hidden text-ellipsis whitespace-nowrap font-medium" title={`${lookName} → ${job.targetName}`}>{lookName} <span aria-hidden>→</span> {job.targetName}</span>
                <span className="flex-1" />
                {job.status === "done" && (
                  <a className="h-8 px-[13px] text-[13.5px] inline-flex items-center gap-1.5 rounded-full font-semibold bg-[var(--accent)] border border-[var(--accent)] text-[var(--on-accent)]" href={`/api/jobs/${job.id}/media?v=after`} download={`edit-${job.id}.mp4`}>Save</a>
                )}
                <button className="h-8 px-[13px] text-[13.5px] inline-flex items-center gap-1.5 rounded-full font-semibold bg-transparent border border-transparent text-[var(--muted)] hover:bg-[var(--sunk)] hover:text-[var(--ink)]" onClick={startOver}>Start over</button>
                <button className="w-[34px] h-8 p-0 justify-center text-lg inline-flex items-center rounded-full font-semibold bg-transparent border-transparent text-[var(--muted)]" aria-label="More" onClick={() => setMenu(v => !v)}>⋯</button>
                {menu && (
                  <>
                    <div className="fixed inset-0 z-20" onClick={() => setMenu(false)} />
                    <div className="absolute right-0 top-[calc(100%+6px)] z-[21] min-w-[236px] p-1 flex flex-col border border-[var(--line-2)] rounded-[10px] bg-[var(--raised)] shadow-[var(--shadow)]" role="menu">
                      {job.status === "done" && targets.length === 1 && (
                        <button role="menuitemcheckbox" aria-checked={compare} onClick={() => { setCompare(v => !v); setMenu(false); }}>Compare with original{compare ? " ✓" : ""}</button>
                      )}
                      {fp && <button role="menuitem" onClick={() => pick("read")}>What we read from the reel</button>}
                      {job.status === "done" && <button role="menuitem" onClick={() => { setMenu(false); runScore(); }}>How close did it get?</button>}
                      <button role="menuitem" onClick={startOver}>Start over</button>
                    </div>
                  </>
                )}
              </div>

              <div className="flex-1 min-h-0 flex flex-col overflow-hidden bg-transparent">
                <div className="flex-1 min-h-0 grid place-items-center p-4 overflow-hidden">
                  <div className="relative w-full max-w-[720px] h-[min(68vh,760px)] aspect-[9/16] bg-[var(--theatre)] rounded-[18px] overflow-hidden shadow-[0_18px_44px_-20px_rgba(27,23,20,0.42),0_0_0_1px_rgba(27,23,20,0.06)]" ref={screenRef} style={{ ["--split" as string]: `${split}%` }}>
                    {job.status === "done" ? (
                      <>
                        {compare && targets.length === 1 && (
                          <video ref={beforeRef} src={`/api/jobs/${job.id}/media?v=before`} muted loop playsInline autoPlay />
                        )}
                        <video ref={afterRef} className={compare && targets.length === 1 ? "after" : undefined}
                          src={`/api/jobs/${job.id}/media?v=after&r=${videoKey}`}
                          muted={!sound} loop playsInline autoPlay
                          onTimeUpdate={e => { if (compare) sync(); setPlayhead((e.target as HTMLVideoElement).currentTime); }} />
                        {compare && targets.length === 1 && (
                          <>
                            <span className="absolute top-0 bottom-0 w-0.5 bg-white pointer-events-none left-[var(--split,50%)] shadow-[0_0_10px_rgba(0,0,0,0.4)]" /><span className="absolute top-1/2 w-[34px] h-[34px] -mt-[17px] -ml-[17px] rounded-full bg-[#FBF7EF] pointer-events-none grid place-items-center text-[13px] text-[#2E2630] left-[var(--split,50%)] shadow-[0_3px_12px_rgba(0,0,0,0.55)]">↔</span>
                            <span className="absolute top-0 bottom-0 w-[30px] -ml-[15px] cursor-ew-resize left-[var(--split,50%)] touch-manipulation select-none" onPointerDown={drag} onPointerMove={drag} />
                            <span className="absolute bottom-3 left-3 bg-[rgba(255,255,255,0.16)] text-white text-[11px] font-bold tracking-[0.05em] uppercase py-1 px-2 rounded-full backdrop-blur-[6px]">Yours</span><span className="absolute bottom-3 right-3 bg-[var(--accent)] text-[#2A232B] text-[11px] font-bold tracking-[0.05em] uppercase py-1 px-2 rounded-full backdrop-blur-[6px]">Edited</span>
                          </>
                        )}
                        <button className="absolute top-2.5 right-2.5 w-8 h-8 rounded-full grid place-items-center text-white bg-black/45 backdrop-blur-md aria-[pressed=true]:bg-white/15" aria-pressed={sound} aria-label={sound ? "Mute" : "Turn sound on"}
                          title={sound ? "Mute" : "Turn sound on"}
                          onClick={() => { setSound(v => !v); afterRef.current?.play().catch(() => {}); }}>
                          <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden>
                            <path d="M4 9v6h4l5 4V5L8 9H4z" fill="currentColor" />
                            {sound
                              ? <path d="M16 8.5a5 5 0 0 1 0 7M18.5 6a8.5 8.5 0 0 1 0 12" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" />
                              : <path d="M16 9.5l5 5M21 9.5l-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />}
                          </svg>
                        </button>
                      </>
                    ) : (
                      <div className="absolute inset-0 grid place-content-center justify-items-center gap-2.5 text-white text-center p-7">
                        {job.status === "running" ? (
                          <>
                            <span className="w-[34px] h-[34px] rounded-full border-[3px] border-white/20 border-t-white animate-spin" />
                            <span className="w-t">{job.stageIndex < 0 ? `Uploading ${Math.round(uploaded * 100)}%` : DOING[job.stageIndex] ?? "Working"}…</span>
                            <span className="w-[150px] h-1 rounded-full bg-white/15 overflow-hidden"><i style={{ width: `${Math.round((job.stageIndex < 0 ? uploaded * 0.08 : job.progress) * 100)}%` }} /></span>
                          </>
                        ) : (
                          <>
                            <span className="w-t">That didn&apos;t work</span>
                            <span className="w-s">{job.error || "Try a different video."}</span>
                            <button className="h-8 px-[13px] text-[13.5px] inline-flex items-center gap-1.5 rounded-full font-semibold border-[1.5px] border-[var(--line-2)] bg-[var(--card)] hover:border-[var(--faint)] aria-[pressed=true]:border-[var(--accent-ink)] aria-[pressed=true]:bg-[var(--accent-soft)] aria-[pressed=true]:text-[var(--accent-ink)]" onClick={() => start(overrides)}>Try again</button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                {panel === "edit" && job.status === "done" && (
                  <Timeline jobId={job.id} at={playhead} version={videoKey} onSeek={t => { if (afterRef.current) afterRef.current.currentTime = t; setPlayhead(t); }} />
                )}
                <p className="m-0 py-0 px-[18px] pb-4 text-center text-[13px] text-[var(--muted)] min-h-[35px]">{job.status === "done" ? (() => {
                  const r = job.receipt; const saved = r ? Math.max(0, r.sourceSeconds - r.outputSeconds) : 0;
                  const facts = r ? [saved >= 1 && `${saved.toFixed(0)}s shorter`, r.captions > 0 && `${r.captions} captions`, r.wordsCut > 0 && `${r.wordsCut} stumbles cut`].filter(Boolean).join(" · ") : "";
                  return facts || " ";
                })() : " "}</p>
              </div>

              {panel && (
                <aside className="border-t border-black/5 bg-[rgba(249,247,239,0.96)] max-h-[42%] overflow-auto">
                  {panel === "edit" ? (
                    <>
                      <div className="flex items-center gap-0.5 pt-2.5 px-3" role="tablist">
                        <button className="flex-1 h-8 rounded-lg text-[13.5px] font-semibold text-[var(--muted)] hover:bg-[var(--sunk)] hover:text-[var(--ink)] aria-[selected=true]:bg-[var(--sunk)] aria-[selected=true]:text-[var(--accent-ink)]" role="tab" aria-selected={tab === "ask"} onClick={() => setTab("ask")}>Ask</button>
                        <button className="flex-1 h-8 rounded-lg text-[13.5px] font-semibold text-[var(--muted)] hover:bg-[var(--sunk)] hover:text-[var(--ink)] aria-[selected=true]:bg-[var(--sunk)] aria-[selected=true]:text-[var(--accent-ink)]" role="tab" aria-selected={tab === "captions"} onClick={() => setTab("captions")}>Captions</button>
                        <button className="flex-1 h-8 rounded-lg text-[13.5px] font-semibold text-[var(--muted)] hover:bg-[var(--sunk)] hover:text-[var(--ink)] aria-[selected=true]:bg-[var(--sunk)] aria-[selected=true]:text-[var(--accent-ink)]" role="tab" aria-selected={tab === "style"} onClick={() => setTab("style")}>Style</button>
                        <button className="ml-auto w-[30px] h-[30px] rounded-lg shrink-0 grid place-items-center text-lg text-[var(--faint)] hover:bg-[var(--sunk)] hover:text-[var(--ink)]" aria-label="Close" onClick={() => setPanel(null)}>×</button>
                      </div>
                      {tab === "ask" && (
                        <>
                          <div className="overflow-y-auto p-4 flex flex-col gap-3" ref={logRef}>
                            {msgs.map((m, i) => (
                              <div key={i} className={`msg ${m.who}`}>
                                <span className="w-[26px] h-[26px] rounded-full shrink-0 grid place-items-center text-[11px] font-extrabold bg-[var(--accent)] text-[var(--on-accent)]">{m.who === "me" ? "You" : "H"}</span>
                                <span>
                                  <span className="py-[9px] px-3 rounded-[15px] text-sm leading-[1.45] bg-[var(--sunk)]" style={{ display: "block" }}>{m.text}</span>
                                  {m.changed && m.changed.length > 0 && (
                                    <span className="mt-1.5 flex flex-wrap gap-1">{m.changed.map(c => <span key={c}>{label(c)}</span>)}</span>
                                  )}
                                </span>
                              </div>
                            ))}
                            {thinking && (<div className="flex gap-2 max-w-full"><span className="w-[26px] h-[26px] rounded-full shrink-0 grid place-items-center text-[11px] font-extrabold bg-[var(--accent)] text-[var(--on-accent)]">H</span><span className="bubble thinking"><i /><i /><i /></span></div>)}
                          </div>
                          <div className="border-t border-[var(--line)] py-2.5 px-3.5 pb-3 flex flex-col gap-2">
                            <div className="flex gap-1.5 overflow-x-auto pb-0.5 shrink-0">
                              {SUGGESTIONS.map(s => (<button key={s} className="h-[31px] px-3 rounded-full text-[13px] font-medium border-[1.5px] border-[var(--line-2)] bg-[var(--sunk)] text-[var(--muted)] whitespace-nowrap hover:border-[var(--accent-ink)] hover:text-[var(--accent-ink)] hover:bg-[var(--accent-soft)] shrink-0" onClick={() => say(s)} disabled={thinking || job.status === "running"}>{s}</button>))}
                            </div>
                            <div className="flex gap-2 items-end border-[1.5px] border-[var(--line-2)] rounded-[10px] py-1.5 px-1.5 pl-3 bg-[var(--card)] focus-within:border-[var(--accent-ink)]">
                              <textarea rows={1} placeholder="Make the captions pop more…" value={draft}
                                onChange={e => setDraft(e.target.value)}
                                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); say(draft); } }} />
                              <button className="w-8 h-8 rounded-full bg-[var(--accent)] text-[var(--on-accent)] shrink-0 grid place-items-center disabled:bg-[var(--line-2)] disabled:text-[var(--faint)]" aria-label="Send" onClick={() => say(draft)} disabled={!draft.trim() || thinking || job.status === "running"}>↑</button>
                            </div>
                          </div>
                        </>
                      )}
                      {tab === "captions" && <CaptionFixer jobId={job.id} ready={job.status === "done"} onApplied={rerendered} />}
                      {tab === "style" && (
                        <div className="overflow-y-auto py-3.5 px-4 pb-[18px]">
                          <div className="flex flex-col gap-2.5">
                            <span className="text-[11.5px] font-semibold tracking-[0.04em] uppercase text-[var(--faint)]">Caption look{styling ? " — applying…" : ""}</span>
                            {looks.length ? (
                              <div className="grid grid-cols-2 gap-1.5">
                                {looks.map(l => (<button key={l.id} className="border-[1.5px] border-[var(--line)] rounded-lg p-2 px-2.5 text-left bg-[var(--card)] hover:border-[var(--line-2)] hover:bg-[var(--sunk)] disabled:opacity-55 aria-[pressed=true]:border-[var(--accent-ink)] aria-[pressed=true]:bg-[var(--accent-soft)]" aria-pressed={look === l.id} disabled={styling || job.status !== "done"} onClick={() => chooseLook(l.id)}><span className="font-semibold text-[12.5px] block">{l.label}</span><span className="text-[11px] text-[var(--muted)] leading-[1.3] block mt-0.5">{l.blurb}</span></button>))}
                              </div>
                            ) : <span className="text-xs text-[var(--muted)]">Loading looks…</span>}
                          </div>
                          <div className="flex flex-col gap-2.5">
                            <span className="text-[11.5px] font-semibold tracking-[0.04em] uppercase text-[var(--faint)]">Music{mixing ? " — mixing…" : ""}</span>
                            <input ref={musicInput} type="file" accept="audio/*" hidden onChange={e => { setMusic(e.target.files?.[0] ?? null); e.target.value = ""; }} />
                            {track ? (
                              <div className="flex items-center gap-2.5 border border-[var(--line)] rounded-[10px] p-2.5 px-3">
                                <span className="w-[30px] h-10 rounded-[5px] bg-[var(--theatre)] shrink-0 grid place-items-center text-[var(--accent)] text-[13px]">♪</span>
                                <span style={{ flex: 1 }}><span className="font-semibold text-[13.5px] overflow-hidden text-ellipsis whitespace-nowrap" style={{ display: "block" }}>{track}</span><span className="text-xs text-[var(--muted)]">Ducks under your voice</span></span>
                                <button className="h-8 px-[13px] text-[13.5px] inline-flex items-center gap-1.5 rounded-full font-semibold bg-transparent border border-transparent text-[var(--muted)] hover:bg-[var(--sunk)] hover:text-[var(--ink)]" disabled={mixing} onClick={() => setMusic(null)}>Remove</button>
                              </div>
                            ) : (
                              <button className="drop-zone" disabled={mixing || job.status !== "done"} onClick={() => musicInput.current?.click()}>
                                <span className="font-semibold text-[15px] max-w-full overflow-hidden text-ellipsis whitespace-nowrap">Add a track</span><span className="text-[12.5px] text-[var(--muted)]">It ducks under your voice automatically</span>
                              </button>
                            )}
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    <>
                      <div className="flex items-center py-2.5 px-3 pl-4 border-b border-[var(--line)]">
                        <span className="text-[11.5px] font-semibold tracking-[0.04em] uppercase text-[var(--faint)]">{panel === "read" ? "What we read from the reel" : "How close it got"}</span>
                        <button className="ml-auto w-[30px] h-[30px] rounded-lg shrink-0 grid place-items-center text-lg text-[var(--faint)] hover:bg-[var(--sunk)] hover:text-[var(--ink)]" aria-label="Close" onClick={() => setPanel(null)}>×</button>
                      </div>
                      <div className="overflow-y-auto py-3.5 px-4 pb-[18px]">
                        {panel === "read" && fp && <Readout fp={fp} />}
                        {panel === "score" && (scoring ? <p className="text-xs text-[var(--muted)]">Measuring your edit against the reel — this takes a moment.</p> : scoreError ? <p className="text-xs text-[var(--muted)]" style={{ color: "var(--bad)" }}>{scoreError}</p> : score ? <Scorecard score={score} /> : <p className="text-xs text-[var(--muted)]">Available once the edit is ready.</p>)}
                      </div>
                    </>
                  )}
                </aside>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── right AI chat immersed in black border (like left menus) ── */}
      <aside className="w-[360px] shrink-0 bg-black rounded-[20px] flex flex-col overflow-hidden border border-white/5 shadow-[0_0_0_1px_rgba(255,255,255,0.03)_inset] max-[1100px]:hidden" aria-label="AI Chat">
        <div className="h-[52px] shrink-0 flex items-center gap-2.5 px-3.5 border-b border-white/5 bg-white/[0.02]">
          <span className="w-8 h-8 rounded-full shrink-0 bg-[#c8f5d0] grid place-items-center overflow-hidden border border-white/5" aria-hidden>🤖</span>
          <div>
            <div className="text-[13px] font-bold text-[#e6e6eb]">Support Assistant</div>
            <div className="text-[11px] text-[#9aa0a6]">Halfheaven AI • online</div>
          </div>
          <span style={{ marginLeft: "auto", fontSize: 11, color: "#6bff8a" }}>●</span>
        </div>

        <div className="flex-1 min-h-0 overflow-auto p-3.5 flex flex-col gap-2.5 bg-black" ref={chatRailRef}>
          {msgs.map((m, i) => (
            <div key={i} className={`msg ${m.who}`}>
              <span className="w-[26px] h-[26px] rounded-full shrink-0 grid place-items-center text-[11px] font-extrabold bg-[var(--accent)] text-[var(--on-accent)]">{m.who === "me" ? "You" : "H"}</span>
              <span>
                <span className="py-[9px] px-3 rounded-[15px] text-sm leading-[1.45] bg-[var(--sunk)]" style={{ display: "block" }}>{m.text}</span>
                {m.changed && m.changed.length > 0 && (
                  <span className="mt-1.5 flex flex-wrap gap-1">{m.changed.map(c => <span key={c}>{label(c)}</span>)}</span>
                )}
              </span>
            </div>
          ))}
          {thinking && (<div className="flex gap-2 max-w-full"><span className="w-[26px] h-[26px] rounded-full shrink-0 grid place-items-center text-[11px] font-extrabold bg-[var(--accent)] text-[var(--on-accent)]">H</span><span className="bubble thinking"><i /><i /><i /></span></div>)}
          {job?.status === "running" && (
            <div className="flex gap-2 max-w-full"><span className="w-[26px] h-[26px] rounded-full shrink-0 grid place-items-center text-[11px] font-extrabold bg-[var(--accent)] text-[var(--on-accent)]">H</span><span className="py-[9px] px-3 rounded-[15px] text-sm leading-[1.45] bg-[var(--sunk)]">Working… {job.stageIndex >= 0 ? DOING[job.stageIndex] : "Uploading"} — {Math.round((job.progress || 0)*100)}%</span></div>
          )}
        </div>

        <div className="border-t border-white/5 p-2.5 flex flex-col gap-2 bg-white/[0.02]">
          <div className="flex gap-1.5 overflow-x-auto pb-0.5 shrink-0">
            {SUGGESTIONS.map(s => (
              <button key={s} className="h-[31px] px-3 rounded-full text-[13px] font-medium border-[1.5px] border-[var(--line-2)] bg-[var(--sunk)] text-[var(--muted)] whitespace-nowrap hover:border-[var(--accent-ink)] hover:text-[var(--accent-ink)] hover:bg-[var(--accent-soft)] shrink-0" onClick={() => say(s)} disabled={thinking || job?.status === "running"}>{s}</button>
            ))}
          </div>
          <div className="flex gap-2 items-end border-[1.5px] border-[var(--line-2)] rounded-[10px] py-1.5 px-1.5 pl-3 bg-[var(--card)] focus-within:border-[var(--accent-ink)]">
            <textarea rows={1} placeholder="Ask a question…" value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); say(draft); } }} />
            <button className="w-8 h-8 rounded-full bg-[var(--accent)] text-[var(--on-accent)] shrink-0 grid place-items-center disabled:bg-[var(--line-2)] disabled:text-[var(--faint)]" aria-label="Send" onClick={() => say(draft)} disabled={!draft.trim() || thinking || job?.status === "running"}>↑</button>
          </div>
          <div style={{ fontSize: 11, color: "#6b7280", textAlign: "center" }}>AI can ask for bigger captions, tighter cuts, warmer colour…</div>
        </div>
      </aside>
    </div>
  );
}

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
