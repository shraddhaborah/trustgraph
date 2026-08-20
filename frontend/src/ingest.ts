/**
 * Ingestion client.
 *
 * The old flow was one POST that stayed open until Claude finished. Codespaces
 * (and nginx, ALB, Cloudflare -- everything) kills idle connections around 60s,
 * which is where the 504 Gateway Timeout came from. Extraction over a real trust
 * document legitimately takes longer than that.
 *
 * New flow: POST returns a workflow_id in milliseconds, then we poll.
 */

export type IngestStatus =
  | { status: 'running'; progress?: number; detail?: string }
  | { status: 'completed'; result: TrustGraph }
  | { status: 'failed'; error: string; error_type?: string };

export interface TrustGraph {
  document_id: string;
  filename: string;
  trust_name: string | null;
  trust_type: string | null;
  execution_date: string | null;
  governing_law: string | null;
  nodes: Array<{ id: string; label: string; type: string; attributes?: Record<string, unknown> }>;
  edges: Array<{ source: string; target: string; relationship: string; evidence?: string }>;
  provisions: Array<{ title: string; summary: string; article: string | null }>;
  stats: {
    chunks_processed: number;
    input_tokens: number;
    output_tokens: number;
    node_count: number;
    edge_count: number;
  };
}

/**
 * In dev, the Vite proxy forwards /api to localhost:8000, so a relative URL works.
 * In production there is no proxy -- set VITE_API_BASE to your deployed API origin.
 */
const API_BASE = import.meta.env.VITE_API_BASE ?? '';

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body.detail ?? JSON.stringify(body);
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}

/**
 * Upload a PDF and resolve with the extracted graph.
 * @param onProgress called with 0..1 and a human-readable stage
 */
export async function ingestPdf(
  file: File,
  onProgress?: (progress: number, stage: string) => void,
  opts: { pollMs?: number; timeoutMs?: number; signal?: AbortSignal } = {},
): Promise<TrustGraph> {
  const { pollMs = 2000, timeoutMs = 15 * 60 * 1000, signal } = opts;

  const form = new FormData();
  form.append('file', file);

  onProgress?.(0, 'uploading');
  const start = await fetch(`${API_BASE}/api/ingest`, { method: 'POST', body: form, signal });
  if (!start.ok) throw new Error(await readError(start));

  const { workflow_id: workflowId } = (await start.json()) as { workflow_id: string };
  onProgress?.(0.05, 'queued');

  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (signal?.aborted) throw new DOMException('Ingestion cancelled', 'AbortError');
    await new Promise((r) => setTimeout(r, pollMs));

    const res = await fetch(`${API_BASE}/api/ingest/${encodeURIComponent(workflowId)}`, { signal });
    if (!res.ok) {
      // A transient proxy hiccup shouldn't abandon a workflow that's still running.
      if (res.status >= 500) continue;
      throw new Error(await readError(res));
    }

    const body = (await res.json()) as IngestStatus;
    if (body.status === 'completed') {
      onProgress?.(1, 'completed');
      return body.result;
    }
    if (body.status === 'failed') {
      throw new Error(body.error || 'Ingestion failed');
    }
    onProgress?.(body.progress ?? 0.1, body.detail ?? 'analyzing');
  }

  throw new Error('Ingestion timed out. Check the Temporal UI at http://localhost:8233');
}
