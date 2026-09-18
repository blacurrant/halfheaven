/**
 * groq.ts — deprecated on frontend.
 *
 * Halfhell backend now owns all Groq calls (ASR / chat / vision) using its
 * own GROQ_API_KEY. Frontend chat route proxies to halfhell /v1/chat.
 * This shim remains so legacy imports don't break, but it throws if used.
 */

export function groqKey(): string {
  // Frontend no longer needs the key; expose a soft fallback for dev warnings
  return process.env.GROQ_API_KEY?.trim() || "";
}

export async function chatJSON(): Promise<never> {
  throw new Error("chatJSON is deprecated on frontend - POST /api/chat proxies to halfhell /v1/chat");
}
