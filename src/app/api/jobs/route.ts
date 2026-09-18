import { halfhellFetch } from "@/lib/halfhell";

export const runtime = "nodejs";
export const maxDuration = 300;

/**
 * BFF proxies for jobs:
 * GET  -> list (halfhell /v1/jobs)
 * POST -> create (halfhell /v1/jobs), forwarding multipart with API key.
 *
 * Legacy browser sends: target (File, one or many), styleId, referencePath,
 * referenceName, overrides (json). For split we prefer fingerprint_id but we
 * keep legacy fields: if referencePath is empty we still forward; halfhell
 * will resolve styleId or require fingerprint.
 *
 * We forward exactly what browser sent plus we also forward a reference file
 * if browser happened to send one under key `reference` (some flows do).
 */

export async function GET() {
  try {
    const { halfhellJSON } = await import("@/lib/halfhell");
    const data = await halfhellJSON<{ jobs: unknown }>("/v1/jobs", { timeoutMs: 8000 });
    return Response.json(data);
  } catch (e) {
    const err = e as Error & { status?: number };
    return Response.json({ jobs: [] }, { status: err.status === 401 ? 502 : 200 });
  }
}

export async function POST(req: Request) {
  // Browser sends multipart via studio page
  const form = await req.formData();

  // Re-build FormData for halfhell, preserving all fields
  const forward = new FormData();

  // Targets: browser appends multiple `target` entries
  const targets = form.getAll("target").filter((f): f is File => f instanceof File);
  for (const t of targets) forward.append("target", t, t.name);

  // Also accept `targets` key if some caller uses it
  for (const t of form.getAll("targets").filter((f): f is File => f instanceof File)) {
    forward.append("target", t, t.name);
  }

  // Reference file if present (browser could send reference directly)
  const refFile = form.get("reference");
  if (refFile instanceof File) forward.set("reference", refFile, refFile.name);

  // Scalar fields
  for (const k of ["styleId", "referencePath", "referenceName", "overrides", "reference_id", "fingerprint_id"]) {
    const v = form.get(k);
    if (v !== null) forward.set(k, String(v));
  }
  // Ensure overrides is at least "{}"
  if (!forward.has("overrides")) forward.set("overrides", "{}");

  if (!targets.length) {
    return Response.json({ error: "No video supplied." }, { status: 400 });
  }

  try {
    const res = await halfhellFetch("/v1/jobs", {
      method: "POST",
      body: forward,
      timeoutMs: 60_000,
    });
    const data = await res.json();
    const rid = res.headers.get("X-Request-Id");
    return Response.json(data, { status: res.status, headers: rid ? { "X-Request-Id": rid } : {} });
  } catch (e) {
    const err = e as Error & { status?: number; message: string };
    const status = err.status && err.status >= 400 ? err.status : 502;
    let msg = err.message || "Job creation failed";
    try {
      const j = JSON.parse(msg);
      if (j?.error?.message) msg = j.error.message;
    } catch {}
    return Response.json({ error: msg }, { status });
  }
}
