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
  referenceName?: string;
  referencePath?: string;
  targetName: string;
  /** The staged footage, so a re-run can reuse it instead of uploading again. */
  targetPaths?: string[];
  startedAt: number;
  finishedAt?: number;
  error?: string;
  log: string[];
  profile?: Record<string, unknown>;
  receipt?: Receipt;
  segments?: number;
  punchAt?: number[];
  clips?: { start: number; end: number }[];
  /** What each stage has reported so far, for the studio to say out loud. */
  facts?: Facts;
  /** When each stage began, in ms from the start of the job. */
  stageAt?: number[];
};

/** The pipeline's own report lines, read as they arrive. Nothing here is
 *  estimated: a fact exists only once the stage that owns it has printed it. */
export type Facts = {
  words?: number;
  sourceSeconds?: number;
  cuts?: number;
  wordsCut?: number;
  cards?: number;
  punches?: number;
  emphasised?: number;
  reframed?: boolean;
  /** Mean LAB of the footage, and of the reel it is being graded toward. */
  gradeFrom?: [number, number, number];
  gradeTo?: [number, number, number];
  subjectSeconds?: number;
  subjectMissing?: string;
  captionsMoved?: number;
  clips?: number;
  outputSeconds?: number;
  captions?: number;
};

const LAB = String.raw`\(([-\d.]+), ([-\d.]+), ([-\d.]+)\)`;
const FACTS: [RegExp, (m: RegExpExecArray, f: Facts) => void][] = [
  [new RegExp(`^grade LAB mean=${LAB}`), (m, f) => { f.gradeTo = [+m[1], +m[2], +m[3]]; }],
  [/^(\d+) words over ([\d.]+)s/, (m, f) => { f.words = +m[1]; f.sourceSeconds = +m[2]; }],
  [/^(\d+) cuts removing (\d+) words, (\d+) caption cards, (\d+) punch-ins, (\d+) emphasised words/,
    (m, f) => Object.assign(f, { cuts: +m[1], wordsCut: +m[2], cards: +m[3], punches: +m[4], emphasised: +m[5] })],
  [/^reframing /, (_m, f) => { f.reframed = true; }],
  [new RegExp(`^grade: target LAB mean=${LAB}`), (m, f) => { f.gradeFrom = [+m[1], +m[2], +m[3]]; }],
  [/^subject separated in (\d+)s/, (m, f) => { f.subjectSeconds = +m[1]; }],
  [/^no subject separation: (.*)/, (m, f) => { f.subjectMissing = m[1]; }],
  [/^captions \w+ the speaker: (\d+) moved/, (m, f) => { f.captionsMoved = +m[1]; }],
  [/^(\d+) clips, ([\d.]+)s \(from [\d.]+s\), (\d+) captions/,
    (m, f) => Object.assign(f, { clips: +m[1], outputSeconds: +m[2], captions: +m[3] })],
];

export function readFacts(line: string, facts: Facts) {
  const text = line.trim();
  for (const [pattern, take] of FACTS) {
    const m = pattern.exec(text);
    if (m) { take(m, facts); return; }
  }
}

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
export const listJobs = () => [...jobs.values()].sort((a, b) => b.startedAt - a.startedAt);
export const workDir = (id: string) => path.join(WORKROOT, id);

/** Jobs live in memory while this server runs, and on disk so an edit a page
 *  reopens after a restart still has its record. */
export function getJob(id: string): Job | undefined {
  const live = jobs.get(id);
  if (live || !/^[\w-]+$/.test(id)) return live;
  try {
    const job: Job = JSON.parse(fs.readFileSync(path.join(workDir(id), "job.json"), "utf8"));
    // Its process died with the server that ran it.
    if (job.status === "running") {
      Object.assign(job, { status: "error", error: "The server restarted mid-edit. Try again." });
    }
    jobs.set(id, job);
    return job;
  } catch { return undefined; }
}

function saveJob(job: Job) {
  try {
    fs.writeFileSync(path.join(workDir(job.id), "job.json"),
      JSON.stringify({ ...job, log: job.log.slice(-20) }));
  } catch { /* the in-memory copy still serves this run */ }
}

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

const PIPELINE_ENV = { ...process.env, PYTHONUNBUFFERED: "1", PYTHONPATH: path.join(REPO, "packages", "pipeline") };

// ---- versions -------------------------------------------------------------
// Every change a creator makes re-renders the edit in place. The version it
// replaces is kept first, so Undo is a file copy rather than another render,
// and a render that fails puts the old version straight back instead of
// leaving a program that no longer matches the video.

const KEEP_VERSIONS = 8;
const VERSIONED = ["out.mp4", "edit_program.json", "style_profile.json"];
const versionsDir = (id: string) => path.join(jobPaths(id).work, "versions");

function versions(id: string): number[] {
  try {
    return fs.readdirSync(versionsDir(id)).filter((n) => /^\d+$/.test(n)).map(Number).sort((a, b) => a - b);
  } catch { return []; }
}

function keepVersion(id: string): boolean {
  if (id === "demo") return false;   // the demo points at the repo's own files
  const { work } = jobPaths(id);
  const kept = versions(id);
  const at = path.join(versionsDir(id), String((kept.at(-1) ?? 0) + 1));
  fs.mkdirSync(at, { recursive: true });
  for (const name of VERSIONED) {
    const from = path.join(work, name);
    if (fs.existsSync(from)) fs.copyFileSync(from, path.join(at, name));
  }
  for (const old of kept.slice(0, Math.max(0, kept.length + 1 - KEEP_VERSIONS))) {
    fs.rmSync(path.join(versionsDir(id), String(old)), { recursive: true, force: true });
  }
  return true;
}

/** Put the most recent kept version back. False when there is none. */
function restoreVersion(id: string): boolean {
  const latest = versions(id).at(-1);
  if (latest === undefined) return false;
  const { work } = jobPaths(id);
  const at = path.join(versionsDir(id), String(latest));
  for (const name of VERSIONED) {
    const from = path.join(at, name);
    if (fs.existsSync(from)) fs.copyFileSync(from, path.join(work, name));
  }
  fs.rmSync(at, { recursive: true, force: true });
  return true;
}

export const undoCount = (id: string) => versions(id).length;

// One change at a time per edit: two renders writing the same out.mp4 would
// leave whichever finished last, and a program that describes the other.
const applying = new Set<string>();
export const isApplying = (id: string) => applying.has(id);
export const BUSY = -1;

/** Re-render an edit in place with `halfheaven.recut` and the given flags. */
export async function runRecut(id: string, args: string[]): Promise<{ code: number; err: string }> {
  if (applying.has(id)) return { code: BUSY, err: "Another change is still applying." };
  applying.add(id);
  try {
    const { program, out, work } = jobPaths(id);
    const kept = keepVersion(id);
    const result = await new Promise<{ code: number; err: string }>((resolve) => {
      let err = "";
      const child = spawn(PYTHON,
        ["-u", "-m", "halfheaven.recut", "--program", program, "--out", out, "--work", work, ...args],
        { cwd: REPO, env: PIPELINE_ENV });
      child.stderr.on("data", (b) => (err += b.toString()));
      child.on("close", (code) => resolve({ code: code ?? 1, err }));
    });
    if (result.code !== 0 && kept) restoreVersion(id);
    return result;
  } finally {
    applying.delete(id);
  }
}

/** Step back one change. */
export function undo(id: string): { ok: boolean; left: number; error?: string } {
  if (applying.has(id)) return { ok: false, left: undoCount(id), error: "A change is still applying." };
  const ok = restoreVersion(id);
  return { ok, left: undoCount(id), error: ok ? undefined : "Nothing to undo." };
}

// ---- look previews ----------------------------------------------------------

export type LookPreview = { id: string; label: string; blurb: string; file: string };

/** A still of every caption look on this edit, drawn by the real renderer.
 *  Redrawn only when the program has changed since the last set. */
export async function lookPreviews(id: string): Promise<{ looks: LookPreview[]; version: number }> {
  const { program, work } = jobPaths(id);
  const dir = path.join(work, "previews");
  const version = Math.round(fs.statSync(program).mtimeMs);
  const manifest = path.join(dir, "manifest.json");
  try {
    const kept = JSON.parse(fs.readFileSync(manifest, "utf8"));
    if (kept.version === version) return kept;
  } catch { /* none yet */ }

  const looks = await new Promise<LookPreview[]>((resolve, reject) => {
    let out = "", err = "";
    const child = spawn(PYTHON,
      ["-m", "halfheaven.previews", "--program", program, "--work", work, "--out-dir", dir],
      { cwd: REPO, env: PIPELINE_ENV });
    child.stdout.on("data", (b) => (out += b.toString()));
    child.stderr.on("data", (b) => (err += b.toString()));
    child.on("close", (code) => {
      try { if (code === 0) return resolve(JSON.parse(out.trim().split("\n").pop() || "[]")); } catch { /* below */ }
      reject(new Error(err.trim().split("\n").pop() || `previews exited ${code}`));
    });
  });
  fs.writeFileSync(manifest, JSON.stringify({ looks, version }));
  return { looks, version };
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
  styleId?: string;
  /** An uploaded reel to copy. Takes precedence over `styleId`. */
  referencePath?: string;
  referenceName?: string;
  targetPaths: string[];
  targetName: string;
  overrides?: Record<string, unknown>;
}): Promise<Job> {
  const id = randomUUID().slice(0, 8);
  const dir = workDir(id);
  fs.mkdirSync(dir, { recursive: true });

  // The CLI has always taken any file as its reference; only this app insisted
  // on a fixed menu. An uploaded reel is the ordinary case now, and the baked
  // styles are what someone gets for having nothing to point at.
  const style = availableStyles().find((s) => s.id === opts.styleId);
  const reference = opts.referencePath ?? path.join(REPO, (style ?? availableStyles()[0]).file);
  const referenceName = opts.referenceName ?? style?.name ?? availableStyles()[0]?.name ?? "reference";
  const out = path.join(dir, "out.mp4");

  const job: Job = {
    id,
    status: "running",
    stageIndex: 0,
    progress: 0.08, // never start at zero
    styleId: style?.id ?? "uploaded",
    referenceName,
    referencePath: reference,
    targetName: opts.targetName,
    targetPaths: opts.targetPaths,
    startedAt: Date.now(),
    log: [],
    facts: {},
    stageAt: [0],
  };
  jobs.set(id, job);
  saveJob(job);

  const child = spawn(
    PYTHON,
    // -u: Python block-buffers stdout when it is piped rather than attached to a
    // TTY, so without this every stage line arrives at once on exit and the
    // progress UI sits at its starting value until the job is already finished.
    ["-u", "-m", "halfheaven.cli", "--reference", reference, "--target", ...opts.targetPaths,
     "--out", out, "--work", dir,
     // the reading step already measured this reference; reuse it
     ...(fs.existsSync(`${reference}.fingerprint.json`)
       ? ["--fingerprint", `${reference}.fingerprint.json`] : []),
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
        job.stageAt![stage] = Date.now() - job.startedAt;
      } else {
        readFacts(line, job.facts!);
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
      saveJob(job);
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
      // The look this edit was first made with, so "Matched" can bring it back
      // after any other look has replaced it.
      fs.copyFileSync(path.join(dir, "style_profile.json"), path.join(dir, "style_profile.matched.json"));
    } catch (e) {
      job.status = "error";
      job.error = `finished but produced no readable program: ${(e as Error).message}`;
    }
    saveJob(job);
  });

  return job;
}
