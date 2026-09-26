/**
 * Draws one layout spec. Every length is a percent of the frame, and text is
 * sized in `cqw` (the frame is a size container), so a 120px thumbnail and a
 * full preview are the same drawing at two scales.
 */

import type { CSSProperties, ReactNode } from "react";

import { type Block, type Copy, fitScale, type Layout, RATIO, wordsOf } from "@/lib/layouts";

import s from "./layouts.module.css";

const ROUND = new Set(["avatar", "icon", "mark", "knob", "qr", "burst"]);

export default function Wireframe({ layout, copy, className }: { layout: Layout; copy: Copy; className?: string }) {
  const leaders = layout.blocks.filter((b) => b.k === "leader");
  return (
    <div className={`${s.frame} ${className ?? ""}`} style={{ aspectRatio: RATIO[layout.format] }}>
      {layout.blocks.map((b, i) => (b.k === "leader" ? null : <Piece key={i} b={b} copy={copy} />))}
      {leaders.length > 0 && (
        <svg className={s.leaders} viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
          {leaders.map((b, i) => (
            <line key={i} x1={b.x} y1={b.y} x2={b.x2} y2={b.y2} vectorEffect="non-scaling-stroke" />
          ))}
        </svg>
      )}
      {leaders.map((b, i) => (
        <i key={i} className={s.leaderDot} style={{ left: `${b.x2}%`, top: `${b.y2}%` }} />
      ))}
    </div>
  );
}

function place(b: Block): CSSProperties {
  const st: CSSProperties = { left: `${b.x}%`, top: `${b.y}%`, width: `${b.w}%` };
  if (ROUND.has(b.k)) st.aspectRatio = 1;
  else if (b.h !== undefined && b.k !== "bubble") st.height = `${b.h}%`;
  if (b.r !== undefined) st.borderRadius = `${b.r}cqw`;
  return st;
}

function type(b: Block, copy?: Copy): CSSProperties {
  let size = b.s ?? 3;
  // Copy longer than the block holds shrinks until it wraps into its lines,
  // rather than being cut. A masthead may shrink furthest.
  const w = copy && !b.t ? wordsOf(b, copy) : null;
  if (w) size *= fitScale(b, w.text);
  return {
    fontSize: `${size}cqw`,
    fontWeight: b.wt,
    textAlign: b.a === "c" ? "center" : b.a === "r" ? "right" : "left",
    lineHeight: size >= 5 ? 1.08 : 1.28,
    letterSpacing: b.ls !== undefined ? `${b.ls}em` : undefined,
  };
}

const tone = (b: Block) =>
  [
    b.c === 2 ? s.ink2 : b.c === 3 ? s.ink3 : b.c === "dark" ? s.inkDark : "",
    b.serif ? s.serif : "", b.mono ? s.mono : "", b.caps ? s.caps : "", b.strike ? s.strike : "",
  ].join(" ");

/** Skeleton bars standing in for text that hasn't been written yet. */
function Bars({ b, n, strong }: { b: Block; n: number; strong?: boolean }) {
  const size = b.s ?? 3;
  const widths = n === 1 ? [72] : Array.from({ length: n }, (_, i) => (i === n - 1 ? 58 : 100 - i * 6));
  return (
    <span className={s.bars} style={{ gap: `${size * 0.42}cqw`, alignItems: b.a === "c" ? "center" : b.a === "r" ? "flex-end" : "flex-start" }}>
      {widths.map((w, i) => (
        <i key={i} className={strong ? s.barStrong : s.bar} style={{ width: `${w}%`, height: `${size * 0.58}cqw` }} />
      ))}
    </span>
  );
}

function Words({ b, copy, strong }: { b: Block; copy: Copy; strong?: boolean }) {
  const w = wordsOf(b, copy);
  if (!w) return <Bars b={b} n={b.n ?? 1} strong={strong ?? (b.wt ?? 400) >= 600} />;
  const clamp: CSSProperties = b.n ? { WebkitLineClamp: b.n } : {};
  return (
    <span key={w.text} className={`${s.words} ${b.n ? s.clamp : ""} ${w.placeholder ? s.ph : s.fresh}`} style={clamp}>
      {b.cap ? <span className={s.cap}>{w.text}</span> : w.text}
    </span>
  );
}

function Piece({ b, copy }: { b: Block; copy: Copy }) {
  const st = place(b);
  switch (b.k) {
    case "img":
      return (
        <div className={`${s.img} ${b.v ? s[`img_${b.v}`] : ""}`} style={st}>
          <svg className={s.cross} viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
            <line x1="0" y1="0" x2="100" y2="100" vectorEffect="non-scaling-stroke" />
            <line x1="100" y1="0" x2="0" y2="100" vectorEffect="non-scaling-stroke" />
          </svg>
          {b.label && (
            <span className={s.imgLabel}>
              <Glyph name="image" />
              {b.label}
            </span>
          )}
        </div>
      );
    case "scrim":
      return <div className={s.scrim} style={st} />;
    case "box":
      return <div className={`${s.box} ${s[`box_${b.v ?? "card"}`]}`} style={st} />;
    case "rule":
      return <div className={`${s.rule} ${b.v === "light" ? s.ruleLight : ""}`} style={st} />;
    case "text":
      return (
        <div className={`${s.text} ${b.mid ? s.mid : ""} ${tone(b)}`} style={{ ...st, ...type(b, copy) }}>
          <Words b={b} copy={copy} />
        </div>
      );
    case "link":
      return (
        <div className={`${s.text} ${s.link} ${tone(b)}`} style={{ ...st, ...type(b, copy) }}>
          <Words b={b} copy={copy} />
        </div>
      );
    case "btn":
      return (
        <div className={`${s.btn} ${b.v === "outline" ? s.btnOutline : ""} ${tone(b)}`} style={{ ...st, ...type(b, copy), textAlign: "center" }}>
          <Words b={{ ...b, n: 1, a: "c" }} copy={copy} strong />
        </div>
      );
    case "chip":
      return (
        <div className={`${s.chip} ${s[`chip_${b.v ?? "glass"}`]} ${tone(b)}`} style={{ ...st, ...type(b, copy) }}>
          <Words b={{ ...b, n: 1, a: "c" }} copy={copy} />
        </div>
      );
    case "logo": {
      const w = wordsOf(b, copy);
      return (
        <div className={`${s.logo} ${w ? "" : s.logoEmpty}`} style={{ ...st, fontSize: `${b.s ?? 2.8}cqw` }}>
          <span className={w ? s.fresh : ""} key={w?.text}>{w?.text ?? "LOGO"}</span>
        </div>
      );
    }
    case "burst":
      return (
        <div className={s.burst} style={{ ...st, ...type(b) }}>
          <svg viewBox="0 0 100 100" aria-hidden>
            <polygon points={burstPoints()} />
          </svg>
          <span className={s.burstText}><Words b={{ ...b, n: 2, a: "c" }} copy={copy} /></span>
        </div>
      );
    case "stars":
      return (
        <div className={s.stars} style={st}>
          {Array.from({ length: 5 }, (_, i) => <Glyph key={i} name="star" />)}
        </div>
      );
    case "avatar":
      return (
        <div className={s.avatar} style={st}>
          <Glyph name="person" />
        </div>
      );
    case "icon": {
      const [name, solid] = (b.v ?? "dot").split("-");
      return (
        <div className={`${s.icon} ${solid ? s.iconSolid : ""}`} style={st}>
          <Glyph name={name} />
        </div>
      );
    }
    case "mark":
      return (
        <div className={`${s.mark} ${s[`mark_${b.v ?? "outline"}`]}`} style={{ ...st, ...type(b) }}>
          {b.v === "check" ? <Glyph name="check" /> : b.v === "cross" ? <Glyph name="cross" /> : b.t}
        </div>
      );
    case "knob":
      return (
        <div className={s.knob} style={st}>
          <Glyph name="swap" />
        </div>
      );
    case "timer":
      return (
        <div className={s.timer} style={st}>
          {[["02", "DAYS"], ["14", "HRS"], ["36", "MIN"], ["09", "SEC"]].map(([v, l]) => (
            <div key={l} className={s.timerCell}>
              <b style={{ fontSize: `${b.s ?? 9}cqw` }}>{v}</b>
              <small style={{ fontSize: `${(b.s ?? 9) * 0.26}cqw` }}>{l}</small>
            </div>
          ))}
        </div>
      );
    case "dots":
      return (
        <div className={s.dots} style={st}>
          {Array.from({ length: 5 }, (_, i) => <i key={i} className={i === 0 ? s.dotOn : ""} />)}
        </div>
      );
    case "progress":
      return (
        <div className={s.progress} style={st}>
          {Array.from({ length: 4 }, (_, i) => <i key={i} className={i === 0 ? s.progressOn : ""} />)}
        </div>
      );
    case "bars":
      return (
        <div className={s.chart} style={st}>
          {[28, 40, 34, 55, 68, 92].map((h, i) => <i key={i} className={i === 5 ? s.chartOn : ""} style={{ height: `${h}%` }} />)}
        </div>
      );
    case "qr":
      return (
        <div className={s.qr} style={st}>
          <svg viewBox="0 0 25 25" shapeRendering="crispEdges" aria-hidden>{QR}</svg>
        </div>
      );
    case "barcode":
      return (
        <div className={s.barcode} style={st}>
          <svg viewBox="0 0 100 60" preserveAspectRatio="none" aria-hidden>{BARCODE}</svg>
        </div>
      );
    case "phone":
      return (
        <div className={s.phone} style={st}>
          <i className={s.notch} />
          <div className={s.screen}>
            <i className={s.scrTop} />
            <i className={s.scrHero} />
            {[0, 1, 2].map((i) => (
              <span key={i} className={s.scrRow}>
                <i /><i /><i />
              </span>
            ))}
            <i className={s.scrTab} />
          </div>
        </div>
      );
    case "bubble": {
      // Written bubbles shrink to their words like a real chat; empty ones hold their width.
      const sized = wordsOf(b, copy) ? { width: undefined, maxWidth: `${b.w}%` } : {};
      const side = b.v === "me" ? { left: undefined, right: `${100 - b.x - b.w}%` } : {};
      return (
        <div className={`${s.bubble} ${b.v === "me" ? s.bubbleMe : ""}`} style={{ ...st, ...type(b), ...sized, ...side }}>
          <Words b={b} copy={copy} />
        </div>
      );
    }
    default:
      return null;
  }
}

function burstPoints() {
  const pts: string[] = [];
  for (let i = 0; i < 24; i++) {
    const r = i % 2 ? 41 : 50, a = (Math.PI * 2 * i) / 24 - Math.PI / 2;
    pts.push(`${(50 + r * Math.cos(a)).toFixed(2)},${(50 + r * Math.sin(a)).toFixed(2)}`);
  }
  return pts.join(" ");
}

// A fixed pattern that reads as a QR code at a glance: three finders, seeded noise.
const QR: ReactNode = (() => {
  const cells: ReactNode[] = [];
  const finder = (x: number, y: number) => {
    cells.push(<rect key={`f${x}${y}`} x={x} y={y} width="7" height="7" />);
    cells.push(<rect key={`g${x}${y}`} x={x + 1} y={y + 1} width="5" height="5" fill="var(--wf-light)" />);
    cells.push(<rect key={`h${x}${y}`} x={x + 2} y={y + 2} width="3" height="3" />);
  };
  finder(0, 0); finder(18, 0); finder(0, 18);
  let seed = 7;
  for (let y = 0; y < 25; y++) for (let x = 0; x < 25; x++) {
    if ((x < 8 && y < 8) || (x > 16 && y < 8) || (x < 8 && y > 16)) continue;
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    if (seed % 5 < 2) cells.push(<rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" />);
  }
  return cells;
})();

const BARCODE: ReactNode = (() => {
  const bars: ReactNode[] = [];
  let x = 4, seed = 3;
  while (x < 96) {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    const w = 0.8 + (seed % 3) * 0.9;
    bars.push(<rect key={x} x={x} y="4" width={w} height={52} />);
    x += w + 0.9 + ((seed >> 4) % 3) * 0.8;
  }
  return bars;
})();

function Glyph({ name }: { name: string }) {
  const p = { fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  switch (name) {
    case "star":
      return <svg viewBox="0 0 24 24" aria-hidden><path fill="currentColor" d="M12 2.8l2.8 5.9 6.4.8-4.7 4.4 1.2 6.4L12 17.2l-5.7 3.1 1.2-6.4L2.8 9.5l6.4-.8z" /></svg>;
    case "person":
      return <svg viewBox="0 0 24 24" aria-hidden><circle cx="12" cy="9" r="4" fill="currentColor" /><path fill="currentColor" d="M3.5 22c.8-4.6 4.2-7.2 8.5-7.2s7.7 2.6 8.5 7.2z" /></svg>;
    case "image":
      return <svg viewBox="0 0 24 24" aria-hidden {...p}><rect x="3" y="4" width="18" height="16" rx="2.5" /><circle cx="9" cy="10" r="1.8" /><path d="M21 16l-5-5-8.5 9" /></svg>;
    case "check":
      return <svg viewBox="0 0 24 24" aria-hidden {...p} strokeWidth={3}><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>;
    case "cross":
      return <svg viewBox="0 0 24 24" aria-hidden {...p} strokeWidth={2.6}><path d="M7 7l10 10M17 7L7 17" /></svg>;
    case "swap":
      return <svg viewBox="0 0 24 24" aria-hidden {...p} strokeWidth={2.4}><path d="M9 7l-5 5 5 5M15 7l5 5-5 5" /></svg>;
    case "heart":
      return <svg viewBox="0 0 24 24" aria-hidden {...p}><path d="M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.2a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z" /></svg>;
    case "chat":
      return <svg viewBox="0 0 24 24" aria-hidden {...p}><path d="M20 12a8 8 0 0 1-11.6 7.1L4 20l1-4.1A8 8 0 1 1 20 12z" /></svg>;
    case "send":
      return <svg viewBox="0 0 24 24" aria-hidden {...p}><path d="M21 3L10 14M21 3l-7 18-4-7-7-4z" /></svg>;
    case "clock":
      return <svg viewBox="0 0 24 24" aria-hidden {...p}><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3 2" /></svg>;
    case "pin":
      return <svg viewBox="0 0 24 24" aria-hidden {...p}><path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z" /><circle cx="12" cy="10" r="2.3" /></svg>;
    case "bed":
      return <svg viewBox="0 0 24 24" aria-hidden {...p}><path d="M3 18V7M3 14h18v4M21 14v-2.5a3 3 0 0 0-3-3h-7v5.5" /><circle cx="7" cy="11" r="1.6" /></svg>;
    case "bath":
      return <svg viewBox="0 0 24 24" aria-hidden {...p}><path d="M3 12h18v2a5 5 0 0 1-5 5H8a5 5 0 0 1-5-5zM6 12V6a2 2 0 0 1 4 0" /></svg>;
    case "area":
      return <svg viewBox="0 0 24 24" aria-hidden {...p}><path d="M4 9V4h5M20 15v5h-5M4 4l6 6M20 20l-6-6" /></svg>;
    case "arrow":
      return <svg viewBox="0 0 24 24" aria-hidden {...p} strokeWidth={2.4}><path d="M5 12h14M13 6l6 6-6 6" /></svg>;
    default:
      return <svg viewBox="0 0 24 24" aria-hidden><circle cx="12" cy="12" r="3" fill="currentColor" /></svg>;
  }
}
