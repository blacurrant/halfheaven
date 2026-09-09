import { getJob } from "@/lib/pipeline";

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const job = getJob(id);
  if (!job) return Response.json({ error: "No such job." }, { status: 404 });
  const { log, ...rest } = job;
  return Response.json({ ...rest, tail: log.slice(-6) });
}
