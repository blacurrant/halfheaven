"use client";

import { useState } from "react";

import type { Fingerprint, Reading } from "@/lib/fingerprint";
import { absences, groupsFor } from "@/lib/readout";

const MARK: Record<Reading["confidence"], { sign: string; tone: string; title: string }> = {
  measured: { sign: "●", tone: "var(--good)", title: "measured directly" },
  inferred: { sign: "◐", tone: "var(--gold)", title: "inferred from another measurement" },
  absent: { sign: "○", tone: "var(--faint)", title: "looked for, not found" },
};

function show(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.map((v) => (typeof v === "number" ? v.toFixed(2) : v)).join(", ");
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3);
  return String(value);
}

/** What we read out of a reel: one plain sentence per group, the numbers one
 *  fold down for whoever wants to check our working, and the things we looked
 *  for and could not find said out loud rather than quietly left out. */
export default function Readout({ fp }: { fp: Fingerprint }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const groups = groupsFor(fp);
  const missing = absences(fp);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
      {groups.map((g) => (
        <div key={g.key} className="card" style={{ padding: "12px 14px 13px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 9, flexWrap: "wrap" }}>
            <span className="eyebrow">{g.title}</span>
            {g.swatches?.map((s) => (
              <span key={s.label} style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 13, height: 13, borderRadius: 4, background: s.hex,
                               border: "1px solid var(--line-2)" }} />
                <span className="tiny">{s.hex}</span>
              </span>
            ))}
            <button className="ln" style={{ marginLeft: "auto" }}
                    onClick={() => setOpen((o) => ({ ...o, [g.key]: !o[g.key] }))}>
              {open[g.key] ? "hide" : "numbers"}
            </button>
          </div>
          <div style={{ fontSize: 15.5, fontWeight: 600, marginTop: 6 }}>
            {g.headline ?? <span style={{ color: "var(--faint)" }}>Nothing measurable here</span>}
          </div>
          {g.detail.map((line, i) => (
            <p key={i} className="tiny" style={{ margin: "3px 0 0" }}>{line}</p>
          ))}
          {open[g.key] && (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", marginTop: 10, borderCollapse: "collapse",
                              fontSize: 12.5, fontVariantNumeric: "tabular-nums" }}>
                <tbody>
                  {g.readings.map(([name, r]) => (
                    <tr key={name} style={{ borderTop: "1px solid var(--line)" }}>
                      <td title={MARK[r.confidence].title}
                          style={{ padding: "4px 8px 4px 0", color: MARK[r.confidence].tone, width: 16 }}>
                        {MARK[r.confidence].sign}
                      </td>
                      <td style={{ padding: "4px 10px 4px 0", color: "var(--muted)", whiteSpace: "nowrap" }}>
                        {name.replace(/_/g, " ")}
                      </td>
                      <td style={{ padding: "4px 10px 4px 0", fontWeight: 600 }}>{show(r.value)}</td>
                      <td style={{ padding: "4px 0", color: "var(--faint)" }}>{r.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}
      {missing.length > 0 && (
        <div className="card" style={{ padding: "12px 14px 13px" }}>
          <span className="eyebrow">Looked for, didn&apos;t find</span>
          <ul style={{ margin: "7px 0 0", paddingLeft: 18 }}>
            {missing.map((m) => <li key={m} className="tiny">{m}</li>)}
          </ul>
        </div>
      )}
      <p className="tiny" style={{ margin: "4px 0 0", color: "var(--faint)" }}>
        ● measured · ◐ inferred · ○ looked for, not found
      </p>
    </div>
  );
}
