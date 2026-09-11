"use client";

/**
 * The measuring bench: the reference-to-edit flow with every reading and the
 * scorecard laid out in the open. The studio at the root hides all of this
 * behind a menu for creators; this page keeps it on the surface for whoever is
 * checking the measurements themselves.
 *
 * Both files sit on one step rather than in sequence, because the work behind
 * them is a graph and not a queue: reading a reference depends only on the
 * reference, so it starts the moment that file lands and is usually finished
 * before anyone has chosen their footage.
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import Drop from "@/components/Drop";
import Readout from "@/components/Readout";
import Scorecard from "@/components/Scorecard";
import type { Fingerprint } from "@/lib/fingerprint";
import type { Score } from "@/lib/score";

type ReadJob = {
  id: string;
  status: "running" | "done" | "error";
  name: string;
  videoPath: string;
  error?: string;
  fingerprint?: Fingerprint;
};

type RenderJob = {
  id: string;
  status: "running" | "done" | "error";
  stageIndex: number;
  progress: number;
  targetName: string;
  error?: string;
  receipt?: {
    clips: number; captions: number; emphasised: number; punches: number;
    sourceSeconds: number; outputSeconds: number;
  };
};

const STAGES = ["Reading the reference", "Transcribing", "Editorial pass", "Planning the cut", "Rendering"];

const mb = (files: File[]) => `${(files.reduce((a, f) => a + f.size, 0) / 1e6).toFixed(1)} MB`;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginTop: 34 }}>
      <h2 className="display" style={{ fontSize: 17, marginBottom: 12 }}>{title}</h2>
      {children}
    </section>
  );
}

export default function Lab() {
  const [refFile, setRefFile] = useState<File | null>(null);
  const [read, setRead] = useState<ReadJob | null>(null);

  const [targets, setTargets] = useState<File[]>([]);
  const [render, setRender] = useState<RenderJob | null>(null);

  const [score, setScore] = useState<Score | null>(null);
  const [scoring, setScoring] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  // ---- polling -----------------------------------------------------------
  useEffect(() => {
    if (!read || read.status !== "running") return;
    const t = setInterval(async () => {
      const r = await fetch(`/api/fingerprint/${read.id}`);
      if (r.ok) setRead(await r.json());
    }, 1200);
    const c = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => { clearInterval(t); clearInterval(c); };
  }, [read]);

  useEffect(() => {
    if (!render || render.status !== "running") return;
    const t = setInterval(async () => {
      const r = await fetch(`/api/jobs/${render.id}`);
      if (r.ok) setRender(await r.json());
    }, 1500);
    return () => clearInterval(t);
  }, [render]);

  // ---- actions -----------------------------------------------------------
  const readReference = useCallback(async (file: File) => {
    setRefFile(file);
    setElapsed(0);
    setRead({ id: "…", status: "running", name: file.name, videoPath: "" });
    setRender(null);
    setScore(null);
    const form = new FormData();
    form.set("reference", file);
    const res = await fetch("/api/fingerprint", { method: "POST", body: form });
    const data = await res.json();
    setRead(data.id
      ? { id: data.id, status: "running", name: file.name, videoPath: "" }
      : { id: "—", status: "error", name: file.name, videoPath: "", error: data.error });
  }, []);

  const applyToFootage = useCallback(async () => {
    if (!targets.length || read?.status !== "done") return;
    setScore(null);
    setRender({ id: "…", status: "running", stageIndex: 0, progress: 0.04, targetName: targets[0].name });
    const form = new FormData();
    for (const f of targets) form.append("target", f);
    form.set("referencePath", read.videoPath);
    form.set("referenceName", read.name);
    const res = await fetch("/api/jobs", { method: "POST", body: form });
    const data = await res.json();
    setRender(data.id
      ? { id: data.id, status: "running", stageIndex: 0, progress: 0.08, targetName: targets[0].name }
      : { id: "—", status: "error", stageIndex: 0, progress: 0, targetName: targets[0].name, error: data.error });
  }, [targets, read]);

  const runScore = useCallback(async () => {
    if (render?.status !== "done") return;
    setScoring(true);
    const res = await fetch("/api/score", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ jobId: render.id }),
    });
    const data = await res.json();
    setScoring(false);
    if (!data.error) setScore(data);
  }, [render]);

  const fp = read?.status === "done" ? read.fingerprint : undefined;

  return (
    <main style={{ maxWidth: 800, margin: "0 auto", padding: "48px 20px 110px" }}>
      <p className="eyebrow">Halfheaven · lab</p>
      <h1 className="display" style={{ fontSize: 32, marginTop: 6, lineHeight: 1.12 }}>
        Give your footage<br />someone else&apos;s edit.
      </h1>
      <p style={{ color: "var(--muted)", marginTop: 10, maxWidth: 580 }}>
        Point at a reel whose editing you like. We measure how it was made, then cut your own
        footage the same way. Everything we can&apos;t measure, we say so instead of guessing.
      </p>

      {/* ---------------- both files, either order ---------------- */}
      <section style={{ marginTop: 30 }}>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span className="eyebrow">A reel you want to look like</span>
              {read?.status === "done" && (
                <span className="tiny" style={{ color: "var(--good)" }}>read ✓</span>
              )}
              {read?.status === "running" && (
                <span className="tiny" style={{ color: "var(--gold)" }}>reading… {elapsed}s</span>
              )}
            </div>
            <Drop onFiles={(fl) => readReference(fl[0])} disabled={read?.status === "running"}>
              <div style={{ fontWeight: 600 }}>{refFile ? refFile.name : "Drop an edited reel"}</div>
              <div className="tiny" style={{ marginTop: 4 }}>
                {refFile ? mb([refFile]) : "Someone else's finished video"}
              </div>
            </Drop>
            {read?.status === "error" && (
              <p className="tiny" style={{ color: "var(--bad)", marginTop: 6 }}>{read.error}</p>
            )}
          </div>

          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span className="eyebrow">Your raw clips</span>
              {targets.length > 0 && (
                <span className="tiny" style={{ color: "var(--good)" }}>ready ✓</span>
              )}
            </div>
            <Drop multiple onFiles={setTargets} disabled={render?.status === "running"}>
              <div style={{ fontWeight: 600 }}>
                {targets.length > 1 ? `${targets.length} takes` : targets[0]?.name ?? "Drop your footage"}
              </div>
              <div className="tiny" style={{ marginTop: 4 }}>
                {targets.length ? mb(targets) : "Several takes are treated as one"}
              </div>
            </Drop>
          </div>
        </div>

        <div style={{ marginTop: 14, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          <button
            className="btn primary"
            disabled={!targets.length || read?.status !== "done" || render?.status === "running"}
            onClick={applyToFootage}
          >
            {render?.status === "running" ? "Editing…" : "Edit it like that"}
          </button>
          {/* Say which half is missing rather than leaving a dead button. */}
          {(!targets.length || read?.status !== "done") && render?.status !== "running" && (
            <span className="tiny">
              {read?.status === "running"
                ? targets.length
                  ? "Still reading the reference — nearly there."
                  : "Reading the reference. Drop your footage meanwhile."
                : !read
                  ? targets.length
                    ? "Now point at a reel you want to look like."
                    : "Needs a reel to copy and some footage of your own."
                  : !targets.length
                    ? "Now drop your own footage."
                    : ""}
            </span>
          )}
        </div>

        {render?.status === "running" && (
          <div style={{ marginTop: 14 }}>
            <div style={{ height: 5, borderRadius: 99, background: "var(--sunk)", overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${Math.round(render.progress * 100)}%`,
                            background: "var(--accent)", transition: "width .4s" }} />
            </div>
            <p className="tiny" style={{ marginTop: 6 }}>{STAGES[render.stageIndex] ?? "Working"}…</p>
          </div>
        )}
        {render?.status === "error" && (
          <p className="tiny" style={{ color: "var(--bad)", marginTop: 8 }}>{render.error}</p>
        )}
      </section>

      {/* ---------------- readout ---------------- */}
      {fp && (
        <Section title="What we read out of it">
          <Readout fp={fp} />
        </Section>
      )}

      {/* ---------------- result ---------------- */}
      {render?.status === "done" && (
        <Section title="Your edit">
          <video
            key={render.id}
            src={`/api/jobs/${render.id}/media?v=after`}
            controls
            playsInline
            style={{ width: "100%", maxWidth: 320, borderRadius: "var(--r)",
                     background: "var(--theatre)", display: "block" }}
          />
          {render.receipt && (
            <p className="tiny" style={{ marginTop: 10 }}>
              {render.receipt.clips} clips · {render.receipt.captions} caption cards ·{" "}
              {render.receipt.punches} push-ins · {render.receipt.sourceSeconds.toFixed(0)}s in,{" "}
              {render.receipt.outputSeconds.toFixed(0)}s out
            </p>
          )}

          <div style={{ marginTop: 18 }}>
            {score ? <Scorecard score={score} /> : (
              <button className="btn sm" onClick={runScore} disabled={scoring}>
                {scoring ? "Scoring…" : "How close did it get?"}
              </button>
            )}
          </div>
        </Section>
      )}

      <p className="tiny" style={{ marginTop: 44, color: "var(--faint)" }}>
        <Link href="/" style={{ color: "var(--muted)" }}>Back to the studio</Link>
      </p>
    </main>
  );
}
