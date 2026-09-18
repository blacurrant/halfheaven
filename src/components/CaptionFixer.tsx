"use client";

import { useEffect, useState } from "react";

type Card = { index: number; t: number; duration: number; words: string[]; emphasis: number[] };
type Edit = { index: number; text?: string; emphasis?: number[]; delete?: boolean };

const clock = (s: number) =>
  `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

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
    return <div className="p-5 py-5 text-[13.5px] text-[var(--muted)] text-center">The captions show up here once the edit is ready.</div>;
  }

  return (
    <>
      <div className="overflow-y-auto p-3 flex flex-col gap-1.5">
        {cards.map(c => {
          const words = wordsOf(c);
          const emph = emphOf(c);
          const gone = edits[c.index]?.delete;
          const touched = !!edits[c.index];
          return (
            <div key={c.index} className={`border rounded-[10px] p-2 pt-2 pb-2.5 bg-[var(--card)] ${touched ? "border-[var(--accent-ink)]" : "border-[var(--line)]"} ${gone ? "opacity-40" : ""}`}>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[11.5px] text-[var(--faint)] tabular-nums">{clock(c.t)}</span>
                <span className="ml-auto flex gap-2">
                  <button className="text-[11.5px] font-semibold text-[var(--faint)] hover:text-[var(--accent-ink)]" onClick={() => { setEditing(c.index); setDraft(words.join(" ")); }}>
                    Fix words
                  </button>
                  <button className="text-[11.5px] font-semibold text-[var(--faint)] hover:text-[var(--accent-ink)]" onClick={() => patch(c.index, { delete: !gone })}>
                    {gone ? "Keep" : "Remove"}
                  </button>
                </span>
              </div>

              {editing === c.index ? (
                <input className="w-full border-[1.5px] border-[var(--accent-ink)] rounded-[7px] bg-[var(--sunk)] py-1.5 px-2 text-[13.5px] outline-none" autoFocus value={draft}
                  onChange={e => setDraft(e.target.value)}
                  onBlur={() => commitText(c)}
                  onKeyDown={e => {
                    if (e.key === "Enter") commitText(c);
                    if (e.key === "Escape") setEditing(null);
                  }} />
              ) : (
                <div className={`flex flex-wrap gap-1 ${gone ? "line-through opacity-60" : ""}`}>
                  {words.map((w, i) => (
                    <button key={i} className={`py-0.5 px-1.5 rounded-md text-[13px] transition-colors ${emph.includes(i) ? "bg-[var(--accent)] text-[var(--on-accent)] font-bold" : "bg-[var(--sunk)] text-[var(--ink)] hover:bg-[var(--raised)]"}`}
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

      <div className="border-t border-[var(--line)] py-2.5 px-3 flex items-center gap-2">
        <span className="text-xs text-[var(--muted)]">
          {changed ? `${changed} card${changed > 1 ? "s" : ""} changed` : "Tap a word to make it pop"}
        </span>
        {error && <span className="text-xs text-[var(--bad)]">{error}</span>}
        <button className="ml-auto h-8 px-[13px] text-[13.5px] inline-flex items-center gap-1.5 rounded-full font-semibold bg-[var(--accent)] border border-[var(--accent)] text-[var(--on-accent)] disabled:opacity-50" disabled={!changed || busy} onClick={apply}>
          {busy ? "Re-rendering…" : "Apply fixes"}
        </button>
      </div>
    </>
  );
}
