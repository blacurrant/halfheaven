"use client";

/** The waitlist form. It asks one thing beyond an email - what someone spends
 *  on editing today - because that answer is the demand evidence a launch (or
 *  a pitch) needs, and it costs the visitor one tap. */

import { useState, type FormEvent } from "react";

import s from "@/app/landing.module.css";

const ROLES = [
  ["creator", "A creator"],
  ["editor", "An editor or agency"],
  ["brand", "A brand or business"],
] as const;

const SPEND = [
  ["self", "Nothing, I edit myself"],
  ["under-5k", "Under ₹5,000"],
  ["5-15k", "₹5,000 – 15,000"],
  ["15-30k", "₹15,000 – 30,000"],
  ["30k-plus", "More than ₹30,000"],
] as const;

const FAILED = "That didn’t go through. Try again?";

const Tick = ({ size = 22 }: { size?: number }) => (
  <svg viewBox="0 0 16 16" width={size} height={size} aria-hidden>
    <path d="M3.5 8.5l3 3 6-7" fill="none" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

export default function Waitlist() {
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");
  const [error, setError] = useState("");
  const [already, setAlready] = useState(false);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fields = Object.fromEntries(new FormData(e.currentTarget));
    setState("sending");
    setError("");
    try {
      const r = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(fields),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { setError(d.error ?? FAILED); setState("error"); return; }
      setAlready(Boolean(d.already));
      setState("done");
    } catch {
      // a network failure's own message ("Failed to fetch") means nothing to anyone
      setError(FAILED);
      setState("error");
    }
  };

  if (state === "done") {
    return (
      <div className={`${s.form} ${s.done}`} role="status">
        <span className={s.doneIcon}><Tick /></span>
        <p className={s.formTitle}>{already ? "You’re already on the list." : "You’re on the list."}</p>
        <p className={s.formFine}>We’ll email you when your spot opens, with your early-access price locked in.</p>
      </div>
    );
  }

  return (
    <form className={s.form} onSubmit={submit}>
      <p className={s.formTitle}>Join the waitlist</p>
      <label className={s.field}>
        <span>Email</span>
        <input name="email" type="email" required autoComplete="email" placeholder="you@example.com" />
      </label>
      <label className={s.field}>
        <span>Instagram or YouTube handle <em>(optional)</em></span>
        <input name="handle" autoComplete="off" placeholder="@yourhandle" />
      </label>
      <div className={s.row2}>
        <label className={s.field}>
          <span>I’m</span>
          <select name="role" defaultValue="creator">
            {ROLES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
          </select>
        </label>
        <label className={s.field}>
          <span>Monthly editing spend</span>
          <select name="spend" defaultValue="" required>
            <option value="" disabled>Choose one</option>
            {SPEND.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
          </select>
        </label>
      </div>
      {state === "error" && <p className={s.err} role="alert">{error}</p>}
      <button className={`btn primary ${s.full}`} disabled={state === "sending"}>
        {state === "sending" ? "Adding you…" : "Join the waitlist"}
      </button>
      <p className={s.formFine}>No spam. One email when your spot opens.</p>
    </form>
  );
}
