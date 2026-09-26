import fs from "node:fs";
import path from "node:path";
import { REPO } from "./pipeline";

/** Jev, TypeSafe's decision model: typed answers with probabilities, no text.
 *  Pinned to one release so its probabilities stay comparable across runs. */
export const JEV = process.env.OPENROUTER_JEV_MODEL?.trim() || "typesafe/jev-1.13";
/** Jev Router: a chat model that routes each request to the model it judges best. */
export const JEV_CHAT = process.env.OPENROUTER_CHAT_MODEL?.trim() || "typesafe/jev-router";
/** Jev Router routes through Jev, so when Jev is down the chat is too; this
 *  one keeps the conversation going, and the reply says which model wrote it. */
export const CHAT_FALLBACK = process.env.OPENROUTER_CHAT_FALLBACK?.trim() || "google/gemini-3.8-flash";

/** A real environment variable wins; the repo's .env.local is the local
 *  convenience, and Next does not read it from this directory. */
export function openrouterKey(): string {
  const fromEnv = process.env.OPENROUTER_API_KEY?.trim();
  if (fromEnv) return fromEnv;
  const file = path.join(REPO, ".env.local");
  if (!fs.existsSync(file)) return "";
  const line = fs.readFileSync(file, "utf8").split("\n").find((l) => l.startsWith("OPENROUTER_API_KEY="));
  return line ? line.split("=")[1].trim() : "";
}

export type Choice = {
  type: "choice"; choice: string; confidence: number; probabilities: Record<string, number>;
};
export type Noul = { type: "noul"; noul: number };
export type Answer = Choice | Noul;

export type Question =
  | { type: "choice"; instructions: string; criteria: Record<string, string> }
  | { type: "noul"; instructions: string; criteria: { true: string; false: string } };

/** One Decisions call: every question is answered in parallel against the same state. */
export async function decide(
  state: Record<string, unknown>, questions: Record<string, Question>, signal?: AbortSignal,
) {
  const res = await fetch("https://openrouter.ai/api/alpha/decisions", {
    method: "POST",
    headers: { Authorization: `Bearer ${openrouterKey()}`, "Content-Type": "application/json" },
    body: JSON.stringify({ model: JEV, state, questions }),
    signal,
  });
  if (!res.ok) throw new Error(`jev ${res.status}: ${(await res.text()).slice(0, 200)}`);
  const data = await res.json();
  return {
    answers: data.answers as Record<string, Answer>,
    model: String(data.model ?? JEV),
    cost: Number(data.usage?.cost ?? 0),
  };
}

export async function chatJSON(system: string, user: string) {
  let last = "";
  for (const model of [JEV_CHAT, CHAT_FALLBACK]) {
    const res = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: { Authorization: `Bearer ${openrouterKey()}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model,
        max_tokens: 1400,
        response_format: { type: "json_object" },
        messages: [
          { role: "system", content: system },
          { role: "user", content: user },
        ],
      }),
    });
    if (!res.ok) { last = `${model} ${res.status}: ${(await res.text()).slice(0, 200)}`; continue; }
    const data = await res.json();
    const raw = String(data.choices?.[0]?.message?.content ?? "");
    // Routed models don't all honour response_format; take the outermost object.
    const json = raw.slice(raw.indexOf("{"), raw.lastIndexOf("}") + 1);
    try {
      return { out: JSON.parse(json), model: String(data.model ?? model), cost: Number(data.usage?.cost ?? 0) };
    } catch { last = `${model}: reply was not JSON`; }
  }
  throw new Error(last);
}
