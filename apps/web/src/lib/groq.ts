import fs from "node:fs";
import path from "node:path";
import { REPO } from "./pipeline";

/** The key lives in the repo's .env.local, which Next does not read from here. */
export function groqKey(): string {
  if (process.env.GROQ_API_KEY) return process.env.GROQ_API_KEY;
  const file = path.join(REPO, ".env.local");
  if (!fs.existsSync(file)) return "";
  const line = fs.readFileSync(file, "utf8").split("\n").find((l) => l.startsWith("GROQ_API_KEY="));
  return line ? line.split("=")[1].trim() : "";
}

export async function chatJSON(system: string, user: string) {
  const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: { Authorization: `Bearer ${groqKey()}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "openai/gpt-oss-120b",
      temperature: 0.3,
      max_tokens: 1200,
      reasoning_effort: "low",
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: system },
        { role: "user", content: user },
      ],
    }),
  });
  if (!res.ok) throw new Error(`groq ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const data = await res.json();
  return JSON.parse(data.choices[0].message.content);
}
