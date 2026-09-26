"use client";

/**
 * Describe an ad; watch the layout choose itself.
 *
 * Two models, two jobs. Jev (TypeSafe's decision model) reads the chat, and
 * whatever is being typed right now, and returns a probability for each of
 * the twenty wireframes: that ranks the rail and picks the preview, on every
 * pause in typing. On send, Jev Router writes the reply and the copy that
 * fills the chosen wireframe's slots.
 *
 * Tapping a wireframe pins it; Jev keeps ranking beside it, and "Let Jev
 * choose" hands the choice back. The chat, copy and pin survive a refresh.
 */

import { type CSSProperties, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import Wireframe from "@/components/layouts/Wireframe";
import s from "@/components/layouts/layouts.module.css";
import { Check, Mark, Undo, Up } from "@/components/studio/icons";
import { BY_ID, type Copy, fieldsOf, LAYOUTS, RATIO, wordsOf } from "@/lib/layouts";
import { forget, recall, remember } from "@/lib/remember";

type Msg = { role: "user" | "assistant"; text: string; meta?: string };
type Pick = { pick: string; confidence: number; probabilities: Record<string, number>; ms: number };
type Saved = { messages: Msg[]; copy: Copy; jev: Pick | null; manual: string | null };

const STORE = "layouts.v1";
const SUGGESTIONS = [
  "Diwali sale on silk sarees, flat 40% off",
  "Launch ad for our budgeting app",
  "Pottery workshop in Bengaluru on Oct 12",
  "Vitamin C serum, visible results in 4 weeks",
];

const pct = (p: number | undefined) => `${Math.round((p ?? 0) * 100)}%`;

export default function LayoutsPage() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [draft, setDraft] = useState("");
  const [copy, setCopy] = useState<Copy>({});
  const [jev, setJev] = useState<Pick | null>(null);
  const [reading, setReading] = useState(false);
  const [jevFailed, setJevFailed] = useState(false);
  const [manual, setManual] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);
  const [copied, setCopied] = useState(false);

  // The latest values, for the async paths (debounced picks, the send) to read
  // without re-arming timers every time one of them changes.
  const live = useRef({ messages, copy, manual });
  useEffect(() => { live.current = { messages, copy, manual }; }, [messages, copy, manual]);

  // Nothing is saved until the saved state has been read back, or the first
  // (empty) render would overwrite it before it loads.
  const [restored, setRestored] = useState(false);
  useEffect(() => {
    const saved = recall<Saved>(STORE);
    /* eslint-disable react-hooks/set-state-in-effect -- storage is only readable after mount */
    if (saved) {
      setMessages(saved.messages ?? []);
      setCopy(saved.copy ?? {});
      setJev(saved.jev ?? null);
      setManual(saved.manual ?? null);
    }
    setRestored(true);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, []);
  useEffect(() => {
    if (restored) remember(STORE, { messages, copy, jev, manual } satisfies Saved);
  }, [restored, messages, copy, jev, manual]);

  // Only the newest Jev request may land: typing fires one per pause, and a
  // slow answer to an older draft must not overwrite a newer one.
  const seq = useRef(0);
  const inflight = useRef<AbortController | null>(null);
  const ask = useCallback(async (msgs: Msg[], typing: string): Promise<Pick | null> => {
    const id = ++seq.current;
    inflight.current?.abort();
    const ctl = new AbortController();
    inflight.current = ctl;
    setReading(true);
    try {
      const res = await fetch("/api/layouts/pick", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: msgs.map(({ role, text }) => ({ role, text })), draft: typing }),
        signal: ctl.signal,
      });
      const data = await res.json();
      if (id !== seq.current) return null;
      if (!res.ok || !BY_ID[data.pick]) { setJevFailed(true); return null; }
      const p: Pick = { pick: data.pick, confidence: data.confidence, probabilities: data.probabilities, ms: data.ms };
      setJev(p);
      setJevFailed(false);
      return p;
    } catch {
      if (id === seq.current && !ctl.signal.aborted) setJevFailed(true);
      return null;
    } finally {
      if (id === seq.current) setReading(false);
    }
  }, []);

  // Realtime: Jev re-reads on every pause in typing.
  useEffect(() => {
    const typing = draft.trim();
    if (typing.length < 3) return;
    const t = setTimeout(() => ask(live.current.messages, typing), 300);
    return () => clearTimeout(t);
  }, [draft, ask]);

  const send = async (raw?: string) => {
    const text = (raw ?? draft).trim();
    if (!text || thinking) return;
    const next: Msg[] = [...live.current.messages, { role: "user", text }];
    setMessages(next);
    setDraft("");
    setThinking(true);
    const p = await ask(next, "");
    const layout = live.current.manual ?? p?.pick ?? jev?.pick ?? LAYOUTS[0].id;
    try {
      const res = await fetch("/api/layouts/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: next.map(({ role, text }) => ({ role, text })), copy: live.current.copy, layout }),
      });
      const data = await res.json();
      setCopy((c) => ({ ...c, ...data.copy }));
      const meta = data.model ? `${data.model} · ${(data.ms / 1000).toFixed(1)}s` : undefined;
      setMessages((m) => [...m, { role: "assistant", text: data.reply, meta }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "I couldn't reach the model just then. Try that again." }]);
    } finally {
      setThinking(false);
    }
  };

  const startOver = () => {
    inflight.current?.abort();
    seq.current++;
    setMessages([]); setDraft(""); setCopy({}); setJev(null); setManual(null); setReading(false); setJevFailed(false);
    forget(STORE);
  };

  const selected = BY_ID[manual ?? jev?.pick ?? ""] ?? LAYOUTS[0];
  const suggestion = manual && jev && jev.pick !== manual ? BY_ID[jev.pick] : null;

  // Ranked by Jev, ties kept in catalogue order so the rail doesn't shuffle on zeros.
  const ranked = useMemo(() => {
    if (!jev) return LAYOUTS;
    return LAYOUTS.map((l, i) => ({ l, i, p: jev.probabilities[l.id] ?? 0 }))
      .sort((a, b) => b.p - a.p || a.i - b.i).map((x) => x.l);
  }, [jev]);
  const order = ranked.map((l) => l.id).join();

  // FLIP: each thumbnail glides from where it was to its new rank.
  const listRef = useRef<HTMLDivElement>(null);
  const items = useRef(new Map<string, HTMLElement>());
  const was = useRef(new Map<string, { x: number; y: number }>());
  useLayoutEffect(() => {
    const now = new Map<string, { x: number; y: number }>();
    items.current.forEach((el, id) => now.set(id, { x: el.offsetLeft, y: el.offsetTop }));
    now.forEach((pos, id) => {
      const before = was.current.get(id);
      const el = items.current.get(id);
      if (!before || !el || (before.x === pos.x && before.y === pos.y)) return;
      el.animate(
        [{ transform: `translate(${before.x - pos.x}px, ${before.y - pos.y}px)` }, { transform: "none" }],
        { duration: 520, easing: "cubic-bezier(.22,1,.36,1)" },
      );
    });
    was.current = now;
  }, [order]);

  // A new top pick scrolls the rail back to it.
  const top = jev?.pick;
  useEffect(() => { if (top) listRef.current?.scrollTo({ top: 0, left: 0, behavior: "smooth" }); }, [top]);

  const copySpec = () => {
    const spec = {
      layout: selected.id, name: selected.name, format: selected.format,
      copy: Object.fromEntries(fieldsOf(selected).filter((f) => copy[f] !== undefined).map((f) => [f, copy[f]])),
      blocks: selected.blocks.map((b) => {
        const w = wordsOf(b, copy);
        return { ...b, ...(w && !w.placeholder ? { text: w.text } : {}) };
      }),
    };
    navigator.clipboard.writeText(JSON.stringify(spec, null, 2)).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    }, () => {});
  };

  const msgsRef = useRef<HTMLDivElement>(null);
  useEffect(() => { msgsRef.current?.scrollTo({ top: msgsRef.current.scrollHeight, behavior: "smooth" }); }, [messages, thinking]);

  const inputRef = useRef<HTMLTextAreaElement>(null);
  const grow = (el: HTMLTextAreaElement) => { el.style.height = "auto"; el.style.height = `${Math.min(el.scrollHeight, 160)}px`; };
  useEffect(() => { if (inputRef.current) grow(inputRef.current); }, [draft]);

  return (
    <main className={s.page}>
      <section className={s.chat} aria-label="Chat">
        <header className={s.head}>
          <div className={s.brand}><Mark size={18} />Layouts<span>by Jev</span></div>
          <button className={s.ghost} onClick={startOver} disabled={!messages.length && !draft}>
            <Undo size={15} />New
          </button>
        </header>

        <div className={s.msgs} ref={msgsRef}>
          {messages.length === 0 ? (
            <div className={s.empty}>
              <h2>Describe the ad you want.</h2>
              <p>Jev picks one of twenty layouts as you type. Send it and the copy gets written into the frame.</p>
              <div className={s.sugs}>
                {SUGGESTIONS.map((q) => (
                  <button key={q} className={s.sug} onClick={() => { setDraft(q); inputRef.current?.focus(); }}>{q}</button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, i) => m.role === "user"
              ? <div key={i} className={s.user}>{m.text}</div>
              : <div key={i} className={s.bot}>{m.text}{m.meta && <small className={s.mono}>{m.meta}</small>}</div>)
          )}
          {thinking && <div className={s.typing} aria-label="Writing"><i /><i /><i /></div>}
        </div>

        <div className={s.composer}>
          <div className={s.field}>
            <textarea
              ref={inputRef}
              rows={1}
              value={draft}
              placeholder={messages.length ? "Change anything…" : "A launch ad for…"}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }}
            />
            <button className={`${s.send} ${draft.trim() && !thinking ? s.ready : ""}`} onClick={() => send()}
                    disabled={!draft.trim() || thinking} aria-label="Send">
              <Up size={18} />
            </button>
          </div>
          <div className={s.jevLine} aria-live="polite">
            <i className={`${s.jevDot} ${reading ? s.live : jev ? s.on : ""}`} />
            {reading ? <span>Jev is reading{draft.trim() ? " as you type" : ""}…</span>
              : jevFailed ? <span>Jev is unavailable right now. Tap a layout to pick by hand.</span>
              : jev ? (
                <span>Jev picked <b>{BY_ID[jev.pick].name}</b> <span className={s.mono}>{pct(jev.probabilities[jev.pick])}</span>
                  <span className={s.faint}> · {jev.ms} ms</span></span>
              ) : <span>Jev picks a layout as you type</span>}
          </div>
        </div>
      </section>

      <section className={s.stage} aria-label="Preview">
        <div className={s.stageBar}>
          <div className={s.title}>
            <h1>{selected.name}</h1>
            <span className={`${s.fmt} ${s.mono}`}>{selected.format}</span>
          </div>
          <div className={s.source}>
            {manual ? (
              <>
                <span className={`${s.pill} ${s.mine}`}>Your pick</span>
                <button className={s.ghost} onClick={() => setManual(null)}>
                  {suggestion ? <>Jev says {suggestion.name}</> : "Let Jev choose"}
                </button>
              </>
            ) : jev ? (
              <span className={s.pill}><i />Jev · {pct(jev.probabilities[selected.id])}</span>
            ) : null}
            <button className={s.ghost} onClick={copySpec}>{copied ? <><Check size={15} />Copied</> : "Copy spec"}</button>
          </div>
        </div>
        <div className={s.canvas} style={{ "--r": RATIO[selected.format] } as CSSProperties}>
          <Wireframe key={selected.id} layout={selected} copy={copy} className={s.preview} />
        </div>
      </section>

      <aside className={s.rail} aria-label="All layouts">
        <div className={s.railHead}>
          <span><b>20 layouts</b></span>
          <span>{jev ? "ranked by Jev" : "tap to pick"}</span>
        </div>
        <div className={s.list} ref={listRef}>
          {ranked.map((l) => {
            const p = jev?.probabilities[l.id] ?? 0;
            const cls = [s.thumb, l.id === selected.id ? s.on : "", jev && l.id === jev.pick ? s.top : "", jev && p < 0.005 ? s.out : ""].join(" ");
            return (
              <button
                key={l.id}
                ref={(el) => { if (el) items.current.set(l.id, el); else items.current.delete(l.id); }}
                className={cls}
                onClick={() => setManual(manual === l.id ? null : l.id)}
                aria-pressed={l.id === selected.id}
              >
                <div className={s.art} style={{ "--r": RATIO[l.format] } as CSSProperties}>
                  <Wireframe layout={l} copy={copy} />
                </div>
                <div className={s.meta}>
                  <span>{l.name}</span>
                  <span className={s.mono}>{jev ? pct(p) : l.format}</span>
                </div>
                {jev && <div className={s.prob}><i style={{ width: pct(p) }} /></div>}
              </button>
            );
          })}
        </div>
      </aside>
    </main>
  );
}
