"use client";

import { Close } from "./icons";
import s from "./studio.module.css";

export type Tab = "looks" | "ask" | "type" | "you" | "words" | "music";

const TABS: { id: Tab; label: string }[] = [
  { id: "looks", label: "Looks" },
  { id: "ask", label: "Ask" },
  { id: "type", label: "Type" },
  { id: "you", label: "You" },
  { id: "words", label: "Words" },
  { id: "music", label: "Music" },
];

/** Everything a creator can change, one tab at a time. On a phone it sits
 *  under the video, which shrinks to stay whole above it; on a wide screen it
 *  is a panel beside it. Either way the video keeps playing. */
export default function Sheet({ tab, onTab, onClose, flush, children }: {
  tab: Tab; onTab: (tab: Tab) => void; onClose: () => void; flush?: boolean; children: React.ReactNode;
}) {
  return (
    <section className={s.sheet} aria-label="Edit">
      <div className={s.sheetHead}>
        <span className={s.handle} />
        <div className={s.tabs} role="tablist">
          {TABS.map(t => (
            <button key={t.id} role="tab" className={s.tab} aria-selected={tab === t.id}
                    onClick={() => onTab(t.id)}>{t.label}</button>
          ))}
        </div>
        <button className={s.sheetClose} aria-label="Close" onClick={onClose}><Close /></button>
      </div>
      <div className={`${s.sheetBody} ${flush ? s.flush : ""}`} role="tabpanel">{children}</div>
    </section>
  );
}
