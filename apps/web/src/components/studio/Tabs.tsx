"use client";

import { useEffect, useRef, useState } from "react";

import { Check, Mark, Music, Up } from "./icons";
import s from "./studio.module.css";

// ---- looks ------------------------------------------------------------------

type Look = { id: string; label: string; blurb: string; file: string };

/** Every caption look, as the renderer would draw it on this edit. The stills
 *  are real renders, so what you tap is what you get. */
export function LooksTab({ jobId, version, current, applying, landed, disabled, onChoose }: {
  jobId: string;
  version: number;
  current: string;
  applying: string | null;
  landed: string | null;
  disabled: boolean;
  onChoose: (look: Look) => void;
}) {
  const [looks, setLooks] = useState<Look[] | null>(null);
  const [stamp, setStamp] = useState(0);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    fetch(`/api/jobs/${jobId}/looks`).then(r => r.json()).then(d => {
      if (!live) return;
      if (d.looks) { setLooks(d.looks); setStamp(d.version); setFailed(false); } else setFailed(true);
    }).catch(() => live && setFailed(true));
    return () => { live = false; };
  }, [jobId, version]);

  const selected = current || looks?.[0]?.id;
  return (
    <>
      <div className={s.looks}>
        {looks ? looks.map(look => (
          <button key={look.id} className={s.look} aria-pressed={selected === look.id}
                  disabled={disabled && applying !== look.id} title={look.blurb}
                  onClick={() => look.id !== selected && onChoose(look)}>
            <span className={s.lookPic}>
              {/* stills from our own API, redrawn per version: nothing for next/image to optimise */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={`/api/jobs/${jobId}/looks/${look.file}?v=${stamp}`} alt={`${look.label}: ${look.blurb}`} />
              {applying === look.id && (
                <svg className={s.spin} viewBox="0 0 112 191" preserveAspectRatio="none" aria-hidden>
                  <rect x="1.5" y="1.5" width="109" height="188" rx="15" pathLength={100} />
                </svg>
              )}
              {landed === look.id && <span className={s.doneMark}><Check size={13} /></span>}
            </span>
            <span className={s.lookName}>{look.label}</span>
          </button>
        )) : Array.from({ length: 5 }, (_, i) => (
          <span key={i} className={s.look}>
            <span className={`${s.lookPic} ${s.skeleton}`} style={{ borderRadius: 12 }} />
            <span className={s.lookName} style={{ color: "var(--text-3)" }}>…</span>
          </span>
        ))}
      </div>
      <p className={s.note}>
        {failed ? "Couldn't draw the looks just now. Close and open Edit to try again."
          : "Looks only change the captions. Your cut stays as it is."}
      </p>
    </>
  );
}

// ---- ask --------------------------------------------------------------------

export type Msg = { who: "me" | "bot"; text: string; changed?: string[] };

const SUGGESTIONS = ["Cut it tighter", "Bigger captions", "Warmer colour", "Less zooming",
                     "Move captions up", "Fewer words per line", "Keep more pauses"];

/** Turn a settings path into something a creator recognises. */
function plain(path: string) {
  const map: Record<string, string> = {
    "captions.size_pct": "caption size", "captions.anchor": "caption position",
    "captions.fill_hex": "caption colour", "captions.max_words": "words per line",
    "captions.all_caps": "capitals", "emphasis.size_pct": "punch size",
    "trim.aggressiveness": "how much is cut", "trim.max_silence": "pauses",
    "punch.rate": "how often it zooms", "punch.scale_mean": "zoom amount", "grade.strength": "colour",
  };
  return map[path] ?? path.split(".").pop()!;
}

/** Plain words in, a remade edit out. The old version keeps playing meanwhile. */
export function AskTab({ msgs, thinking, busy, onSay }: {
  msgs: Msg[]; thinking: boolean; busy: boolean; onSay: (text: string) => void;
}) {
  const [draft, setDraft] = useState("");
  const log = useRef<HTMLDivElement>(null);
  useEffect(() => { log.current?.scrollTo({ top: 1e6, behavior: "smooth" }); }, [msgs, thinking]);
  const say = (text: string) => { if (text.trim() && !busy) { onSay(text.trim()); setDraft(""); } };

  return (
    <>
      <div className={s.chatLog} ref={log}>
        {msgs.map((m, i) => (
          <div key={i} className={`${s.msg} ${m.who === "me" ? s.me : ""}`}>
            {m.who === "bot" && <span className={s.av}><Mark size={16} /></span>}
            <span>
              <span className={s.bub} style={{ display: "inline-block" }}>{m.text}</span>
              {m.changed && m.changed.length > 0 && (
                <span className={s.did}>{m.changed.map(c => <span key={c}>{plain(c)}</span>)}</span>
              )}
            </span>
          </div>
        ))}
        {thinking && (
          <div className={s.msg}>
            <span className={s.av}><Mark size={16} /></span>
            <span className={`${s.bub} ${s.dots}`}><i /><i /><i /></span>
          </div>
        )}
      </div>
      <div className={s.askFoot}>
        <div className={s.suggest}>
          {SUGGESTIONS.map(t => <button key={t} disabled={busy} onClick={() => say(t)}>{t}</button>)}
        </div>
        <div className={s.composer}>
          <textarea rows={1} placeholder={busy ? "Wait for this change to land…" : "Tell me what to change…"}
            value={draft} onChange={e => setDraft(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); say(draft); } }} />
          <button className={s.send} aria-label="Send" disabled={!draft.trim() || busy} onClick={() => say(draft)}>
            <Up size={18} />
          </button>
        </div>
      </div>
    </>
  );
}

// ---- you --------------------------------------------------------------------

const MODES = [
  { id: "off", label: "As styled", note: "Captions sit where the look puts them." },
  { id: "around", label: "Around you", note: "Kept off your face and body." },
  { id: "behind", label: "Behind you", note: "Key words tuck behind your head." },
];
// Two neutrals, then a few saturated plates that sit well behind skin.
const BACKDROPS = ["#111111", "#F4F1EA", "#1E3A8A", "#B91C1C", "#15803D", "#F5B700"];

/** How the captions treat you, and what stands behind you. Both are renders
 *  over the separation made with the edit. */
export function YouTab({ speaker, backdrop, disabled, onSpeaker, onBackdrop }: {
  speaker: string; backdrop: string | null; disabled: boolean;
  onSpeaker: (mode: string) => void; onBackdrop: (hex: string | null) => void;
}) {
  // A colour picker reports every step of a drag; the native change event
  // fires once, when it closes, which is when a render should start.
  const picker = useRef<HTMLInputElement>(null);
  const latest = useRef(onBackdrop);
  useEffect(() => { latest.current = onBackdrop; }, [onBackdrop]);
  useEffect(() => {
    const input = picker.current;
    if (!input) return;
    const picked = () => latest.current(input.value);
    input.addEventListener("change", picked);
    return () => input.removeEventListener("change", picked);
  }, []);
  const custom = backdrop !== null && !BACKDROPS.some(c => c.toLowerCase() === backdrop.toLowerCase());

  return (
    <>
      <div className={s.group}>
        <span className={s.groupLabel}>Captions and you</span>
        <div className={s.seg}>
          {MODES.map(m => (
            <button key={m.id} aria-pressed={speaker === m.id} disabled={disabled}
                    onClick={() => m.id !== speaker && onSpeaker(m.id)}>{m.label}</button>
          ))}
        </div>
        <p className={s.note}>{MODES.find(m => m.id === speaker)?.note}</p>
      </div>
      <div className={s.group}>
        <span className={s.groupLabel}>Background</span>
        <div className={s.swatches}>
          <button className={`${s.swatch} ${s.asShot}`} aria-pressed={backdrop === null} aria-label="As shot"
                  title="As shot" disabled={disabled} onClick={() => backdrop !== null && onBackdrop(null)} />
          {BACKDROPS.map(c => (
            <button key={c} className={s.swatch} style={{ background: c }} aria-label={c} title={c} disabled={disabled}
                    aria-pressed={backdrop?.toLowerCase() === c.toLowerCase()}
                    onClick={() => backdrop?.toLowerCase() !== c.toLowerCase() && onBackdrop(c)} />
          ))}
          <label className={`${s.swatch} ${s.custom}`} title="Any colour" aria-pressed={custom}
                 style={custom ? { background: backdrop! } : undefined}>
            <input ref={picker} type="color" aria-label="Any colour" disabled={disabled} defaultValue={backdrop ?? "#ffffff"} />
          </label>
        </div>
        <p className={s.note}>{backdrop ? "Everything behind you becomes this colour." : "Your own background, as shot."}</p>
      </div>
    </>
  );
}

// ---- music ------------------------------------------------------------------

/** A bed under the speech. It ducks whenever you talk. */
export function MusicTab({ track, disabled, onFile, onRemove }: {
  track: string; disabled: boolean; onFile: (file: File) => void; onRemove: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  return (
    <div className={s.group}>
      <span className={s.groupLabel}>Music</span>
      <input ref={input} type="file" accept="audio/*" hidden
             onChange={e => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
      {track ? (
        <div className={s.track}>
          <span className={s.trackIcon}><Music /></span>
          <span><b>{track}</b><small>Ducks under your voice</small></span>
          <button className={s.smallBtn} disabled={disabled} onClick={onRemove}>Remove</button>
        </div>
      ) : (
        <button className={s.drop} disabled={disabled} onClick={() => input.current?.click()}>
          <Music />
          <b>Add a track</b>
          <span>It ducks under your voice on its own</span>
        </button>
      )}
    </div>
  );
}
