import type { Score, ScoreRow } from "@/lib/score";

const VERDICT: Record<ScoreRow["verdict"], { sign: string; tone: string }> = {
  match: { sign: "✓", tone: "var(--good)" },
  near: { sign: "≈", tone: "var(--gold)" },
  miss: { sign: "✗", tone: "var(--bad)" },
  unscored: { sign: "·", tone: "var(--faint)" },
};

/** How close a render landed to the reel it copied, trait by trait. */
export default function Scorecard({ score }: { score: Score }) {
  return (
    <div className="card" style={{ padding: "13px 15px 14px" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 9 }}>
        <span className="eyebrow">Against the reference</span>
        <span className="display" style={{ fontSize: 19, marginLeft: "auto" }}>
          {Math.round(score.score * 100)}%
        </span>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", marginTop: 9, borderCollapse: "collapse",
                        fontSize: 12.5, fontVariantNumeric: "tabular-nums" }}>
          <tbody>
            {score.rows.map((row) => (
              <tr key={row.field} style={{ borderTop: "1px solid var(--line)" }}>
                <td style={{ padding: "4px 8px 4px 0", color: VERDICT[row.verdict].tone, width: 16 }}>
                  {VERDICT[row.verdict].sign}
                </td>
                <td style={{ padding: "4px 10px 4px 0", color: "var(--muted)" }}>{row.label}</td>
                <td style={{ padding: "4px 10px 4px 0", fontWeight: 600 }}>
                  {row.verdict === "unscored" ? "—" : String(row.ours)}
                </td>
                <td style={{ padding: "4px 0", color: "var(--faint)" }}>
                  {row.verdict === "unscored" ? row.why : String(row.theirs)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="tiny" style={{ margin: "9px 0 0", color: "var(--faint)" }}>
        This measures resemblance, not quality — it says how close the edit landed to the
        reference&apos;s decisions, not whether the result is good. Watch the video too.
      </p>
    </div>
  );
}
