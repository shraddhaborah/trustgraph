import type { TrustGraph } from './ingest';

/**
 * Client-side fixture, mirroring backend/activities.py::_demo_graph.
 *
 * Used when the app is built without VITE_API_BASE (e.g. the static Vercel
 * deploy). Lets the whole UI -- upload, progress, graph, inspector -- be
 * exercised with no backend, no Temporal, and no API key.
 *
 * Keep this in sync with the Python fixture so the demo matches the real thing.
 */
export function demoGraph(filename: string): TrustGraph {
  return {
    document_id: 'demo-c3557249-c58b-4850-a4e3-a96feff6fd0c',
    filename,
    trust_name: 'The Jane A. Doe Irrevocable Life Insurance Trust',
    trust_type: 'ILIT (Irrevocable Life Insurance Trust)',
    execution_date: 'March 14, 2019',
    governing_law: 'State of New York',
    nodes: [
      { id: 'jane_a_doe', label: 'Jane A. Doe', type: 'grantor', attributes: { role: 'Settlor and insured' } },
      { id: 'ilit', label: 'Doe ILIT', type: 'trust', attributes: {} },
      { id: 'first_national', label: 'First National Trust Co.', type: 'trustee', attributes: { capacity: 'Corporate trustee' } },
      { id: 'michael_doe', label: 'Michael Doe', type: 'successor_trustee', attributes: {} },
      { id: 'sarah_doe', label: 'Sarah Doe', type: 'beneficiary', attributes: { relationship: 'Daughter' } },
      { id: 'thomas_doe', label: 'Thomas Doe', type: 'beneficiary', attributes: { relationship: 'Son' } },
      { id: 'doe_foundation', label: 'Doe Family Foundation', type: 'contingent_beneficiary', attributes: {} },
      { id: 'policy', label: 'Term Life Policy #4471-B', type: 'asset', attributes: { face_value: '$2,000,000' } },
    ],
    edges: [
      { source: 'jane_a_doe', target: 'ilit', relationship: 'settles', evidence: 'Grantor hereby establishes this Trust' },
      { source: 'first_national', target: 'ilit', relationship: 'serves_as_trustee', evidence: 'shall serve as initial Trustee' },
      { source: 'michael_doe', target: 'first_national', relationship: 'succeeds_trustee', evidence: 'upon resignation of the Trustee' },
      { source: 'ilit', target: 'sarah_doe', relationship: 'distributes_to', evidence: "in equal shares to the Grantor's children" },
      { source: 'ilit', target: 'thomas_doe', relationship: 'distributes_to', evidence: "in equal shares to the Grantor's children" },
      { source: 'ilit', target: 'doe_foundation', relationship: 'remainder_to', evidence: 'if no issue survive' },
      { source: 'ilit', target: 'policy', relationship: 'owns', evidence: 'Trustee shall hold the Policy' },
    ],
    provisions: [
      {
        title: 'Crummey withdrawal rights',
        summary:
          'Beneficiaries may withdraw contributions within 30 days of notice, qualifying gifts for the annual exclusion.',
        article: 'IV',
      },
      {
        title: 'Spendthrift clause',
        summary: 'Beneficial interests cannot be assigned or reached by creditors before distribution.',
        article: 'VII',
      },
      {
        title: 'Trustee removal',
        summary: 'A majority of adult beneficiaries may remove the corporate trustee and appoint a successor.',
        article: 'IX',
      },
    ],
    stats: {
      chunks_processed: 1,
      input_tokens: 0,
      output_tokens: 0,
      node_count: 8,
      edge_count: 7,
    },
  };
}

/** Fake the real pipeline's timing so the progress bar behaves as it does live. */
export async function runDemoIngest(
  file: File,
  onProgress?: (progress: number, stage: string) => void,
): Promise<TrustGraph> {
  const steps: Array<[number, string, number]> = [
    [0.05, 'queued', 500],
    [0.15, 'extracting text', 900],
    [0.45, 'analyzing (1 chunk)', 1100],
    [0.9, 'analyzing (1 chunk)', 900],
    [0.95, 'persisting', 400],
  ];

  for (const [progress, stage, delay] of steps) {
    onProgress?.(progress, stage);
    await new Promise((r) => setTimeout(r, delay));
  }

  onProgress?.(1, 'completed');
  return demoGraph(file.name);
}