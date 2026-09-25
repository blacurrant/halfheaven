"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { forget, recall, remember } from "@/lib/remember";

type Face = { file: string; family: string; genre: string; italic: boolean;
              caps_only: boolean; weights: [number, number] | null };
type Decor = "none" | "stroke" | "shadow_soft" | "shadow_hard" | "box" | "pill";
type Type = { fill_hex: string; size_pct: number; font_file: string | null; font_weight: number;
              all_caps: boolean; decor: Decor; stroke_hex: string; shadow_hex: string; box_hex: string };
type Side = "body" | "pop";

const SIDES: { id: Side; label: string }[] = [
  { id: "body", label: "Normal words" },
  { id: "pop", label: "Pop words" },
];
const EDGES: { id: Decor; label: string }[] = [
  { id: "stroke", label: "Outline" }, { id: "shadow_soft", label: "Soft shadow" },
  { id: "shadow_hard", label: "Hard shadow" }, { id: "box", label: "Box" },
  { id: "pill", label: "Pill" }, { id: "none", label: "None" },
];
// Which colour the edge control sets depends on the edge.
const EDGE_COLOUR: Record<Decor, keyof Type | null> = {
  stroke: "stroke_hex", shadow_soft: "shadow_hex", shadow_hard: "shadow_hex",
  box: "box_hex", pill: "box_hex", none: null,
};
const GENRES: Record<string, string> = {
  sans: "Sans", serif: "Serif", display: "Display", script: "Script", mono: "Mono",
};
const MIN_SIZE = 0.015, MAX_SIZE = 0.2;
// The preview frame, a phone screen in miniature.
const FRAME_H = 240;

/** Load a shipped face into the page once, under a name tied to its file. */
const loaded = new Map<string, Promise<void>>();
function useFace(face: Face | undefined): string {
  const [ready, setReady] = useState<string>("");
  useEffect(() => {
    if (!face) return;
    const family = `hh-${face.file.replace(/\W/g, "-")}`;
    if (!loaded.has(face.file)) {
      const font = new FontFace(family, `url(/api/fonts/${face.file})`,
        face.weights ? { weight: `${face.weights[0]} ${face.weights[1]}` } : {});
      loaded.set(face.file, font.load().then(f => { document.fonts.add(f); }));
    }
    loaded.get(face.file)!.then(() => setReady(family), () => setReady(""));
  }, [face]);
  return ready;
}

function cssFor(type: Type, family: string): React.CSSProperties {
  const px = type.size_pct * FRAME_H;
  const edge: React.CSSProperties = {};
  if (type.decor === "stroke") {
    Object.assign(edge, { WebkitTextStroke: `${Math.max(1, px * 0.14)}px ${type.stroke_hex}`,
                          paintOrder: "stroke fill" });
  } else if (type.decor === "shadow_soft" || type.decor === "shadow_hard") {
    const o = px * 0.07;
    edge.textShadow = `${o}px ${o}px ${type.decor === "shadow_soft" ? px * 0.16 : 0}px ${type.shadow_hex}`;
  } else if (type.decor === "box" || type.decor === "pill") {
    Object.assign(edge, { background: type.box_hex, padding: `${px * 0.15}px ${px * 0.3}px`,
                          borderRadius: type.decor === "pill" ? px : px * 0.2 });
  }
  return {
    fontFamily: family ? `"${family}"` : "inherit", fontSize: px, lineHeight: 1.15,
    fontWeight: type.font_weight, color: type.fill_hex,
    textTransform: type.all_caps ? "uppercase" : "none", ...edge,
  };
}

/** A creator's own caption type, for normal words and for the ones that pop.
 *  Changes are drafted here and previewed live; Apply renders once. */
export default function TypeControls({
  jobId, ready, version, onApplied, onStart, onFailed,
}: {
  jobId: string; ready: boolean; version: number; onApplied: () => void;
  /** Told when a render starts and when one fails, for a page that shows it. */
  onStart?: () => void; onFailed?: (why: string) => void;
}) {
  const [faces, setFaces] = useState<Face[]>([]);
  const [saved, setSaved] = useState<Record<Side, Type> | null>(null);
  const [draft, setDraft] = useState<Record<Side, Type> | null>(null);
  const [side, setSide] = useState<Side>("body");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fetched = useRef(false);

  useEffect(() => {
    fetch("/api/fonts").then(r => r.json()).then(d => d.faces && setFaces(d.faces));
  }, []);
  useEffect(() => {
    if (!ready) return;
    fetch(`/api/jobs/${jobId}/type`).then(r => r.json()).then(d => {
      if (!d.body) return;
      // A draft left unapplied before a refresh picks up where it was - but not
      // after a new look, whose type it would quietly undo.
      const kept = fetched.current ? null : recall<Record<Side, Type>>(`type.${jobId}`);
      fetched.current = true;
      setSaved(d); setDraft(kept ?? d); setError("");
    });
  }, [jobId, ready, version]);   // a new look redraws every card: read it again

  useEffect(() => {
    if (!draft || !saved) return;
    if (JSON.stringify(draft) === JSON.stringify(saved)) forget(`type.${jobId}`);
    else remember(`type.${jobId}`, draft);
  }, [jobId, draft, saved]);

  const byFile = useMemo(() => new Map(faces.map(f => [f.file, f])), [faces]);
  const bodyFamily = useFace(draft?.body.font_file ? byFile.get(draft.body.font_file) : undefined);
  const popFamily = useFace(draft?.pop.font_file ? byFile.get(draft.pop.font_file) : undefined);

  if (!draft || !saved) {
    return <span className="tiny">{ready ? "Loading type…" : "Available once the edit is ready."}</span>;
  }
  const type = draft[side];
  const face = type.font_file ? byFile.get(type.font_file) : undefined;
  const set = (change: Partial<Type>) => setDraft(d => d && ({ ...d, [side]: { ...d[side], ...change } }));

  // Only what differs from the edit as drawn goes to the server.
  const patch: Partial<Record<Side, Partial<Type>>> = {};
  for (const s of ["body", "pop"] as Side[]) {
    const changed = Object.fromEntries(Object.entries(draft[s])
      .filter(([k, v]) => saved[s][k as keyof Type] !== v));
    if (Object.keys(changed).length) patch[s] = changed as Partial<Type>;
  }
  const dirty = Object.keys(patch).length > 0;

  const apply = async () => {
    setBusy(true); setError(""); onStart?.();
    try {
      const r = await fetch(`/api/jobs/${jobId}/type`, {
        method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(patch),
      });
      const d = await r.json().catch(() => ({}));
      if (r.ok) { setSaved(draft); onApplied(); }
      else { setError(d.error ?? "That didn't apply."); onFailed?.(d.error ?? "That didn't apply."); }
    } catch {
      setError("That didn't apply."); onFailed?.("That didn't apply.");
    } finally { setBusy(false); }
  };

  const edgeKey = EDGE_COLOUR[type.decor];
  const genres = Object.keys(GENRES).filter(g => faces.some(f => f.genre === g));

  return (
    <div className="type-ctl">
      <div className="type-preview" aria-hidden>
        <span style={cssFor(draft.body, bodyFamily)}>what you said </span>
        <span style={cssFor(draft.pop, popFamily)}>stressed</span>
      </div>

      <div className="seg" role="tablist">
        {SIDES.map(s => (
          <button key={s.id} role="tab" aria-selected={side === s.id} onClick={() => setSide(s.id)}>
            {s.label}
          </button>
        ))}
      </div>

      <label className="row">
        <span>Colour</span>
        <input type="color" value={type.fill_hex} onChange={e => set({ fill_hex: e.target.value })} />
      </label>

      <label className="row">
        <span>Size</span>
        <input type="range" min={MIN_SIZE} max={MAX_SIZE} step={0.001} value={type.size_pct}
          onChange={e => set({ size_pct: Number(e.target.value) })} />
        <output>{(type.size_pct * 100).toFixed(1)}%</output>
      </label>

      <label className="row">
        <span>Typeface</span>
        <select value={type.font_file ?? ""} onChange={e => {
          const next = byFile.get(e.target.value);
          const [lo, hi] = next?.weights ?? [type.font_weight, type.font_weight];
          set({ font_file: e.target.value, font_weight: Math.min(hi, Math.max(lo, type.font_weight)) });
        }}>
          {!type.font_file && <option value="">As the look chose</option>}
          {genres.map(g => (
            <optgroup key={g} label={GENRES[g]}>
              {faces.filter(f => f.genre === g).map(f => (
                <option key={f.file} value={f.file}>{f.family}{f.italic ? " Italic" : ""}</option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>

      <label className="row">
        <span>Weight</span>
        {face?.weights ? (
          <>
            <input type="range" min={face.weights[0]} max={face.weights[1]} step={50}
              value={type.font_weight} onChange={e => set({ font_weight: Number(e.target.value) })} />
            <output>{type.font_weight}</output>
          </>
        ) : <span className="tiny">{face ? "This face comes in one weight" : "Pick a typeface first"}</span>}
      </label>

      <label className="row">
        <span>ALL CAPS</span>
        <input type="checkbox" checked={type.all_caps} onChange={e => set({ all_caps: e.target.checked })} />
      </label>

      <label className="row">
        <span>Edge</span>
        <select value={type.decor} onChange={e => set({ decor: e.target.value as Decor })}>
          {EDGES.map(d => <option key={d.id} value={d.id}>{d.label}</option>)}
        </select>
        {edgeKey && (
          <input type="color" aria-label="Edge colour" value={String(type[edgeKey])}
            onChange={e => set({ [edgeKey]: e.target.value } as Partial<Type>)} />
        )}
      </label>

      <div className="type-foot">
        {error ? <span className="tiny" style={{ color: "var(--bad)" }}>{error}</span>
          : <span className="tiny">{dirty ? "Preview only until you apply" : "Matches your edit"}</span>}
        <button className="btn ghost sm" disabled={!dirty || busy} onClick={() => setDraft(saved)}>Reset</button>
        <button className="btn primary sm" disabled={!dirty || busy || !ready} onClick={apply}>
          {busy ? "Applying…" : "Apply"}
        </button>
      </div>
    </div>
  );
}
