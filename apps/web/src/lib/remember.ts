/** What the studio keeps in this browser so a refresh lands back where it was.
 *
 * Only small things go here: ids the server can answer for, choices, the chat.
 * The videos themselves stay on the server, which already keeps every render
 * on disk. Storage can be missing or full (private windows, cleared site data),
 * so every call is allowed to fail and the page simply starts fresh. */

const PREFIX = "hh.";

export function recall<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch { return null; }
}

export function remember(key: string, value: unknown) {
  try { localStorage.setItem(PREFIX + key, JSON.stringify(value)); } catch { /* the choice lasts this visit */ }
}

export function forget(key: string) {
  try { localStorage.removeItem(PREFIX + key); } catch { /* nothing to clear */ }
}

/** Drop everything remembered about one edit, e.g. when starting over. */
export function forgetJob(jobId: string) {
  forget(`captions.${jobId}`);
  forget(`type.${jobId}`);
}
