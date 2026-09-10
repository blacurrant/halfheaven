import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

/** Repo root, two levels up from apps/web. */
export const REPO = path.resolve(process.cwd(), "..", "..");
const PYTHON = path.join(REPO, ".venv", "bin", "python");
const WORKROOT = path.join(REPO, ".web-work");

export type StageKey = "analyse" | "transcribe" | "edit" | "plan" | "render";

export const STAGES: { key: StageKey; label: string }[] = [
  { key: "analyse", label: "Reading the reference" },
  { key: "transcribe", label: "Transcribing" },
  { key: "edit", label: "Editorial pass" },
  { key: "plan", label: "Planning the cut" },
  { key: "render", label: "Rendering" },
];

export type Job = {
  id: string;
  status: "running" | "done" | "error";
  stageIndex: number;
  progress: number;
  styleId: string;
  targetName: string;
  startedAt: number;
  finishedAt?: number;
  error?: string;
  log: string[];
  profile?: Record<string, unknown>;
  receipt?: Receipt;
  segments?: number;
  punchAt?: number[];
  clips?: { start: number; end: number }[];
};

export type Receipt = {
  clips: number;
  captions: number;
  emphasised: number;
  punches: number;
  wordsCut: number;
  sourceSeconds: number;
  outputSeconds: number;
  emphasisWords: string[];
};

const jobs = new Map<string, Job>();
export const getJob = (id: string) => jobs.get(id);
export const listJobs = () => [...jobs.values()].sort((a, b) => b.startedAt - a.startedAt);
export const workDir = (id: string) => path.join(WORKROOT, id);

/** Where a job's document and output live. The seeded demo points at the
 *  repo's own last render so the studio opens on something real. */
export function jobPaths(id: string) {
  if (id === "demo") {
    return { program: path.join(REPO, "work", "edit_program.json"),
             out: path.join(REPO, "styled.mp4"),
             work: path.join(REPO, "work") };
  }
  const dir = workDir(id);
  return { program: path.join(dir, "edit_program.json"),
           out: path.join(dir, "out.mp4"), work: dir };
}

/** Re-render after a caption fix. Deliberately not the pipeline:
 *  re-transcribing would discard the correction that prompted it. */
export function recut(id: string, edits: unknown[]): Promise<void> {
  const { program, out, work } = jobPaths(id);
  return new Promise((resolve, reject) => {
    const child = spawn(
      PYTHON,
      ["-u", "-m", "halfheaven.recut", "--program", program,
       "--out", out, "--work", work, "--edits", JSON.stringify(edits)],
      { cwd: REPO, env: { ...process.env, PYTHONUNBUFFERED: "1",
                          PYTHONPATH: path.join(REPO, "packages", "pipeline") } }
    );
    let err = "";
    child.stderr.on("data", (b) => (err += b.toString()));
    child.on("close", (code) =>
      code === 0 ? resolve() : reject(new Error(err.slice(-400) || `recut exited ${code}`)));
  });
}

/** Reference videos available as styles. Real files, real cached profiles. */
export type Style = { id: string; name: string; file: string; hint: string };
export const STYLES: Style[] = [
  { id: "night-interview", name: "Night Interview", file: "edited.mp4", hint: "mono + didone" },
  { id: "street-montage", name: "Street Montage", file: "insta.mp4", hint: "montage, no speech" },
];

export function availableStyles() {
  return STYLES.filter((s) => fs.existsSync(path.join(REPO, s.file)));
}

/** The CLI prints "[n/5] label"; that is the honest progress signal. */
function parseStage(line: string): number | null {
  const m = /^\[(\d)\/5\]/.exec(line.trim());
  return m ? Number(m[1]) - 1 : null;
}

export async function startJob(opts: {
  styleId: string;
  targetPath: string;
  targetName: string;
  overrides?: Record<string, unknown>;
}): Promise<Job> {
  const id = randomUUID().slice(0, 8);
  const dir = workDir(id);
  fs.mkdirSync(dir, { recursive: true });

  const style = availableStyles().find((s) => s.id === opts.styleId) ?? availableStyles()[0];
  const reference = path.join(REPO, style.file);
  const out = path.join(dir, "out.mp4");

  const job: Job = {
    id,
    status: "running",
    stageIndex: 0,
    progress: 0.08, // never start at zero
    styleId: style.id,
    targetName: opts.targetName,
    startedAt: Date.now(),
    log: [],
  };
  jobs.set(id, job);

  const child = spawn(
    PYTHON,
    // -u: Python block-buffers stdout when it is piped rather than attached to a
    // TTY, so without this every stage line arrives at once on exit and the
    // progress UI sits at its starting value until the job is already finished.
    ["-u", "-m", "halfheaven.cli", "--reference", reference, "--target", opts.targetPath,
     "--out", out, "--work", dir,
     ...(opts.overrides && Object.keys(opts.overrides).length
       ? ["--overrides", JSON.stringify(opts.overrides)] : [])],
    { cwd: REPO, env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONPATH: path.join(REPO, "packages", "pipeline") } }
  );

  const absorb = (buf: Buffer) => {
    for (const line of buf.toString().split("\n")) {
      if (!line.trim()) continue;
      job.log.push(line);
      const stage = parseStage(line);
      if (stage !== null) {
        job.stageIndex = stage;
        job.progress = 0.08 + (0.9 * stage) / STAGES.length;
      }
    }
  };
  child.stdout.on("data", absorb);
  child.stderr.on("data", absorb);

  child.on("close", (code) => {
    job.finishedAt = Date.now();
    if (code !== 0) {
      job.status = "error";
      job.error = job.log.filter((l) => /error|Error|Traceback|no audio/i.test(l)).slice(-2).join(" ")
        || `pipeline exited ${code}`;
      return;
    }
    try {
      job.profile = JSON.parse(fs.readFileSync(path.join(dir, "style_profile.json"), "utf8"));
      const prog = JSON.parse(fs.readFileSync(path.join(dir, "edit_program.json"), "utf8"));
      const runs = prog.captions.flatMap((c: { runs: { text: string; style: string }[] }) => c.runs);
      const emph = runs.filter((r: { style: string }) => r.style === "emphasis");
      const outSecs = prog.video.reduce(
        (a: number, c: { start: number; end: number }) => a + (c.end - c.start), 0);
      const punchAt: number[] = prog.video
        .map((c: { scale_to?: number }, i: number) => (c.scale_to ? i : -1))
        .filter((i: number) => i >= 0);
      job.segments = prog.video.length;
      job.punchAt = punchAt;
      job.clips = prog.video.map((c: { start: number; end: number }) => ({ start: c.start, end: c.end }));
      job.receipt = {
        clips: prog.video.length,
        captions: prog.captions.length,
        emphasised: emph.length,
        punches: punchAt.length,
        wordsCut: Number(/removing (\d+) words/.exec(job.log.join(" "))?.[1] ?? 0),
        sourceSeconds: Number(/over ([\d.]+)s/.exec(job.log.join(" "))?.[1] ?? 0),
        outputSeconds: outSecs,
        emphasisWords: [...new Set(emph.map((r: { text: string }) => r.text))].slice(0, 8) as string[],
      };
      job.status = "done";
      job.progress = 1;
    } catch (e) {
      job.status = "error";
      job.error = `finished but produced no readable program: ${(e as Error).message}`;
    }
  });

  return job;
}
