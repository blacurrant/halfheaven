"use client";

import { useRef, useState } from "react";

import { Check, Download, Share } from "./icons";
import s from "./studio.module.css";

type State = { at: "idle" } | { at: "saving"; got: number } | { at: "share" } | { at: "saved" } | { at: "failed" };

/**
 * Save the edit, with the real download progress rather than a spinner.
 *
 * On a phone that can share files, the finished file opens the phone's own
 * share sheet instead, so the edit goes straight to wherever it gets posted.
 * Sharing needs a fresh tap (browsers only share inside a user gesture), so
 * the button turns into "Share" once the file is in hand.
 *
 * Keyed on the version by its parent: a new version is a new file.
 */
export default function SaveButton({ src, name }: { src: string; name: string }) {
  const [state, setState] = useState<State>({ at: "idle" });
  const file = useRef<File | null>(null);

  const download = (f: File) => {
    const url = URL.createObjectURL(f);
    const a = Object.assign(document.createElement("a"), { href: url, download: f.name });
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 4000);
    setState({ at: "saved" });
    window.setTimeout(() => setState(st => (st.at === "saved" ? { at: "idle" } : st)), 2600);
  };

  const canShare = (f: File) => typeof navigator !== "undefined" && !!navigator.canShare?.({ files: [f] });

  const fetchIt = async () => {
    setState({ at: "saving", got: 0 });
    try {
      const res = await fetch(src);
      if (!res.ok || !res.body) throw new Error("not ready");
      const total = Number(res.headers.get("content-length") || 0);
      const reader = res.body.getReader();
      const parts: BlobPart[] = [];
      let got = 0;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        parts.push(value);
        got += value.length;
        if (total) setState({ at: "saving", got: got / total });
      }
      const f = new File(parts, name, { type: "video/mp4" });
      file.current = f;
      if (canShare(f)) setState({ at: "share" }); else download(f);
    } catch {
      setState({ at: "failed" });
    }
  };

  const click = async () => {
    if (state.at === "saving") return;
    const f = file.current;
    if (state.at === "share" && f) {
      try { await navigator.share({ files: [f], title: "My edit" }); }
      catch { /* dismissed: the button stays ready to share */ }
      return;
    }
    if (f) { if (canShare(f)) setState({ at: "share" }); else download(f); return; }
    fetchIt();
  };

  const progress = state.at === "saving" ? state.got : state.at === "idle" || state.at === "failed" ? 0 : 1;
  return (
    <button className={s.primary} onClick={click} aria-busy={state.at === "saving"}>
      <span className={s.fill} style={{ transform: `scaleX(${progress})` }} />
      <span>
        {state.at === "saving" ? <>Saving… <span className={s.mono}>{Math.round(state.got * 100)}%</span></>
          : state.at === "share" ? <><Share size={18} />Share or save</>
          : state.at === "saved" ? <><Check size={18} />Saved</>
          : state.at === "failed" ? "Try again"
          : <><Download size={18} />Save video</>}
      </span>
    </button>
  );
}
