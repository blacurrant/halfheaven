"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { Pause, Play } from "./icons";
import s from "./studio.module.css";

type Clip = { start: number; end: number };
type Layer = { key: number; src: string; start: number };

const WIPE_MS = 950;
const HOLD_MS = 180;
const EASE = "cubic-bezier(.65,0,.35,1)";
const quiet = () => typeof window !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

/** One version of the video. An incoming one reports when it can show the
 *  right frame; one that will not load reports anyway, so it still replaces
 *  the version it follows. */
function LayerVideo({ layer, incoming, register, onReady, onTime }: {
  layer: Layer;
  incoming: boolean;
  register: (key: number, video: HTMLVideoElement | null) => void;
  onReady: (key: number, video: HTMLVideoElement) => void;
  onTime?: (video: HTMLVideoElement) => void;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const video = ref.current!;
    register(layer.key, video);
    if (!incoming) return () => register(layer.key, null);
    let done = false;
    const ready = () => { if (!done) { done = true; window.clearTimeout(timer); onReady(layer.key, video); } };
    const loaded = () => {
      const at = Math.min(layer.start, Math.max(0, (video.duration || 0) - 0.05));
      if (at > 0.05 && Math.abs(video.currentTime - at) > 0.05) {
        video.addEventListener("seeked", ready, { once: true });
        video.currentTime = at;
      } else ready();
    };
    const timer = window.setTimeout(ready, 10000);
    if (video.readyState >= 2) loaded();
    else video.addEventListener("loadeddata", loaded, { once: true });
    video.addEventListener("error", ready, { once: true });
    return () => {
      done = true;
      window.clearTimeout(timer);
      video.removeEventListener("loadeddata", loaded);
      video.removeEventListener("seeked", ready);
      video.removeEventListener("error", ready);
      register(layer.key, null);
    };
    // a layer is set up once, for the src it was born with
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <video ref={ref} className={s.video} src={layer.src} autoPlay loop playsInline muted preload="auto"
      onTimeUpdate={onTime ? e => onTime(e.currentTarget) : undefined} />
  );
}

/**
 * The video, and every way it changes.
 *
 * A new `src` never cuts to black: the next version loads underneath, seeks
 * to where the current one is (or to `startAt`), and is wiped in over it from
 * left to right. That one move is how every change lands, from the first
 * reveal to a new caption look.
 *
 * Hold the picture to see the original footage at the same moment; tap it to
 * pause. `reelHeld` shows the reel being copied, for the inset the page owns.
 */
export default function Player({
  src, startAt, muted, original, clips, reference, reelHeld, onTime, onWipeDone, onHeld, seek, children,
}: {
  src: string;
  /** Where a new `src` starts. Left out, it keeps the current playhead. */
  startAt?: number;
  muted: boolean;
  original?: string | null;
  clips?: Clip[];
  reference?: string | null;
  reelHeld?: boolean;
  onTime?: (t: number, duration: number) => void;
  onWipeDone?: () => void;
  onHeld?: () => void;
  seek?: { t: number; n: number };
  children?: React.ReactNode;
}) {
  const [layers, setLayers] = useState<Layer[]>([{ key: 0, src, start: startAt ?? 0 }]);
  const [wiping, setWiping] = useState(false);
  const [held, setHeld] = useState(false);
  const [flash, setFlash] = useState<{ n: number; paused: boolean } | null>(null);
  const frame = useRef<HTMLDivElement>(null);
  const seam = useRef<HTMLSpanElement>(null);
  const shells = useRef(new Map<number, HTMLDivElement>());
  const videos = useRef(new Map<number, HTMLVideoElement>());
  const originalRef = useRef<HTMLVideoElement>(null);
  const pressTimer = useRef<number | null>(null);
  const top = layers[layers.length - 1];
  const topKey = useRef(top.key);
  useEffect(() => { topKey.current = top.key; }, [top.key]);

  // ---- a new version arrives ------------------------------------------------
  useEffect(() => {
    setLayers(current => {
      const last = current[current.length - 1];
      if (last.src === src) return current;
      const start = startAt ?? videos.current.get(last.key)?.currentTime ?? 0;
      return [...current.slice(-1), { key: last.key + 1, src, start }];
    });
    // startAt only means something together with the src it arrives with
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src]);

  const register = useCallback((key: number, video: HTMLVideoElement | null) => {
    if (video) videos.current.set(key, video); else videos.current.delete(key);
  }, []);

  const settle = useCallback((key: number) => {
    setLayers(current => current.filter(l => l.key >= key));
    setWiping(false);
    onWipeDone?.();
  }, [onWipeDone]);

  const wipeIn = useCallback((key: number, video: HTMLVideoElement) => {
    const shell = shells.current.get(key);
    const width = frame.current?.clientWidth ?? 0;
    video.play().catch(() => {});
    if (!shell || !width) { settle(key); return; }
    setWiping(true);
    if (quiet()) {
      shell.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 200, fill: "forwards" }).onfinish = () => settle(key);
      return;
    }
    shell.animate([{ clipPath: "inset(0 100% 0 0)" }, { clipPath: "inset(0 0% 0 0)" }],
      { duration: WIPE_MS, easing: EASE, fill: "forwards" }).onfinish = () => settle(key);
    // the seam is mounted by the same render that set `wiping`
    requestAnimationFrame(() => seam.current?.animate(
      [{ transform: "translateX(0)", opacity: 1 }, { transform: `translateX(${width}px)`, opacity: 1, offset: 0.86 },
       { transform: `translateX(${width}px)`, opacity: 0 }],
      { duration: WIPE_MS + 160, easing: EASE, fill: "forwards" }));
  }, [settle]);

  // Only the settled top layer is heard; an incoming one is silent until it has landed.
  useEffect(() => {
    videos.current.forEach((video, key) => { video.muted = muted || key !== top.key || wiping; });
  }, [muted, top.key, wiping, layers]);

  useEffect(() => {
    if (!seek) return;
    const video = videos.current.get(topKey.current);
    if (video) video.currentTime = seek.t;
  }, [seek]);

  // ---- hold to compare, tap to pause -------------------------------------------
  /** Program time back to source time: the cut runs ahead of the footage. */
  const sourceTime = (t: number) => {
    if (!clips?.length) return t;
    let at = 0;
    for (const c of clips) {
      const d = c.end - c.start;
      if (t < at + d) return c.start + (t - at);
      at += d;
    }
    return clips[clips.length - 1].end;
  };

  const down = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    pressTimer.current = window.setTimeout(() => {
      pressTimer.current = null;
      const o = originalRef.current, v = videos.current.get(topKey.current);
      if (!original || !o || !v) return;
      o.currentTime = sourceTime(v.currentTime);
      o.play().catch(() => {});
      setHeld(true);
      onHeld?.();
    }, HOLD_MS);
  };
  const up = () => {
    if (pressTimer.current !== null) {
      window.clearTimeout(pressTimer.current);
      pressTimer.current = null;
      const v = videos.current.get(topKey.current);
      if (!v) return;
      if (v.paused) v.play().catch(() => {}); else v.pause();
      setFlash(f => ({ n: (f?.n ?? 0) + 1, paused: v.paused }));
      return;
    }
    if (held) { originalRef.current?.pause(); setHeld(false); }
  };
  const cancel = () => {
    if (pressTimer.current !== null) { window.clearTimeout(pressTimer.current); pressTimer.current = null; }
    if (held) { originalRef.current?.pause(); setHeld(false); }
  };

  return (
    <div className={s.frame} ref={frame}>
      {layers.map((layer, i) => (
        <div key={layer.key} className={s.video}
             ref={el => { if (el) shells.current.set(layer.key, el); else shells.current.delete(layer.key); }}
             style={i > 0 && !quiet() ? { clipPath: "inset(0 100% 0 0)" } : i > 0 ? { opacity: 0 } : undefined}>
          <LayerVideo layer={layer} incoming={layer.key > 0 && i > 0} register={register} onReady={wipeIn}
            onTime={i === layers.length - 1 ? v => onTime?.(v.currentTime, v.duration || 0) : undefined} />
        </div>
      ))}
      {original && (
        <video ref={originalRef} className={`${s.video} ${held ? "" : s.hidden}`} src={original}
               muted playsInline preload="auto" style={{ zIndex: 1 }} />
      )}
      {reference && reelHeld && (
        <video className={s.video} src={reference} muted playsInline autoPlay loop style={{ zIndex: 1 }} />
      )}
      {wiping && <span ref={seam} className={s.seam} />}
      <div className={s.press} onPointerDown={down} onPointerUp={up} onPointerCancel={cancel}
           onContextMenu={e => e.preventDefault()} />
      {held && <div className={s.tag}><span>Your original</span></div>}
      {reelHeld && <div className={s.tag}><span>The reel you love</span></div>}
      {flash && (
        <span key={flash.n} className={s.flash} aria-hidden>
          {flash.paused ? <Pause size={24} /> : <Play size={24} />}
        </span>
      )}
      {children}
    </div>
  );
}
