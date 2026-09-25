"use client";

import { useRef, useState } from "react";

import type { Fingerprint } from "@/lib/fingerprint";
import { about, clock, editSeconds, readChips } from "@/lib/studio";

import { Arrow, Bolt, Check, Mark, Plus } from "./icons";
import s from "./studio.module.css";

type Read = { id: string; status: "running" | "done" | "error"; name: string; error?: string };
type Style = { id: string; name: string };

/** A tile that takes a video by drop or by tap. On a phone, tap opens the
 *  gallery; the picker is cleared after each pick so the same file fires again. */
function Drop({ className, multiple, onFiles, label, children }: {
  className: string; multiple?: boolean; onFiles: (files: File[]) => void; label: string; children: React.ReactNode;
}) {
  const picker = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const take = (list: FileList | null) => { if (list?.length) onFiles(Array.from(list)); };
  return (
    <button type="button" aria-label={label} className={`${className}${over ? " over" : ""}`}
      onClick={() => picker.current?.click()}
      onDragOver={e => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={e => { e.preventDefault(); setOver(false); take(e.dataTransfer.files); }}>
      <input ref={picker} type="file" accept="video/*" multiple={multiple} hidden
             onClick={e => e.stopPropagation()}
             onChange={e => { take(e.target.files); e.target.value = ""; }} />
      {children}
    </button>
  );
}

/**
 * The first screen: the reel you love on the left, your footage on the right,
 * the same picture the landing page draws. Reading the reel starts the moment
 * it lands; what we found appears under the pair as it comes in.
 */
export default function Setup({
  refUrl, read, elapsed, fp, presets, styles, preset, targets, targetUrl, sourceSeconds, queued,
  onReel, onFootage, onPreset, onPresets, onGo, onSeeAll,
}: {
  refUrl: string | null;
  read: Read | null;
  elapsed: number;
  fp?: Fingerprint;
  presets: boolean;
  styles: Style[];
  preset: Style | null;
  targets: File[];
  targetUrl: string | null;
  sourceSeconds: number | null;
  queued: boolean;
  onReel: (file: File) => void;
  onFootage: (files: File[]) => void;
  onPreset: (style: Style) => void;
  onPresets: (on: boolean) => void;
  onGo: () => void;
  onSeeAll: () => void;
}) {
  const reading = read?.status === "running";
  const lookReady = read?.status === "done" || !!preset;
  const has = targets.length > 0;
  const armed = lookReady && has;
  const chips = fp ? readChips(fp) : [];

  const hint = queued ? "Starts as soon as the reel is read."
    : armed ? (sourceSeconds ? `Ready. Usually ${about(editSeconds(sourceSeconds))} for ${clock(sourceSeconds)} of video.` : "Ready.")
    : reading ? (has ? "Still reading the reel. Tap and it starts the moment it's done." : "Reading the reel. Add your footage meanwhile.")
    : lookReady ? "Now add your own footage."
    : has ? (presets ? "Now pick a look." : "Now add a reel you love.")
    : presets ? "Pick a look and add your footage." : "Add a reel you love and your own footage.";

  return (
    <main className={s.setup}>
      <header className={s.top}>
        <span className={s.brand}><Mark />Halfheaven</span>
      </header>

      <div className={s.lead}>
        <p>See a reel you love?</p>
        <h1>Make yours look like <em>that</em>.</h1>
      </div>

      <div className={s.pair}>
        <div className={s.col}>
          <span className={s.colLabel}>{presets ? "A built-in look" : "A reel you love"}</span>
          {presets ? (
            <div className={s.tile} style={{ cursor: "default", justifyContent: "flex-start" }}>
              <div className={s.presets}>
                {styles.map(st => (
                  <button key={st.id} className={s.presetBtn} aria-pressed={preset?.id === st.id}
                          onClick={() => onPreset(st)}>{st.name}</button>
                ))}
              </div>
              <span className={s.grow} />
              <button className={s.linkBtn} onClick={() => onPresets(false)}>Use a reel instead</button>
            </div>
          ) : (
            <Drop className={`${s.tile} ${read ? s.full : ""}`} onFiles={f => onReel(f[0])}
                  label={read ? "Choose a different reel" : "Add a reel you love"}>
              {read ? (
                <>
                  {refUrl && <video src={refUrl} muted loop playsInline autoPlay />}
                  {reading && <span className={s.scan} />}
                  {!refUrl && <span className={s.t2} style={{ padding: 12 }}>{read.name}</span>}
                  {read.status === "running" && <span className={s.tchip}><i className={s.dot} />Reading · <span className={s.mono}>{elapsed}s</span></span>}
                  {read.status === "done" && <span className={s.tchip}><Check size={14} />Read</span>}
                  {read.status === "error" && <span className={`${s.tchip} ${s.bad}`}>{read.error || "Couldn't read that one. Try another."}</span>}
                </>
              ) : (
                <>
                  <span className={s.plus}><Plus /></span>
                  <span className={s.t1}>Add a reel</span>
                  <span className={s.t2}>From your gallery</span>
                </>
              )}
            </Drop>
          )}
        </div>

        <div className={s.bridgeCol}>
          <span className={`${s.bridge} ${armed ? s.live : ""}`}><Arrow size={16} /></span>
        </div>

        <div className={s.col}>
          <span className={s.colLabel}>Your footage</span>
          {has ? (
            <div className={s.fan}>
              {targets.length > 1 && <><span className={`${s.ghost} ${s.ghost1}`} /><span className={`${s.ghost} ${s.ghost2}`} /></>}
              <Drop className={`${s.tile} ${s.full}`} multiple onFiles={onFootage} label="Choose different footage">
                {targetUrl && <video src={`${targetUrl}#t=0.5`} muted playsInline preload="metadata" />}
                <span className={s.tchip}>
                  {targets.length > 1 ? `${targets.length} takes` : <Check size={14} />}
                  {sourceSeconds ? <span className={s.mono}>{targets.length > 1 ? " · " : ""}{clock(sourceSeconds)}</span> : null}
                </span>
              </Drop>
            </div>
          ) : (
            <Drop className={s.tile} multiple onFiles={onFootage} label="Add your footage">
              <span className={s.plus}><Plus /></span>
              <span className={s.t1}>Add your footage</span>
              <span className={s.t2}>One take or several</span>
            </Drop>
          )}
        </div>
      </div>

      {chips.length > 0 ? (
        <section className={s.dna} aria-label="What we read from the reel">
          <div className={s.dnaHead}>
            <span>What we read</span>
            <button className={s.seeAll} onClick={onSeeAll}>See all</button>
          </div>
          <div className={s.chips}>
            {chips.map(c => (
              <span key={c.key} className={s.chip}>
                {c.icon === "pace" && <Bolt size={15} />}
                {c.icon === "type" && <span className={s.aa}>Aa</span>}
                {c.swatch && <span className={s.sw} style={{ background: c.swatch }} />}
                {c.text}
              </span>
            ))}
          </div>
        </section>
      ) : !presets && !read && styles.length > 0 ? (
        <button className={s.linkBtn} style={{ alignSelf: "flex-start", marginTop: 12 }} onClick={() => onPresets(true)}>
          No reel? Use a built-in look
        </button>
      ) : null}

      <span className={s.grow} />

      <footer className={s.foot}>
        <span className={s.hint} aria-live="polite">{hint}</span>
        <button className={`${s.go} ${armed && !queued ? s.armed : ""}`}
                disabled={!has || queued || !(lookReady || reading)} onClick={onGo}>
          {queued ? "Starting when it's read…" : <>Make mine look like that <Arrow size={18} /></>}
        </button>
      </footer>
    </main>
  );
}
