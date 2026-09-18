import { halfhellFetch } from "@/lib/halfhell";

export const runtime = "nodejs";
export const maxDuration = 300;

export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  // Browser sends multipart with `track` file or `remove=1`
  const form = await req.formData();
  // Re-forward as-is to halfhell (keeps file boundary)
  const forward = new FormData();
  const track = form.get("track");
  if (track instanceof File) forward.set("track", track, track.name);
  const remove = form.get("remove");
  if (remove !== null) forward.set("remove", String(remove));

  if (!(track instanceof File) && String(remove) !== "1") {
    return Response.json({ error: "No track supplied." }, { status: 400 });
  }

  try {
    const res = await halfhellFetch(`/v1/jobs/${encodeURIComponent(id)}/music`, {
      method: "POST",
      body: forward,
      timeoutMs: 120_000,
    });
    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch (e) {
    const err = e as Error & { status?: number; message: string };
    const status = err.status || 500;
    return Response.json({ error: err.message || "That track didn't mix. Try an mp3 or m4a." }, { status });
  }
}
