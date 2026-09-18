import { halfhellJSON } from "@/lib/halfhell";

export const runtime = "nodejs";

export async function GET() {
  try {
    const data = await halfhellJSON("/v1/demo", { timeoutMs: 8000 });
    return Response.json(data);
  } catch {
    return Response.json({ job: null });
  }
}
