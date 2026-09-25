"use client";

import { useEffect } from "react";

import { Check, Close, Undo } from "./icons";
import s from "./studio.module.css";

export type Note = { n: number; text: string; bad?: boolean; undo?: boolean };

const LIFE_MS = 6000;

/** What just happened, and the way back. It drains away on its own. */
export default function Toast({ note, overSheet, onUndo, onGone }: {
  note: Note | null; overSheet: boolean; onUndo: () => void; onGone: () => void;
}) {
  useEffect(() => {
    if (!note) return;
    const t = window.setTimeout(onGone, LIFE_MS);
    return () => window.clearTimeout(t);
    // each note lives for its own six seconds
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [note?.n]);
  if (!note) return null;
  return (
    <div className={`${s.toastWrap} ${overSheet ? s.overSheet : ""}`} role="status" aria-live="polite">
      <div key={note.n} className={`${s.toast} ${note.bad ? s.bad : ""}`}>
        {note.bad ? <Close size={18} /> : <Check size={18} />}
        <span>{note.text}</span>
        {note.undo && <button className={s.undo} onClick={onUndo}><Undo size={16} />Undo</button>}
        <span className={s.drain} />
      </div>
    </div>
  );
}
