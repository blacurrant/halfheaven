"use client";

import { useEffect, useState } from "react";

type Card = { index: number; t: number; duration: number; words: string[]; emphasis: number[] };
type Edit = { index: number; text?: string; emphasis?: number[]; delete?: boolean };

const clock = (s: number) =>
  `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** Fixing what the machine misheard.
 *  A wrong word is the most visible flaw an auto-caption has, so this is the
 *  first thing a creator reaches for. Applying edits re-renders only - the
 *  transcript is never regenerated, which would undo the correction. */
export default function CaptionFixer({
  jobId, ready, onApplied,
}: { jobId: string; ready: boolean; onApplied: () => void }) {
  const [cards, setCards] = useState<Card[]>([]);
  const [edits, setEdits] = useState<Record<number, Edit>>({});
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!ready) return;
    fetch(`/api/jobs/${jobId}/captions`).then(r => r.json())
      .then(d => { if (d.captions) { setCards(d.captions); setEdits({}); } });
  }, [jobId, ready]);

  const wordsOf = (c: Card) => (edits[c.index]?.text ?? c.words.join(" ")).split(" ").filter(Boolean);
  const emphOf = (c: Card) => edits[c.index]?.emphasis ?? c.emphasis;
  const changed = Object.keys(edits).length;

  const patch = (index: number, next: Partial<Edit>) =>
    setEdits(e => ({ ...e, [index]: { ...e[index], ...next, index } }));

  const toggleWord = (c: Card, i: number) => {
    const on = emphOf(c);
    patch(c.index, { emphasis: on.includes(i) ? on.filter(x => x !== i) : [...on, i].sort((a, b) => a - b) });
  };

  const commitText = (c: Card) => {
    const text = draft.trim();
    setEditing(null);
    if (text && text !== c.words.join(" ")) patch(c.index, { text });
  };

  const apply = async () => {
    setBusy(true); setError("");
    try {
      const r = await fetch(`/api/jobs/${jobId}/captions`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ edits: Object.values(edits) }),
      });
      const d = await r.json();
      if (d.error) setError(d.error);
      else { setEdits({}); onApplied(); }
    } finally { setBusy(false); }
  };

  if (!ready) {
    return <div className="fix-empty">Make an edit first, then you can fix any caption here.</div>;
  }

  return (
    <>
      <div className="cards">
        {cards.map(c => {
          const words = wordsOf(c);
          const emph = emphOf(c);
          const gone = edits[c.index]?.delete;
          const touched = !!edits[c.index];
          return (
            <div key={c.index} className={`card${touched ? " touched" : ""}${gone ? " gone" : ""}`}>
              <div className="card-top">
                <span className="at">{clock(c.t)}</span>
                <span className="card-actions">
                  <button className="ln" onClick={() => { setEditing(c.index); setDraft(words.join(" ")); }}>
                    Fix words
                  </button>
                  <button className="ln" onClick={() => patch(c.index, { delete: !gone })}>
                    {gone ? "Keep" : "Remove"}
                  </button>
                </span>
              </div>

              {editing === c.index ? (
                <input className="fix-input" autoFocus value={draft}
                  onChange={e => setDraft(e.target.value)}
                  onBlur={() => commitText(c)}
                  onKeyDown={e => {
                    if (e.key === "Enter") commitText(c);
                    if (e.key === "Escape") setEditing(null);
                  }} />
              ) : (
                <div className="words">
                  {words.map((w, i) => (
                    <button key={i} className={`w${emph.includes(i) ? " on" : ""}`}
                      title="Tap to make this word pop" onClick={() => toggleWord(c, i)}>
                      {w}
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="fix-foot">
        <span className="tiny">
          {changed ? `${changed} card${changed > 1 ? "s" : ""} changed` : "Tap a word to make it pop"}
        </span>
        {error && <span className="tiny" style={{ color: "var(--accent)" }}>{error}</span>}
        <button className="btn primary sm" disabled={!changed || busy} onClick={apply}>
          {busy ? "Re-rendering…" : "Apply fixes"}
        </button>
      </div>
    </>
  );
}
