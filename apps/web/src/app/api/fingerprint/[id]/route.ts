import { readJob } from "@/lib/fingerprint";

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const job = readJob(id);
  if (!job) return Response.json({ error: "No such reading." }, { status: 404 });
  return Response.json(job);
}
