"use client";

/**
 * Point at a reel you love, hand over your footage, get it back cut that way.
 *
 * Three moments, one screen. First the pair: the reel on the left, your
 * footage on the right, reading the reel the moment it lands. Then the edit
 * being made, over your own footage, told in the reel's own caption voice and
 * only in facts the pipeline has reported. Then the edit, which never leaves
 * the screen again: every change (a look, a chat request, an undo) renders
 * behind it and wipes in at the same moment of the video.
 *
 * Everything a creator might reach for lives in the Edit sheet or the ⋯ menu,
 * never on the video. A refresh lands back on the same edit: what the page
 * knows is remembered in this browser (lib/remember) and the files stay on
 * the server.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import CaptionFixer from "@/components/CaptionFixer";
import TypeControls from "@/components/TypeControls";
import Making from "@/components/studio/Making";
import Menu, { type MenuView } from "@/components/studio/Menu";
import Player from "@/components/studio/Player";
import SaveButton from "@/components/studio/SaveButton";
import Setup from "@/components/studio/Setup";
import Sheet, { type Tab } from "@/components/studio/Sheet";
import { AskTab, LooksTab, MusicTab, type Msg, YouTab } from "@/components/studio/Tabs";
import Toast, { type Note } from "@/components/studio/Toast";
import { More, Sliders, Sound, Touch } from "@/components/studio/icons";
import s from "@/components/studio/studio.module.css";
import type { Fingerprint } from "@/lib/fingerprint";
import type { Facts, Receipt } from "@/lib/pipeline";
import { forgetJob, recall, remember } from "@/lib/remember";
import type { Score } from "@/lib/score";
import { STAGE_NAMES, voiceOf } from "@/lib/studio";

type Read = {
  id: string; status: "running" | "done" | "error"; name: string; videoPath: string;
  error?: string; fingerprint?: Fingerprint;
};
type Style = { id: string; name: string };
type Job = {
  id: string; status: "running" | "done" | "error"; stageIndex: number; progress: number;
  targetName: string; error?: string; startedAt?: number; facts?: Facts;
  profile?: Record<string, unknown>; receipt?: Receipt; clips?: { start: number; end: number }[];
};
/** The choices a change can overwrite, kept so Undo can put them back. */
type Ui = { look: string; speaker: string; backdrop: string | null; track: string; overrides: Record<string, unknown> };
/** One step back: a re-render of the same edit, or a whole remade edit. */
type Step = { kind: "restyle"; jobId: string; ui: Ui } | { kind: "remake"; prev: Job; ui: Ui };
type Applying = { label: string; startedAt: number; estimate: number };
type Session = {
  read: Read | null; preset: Style | null; edit: Job | null; run: Job | null;
  footageJob: string | null; takes: number; sourceSeconds: number | null;
  ui: Ui; msgs: Msg[]; history: Step[]; heard: boolean; heldOnce: boolean; sheet: boolean; tab: Tab;
};
const SESSION = "studio.v2";
const HELLO: Msg = { who: "bot", text: "What should I change? Plain words are fine." };
const FIRST_UI: Ui = { look: "", speaker: "off", backdrop: null, track: "", overrides: {} };

// A re-render takes a fixed start-up plus some share of the video's length.
// The share is learned from each change this browser makes.
const RESTYLE_BASE = 3;
const learnedShare = () => { try { return Number(localStorage.getItem("hh.restyleShare")) || 0.45; } catch { return 0.45; } };
const learn = (seconds: number, videoSeconds: number) => {
  if (!videoSeconds) return;
  const share = Math.min(2, Math.max(0.1, 0.6 * learnedShare() + 0.4 * ((seconds - RESTYLE_BASE) / videoSeconds)));
  try { localStorage.setItem("hh.restyleShare", String(share)); } catch { /* estimate stays the default */ }
};

const durationOf = (file: File) => new Promise<number>(resolve => {
  const url = URL.createObjectURL(file);
  const v = document.createElement("video");
  v.preload = "metadata";
  v.onloadedmetadata = () => { resolve(Number.isFinite(v.duration) ? v.duration : 0); URL.revokeObjectURL(url); };
  v.onerror = () => { resolve(0); URL.revokeObjectURL(url); };
  v.src = url;
});

const real = (id: string | undefined) => !!id && id !== "…" && id !== "—";

export default function Studio() {
  // ---- what goes in ------------------------------------------------------
  const [read, setRead] = useState<Read | null>(null);
  const [refUrl, setRefUrl] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const readSeq = useRef(0);                      // the latest reel dropped wins
  const [styles, setStyles] = useState<Style[]>([]);
  const [presets, setPresets] = useState(false);
  const [preset, setPreset] = useState<Style | null>(null);
  const [targets, setTargets] = useState<File[]>([]);
  const [targetUrl, setTargetUrl] = useState<string | null>(null);
  const [sourceSeconds, setSourceSeconds] = useState<number | null>(null);
  const [takes, setTakes] = useState(0);
  // The first job made with this footage. Every re-run reuses what it uploaded.
  const [footageJob, setFootageJob] = useState<string | null>(null);
  const [queued, setQueued] = useState(false);

  // ---- the edit ------------------------------------------------------------
  const [run, setRun] = useState<Job | null>(null);          // being made
  const [edit, setEdit] = useState<Job | null>(null);        // on screen
  const [uploaded, setUploaded] = useState<number | null>(null);
  const [version, setVersion] = useState(0);                 // bumps when the file changes in place
  const [startAt, setStartAt] = useState<number | undefined>(0);
  const [applying, setApplying] = useState<Applying | null>(null);
  const [applyingLook, setApplyingLook] = useState<string | null>(null);
  const [landedLook, setLandedLook] = useState<string | null>(null);
  const [history, setHistory] = useState<Step[]>([]);
  const [ui, setUi] = useState<Ui>(FIRST_UI);
  const [msgs, setMsgs] = useState<Msg[]>([HELLO]);
  const [thinking, setThinking] = useState(false);

  // ---- watching it ---------------------------------------------------------
  const [muted, setMuted] = useState(true);
  const [heard, setHeard] = useState(false);       // has turned the sound on once
  const [heldOnce, setHeldOnce] = useState(false); // has held the video once
  const [revealing, setRevealing] = useState(false);
  const [unseen, setUnseen] = useState(false);
  const [time, setTime] = useState(0);
  const [length, setLength] = useState(0);
  const [seek, setSeek] = useState<{ t: number; n: number } | undefined>();
  const [reelHeld, setReelHeld] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [tab, setTab] = useState<Tab>("looks");
  const [menu, setMenu] = useState<MenuView | null>(null);
  const [note, setNote] = useState<Note | null>(null);
  const [score, setScore] = useState<Score | null>(null);
  const [scoring, setScoring] = useState(false);
  const [scoreError, setScoreError] = useState("");

  // Handlers and pollers read the latest of these without re-subscribing.
  const editRef = useRef(edit);
  const historyRef = useRef(history);
  const uiRef = useRef(ui);
  useEffect(() => { editRef.current = edit; historyRef.current = history; uiRef.current = ui; }, [edit, history, ui]);
  const busy = useRef(false);                       // one change at a time
  const remake = useRef<Ui | null>(null);           // the choices before a chat re-run
  const before = useRef<Ui | null>(null);           // the choices before a restyle
  const pendingNote = useRef<Omit<Note, "n"> | null>(null);
  const synced = useRef<string | null>(null);       // the edit whose choices were last read from its profile
  const notes = useRef(0);

  const say = useCallback((n: Omit<Note, "n">) => setNote({ ...n, n: ++notes.current }), []);

  // ---- surviving a refresh ---------------------------------------------------
  const [restored, setRestored] = useState(false);
  useEffect(() => {
    const saved = recall<Session>(SESSION);
    /* eslint-disable react-hooks/set-state-in-effect -- storage is only readable after mount */
    if (saved) {
      setRead(saved.read); setPreset(saved.preset); setEdit(saved.edit); setRun(saved.run);
      setFootageJob(saved.footageJob); setTakes(saved.takes); setSourceSeconds(saved.sourceSeconds);
      setUi(saved.ui ?? FIRST_UI); setMsgs(saved.msgs?.length ? saved.msgs : [HELLO]);
      setHistory(saved.history ?? []); setHeard(saved.heard); setHeldOnce(saved.heldOnce);
      setSheet(saved.sheet && !!saved.edit); setTab(saved.tab ?? "looks");
      synced.current = saved.edit?.id ?? null;
      // The server may have lost it while the page was closed.
      const id = saved.edit?.id;
      if (id) {
        fetch(`/api/jobs/${id}`).then(r => {
          if (r.status !== 404) return;
          setEdit(null); setHistory([]); setSheet(false);
          say({ text: "That edit is no longer on the server. Make it again.", bad: true });
        }).catch(() => {});
      }
    }
    setRestored(true);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [say]);

  useEffect(() => {
    if (!restored) return;
    remember(SESSION, {
      read: read && real(read.id) ? read : null, preset, edit,
      run: run && real(run.id) && run.status === "running" ? run : null,
      footageJob, takes, sourceSeconds, ui, msgs, history, heard, heldOnce, sheet, tab,
    } satisfies Session);
  }, [restored, read, preset, edit, run, footageJob, takes, sourceSeconds, ui, msgs, history, heard, heldOnce, sheet, tab]);

  useEffect(() => { fetch("/api/styles").then(r => r.json()).then(d => setStyles(d.styles ?? [])).catch(() => {}); }, []);

  // ---- reading the reel --------------------------------------------------------
  const readId = read?.id;
  const readRunning = read?.status === "running";
  useEffect(() => {
    if (!readRunning || !readId) return;
    const tick = setInterval(() => setElapsed(e => e + 1), 1000);
    const poll = readId === "…" ? undefined : setInterval(async () => {
      const r = await fetch(`/api/fingerprint/${readId}`).catch(() => null);
      if (!r) return;
      if (r.status === 404) {
        setRead(cur => (cur?.id === readId ? { ...cur, status: "error", error: "That reading was interrupted. Add the reel again." } : cur));
        return;
      }
      if (!r.ok) return;
      const next: Read = await r.json();
      setRead(cur => (cur?.id === next.id ? next : cur));
    }, 1200);
    return () => { clearInterval(tick); clearInterval(poll); };
  }, [readId, readRunning]);

  const readReference = useCallback(async (file: File) => {
    const mine = ++readSeq.current;
    setPreset(null); setPresets(false); setElapsed(0);
    setRefUrl(old => { if (old) URL.revokeObjectURL(old); return URL.createObjectURL(file); });
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
        setRead({ id: "—", status: "error", name: file.name, videoPath: "", error: "The upload didn't go through. Try again." });
      }
    }
  }, []);

  const chooseFootage = useCallback(async (files: File[]) => {
    setTargets(files); setFootageJob(null); setTakes(0);
    setTargetUrl(old => { if (old) URL.revokeObjectURL(old); return URL.createObjectURL(files[0]); });
    setSourceSeconds(null);
    const lengths = await Promise.all(files.map(durationOf));
    setSourceSeconds(lengths.reduce((a, b) => a + b, 0) || null);
  }, []);

  // ---- making the edit -----------------------------------------------------------
  // Every run - the first and each chat request - sends the same look. A
  // request that forgot the reel would quietly re-render against a built-in look.
  const start = useCallback(async (patch: Record<string, unknown>, uiBefore?: Ui) => {
    if (!targets.length && !footageJob) return;
    const fd = new FormData();
    if (footageJob) fd.set("fromJob", footageJob);
    else for (const f of targets) fd.append("target", f);
    if (read?.status === "done") { fd.set("referencePath", read.videoPath); fd.set("referenceName", read.name); }
    else if (preset) fd.set("styleId", preset.id);
    // A re-run with neither copies the reel its footage was first edited to.
    else if (!footageJob) return;
    fd.set("overrides", JSON.stringify(patch));
    remake.current = uiBefore ?? null;

    const name = footageJob ? editRef.current?.targetName ?? "" : targets.length > 1 ? `${targets.length} takes` : targets[0].name;
    const sending = !footageJob;
    setUploaded(sending ? 0 : null);
    setRun({ id: "…", status: "running", stageIndex: -1, progress: 0, targetName: name, startedAt: Date.now() });
    const d = await new Promise<{ id?: string; error?: string }>(resolve => {
      const x = new XMLHttpRequest();
      x.open("POST", "/api/jobs");
      x.upload.onprogress = e => { if (e.lengthComputable && sending) setUploaded(e.loaded / e.total); };
      x.onload = () => { try { resolve(JSON.parse(x.responseText || "{}")); } catch { resolve({ error: "The server didn't answer properly." }); } };
      x.onerror = () => resolve({ error: "The upload didn't go through. Try again." });
      x.send(fd);
    });
    setUploaded(null);
    if (d.id) {
      if (!footageJob) { setFootageJob(d.id); setTakes(targets.length); }
      setRun({ id: d.id, status: "running", stageIndex: 0, progress: 0.08, targetName: name, startedAt: Date.now() });
    } else if (editRef.current) {
      setRun(null);
      say({ text: d.error ?? "That didn't go through.", bad: true });
    } else {
      setRun({ id: "—", status: "error", stageIndex: 0, progress: 0, targetName: name, error: d.error });
    }
  }, [targets, footageJob, read, preset, say]);

  // Tapped while the reel was still being read: go the moment it is.
  useEffect(() => {
    if (!queued) return;
    /* eslint-disable react-hooks/set-state-in-effect -- reacting to the reading finishing */
    if (read?.status === "done") { setQueued(false); start({}); }
    else if (read?.status === "error") setQueued(false);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [queued, read?.status, start]);

  const runId = run?.id;
  const runRunning = run?.status === "running";
  useEffect(() => {
    if (!runRunning || !real(runId)) return;
    const id = runId!;
    const t = setInterval(async () => {
      const r = await fetch(`/api/jobs/${id}`).catch(() => null);
      if (!r || (!r.ok && r.status !== 404)) return;
      const next: Job = r.ok ? await r.json()
        : { id, status: "error", stageIndex: 0, progress: 0, targetName: "", error: "This edit is no longer on the server." };
      if (next.status === "running") { setRun(cur => (cur?.id === id ? next : cur)); return; }
      setRun(null);
      const prev = editRef.current;
      if (next.status === "error") {
        if (prev) say({ text: "That change didn't render, so the last version stays.", bad: true });
        else setRun(next);
        return;
      }
      setStartAt(0);
      setEdit(next);
      if (!prev) {
        setRevealing(true);
        setTimeout(() => setRevealing(false), 2000);
        if (document.hidden) setUnseen(true);
      } else {
        setHistory(h => [...h, { kind: "remake", prev, ui: remake.current ?? uiRef.current }]);
        const shorter = prev.receipt && next.receipt ? prev.receipt.outputSeconds - next.receipt.outputSeconds : 0;
        pendingNote.current = { text: shorter >= 1 ? `Done · ${Math.round(shorter)}s shorter` : "Done", undo: true };
      }
    }, 900);
    return () => clearInterval(t);
  }, [runId, runRunning, say]);

  // A fresh edit starts from the choices it was made with.
  useEffect(() => {
    if (!edit || synced.current === edit.id) return;
    synced.current = edit.id;
    const subject = (edit.profile as { subject?: { captions?: string; background_hex?: string | null } } | undefined)?.subject;
    setUi(u => ({ ...u, look: "", speaker: subject?.captions ?? "off", backdrop: subject?.background_hex ?? null }));
  }, [edit]);

  // The tab says where things stand, for someone who switched away.
  useEffect(() => {
    const back = () => { if (!document.hidden) setUnseen(false); };
    document.addEventListener("visibilitychange", back);
    return () => document.removeEventListener("visibilitychange", back);
  }, []);
  useEffect(() => {
    document.title = run && run.status === "running" && !edit
      ? `${STAGE_NAMES[Math.max(0, run.stageIndex)]}… · Halfheaven`
      : unseen ? "Your edit is ready · Halfheaven" : "Studio · Halfheaven";
  }, [run, edit, unseen]);

  // ---- changing it -----------------------------------------------------------------
  // A change shows as chosen the moment it is tapped; the video keeps playing
  // under a sheen until the render lands, then wipes to it. A failure puts the
  // old choice back.
  const applyStart = useRef(0);
  const begin = useCallback((label: string, next?: Partial<Ui>) => {
    const e = editRef.current;
    if (!e || busy.current) return false;
    busy.current = true;
    before.current = uiRef.current;
    applyStart.current = Date.now();
    if (next) setUi(u => ({ ...u, ...next }));
    setApplying({ label, startedAt: applyStart.current, estimate: RESTYLE_BASE + learnedShare() * (e.receipt?.outputSeconds ?? 30) });
    return true;
  }, []);
  const landed = useCallback((text: string) => {
    const e = editRef.current;
    if (e) learn((Date.now() - applyStart.current) / 1000, e.receipt?.outputSeconds ?? 0);
    if (e && before.current) {
      const was = before.current;
      setHistory(h => [...h, { kind: "restyle", jobId: e.id, ui: was }]);
    }
    pendingNote.current = { text, undo: true };
    busy.current = false;
    setApplying(null);
    setStartAt(undefined);
    setVersion(v => v + 1);
  }, []);
  const failed = useCallback((why: string) => {
    busy.current = false;
    if (before.current) setUi(before.current);
    setApplying(null);
    setApplyingLook(null);
    say({ text: why || "That didn't apply.", bad: true });
  }, [say]);

  /** A change that is one POST and a render. */
  const change = useCallback(async (label: string, done: string, url: string, init: RequestInit, next?: Partial<Ui>) => {
    const e = editRef.current;
    if (!e || !begin(label, next)) return false;
    try {
      const r = await fetch(`/api/jobs/${e.id}/${url}`, init);
      if (!r.ok) { failed((await r.json().catch(() => ({}))).error ?? "That didn't apply."); return false; }
      landed(done);
      return true;
    } catch { failed("That didn't apply."); return false; }
  }, [begin, landed, failed]);

  const json = (body: unknown): RequestInit => ({ method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });

  const chooseLook = async (look: { id: string; label: string }) => {
    setApplyingLook(look.id);
    const ok = await change(`Applying ${look.label}`, `${look.label} is on`, "look", json({ preset: look.id }), { look: look.id });
    setApplyingLook(null);
    if (ok) { setLandedLook(look.id); setTimeout(() => setLandedLook(l => (l === look.id ? null : l)), 2400); }
  };
  const chooseSpeaker = (mode: string) => change(
    "Placing your captions",
    mode === "off" ? "Captions back where the look puts them" : mode === "around" ? "Captions kept off you" : "Key words tucked behind you",
    "subject", json({ mode }), { speaker: mode });
  const chooseBackdrop = (hex: string | null) => change(
    hex ? "Changing your background" : "Putting your background back",
    hex ? "New background" : "Background as shot", "subject", json({ background: hex }), { backdrop: hex });
  const setMusic = (file: File | null) => {
    const fd = new FormData();
    if (file) fd.set("track", file); else fd.set("remove", "1");
    return change(file ? "Mixing your track" : "Taking the music out", file ? "Music added" : "Music removed",
      "music", { method: "POST", body: fd }, { track: file ? file.name : "" });
  };

  const ask = async (text: string) => {
    const e = editRef.current;
    if (!e || thinking || run || busy.current) return;
    setMsgs(m => [...m, { who: "me", text }]);
    setThinking(true);
    try {
      const r = await fetch("/api/chat", json({ message: text, profile: e.profile }));
      const d = await r.json();
      setMsgs(m => [...m, { who: "bot", text: d.reply, changed: d.changed }]);
      if (Object.keys(d.overrides ?? {}).length) {
        const merged = { ...uiRef.current.overrides, ...d.overrides };
        const was = uiRef.current;
        setUi(u => ({ ...u, overrides: merged }));
        start(merged, was);
      }
    } catch {
      setMsgs(m => [...m, { who: "bot", text: "I couldn't reach the model just then. Try that again." }]);
    } finally { setThinking(false); }
  };

  const undo = async () => {
    const last = historyRef.current.at(-1);
    if (!last || busy.current || run) return;
    setNote(null);
    if (last.kind === "remake") {
      synced.current = last.prev.id;          // its choices come from the history, not its profile
      setUi(last.ui);
      setHistory(h => h.slice(0, -1));
      pendingNote.current = { text: "Undone" };
      setStartAt(0);
      setEdit(last.prev);
      return;
    }
    busy.current = true;
    setApplying({ label: "Undoing", startedAt: Date.now(), estimate: 1 });
    try {
      const r = await fetch(`/api/jobs/${last.jobId}/undo`, { method: "POST" });
      if (!r.ok) { say({ text: "Couldn't undo that one.", bad: true }); return; }
      setUi(last.ui);
      setHistory(h => h.slice(0, -1));
      pendingNote.current = { text: "Undone" };
      setStartAt(undefined);
      setVersion(v => v + 1);
    } finally { busy.current = false; setApplying(null); }
  };

  // The clock the "about Ns" countdown reads while a change renders.
  const [now, setNow] = useState(0);
  useEffect(() => {
    if (!applying) return;
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, [applying]);

  const onWipeDone = useCallback(() => {
    if (pendingNote.current) { say(pendingNote.current); pendingNote.current = null; }
  }, [say]);

  const runScore = async () => {
    setMenu("score");
    const e = editRef.current;
    if (!e || score || scoring) return;
    setScoring(true); setScoreError("");
    try {
      const d = await (await fetch("/api/score", json({ jobId: e.id }))).json();
      if (d.error) setScoreError(d.error); else setScore(d);
    } catch { setScoreError("Couldn't reach the scorer. Try again in a moment."); }
    finally { setScoring(false); }
  };

  const startOver = () => {
    readSeq.current++;
    for (const j of [edit, run, ...history.flatMap(h => (h.kind === "remake" ? [h.prev] : []))]) if (j) forgetJob(j.id);
    if (refUrl) URL.revokeObjectURL(refUrl);
    if (targetUrl) URL.revokeObjectURL(targetUrl);
    setRead(null); setRefUrl(null); setPreset(null); setPresets(false); setTargets([]); setTargetUrl(null);
    setSourceSeconds(null); setFootageJob(null); setTakes(0); setQueued(false);
    setRun(null); setEdit(null); setHistory([]); setUi(FIRST_UI); setMsgs([HELLO]); setVersion(0);
    setSheet(false); setTab("looks"); setMenu(null); setNote(null); setScore(null); setScoreError("");
    setMuted(true); synced.current = null;
  };

  if (!restored) return null;

  const fp = read?.status === "done" ? read.fingerprint : undefined;
  const menuEl = menu && (
    <Menu view={menu} fp={fp} canScore={!!edit} score={score} scoring={scoring} scoreError={scoreError}
      onView={v => (v === "score" ? runScore() : setMenu(v))} onClose={() => setMenu(null)}
      onStartOver={startOver} />
  );

  // ================================================================ the pair
  if (!edit && !run) {
    return (
      <>
        <Setup refUrl={refUrl} read={read} elapsed={elapsed} fp={fp} presets={presets} styles={styles}
          preset={preset} targets={targets} targetUrl={targetUrl} sourceSeconds={sourceSeconds} queued={queued}
          onReel={readReference} onFootage={chooseFootage}
          onPreset={st => { readSeq.current++; setPreset(st); setRead(null); }}
          onPresets={on => { setPresets(on); if (!on) setPreset(null); }}
          onGo={() => (read?.status === "running" ? setQueued(true) : start({}))}
          onSeeAll={() => setMenu("read")} />
        <Toast note={note} overSheet={false} onUndo={undo} onGone={() => setNote(null)} />
        {menuEl}
      </>
    );
  }

  // ================================================== making it, and the edit
  const job = edit ?? run!;
  const footage = targetUrl ?? (real(job.id) ? `/api/jobs/${job.id}/media?v=before` : null);
  const src = edit ? `/api/jobs/${edit.id}/media?v=after&r=${version}` : footage;
  const reference = refUrl ?? (real(job.id) ? `/api/jobs/${job.id}/media?v=reference` : null);
  const original = edit && takes === 1 ? footage : null;
  const making = !edit && !!run;
  const remaking = !!edit && !!run;
  const r = edit?.receipt;
  const saved = r ? Math.max(0, r.sourceSeconds - r.outputSeconds) : 0;
  const facts = r ? [saved >= 1 && `${Math.round(saved)}s shorter`, r.captions > 0 && `${r.captions} captions`,
    r.wordsCut > 0 && `${r.wordsCut} ${r.wordsCut === 1 ? "stumble" : "stumbles"} cut`].filter(Boolean).join(" · ") : "";
  const locked = !!applying || !!run;
  const spent = applying ? Math.max(0, now - applying.startedAt) / 1000 : 0;
  const remaining = applying ? Math.max(1, Math.round(applying.estimate - spent)) : 0;
  const fileName = `${(edit?.targetName ?? "edit").replace(/\.[^.]+$/, "")}-edited.mp4`;

  const scrub = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.type === "pointerdown") e.currentTarget.setPointerCapture(e.pointerId);
    else if (e.buttons === 0) return;
    const box = e.currentTarget.getBoundingClientRect();
    const t = Math.max(0, Math.min(1, (e.clientX - box.left) / box.width)) * length;
    setTime(t);
    setSeek(k => ({ t, n: (k?.n ?? 0) + 1 }));
  };

  return (
    <div className={`${s.studio} ${sheet && edit ? s.open : ""}`}>
      <div className={s.stage}>
        {src && (
          <Player src={src} startAt={startAt} muted={muted} original={original} clips={edit?.clips}
            reference={reference} reelHeld={reelHeld} seek={seek} onWipeDone={onWipeDone}
            onHeld={() => setHeldOnce(true)} onTime={(t, d) => { setTime(t); setLength(d); }}>

            {making && (
              <Making run={run!} uploaded={uploaded} voice={voiceOf(fp)}
                reelLab={(fp?.grade.lab_mean?.value as number[] | undefined) ?? null}
                sourceSeconds={sourceSeconds} time={time}
                matte={run!.facts?.subjectSeconds !== undefined && real(run!.id) ? `/api/jobs/${run!.id}/media?v=matte` : null}
                onRetry={() => start(ui.overrides)} onStartOver={startOver} />
            )}

            {edit && <div className={s.shade} />}
            {(applying || remaking) && <div className={s.sheen} />}
            {applying && (
              <div className={s.pillWrap}>
                <span className={s.pill}>
                  {applying.label}{applying.label !== "Undoing" && <> · <span className={s.mono}>about {remaining}s</span></>}
                  <span className={s.pillBar}>
                    <i style={{ transform: `scaleX(${Math.min(0.9, spent / applying.estimate)})` }} />
                  </span>
                </span>
              </div>
            )}
            {remaking && (
              <div className={s.pillWrap}>
                <span className={s.pill}>
                  Remaking your edit
                  <span className={s.segs} aria-hidden>
                    {STAGE_NAMES.map((n, i) => <i key={n} className={i < run!.stageIndex ? s.on : i === run!.stageIndex ? s.now : undefined} />)}
                  </span>
                </span>
              </div>
            )}
            {revealing && <p className={s.title}>Here&apos;s <em>yours</em>.</p>}

            <div className={`${s.topbar} ${making ? s.belowBars : ""}`}>
              {reference ? (
                <button className={s.insetBtn} aria-label="Hold to see the reel you love"
                  onPointerDown={e => { e.currentTarget.setPointerCapture(e.pointerId); setReelHeld(true); }}
                  onPointerUp={() => setReelHeld(false)} onPointerCancel={() => setReelHeld(false)}
                  onContextMenu={e => e.preventDefault()}>
                  <span className={s.inset}><video src={reference} muted loop playsInline autoPlay /></span>
                  <span className={s.insetLabel}>Reel you love</span>
                </button>
              ) : <span />}
              <div className={s.tools}>
                {edit && !heard && !revealing && (
                  <button className={s.nudge} onClick={() => { setMuted(false); setHeard(true); }}>Tap for sound</button>
                )}
                {edit && (
                  <button className={s.round} aria-label={muted ? "Turn sound on" : "Mute"}
                          onClick={() => { setMuted(m => !m); setHeard(true); }}>
                    <Sound on={!muted} size={18} />
                  </button>
                )}
                <button className={s.round} aria-label="More" onClick={() => setMenu("menu")}><More size={20} /></button>
              </div>
            </div>

            {edit && !revealing && (
              <div className={s.bottom}>
                {takes === 1 && !heldOnce && !sheet && (
                  <span className={s.hintPill}><Touch size={16} />Hold the video to see your original</span>
                )}
                {facts && <p className={s.facts}>{facts}</p>}
                <div className={s.scrub} onPointerDown={scrub} onPointerMove={scrub} role="slider"
                     aria-label="Seek" aria-valuemin={0} aria-valuemax={Math.round(length)} aria-valuenow={Math.round(time)}>
                  <span className={s.scrubbed} style={{ width: `${length ? (time / length) * 100 : 0}%` }} />
                </div>
                <div className={s.actions}>
                  <button className={s.secondary} aria-pressed={sheet} onClick={() => setSheet(v => !v)}>
                    <Sliders size={18} />Edit
                  </button>
                  <SaveButton key={`${edit.id}-${version}`} src={`/api/jobs/${edit.id}/media?v=after&r=${version}`} name={fileName} />
                </div>
              </div>
            )}
          </Player>
        )}
      </div>

      {sheet && edit && (
        <Sheet tab={tab} onTab={setTab} onClose={() => setSheet(false)} flush={tab === "ask"}>
          {tab === "looks" && (
            <LooksTab jobId={edit.id} version={version} current={ui.look} applying={applyingLook}
              landed={landedLook} disabled={locked} onChoose={chooseLook} />
          )}
          {tab === "ask" && <AskTab msgs={msgs} thinking={thinking} busy={locked || thinking} onSay={ask} />}
          {tab === "type" && (
            <fieldset disabled={locked} className={s.plain}>
              <TypeControls jobId={edit.id} ready version={version}
                onStart={() => begin("Setting your type")} onApplied={() => landed("Type updated")} onFailed={failed} />
            </fieldset>
          )}
          {tab === "you" && (
            <YouTab speaker={ui.speaker} backdrop={ui.backdrop} disabled={locked}
              onSpeaker={chooseSpeaker} onBackdrop={chooseBackdrop} />
          )}
          {tab === "words" && (
            <fieldset disabled={locked} className={s.plain}>
              <CaptionFixer key={`${edit.id}-${version}`} jobId={edit.id} ready
                onStart={() => begin("Fixing your captions")} onApplied={() => landed("Captions fixed")} onFailed={failed} />
            </fieldset>
          )}
          {tab === "music" && (
            <MusicTab track={ui.track} disabled={locked} onFile={f => setMusic(f)} onRemove={() => setMusic(null)} />
          )}
        </Sheet>
      )}

      <Toast note={note} overSheet={sheet && !!edit} onUndo={undo} onGone={() => setNote(null)} />
      {menuEl}
    </div>
  );
}
