/**
 * halfhell client - BFF layer.
 *
 * Browser never sees HALFHELL_API_KEY. Every call in this module runs
 * on the Next.js server (api routes / server actions) and forwards to
 * the Python FastAPI backend (`halfhell`) with proper auth.
 *
 * Prod quality:
 * - API key from env (HALFHELL_API_KEY or HALFHELL_API_KEYS first entry)
 * - Base URL from HALFHELL_API_URL (default http://localhost:8000)
 * - Timeout per request, retries on 5xx, request-id propagation
 * - Consistent error envelope mapping
 * - No key ever returned to client
 *
 * Usage: import { halfhellFetch, getHalfhellConfig } from "@/lib/halfhell"
 */

const DEFAULT_TIMEOUT = 30_000; // ms for most calls; overridden for polls
const RETRY_ON = new Set([502, 503, 504]);

type HalfhellConfig = {
  url: string;
  key: string;
};

export function getHalfhellConfig(): HalfhellConfig {
  const rawUrl = process.env.HALFHELL_API_URL?.trim() || "http://localhost:8000";
  // Normalise: no trailing slash
  const url = rawUrl.replace(/\/+$/, "");
  // Support both HALFHELL_API_KEY and HALFHELL_API_KEYS (first entry)
  const rawKeys = process.env.HALFHELL_API_KEYS?.trim() || process.env.HALFHELL_API_KEY?.trim() || "";
  const key = rawKeys.split(",")[0]?.trim() || "";
  return { url, key };
}

/** Headers that must be sent to halfhell */
function authHeaders(key: string, extra?: HeadersInit): Headers {
  const h = new Headers(extra);
  if (key) {
    // Prefer X-API-Key (explicit) and also Bearer for compatibility
    h.set("X-API-Key", key);
    if (!h.has("Authorization")) h.set("Authorization", `Bearer ${key}`);
  }
  // Always request json unless caller overrides
  if (!h.has("Accept")) h.set("Accept", "application/json");
  return h;
}

/** Small helper to attach request-id if caller passed one */
function forwardHeaders(req?: Request): HeadersInit | undefined {
  if (!req) return undefined;
  const rid = req.headers.get("x-request-id") || req.headers.get("X-Request-Id");
  return rid ? { "X-Request-Id": rid } : undefined;
}

export type HalfhellError = {
  code: string;
  message: string;
  status: number;
  details?: unknown;
};

export async function halfhellFetch(
  path: string,
  opts: {
    method?: string;
    headers?: HeadersInit;
    body?: BodyInit | null;
    timeoutMs?: number;
    retries?: number;
    // When true, don't throw on non-2xx, return Response as-is (for streaming)
    rawResponse?: boolean;
    // Forward incoming request headers (e.g. Range, X-Request-Id)
    forwardFrom?: Request;
  } = {}
): Promise<Response> {
  const cfg = getHalfhellConfig();
  const url = `${cfg.url}${path.startsWith("/") ? path : `/${path}`}`;
  const timeout = opts.timeoutMs ?? DEFAULT_TIMEOUT;
  const maxRetries = opts.retries ?? 1;

  const headers = authHeaders(cfg.key, {
    ...forwardHeaders(opts.forwardFrom),
    ...(opts.headers || {}),
  });

  // Warn once if key missing (dev ergonomics)
  if (!cfg.key) {
    console.warn("[halfhell] HALFHELL_API_KEY is not set - requests will get 401");
  }

  let lastErr: Error | null = null;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(`timeout ${timeout}ms`), timeout);

    try {
      const res = await fetch(url, {
        method: opts.method || "GET",
        headers,
        body: opts.body ?? undefined,
        signal: controller.signal,
        // Next.js fetch caches by default; disable for backend
        cache: "no-store",
        // Ensure we propagate proxy headers
        // eslint-disable-next-line @typescript-eslint/ban-ts-comment
        // @ts-ignore next-specific
        next: { revalidate: 0 },
      });

      clearTimeout(t);

      // Retry on transient 5xx if we have retries left
      if (!res.ok && RETRY_ON.has(res.status) && attempt < maxRetries) {
        const backoff = 250 * Math.pow(2, attempt);
        await new Promise((r) => setTimeout(r, backoff));
        continue;
      }

      if (opts.rawResponse) return res;

      // Surface halfhell error envelope as thrown HalfhellError for callers to map
      if (!res.ok) {
        let body: unknown = null;
        try {
          body = await res.json();
        } catch {
          body = await res.text().catch(() => null);
        }
        const errObj = (body as { error?: { code?: string; message?: string; details?: unknown } })?.error;
        const msg =
          errObj?.message ||
          (typeof body === "string" ? body : `halfhell ${res.status}`) ||
          `halfhell ${res.status}`;
        const code = errObj?.code || `http_${res.status}`;
        // Copy request-id back to help debugging
        const rid = res.headers.get("x-request-id") || res.headers.get("X-Request-Id");
        const err = Object.assign(new Error(msg), {
          code,
          status: res.status,
          details: errObj?.details ?? body,
          requestId: rid,
        }) as Error & HalfhellError & { requestId?: string };
        throw err;
      }

      return res;
    } catch (e) {
      clearTimeout(t);
      lastErr = e as Error;
      // Don't retry on client errors (4xx) or abort
      const status = (e as { status?: number })?.status;
      if (status && status >= 400 && status < 500) throw e;
      if ((e as Error)?.name === "AbortError" || String(e).includes("timeout")) {
        if (attempt < maxRetries) {
          await new Promise((r) => setTimeout(r, 200 * (attempt + 1)));
          continue;
        }
        const te = new Error(`halfhell timeout after ${timeout}ms: ${url}`) as Error & HalfhellError;
        (te as HalfhellError).code = "timeout";
        (te as HalfhellError).status = 504;
        throw te;
      }
      if (attempt < maxRetries) {
        await new Promise((r) => setTimeout(r, 200 * (attempt + 1)));
        continue;
      }
      throw e;
    }
  }
  throw lastErr!;
}

/** Helper for JSON endpoints: fetch + parse */
export async function halfhellJSON<T>(
  path: string,
  opts: {
    method?: string;
    headers?: HeadersInit;
    body?: BodyInit | null;
    timeoutMs?: number;
    retries?: number;
    forwardFrom?: Request;
  } = {}
): Promise<T> {
  const res = await halfhellFetch(path, opts);
  const text = await res.text();
  if (!text) return {} as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as unknown as T;
  }
}

/** Proxy helper: fetch from halfhell and pipe to caller (for media/thumbs) */
export async function proxyToHalfhell(
  req: Request,
  halfhellPath: string,
  init?: { method?: string; body?: BodyInit | null }
): Promise<Response> {
  const cfg = getHalfhellConfig();
  const url = `${cfg.url}${halfhellPath}`;
  const headers = authHeaders(cfg.key);
  // Forward Range for media, Content-Type for posts, and request-id
  const range = req.headers.get("range");
  if (range) headers.set("Range", range);
  const reqId = req.headers.get("x-request-id") || req.headers.get("X-Request-Id");
  if (reqId) headers.set("X-Request-Id", reqId);

  // For multipart posts we must not set Content-Type manually (fetch will set boundary)
  // So only copy if not multipart
  if (init?.body && !(init.body instanceof FormData)) {
    const ct = req.headers.get("content-type");
    if (ct) headers.set("Content-Type", ct);
  }

  const res = await fetch(url, {
    method: init?.method || req.method,
    headers,
    body: init?.body ?? (["POST", "PUT", "PATCH"].includes(req.method) ? await req.arrayBuffer().then((b) => (b.byteLength ? b : undefined)) : undefined),
    cache: "no-store",
  });

  // Pipe headers back (important for Range/Content-Range, Content-Type, X-Request-Id)
  const outHeaders = new Headers();
  for (const [k, v] of res.headers.entries()) {
    // Allow-list to avoid leaking internal headers
    if (
      [
        "content-type",
        "content-length",
        "content-range",
        "accept-ranges",
        "cache-control",
        "x-request-id",
        "etag",
      ].includes(k.toLowerCase())
    ) {
      outHeaders.set(k, v);
    }
  }
  // Ensure X-Request-Id is present
  const rid = res.headers.get("x-request-id") || reqId;
  if (rid) outHeaders.set("X-Request-Id", rid);

  const body = res.body as unknown as BodyInit | null;
  return new Response(body, { status: res.status, headers: outHeaders });
}
