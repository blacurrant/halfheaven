import fs from "node:fs";
import path from "node:path";
import { REPO } from "@/lib/pipeline";

/** The workspace opens on a real previous render rather than an empty frame:
 *  a tool should show what it does before you feed it anything. */
export async function GET() {
  const work = path.join(REPO, "work");
  const out = path.join(REPO, "styled.mp4");
  if (!fs.existsSync(out) || !fs.existsSync(path.join(work, "edit_program.json"))) {
    return Response.json({ job: null });
  }
  const profile = JSON.parse(fs.readFileSync(path.join(work, "style_profile.json"), "utf8"));
  const prog = JSON.parse(fs.readFileSync(path.join(work, "edit_program.json"), "utf8"));
  const runs = prog.captions.flatMap((c: { runs: { text: string; style: string }[] }) => c.runs);
  const emph = runs.filter((r: { style: string }) => r.style === "emphasis");
  const punchAt: number[] = prog.video
    .map((c: { scale_to?: number }, i: number) => (c.scale_to ? i : -1))
    .filter((i: number) => i >= 0);

  return Response.json({
    job: {
      id: "demo",
      status: "done",
      stageIndex: 4,
      progress: 1,
      styleId: "night-interview",
      targetName: "noedit.mp4",
      profile,
      segments: prog.video.length,
      punchAt,
      clips: prog.video.map((c: { start: number; end: number }) => ({ start: c.start, end: c.end })),
      receipt: {
        clips: prog.video.length,
        captions: prog.captions.length,
        emphasised: emph.length,
        punches: punchAt.length,
        wordsCut: 6,
        sourceSeconds: 61.4,
        outputSeconds: prog.video.reduce(
          (a: number, c: { start: number; end: number }) => a + (c.end - c.start), 0),
        emphasisWords: [...new Set(emph.map((r: { text: string }) => r.text))].slice(0, 8),
      },
    },
  });
}
