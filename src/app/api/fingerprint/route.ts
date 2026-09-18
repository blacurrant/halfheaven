import { halfhellFetch } from "@/lib/halfhell";

export const runtime = "nodejs";
export const maxDuration = 300;

/**
 * BFF proxy: receives multipart `reference` from browser, forwards to
 * halfhell /v1/fingerprint with API-key auth. Keeps the same response
 * shape ({id}) so studio page doesn't need to change.
 */
export async function POST(req: Request) {
  const form = await req.formData();
  const file = form.get("reference");
  if (!(file instanceof File)) {
    return Response.json({ error: "No video supplied." }, { status: 400 });
  }
  const depth = String(form.get("depth") ?? "") === "1" ? "1" : "0";

  const forward = new FormData();
  forward.set("reference", file, file.name);
  forward.set("depth", depth);

  try {
    const res = await halfhellFetch("/v1/fingerprint", {
      method: "POST",
      body: forward,
      timeoutMs: 60_000,
    });
    const data = await res.json();
    return Response.json(data, { status: res.status, headers: { "X-Request-Id": res.headers.get("X-Request-Id") || "" } });
  } catch (e) {
    const err = e as Error & { status?: number; message: string };
    const status = err.status && err.status >= 400 ? err.status : 502;
    let msg = err.message || "Fingerprint failed";
    // If backend returned structured error, expose its message
    try {
      const j = JSON.parse(msg);
      if (j?.error?.message) msg = j.error.message;
    } catch {}
    return Response.json({ error: msg }, { status });
  }
}
