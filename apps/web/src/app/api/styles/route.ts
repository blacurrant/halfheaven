import { availableStyles } from "@/lib/pipeline";

export async function GET() {
  return Response.json({ styles: availableStyles() });
}
