"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { Fingerprint, Reading } from "@/lib/fingerprint";
import { absences, groupsFor } from "@/lib/readout";

type Job = {
  id: string;
  status: "running" | "done" | "error";
  name: string;
  error?: string;
  fingerprint?: Fingerprint;
};

const MARK: Record<Reading["confidence"], { sign: string; title: string; tone: string }> = {
  measured: { sign: "●", title: "measured directly", tone: "var(--good)" },
  inferred: { sign: "◐", title: "inferred from another measurement", tone: "var(--gold)" },
  absent: { sign: "○", title: "looked for, not found", tone: "var(--faint)" },
};

function show(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.map((v) => (typeof v === "number" ? v.toFixed(2) : String(v))).join(", ");
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3);
  return String(value);
}

export default function ReadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [depth, setDepth] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [dragging, setDragging] = useState(false);
  const picker = useRef<HTMLInputElement>(null);

  // Poll while the scan runs. It takes roughly a third of the video's length,
  // which is too long to hold a request open and too short to need a queue.
  useEffect(() => {
    if (!job || job.status !== "running") return;
    const tick = setInterval(async () => {
      const res = await fetch(`/api/fingerprint/${job.id}`);
      if (res.ok) setJob(await res.json());
    }, 1200);
    const clock = setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => {
      clearInterval(tick);
      clearInterval(clock);
    };
  }, [job]);

  const start = useCallback(async () => {
    if (!file) return;
    setElapsed(0);
    setJob({ id: "…", status: "running", name: file.name });
    const form = new FormData();
    form.set("reference", file);
    if (depth) form.set("depth", "1");
    const res = await fetch("/api/fingerprint", { method: "POST", body: form });
    const data = await res.json();
    setJob(
      data.id
        ? { id: data.id, status: "running", name: file.name }
        : { id: "—", status: "error", name: file.name, error: data.error },
    );
  }, [file, depth]);

  const drop = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    setDragging(false);
    const dropped = event.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  }, []);

  const fp = job?.status === "done" ? job.fingerprint : undefined;
  const groups = fp ? groupsFor(fp) : [];
  const missing = fp ? absences(fp) : [];

  return (
    <main style={{ maxWidth: 780, margin: "0 auto", padding: "44px 20px 90px" }}>
      <p className="eyebrow">Read a reference</p>
      <h1 className="display" style={{ fontSize: 30, marginTop: 6 }}>
        Point at a reel you like.
      </h1>
      <p style={{ color: "var(--muted)", marginTop: 8, maxWidth: 560 }}>
        We measure how it was edited — its pace, how its words behave, how much of it isn&apos;t
        footage at all. Everything we can&apos;t measure, we say so rather than guess.
      </p>

      {/* ---------------- picker ---------------- */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={drop}
        onClick={() => picker.current?.click()}
        style={{
          marginTop: 26,
          border: `1.5px dashed ${dragging ? "var(--accent)" : "var(--line-2)"}`,
          background: dragging ? "var(--accent-soft)" : "var(--card)",
          borderRadius: "var(--r)",
          padding: "26px 20px",
          textAlign: "center",
          cursor: "pointer",
          transition: "border-color .14s, background .14s",
        }}
      >
        <input
          ref={picker}
          type="file"
          accept="video/*"
          hidden
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <div style={{ fontWeight: 600 }}>{file ? file.name : "Drop a video, or choose one"}</div>
        <div className="tiny" style={{ marginTop: 4 }}>
          {file
            ? `${(file.size / 1e6).toFixed(1)} MB — reading takes about a third of its length`
            : "An edited reel, not your raw footage"}
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 14, flexWrap: "wrap" }}>
        <button className="btn primary" disabled={!file || job?.status === "running"} onClick={start}>
          {job?.status === "running" ? "Reading…" : "Read it"}
        </button>
        <label className="tiny" style={{ display: "flex", alignItems: "center", gap: 7, cursor: "pointer" }}>
          <input type="checkbox" checked={depth} onChange={(e) => setDepth(e.target.checked)} />
          Also check whether type passes behind the subject
          <span style={{ color: "var(--faint)" }}>(slow — loads a segmentation model)</span>
        </label>
      </div>

      {/* ---------------- waiting ---------------- */}
      {job?.status === "running" && (
        <div
          style={{
            marginTop: 22,
            padding: "14px 16px",
            background: "var(--sunk)",
            borderRadius: "var(--r)",
            border: "1px solid var(--line)",
          }}
        >
          <div style={{ fontWeight: 600 }}>Measuring {job.name}</div>
          <div className="tiny" style={{ marginTop: 3 }}>
            {elapsed}s elapsed — masking type at full resolution, frame by frame
            {depth ? ", then segmenting the subject" : ""}.
          </div>
        </div>
      )}

      {job?.status === "error" && (
        <div
          style={{
            marginTop: 22,
            padding: "14px 16px",
            background: "var(--accent-soft)",
            borderRadius: "var(--r)",
            border: "1px solid var(--accent)",
          }}
        >
          <div style={{ fontWeight: 600 }}>That didn&apos;t work</div>
          <div className="tiny" style={{ marginTop: 3 }}>{job.error}</div>
        </div>
      )}

      {/* ---------------- readout ---------------- */}
      {fp && (
        <section style={{ marginTop: 30 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
            <h2 className="display" style={{ fontSize: 19 }}>
              What we picked up
            </h2>
            <span className="tiny">
              {fp.width}×{fp.height} · {fp.duration}s
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 14 }}>
            {groups.map((group) => (
              <div key={group.key} className="card" style={{ padding: "13px 15px 14px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                  <span className="eyebrow">{group.title}</span>
                  {group.swatches?.map((s) => (
                    <span key={s.label} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                      <span
                        style={{
                          width: 14,
                          height: 14,
                          borderRadius: 4,
                          background: s.hex,
                          border: "1px solid var(--line-2)",
                        }}
                      />
                      <span className="tiny" style={{ fontVariantNumeric: "tabular-nums" }}>
                        {s.hex}
                      </span>
                    </span>
                  ))}
                  <button
                    className="ln"
                    style={{ marginLeft: "auto" }}
                    onClick={() => setOpen((o) => ({ ...o, [group.key]: !o[group.key] }))}
                  >
                    {open[group.key] ? "hide numbers" : "numbers"}
                  </button>
                </div>

                <div style={{ fontSize: 16, fontWeight: 600, marginTop: 7 }}>
                  {group.headline ?? <span style={{ color: "var(--faint)" }}>Nothing measurable here</span>}
                </div>
                {group.detail.map((line, i) => (
                  <p key={i} className="tiny" style={{ marginTop: 4 }}>
                    {line}
                  </p>
                ))}

                {open[group.key] && (
                  <table
                    style={{
                      width: "100%",
                      marginTop: 11,
                      borderCollapse: "collapse",
                      fontSize: 12.5,
                      fontVariantNumeric: "tabular-nums",
                    }}
                  >
                    <tbody>
                      {group.readings.map(([name, reading]) => (
                        <tr key={name} style={{ borderTop: "1px solid var(--line)" }}>
                          <td style={{ padding: "5px 8px 5px 0", width: 18, color: MARK[reading.confidence].tone }}>
                            <span title={MARK[reading.confidence].title}>{MARK[reading.confidence].sign}</span>
                          </td>
                          <td style={{ padding: "5px 10px 5px 0", color: "var(--muted)", whiteSpace: "nowrap" }}>
                            {name.replace(/_/g, " ")}
                          </td>
                          <td style={{ padding: "5px 10px 5px 0", fontWeight: 600 }}>{show(reading.value)}</td>
                          <td style={{ padding: "5px 0", color: "var(--faint)" }}>{reading.note}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            ))}
          </div>

          {/* Absence is a finding. Showing it is what keeps the rest trustworthy. */}
          {missing.length > 0 && (
            <div className="card" style={{ marginTop: 10, padding: "13px 15px 14px" }}>
              <span className="eyebrow">Looked for, didn&apos;t find</span>
              <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
                {missing.map((line) => (
                  <li key={line} className="tiny" style={{ marginBottom: 3 }}>
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="tiny" style={{ marginTop: 16, color: "var(--faint)" }}>
            ● measured · ◐ inferred from another measurement · ○ looked for, not found. Nothing here
            is painted onto footage yet — this is the reading only.
          </p>
        </section>
      )}
    </main>
  );
}
