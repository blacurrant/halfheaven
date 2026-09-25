"use client";

import { useEffect } from "react";

import Readout from "@/components/Readout";
import Scorecard from "@/components/Scorecard";
import type { Fingerprint } from "@/lib/fingerprint";
import type { Score } from "@/lib/score";

import { Close, Film, Sliders, Undo } from "./icons";
import s from "./studio.module.css";

export type MenuView = "menu" | "read" | "score";

/** The ⋯ sheet: what we read from the reel, how close the edit got, and the
 *  way out. Each is one tap away and none of it sits on the video. */
export default function Menu({
  view, fp, canScore, score, scoring, scoreError, onView, onClose, onStartOver,
}: {
  view: MenuView;
  fp?: Fingerprint;
  canScore: boolean;
  score: Score | null;
  scoring: boolean;
  scoreError: string;
  onView: (view: MenuView) => void;
  onClose: () => void;
  onStartOver: () => void;
}) {
  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);

  return (
    <>
      <div className={s.scrim} onClick={onClose} />
      <div className={s.menu} role="dialog" aria-modal="true"
           aria-label={view === "read" ? "What we read" : view === "score" ? "How close it got" : "More"}>
        <span className={s.handle} />
        {view === "menu" ? (
          <>
            {fp && (
              <button className={s.menuItem} onClick={() => onView("read")}>
                <Film />What we read from the reel
              </button>
            )}
            {canScore && (
              <button className={s.menuItem} onClick={() => onView("score")}>
                <Sliders />How close it got
              </button>
            )}
            <button className={`${s.menuItem} ${s.danger}`} onClick={onStartOver}>
              <Undo />Start over
            </button>
          </>
        ) : (
          <>
            <div className={s.infoHead}>
              <h2>{view === "read" ? "What we read" : "How close it got"}</h2>
              <button className={s.sheetClose} style={{ position: "static" }} aria-label="Close" onClick={onClose}>
                <Close />
              </button>
            </div>
            <div className={s.infoBody}>
              {view === "read" && fp && <Readout fp={fp} />}
              {view === "score" && (
                scoring ? <p className="tiny">Measuring your edit against the reel. This takes a moment.</p>
                  : scoreError ? <p className="tiny" style={{ color: "var(--bad)" }}>{scoreError}</p>
                  : score ? <Scorecard score={score} />
                  : <p className="tiny">Available once the edit is ready.</p>
              )}
            </div>
          </>
        )}
      </div>
    </>
  );
}
