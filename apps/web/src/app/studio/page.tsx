"use client";

/**
 * Point at a reel, hand over your footage, get it back cut that way.
 *
 * The first screen asks for exactly two things. Everything a creator might
 * reach for afterwards - the chat, caption fixes, looks, music, the timeline,
 * what we read from the reel, how close we got - still exists, but behind Edit
 * or the ⋯ menu: someone who only wanted their video edited should never have
 * to read past controls to get it.
 *
 * Reading the reel starts the moment it is dropped. That work depends only on
 * the reel and takes about a third of its length, which is time the user
 * spends finding their own footage anyway.
 *
 * A refresh lands back on the same edit: what the page knows is remembered in
 * this browser (see lib/remember), and the footage stays on the server, so a
 * re-run after a refresh does not need the files dropped again.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import CaptionFixer from "@/components/CaptionFixer";
import TypeControls from "@/components/TypeControls";
import Drop from "@/components/Drop";
import Readout from "@/components/Readout";
import Scorecard from "@/components/Scorecard";
import ThemeToggle from "@/components/ThemeToggle";
import Timeline from "@/components/Timeline";
import type { Fingerprint } from "@/lib/fingerprint";
import { forgetJob, recall, remember } from "@/lib/remember";
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
/** Everything a refresh should not cost. */
type Session = {
  read: Read | null; preset: Style | null; job: Job | null; lastGood: Job | null;
  footageJob: string | null; takes: number; overrides: Record<string, unknown>;
  msgs: Msg[]; look: string; speaker: string; backdrop: string | null; track: string;
  panel: Panel; tab: Tab; compare: boolean;
};
const SESSION = "studio";

// Colours that sit well behind skin: two neutrals, then a few saturated plates.
const BACKDROPS = ["#111111", "#F4F1EA", "#1E3A8A", "#B91C1C", "#15803D", "#F5B700"];

const SPEAKER_MODES = [
  { id: "off", label: "As styled", blurb: "Captions sit where the look puts them" },
  { id: "around", label: "Around you", blurb: "Kept off your face and body" },
  { id: "behind", label: "Behind you", blurb: "Key words tuck behind your head" },
];
type Tab = "ask" | "captions" | "style";

/* What the app is doing, said the way a person would say it. */
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

export default function Studio() {
  // ---- what goes in ------------------------------------------------------
  const [refFile, setRefFile] = useState<File | null>(null);
  const [read, setRead] = useState<Read | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const readSeq = useRef(0);                      // the latest reel dropped wins
  const [styles, setStyles] = useState<Style[]>([]);
  const [presets, setPresets] = useState(false);  // picking a built-in look instead of a reel
  const [preset, setPreset] = useState<Style | null>(null);
  const [targets, setTargets] = useState<File[]>([]);
  const [takes, setTakes] = useState(0);          // outlives the files, which a refresh drops
  // The first job made with this footage. Every re-run reuses what it uploaded.
  const [footageJob, setFootageJob] = useState<string | null>(null);

  // ---- the render --------------------------------------------------------
  const [job, setJob] = useState<Job | null>(null);
  const [uploaded, setUploaded] = useState(1);
  const lastGood = useRef<Job | null>(null);      // a failed tweak falls back to this
  const [overrides, setOverrides] = useState<Record<string, unknown>>({});
  const [videoKey, setVideoKey] = useState(0);

  // ---- watching it -------------------------------------------------------
  // Browsers only autoplay muted, so the preview starts silent and one tap
  // turns it up. A comparison plays two files at once, so only the edited
  // side carries sound - both would double every word.
  const [sound, setSound] = useState(false);
  const [compare, setCompare] = useState(false);
  const [split, setSplit] = useState(50);
  const [playhead, setPlayhead] = useState(0);
  const [menu, setMenu] = useState(false);
  const [panel, setPanel] = useState<Panel>(null);
  const [tab, setTab] = useState<Tab>("ask");

  // ---- behind Edit -------------------------------------------------------
  const [msgs, setMsgs] = useState<Msg[]>([HELLO]);
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const [looks, setLooks] = useState<{ id: string; label: string; blurb: string }[]>([]);
  const looksAsked = useRef(false);
  const [look, setLook] = useState("");
  const [styling, setStyling] = useState(false);
  const [speaker, setSpeaker] = useState("off");
  const [placing, setPlacing] = useState(false);
  const [speakerNote, setSpeakerNote] = useState("");
  const [backdrop, setBackdrop] = useState<string | null>(null);
  const [track, setTrack] = useState("");
  const [mixing, setMixing] = useState(false);
  const [score, setScore] = useState<Score | null>(null);
  const [scoring, setScoring] = useState(false);
  const [scoreError, setScoreError] = useState("");

  const screenRef = useRef<HTMLDivElement>(null);
  const beforeRef = useRef<HTMLVideoElement>(null);
  const afterRef = useRef<HTMLVideoElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const musicInput = useRef<HTMLInputElement>(null);

  // ---- surviving a refresh ----------------------------------------------
  // Restored after mount rather than in the state initialisers: the server
  // render has no storage, and the two must agree on the first paint.
  const [restored, setRestored] = useState(false);
  const restoredSubject = useRef<string | null>(null);   // the job whose choices were restored
  useEffect(() => {
    const s = recall<Session>(SESSION);
    /* eslint-disable react-hooks/set-state-in-effect -- storage is only readable after mount */
    if (s) {
      setRead(s.read); setPreset(s.preset); setJob(s.job); lastGood.current = s.lastGood;
      setFootageJob(s.footageJob); setTakes(s.takes); setOverrides(s.overrides);
      setMsgs(s.msgs?.length ? s.msgs : [HELLO]); setLook(s.look);
      setSpeaker(s.speaker); setBackdrop(s.backdrop); setTrack(s.track);
      setPanel(s.panel); setTab(s.tab); setCompare(s.compare);
      restoredSubject.current = s.job?.id ?? null;
      // The server may have moved on - or lost it - while the page was closed.
      const id = s.job?.id;
      if (id && s.job?.status !== "running") {
        fetch(`/api/jobs/${id}`).then(r => {
          if (r.status !== 404) return;
          setJob(j => j?.id === id
            ? { ...j, status: "error", error: "This edit is no longer on the server. Start over to make it again." }
            : j);
        }).catch(() => {});
      }
    }
    setRestored(true);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);

  useEffect(() => {
    if (!restored) return;
    // "…" is an upload in flight; there is nothing yet the server could answer for.
    const settled = (j: Job | null) => (j && j.id !== "…" ? j : null);
    const s: Session = {
      read: read && read.id !== "…" ? read : null, preset,
      job: settled(job) ?? settled(lastGood.current), lastGood: lastGood.current,
      footageJob, takes, overrides, msgs, look, speaker, backdrop, track, panel, tab, compare,
    };
    remember(SESSION, s);
  }, [restored, read, preset, job, footageJob, takes, overrides, msgs, look, speaker, backdrop,
      track, panel, tab, compare]);

  useEffect(() => { fetch("/api/styles").then(r => r.json()).then(d => setStyles(d.styles ?? [])); }, []);

  // The look catalogue is read from the renderer, which costs a Python start,
  // so it is only asked for once someone opens Edit.
  useEffect(() => {
    if (panel !== "edit" || looksAsked.current) return;
    looksAsked.current = true;
    fetch("/api/looks").then(r => r.json()).then(d => setLooks(d.looks ?? []));
  }, [panel]);

  useEffect(() => { logRef.current?.scrollTo({ top: 1e6, behavior: "smooth" }); }, [msgs, thinking]);

  useEffect(() => {
    if (!menu) return;
    const close = (e: KeyboardEvent) => { if (e.key === "Escape") setMenu(false); };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [menu]);

  // ---- polling -----------------------------------------------------------
  // Keyed on the id rather than the whole reading, so each poll result does not
  // restart the clock and leave the seconds counter running slow.
  const readId = read?.id;
  const readRunning = read?.status === "running";
  useEffect(() => {
    if (!readRunning || !readId) return;
    const tick = setInterval(() => setElapsed(e => e + 1), 1000);
    const poll = readId === "…" ? undefined : setInterval(async () => {
      const r = await fetch(`/api/fingerprint/${readId}`);
      if (r.status === 404) {
        // Readings live only as long as the server that ran them.
        setRead(cur => (cur?.id === readId
          ? { ...cur, status: "error", error: "That reading was interrupted. Drop the reel again." }
          : cur));
        return;
      }
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
      if (!r.ok && r.status !== 404) return;
      const next: Job = r.ok ? await r.json()
        : { ...job, status: "error", error: "This edit is no longer on the server." };
      if (next.status === "done") lastGood.current = next;
      if (next.status === "error" && lastGood.current) {
        // A tweak that fails shouldn't cost the edit it was tweaking.
        setJob(lastGood.current);
        setMsgs(m => [...m, { who: "bot", text: `That change didn't render, so I kept the last version. ${next.error ?? ""}`.trim() }]);
        return;
      }
      setJob(next);
    }, 900);
    return () => clearInterval(t);
  }, [job]);

  // ---- choosing the look -------------------------------------------------
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

  // ---- making the edit ---------------------------------------------------
  // Every run - the first and each chat tweak - sends the same look. A tweak
  // that forgot the reel would quietly re-render against a built-in look.
  const start = useCallback(async (patch: Record<string, unknown>) => {
    if (!targets.length && !footageJob) return;
    const fd = new FormData();
    if (footageJob) fd.set("fromJob", footageJob);
    else for (const f of targets) fd.append("target", f);
    if (read?.status === "done") {
      fd.set("referencePath", read.videoPath);
      fd.set("referenceName", read.name);
    } else if (preset) {
      fd.set("styleId", preset.id);
    } else return;
    fd.set("overrides", JSON.stringify(patch));

    const name = footageJob ? job?.targetName ?? lastGood.current?.targetName ?? ""
      : targets.length > 1 ? `${targets.length} takes` : targets[0].name;
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
      if (!footageJob) { setFootageJob(d.id); setTakes(targets.length); }
      setJob({ id: d.id, status: "running", stageIndex: 0, progress: 0.08, targetName: name });
    } else if (lastGood.current) {
      setJob(lastGood.current);
      setMsgs(m => [...m, { who: "bot", text: d.error ?? "That didn't go through." }]);
    } else {
      setJob({ id: "—", status: "error", stageIndex: 0, progress: 0, targetName: name, error: d.error });
    }
  }, [targets, footageJob, job, read, preset]);

  const startOver = () => {
    readSeq.current++;
    for (const j of [job, lastGood.current]) if (j) forgetJob(j.id);
    lastGood.current = null;
    setFootageJob(null); setTakes(0);
    setJob(null); setRead(null); setRefFile(null); setPreset(null); setPresets(false); setTargets([]);
    setOverrides({}); setMsgs([HELLO]); setPanel(null); setTab("ask"); setCompare(false);
    setScore(null); setScoreError(""); setTrack(""); setLook(""); setSound(false); setMenu(false);
    setSpeaker("off"); setBackdrop(null);
  };

  // ---- behind Edit -------------------------------------------------------
  /** Caption fixes, looks and music re-render in place: same job, new file. */
  const rerendered = () => { setVideoKey(k => k + 1); setScore(null); };

  const say = useCallback(async (text: string) => {
    // Enter still reaches here while a re-run is going; a second would race it.
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

  // Each edit remembers its own mode; a fresh edit starts from what it was made with.
  useEffect(() => {
    // Straight after a refresh the remembered choice is newer than the profile,
    // which still describes the edit as first made.
    if (restoredSubject.current && restoredSubject.current === job?.id) { restoredSubject.current = null; return; }
    const subject = (job?.profile as { subject?: { captions?: string; background_hex?: string | null } } | undefined)?.subject;
    setSpeaker(subject?.captions ?? "off"); setBackdrop(subject?.background_hex ?? null); setSpeakerNote("");
  }, [job?.id, job?.profile]);

  /** Speaker placement and backdrop share one route: both are a render over
   *  the separation made with the edit. A failure puts the old choice back. */
  const applySubject = async (change: { mode?: string; background?: string | null }, undo: () => void) => {
    if (!job) return;
    setPlacing(true); setSpeakerNote("");
    try {
      const r = await fetch(`/api/jobs/${job.id}/subject`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify(change),
      });
      if (r.ok) rerendered();
      else {
        undo();
        setSpeakerNote((await r.json().catch(() => ({}))).error ?? "That didn't apply.");
      }
    } finally { setPlacing(false); }
  };
  const chooseSpeaker = (mode: string) => {
    if (mode === speaker) return;
    const was = speaker;
    setSpeaker(mode);
    applySubject({ mode }, () => setSpeaker(was));
  };
  const chooseBackdrop = (colour: string | null) => {
    if (colour === backdrop) return;
    const was = backdrop;
    setBackdrop(colour);
    applySubject({ background: colour }, () => setBackdrop(was));
  };
  // A colour picker reports every step of a drag through React's onChange; each
  // would start a render. The native change event fires once, when it closes.
  const picker = useRef<HTMLInputElement>(null);
  const pickLatest = useRef(chooseBackdrop);
  pickLatest.current = chooseBackdrop;
  useEffect(() => {
    const input = picker.current;
    if (!input) return;
    const picked = () => pickLatest.current(input.value);
    input.addEventListener("change", picked);
    return () => input.removeEventListener("change", picked);
  }, [panel, tab]);

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

  /* the edited cut runs ahead of the source, so map program time back */
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

  if (!restored) return null;

  const fp = read?.status === "done" ? read.fingerprint : undefined;
  const lookReady = read?.status === "done" || !!preset;
  const lookName = preset?.name ?? read?.name ?? "";

  // ======================================================================
  // Before anything is made: two slots and one button.
  // ======================================================================
  if (!job) {
    const hint = read?.status === "running"
      ? targets.length ? "Still reading the reel — nearly there." : "Reading the reel. Drop your footage meanwhile."
      : !lookReady
        ? presets
          ? targets.length ? "Now pick a look." : "Pick a look and drop your footage."
          : targets.length ? "Now point at a reel you want to look like." : "Needs a reel to copy and some footage of your own."
        : !targets.length ? "Now drop your own footage." : "";

    return (
      <div className="setup">
        <div className="setup-top">
          <span className="logo"><span className="dot">H</span><span className="name">Halfheaven</span></span>
          <ThemeToggle />
        </div>
        <div className="setup-inner">
          <h1 className="display hero">Give your footage<br />someone else&apos;s edit.</h1>
          <p className="lede">Drop a reel whose editing you like, then your own clips. We&apos;ll cut yours the same way.</p>

          <div className="pair">
            {presets ? (
              <div className="tile">
                <span className="tile-k">Pick a look</span>
                <div className="presets">
                  {styles.map(s => (
                    <button key={s.id} className="preset" aria-pressed={preset?.id === s.id}
                            onClick={() => choosePreset(s)}>{s.name}</button>
                  ))}
                </div>
                <button className="ln" onClick={() => { setPresets(false); setPreset(null); }}>
                  or drop a reel instead
                </button>
              </div>
            ) : (
              <Drop className="tile" onFiles={f => readReference(f[0])}>
                <span className="tile-k">A reel to copy</span>
                <span className="tile-t">{refFile ? refFile.name : "Drop an edited reel"}</span>
                {read?.status === "running" ? <span className="tile-s busy">Reading… {elapsed}s</span>
                  : read?.status === "done" ? <span className="tile-s good">Read ✓</span>
                  : read?.status === "error" ? <span className="tile-s bad">{read.error}</span>
                  : <span className="tile-s">Someone else&apos;s finished video</span>}
              </Drop>
            )}

            <Drop className="tile" multiple onFiles={setTargets}>
              <span className="tile-k">Your footage</span>
              <span className="tile-t">
                {targets.length > 1 ? `${targets.length} takes` : targets[0]?.name ?? "Drop your clips"}
              </span>
              {targets.length
                ? <span className="tile-s good">{mb(targets)} · ready ✓</span>
                : <span className="tile-s">One take or several — it needs sound</span>}
            </Drop>
          </div>

          <button className="btn primary go" disabled={!lookReady || !targets.length} onClick={() => start({})}>
            Edit it like that
          </button>
          {/* Say which half is missing rather than leaving a dead button. */}
          <p className="hint">{hint || " "}</p>
          {!presets && !refFile && styles.length > 0 && (
            <button className="ln" onClick={() => setPresets(true)}>No reel? Use a preset look</button>
          )}
        </div>
      </div>
    );
  }

  // ======================================================================
  // The edit, with everything else one click away.
  // ======================================================================
  const running = job.status === "running";
  const done = job.status === "done";
  // Comparing against the source only lines up for a single take.
  const comparing = compare && takes === 1;
  const r = job.receipt;
  const saved = r ? Math.max(0, r.sourceSeconds - r.outputSeconds) : 0;
  const facts = r ? [
    saved >= 1 && `${saved.toFixed(0)}s shorter`,
    r.captions > 0 && `${r.captions} captions`,
    r.wordsCut > 0 && `${r.wordsCut} stumbles cut`,
  ].filter(Boolean).join(" · ") : "";
  const pick = (next: Panel) => { setPanel(p => (p === next ? null : next)); setMenu(false); };

  return (
    <div className="studio">
      <header className="top">
        <span className="logo"><span className="dot">H</span><span className="name">Halfheaven</span></span>
        <span className="what" title={`${lookName} → ${job.targetName}`}>
          {lookName} <span aria-hidden>→</span> {job.targetName}
        </span>
        <span className="spacer" />
        {(done || panel === "edit") && (
          <button className="btn sm" aria-pressed={panel === "edit"} onClick={() => pick("edit")}>Edit</button>
        )}
        {done && (
          <a className="btn primary sm" href={`/api/jobs/${job.id}/media?v=after`} download={`edit-${job.id}.mp4`}>
            Save video
          </a>
        )}
        <ThemeToggle />
        <div className="menu-wrap">
          <button className="btn ghost sm more" aria-label="More options" aria-expanded={menu}
                  onClick={() => setMenu(v => !v)}>⋯</button>
          {menu && (
            <>
              <div className="menu-scrim" onClick={() => setMenu(false)} />
              <div className="menu" role="menu">
                {done && takes === 1 && (
                  <button role="menuitemcheckbox" aria-checked={compare}
                          onClick={() => { setCompare(v => !v); setMenu(false); }}>
                    Compare with original{compare ? " ✓" : ""}
                  </button>
                )}
                {fp && <button role="menuitem" onClick={() => pick("read")}>What we read from the reel</button>}
                {done && <button role="menuitem" onClick={() => { setMenu(false); runScore(); }}>How close did it get?</button>}
                <button role="menuitem" onClick={startOver}>Start over</button>
              </div>
            </>
          )}
        </div>
      </header>

      <div className={`studio-body${panel ? " with-panel" : ""}`}>
        <main className="stage">
          <div className="theatre">
            <div className="screen" ref={screenRef} style={{ ["--split" as string]: `${split}%` }}>
              {done ? (
                <>
                  {comparing && (
                    <video ref={beforeRef} src={`/api/jobs/${job.id}/media?v=before`} muted loop playsInline autoPlay />
                  )}
                  <video ref={afterRef} className={comparing ? "after" : undefined}
                    src={`/api/jobs/${job.id}/media?v=after&r=${videoKey}`}
                    muted={!sound} loop playsInline autoPlay
                    onTimeUpdate={e => { if (comparing) sync(); setPlayhead((e.target as HTMLVideoElement).currentTime); }} />
                  {comparing && (
                    <>
                      <span className="seam" /><span className="grip">↔</span>
                      <span className="handle" onPointerDown={drag} onPointerMove={drag} />
                      <span className="tag l">Yours</span>
                      <span className="tag r">Edited</span>
                    </>
                  )}
                  <button className="sound" aria-pressed={sound} aria-label={sound ? "Mute" : "Turn sound on"}
                    title={sound ? "Mute" : "Turn sound on"}
                    onClick={() => { setSound(v => !v); afterRef.current?.play().catch(() => {}); }}>
                    <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden>
                      <path d="M4 9v6h4l5 4V5L8 9H4z" fill="currentColor" />
                      {sound
                        ? <path d="M16 8.5a5 5 0 0 1 0 7M18.5 6a8.5 8.5 0 0 1 0 12" stroke="currentColor"
                                strokeWidth="2" fill="none" strokeLinecap="round" />
                        : <path d="M16 9.5l5 5M21 9.5l-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />}
                    </svg>
                  </button>
                </>
              ) : (
                <div className="waiting">
                  {running ? (
                    <>
                      <span className="ring" />
                      <span className="w-t">
                        {job.stageIndex < 0 ? `Uploading ${Math.round(uploaded * 100)}%` : DOING[job.stageIndex] ?? "Working"}…
                      </span>
                      <span className="bar">
                        <i style={{ width: `${Math.round((job.stageIndex < 0 ? uploaded * 0.08 : job.progress) * 100)}%` }} />
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="w-t">That didn&apos;t work</span>
                      <span className="w-s">{job.error || "Try a different video."}</span>
                      <span className="w-row">
                        {(footageJob || targets.length > 0) && (
                          <button className="btn sm" onClick={() => start(overrides)}>Try again</button>
                        )}
                        <button className="btn ghost sm" onClick={startOver}>Start over</button>
                      </span>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>

          {panel === "edit" && done && (
            <Timeline jobId={job.id} at={playhead} version={videoKey}
              onSeek={t => {
                if (afterRef.current) afterRef.current.currentTime = t;
                setPlayhead(t);
              }} />
          )}

          <p className="facts">{done ? facts || " " : " "}</p>
        </main>

        {panel && (
          <aside className="panel">
            {panel === "edit" ? (
              <>
                <div className="tabs" role="tablist">
                  <button className="tab" role="tab" aria-selected={tab === "ask"} onClick={() => setTab("ask")}>Ask</button>
                  <button className="tab" role="tab" aria-selected={tab === "captions"} onClick={() => setTab("captions")}>Captions</button>
                  <button className="tab" role="tab" aria-selected={tab === "style"} onClick={() => setTab("style")}>Style</button>
                  <button className="x" aria-label="Close" onClick={() => setPanel(null)}>×</button>
                </div>

                {tab === "ask" && (
                  <>
                    <div className="chat-log" ref={logRef}>
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
                          <button key={s} className="chip" onClick={() => say(s)} disabled={thinking || running}>{s}</button>
                        ))}
                      </div>
                      <div className="composer">
                        <textarea rows={1} placeholder="Make the captions pop more…" value={draft}
                          onChange={e => setDraft(e.target.value)}
                          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); say(draft); } }} />
                        <button className="send" aria-label="Send" onClick={() => say(draft)}
                                disabled={!draft.trim() || thinking || running}>↑</button>
                      </div>
                    </div>
                  </>
                )}

                {tab === "captions" && <CaptionFixer jobId={job.id} ready={done} onApplied={rerendered} />}

                {tab === "style" && (
                  <div className="panel-scroll">
                    <div className="block">
                      <span className="eyebrow">Caption look{styling ? " — applying…" : ""}</span>
                      {looks.length ? (
                        <div className="looks-grid">
                          {looks.map(l => (
                            <button key={l.id} className="lk" aria-pressed={look === l.id}
                              disabled={styling || !done} onClick={() => chooseLook(l.id)}>
                              <span className="n">{l.label}</span>
                              <span className="b">{l.blurb}</span>
                            </button>
                          ))}
                        </div>
                      ) : <span className="tiny">Loading looks…</span>}
                    </div>

                    <div className="block">
                      <span className="eyebrow">Type</span>
                      <TypeControls jobId={job.id} ready={done} version={videoKey} onApplied={rerendered} />
                    </div>

                    <div className="block">
                      <span className="eyebrow">Captions and you{placing ? " — placing…" : ""}</span>
                      <div className="looks-grid">
                        {SPEAKER_MODES.map(m => (
                          <button key={m.id} className="lk" aria-pressed={speaker === m.id}
                            disabled={placing || styling || !done} onClick={() => chooseSpeaker(m.id)}>
                            <span className="n">{m.label}</span>
                            <span className="b">{m.blurb}</span>
                          </button>
                        ))}
                      </div>
                      {speakerNote && <span className="tiny">{speakerNote}</span>}
                    </div>

                    <div className="block">
                      <span className="eyebrow">Background</span>
                      <div className="swatches">
                        <button className="swatch as-shot" aria-pressed={backdrop === null} aria-label="As shot"
                          title="As shot" disabled={placing || !done} onClick={() => chooseBackdrop(null)} />
                        {BACKDROPS.map(c => (
                          <button key={c} className="swatch" style={{ background: c }} aria-label={c} title={c}
                            aria-pressed={backdrop?.toLowerCase() === c.toLowerCase()}
                            disabled={placing || !done} onClick={() => chooseBackdrop(c)} />
                        ))}
                        <label className="swatch custom" title="Any colour"
                          aria-pressed={backdrop !== null && !BACKDROPS.some(c => c.toLowerCase() === backdrop.toLowerCase())}
                          style={backdrop && !BACKDROPS.includes(backdrop) ? { background: backdrop } : undefined}>
                          <input ref={picker} type="color" aria-label="Any colour" disabled={placing || !done}
                            defaultValue={backdrop ?? "#ffffff"} />
                        </label>
                      </div>
                      <span className="tiny">{backdrop ? "Everything behind you becomes this colour" : "Your own background, as shot"}</span>
                    </div>

                    <div className="block">
                      <span className="eyebrow">Music{mixing ? " — mixing…" : ""}</span>
                      <input ref={musicInput} type="file" accept="audio/*" hidden
                        onChange={e => { setMusic(e.target.files?.[0] ?? null); e.target.value = ""; }} />
                      {track ? (
                        <div className="loaded">
                          <span className="thumb">♪</span>
                          <span style={{ flex: 1 }}>
                            <span className="nm" style={{ display: "block" }}>{track}</span>
                            <span className="tiny">Ducks under your voice</span>
                          </span>
                          <button className="btn ghost sm" disabled={mixing} onClick={() => setMusic(null)}>Remove</button>
                        </div>
                      ) : (
                        <button className="drop-zone" disabled={mixing || !done} onClick={() => musicInput.current?.click()}>
                          <span className="tile-t">Add a track</span>
                          <span className="tile-s">It ducks under your voice automatically</span>
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <>
                <div className="panel-head">
                  <span className="eyebrow">{panel === "read" ? "What we read from the reel" : "How close it got"}</span>
                  <button className="x" aria-label="Close" onClick={() => setPanel(null)}>×</button>
                </div>
                <div className="panel-scroll">
                  {panel === "read" && fp && <Readout fp={fp} />}
                  {panel === "score" && (
                    scoring ? <p className="tiny">Measuring your edit against the reel — this takes a moment.</p>
                      : scoreError ? <p className="tiny" style={{ color: "var(--bad)" }}>{scoreError}</p>
                      : score ? <Scorecard score={score} />
                      : <p className="tiny">Available once the edit is ready.</p>
                  )}
                </div>
              </>
            )}
          </aside>
        )}
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
