import fs from "node:fs";
import path from "node:path";

import { REPO } from "@/lib/pipeline";

/** The landing page's waitlist. One JSON line per person, kept in the working
 *  folder the pipeline already uses - nothing leaves the machine until there
 *  is a real mailing provider to hand it to. */
const FILE = path.join(REPO, ".web-work", "waitlist.jsonl");
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const ROLES = new Set(["creator", "editor", "brand"]);
const SPEND = new Set(["self", "under-5k", "5-15k", "15-30k", "30k-plus"]);

const known = (email: string) => {
  if (!fs.existsSync(FILE)) return false;
  return fs.readFileSync(FILE, "utf8").split("\n").some((line) => {
    try { return JSON.parse(line).email === email; } catch { return false; }
  });
};

export async function POST(req: Request) {
  const body = await req.json().catch(() => null);
  const email = String(body?.email ?? "").trim().toLowerCase();
  if (email.length > 254 || !EMAIL.test(email)) {
    return Response.json({ error: "That email doesn’t look right." }, { status: 400 });
  }
  // Signing up twice is not an error to the person doing it.
  if (known(email)) return Response.json({ ok: true, already: true });

  const entry = {
    email,
    handle: String(body?.handle ?? "").trim().slice(0, 80),
    role: ROLES.has(body?.role) ? body.role : "creator",
    spend: SPEND.has(body?.spend) ? body.spend : "",
    at: new Date().toISOString(),
  };
  fs.mkdirSync(path.dirname(FILE), { recursive: true });
  fs.appendFileSync(FILE, JSON.stringify(entry) + "\n");
  return Response.json({ ok: true });
}
