import { useMemo, useState } from 'react';
import type { TrustGraph } from './ingest';

/** Role colors. Keys are the node `type` values the extractor emits. */
const ROLE_COLOR: Record<string, string> = {
  grantor: '#c2410c',
  trustee: '#1d4ed8',
  successor_trustee: '#60a5fa',
  beneficiary: '#047857',
  contingent_beneficiary: '#34d399',
  trust: '#7c3aed',
  entity: '#a16207',
  asset: '#0f766e',
  other: '#64748b',
};

const colorFor = (t?: string) => ROLE_COLOR[t ?? 'other'] ?? ROLE_COLOR.other;
const prettyRole = (t?: string) => (t ?? 'other').replace(/_/g, ' ');

interface Props {
  graph: TrustGraph;
}

export function TrustGraphView({ graph }: Props) {
  const [selected, setSelected] = useState<string | null>(null);

  // Deterministic radial layout -- no physics sim, no extra dependencies.
  // The trust (or the first grantor) anchors the center; everyone else rings it.
  const layout = useMemo(() => {
    const nodes = graph.nodes ?? [];
    if (nodes.length === 0) return { positions: {} as Record<string, { x: number; y: number }>, w: 800, h: 500 };

    const centerIdx = Math.max(
      0,
      nodes.findIndex((n) => n.type === 'trust' || n.type === 'grantor'),
    );
    const w = 820;
    const h = Math.max(460, 300 + nodes.length * 12);
    const cx = w / 2;
    const cy = h / 2;
    const radius = Math.min(cx, cy) - 90;

    const positions: Record<string, { x: number; y: number }> = {};
    const others = nodes.filter((_, i) => i !== centerIdx);

    positions[nodes[centerIdx].id] = { x: cx, y: cy };
    others.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / Math.max(others.length, 1) - Math.PI / 2;
      positions[n.id] = {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
      };
    });

    return { positions, w, h };
  }, [graph.nodes]);

  const nodeById = useMemo(
    () => Object.fromEntries((graph.nodes ?? []).map((n) => [n.id, n])),
    [graph.nodes],
  );

  const edges = (graph.edges ?? []).filter(
    (e) => layout.positions[e.source] && layout.positions[e.target],
  );

  const selectedNode = selected ? nodeById[selected] : null;
  const selectedEdges = selected
    ? edges.filter((e) => e.source === selected || e.target === selected)
    : [];

  if (!graph.nodes?.length) {
    return (
      <div className="panel">
        <p className="err-title">No parties found</p>
        <p className="err-body">
          The document was read, but no trust parties were extracted. It may be an exhibit,
          a cover page, or a scan without a text layer.
        </p>
      </div>
    );
  }

  return (
    <div className="graph-wrap">
      <section className="meta">
        <h2>{graph.trust_name ?? graph.filename}</h2>
        <dl>
          {graph.trust_type && (
            <div>
              <dt>Type</dt>
              <dd>{graph.trust_type}</dd>
            </div>
          )}
          {graph.execution_date && (
            <div>
              <dt>Executed</dt>
              <dd>{graph.execution_date}</dd>
            </div>
          )}
          {graph.governing_law && (
            <div>
              <dt>Governing law</dt>
              <dd>{graph.governing_law}</dd>
            </div>
          )}
          <div>
            <dt>Parties</dt>
            <dd>{graph.stats.node_count}</dd>
          </div>
          <div>
            <dt>Relationships</dt>
            <dd>{graph.stats.edge_count}</dd>
          </div>
        </dl>
      </section>

      <section className="canvas">
        <svg viewBox={`0 0 ${layout.w} ${layout.h}`} className="graph-svg" role="img"
             aria-label="Trust relationship diagram">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5"
                    markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
            </marker>
          </defs>

          {edges.map((e, i) => {
            const a = layout.positions[e.source];
            const b = layout.positions[e.target];
            const active = selected === e.source || selected === e.target;
            const mx = (a.x + b.x) / 2;
            const my = (a.y + b.y) / 2;
            return (
              <g key={i} opacity={selected && !active ? 0.15 : 1}>
                <line
                  x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke={active ? '#334155' : '#cbd5e1'}
                  strokeWidth={active ? 2 : 1.25}
                  markerEnd="url(#arrow)"
                />
                {active && (
                  <text x={mx} y={my - 6} className="edge-label" textAnchor="middle">
                    {e.relationship.replace(/_/g, ' ')}
                  </text>
                )}
              </g>
            );
          })}

          {(graph.nodes ?? []).map((n) => {
            const p = layout.positions[n.id];
            if (!p) return null;
            const isSel = selected === n.id;
            return (
              <g
                key={n.id}
                transform={`translate(${p.x},${p.y})`}
                onClick={() => setSelected(isSel ? null : n.id)}
                className="node"
              >
                <circle
                  r={isSel ? 26 : 20}
                  fill={colorFor(n.type)}
                  stroke={isSel ? '#0f172a' : '#fff'}
                  strokeWidth={isSel ? 3 : 2}
                />
                <text y={38} textAnchor="middle" className="node-label">
                  {n.label}
                </text>
                <text y={52} textAnchor="middle" className="node-role">
                  {prettyRole(n.type)}
                </text>
              </g>
            );
          })}
        </svg>

        {selectedNode && (
          <aside className="inspector">
            <h3>{selectedNode.label}</h3>
            <span className="chip" style={{ background: colorFor(selectedNode.type) }}>
              {prettyRole(selectedNode.type)}
            </span>
            {selectedEdges.length > 0 && (
              <ul className="rel-list">
                {selectedEdges.map((e, i) => {
                  const outgoing = e.source === selectedNode.id;
                  const other = nodeById[outgoing ? e.target : e.source];
                  return (
                    <li key={i}>
                      <span className="rel">{e.relationship.replace(/_/g, ' ')}</span>{' '}
                      {outgoing ? '→' : '←'} <strong>{other?.label ?? '?'}</strong>
                      {e.evidence && <em className="evidence">“{e.evidence}”</em>}
                    </li>
                  );
                })}
              </ul>
            )}
            <button onClick={() => setSelected(null)}>Clear selection</button>
          </aside>
        )}
      </section>

      <section className="legend">
        {Array.from(new Set((graph.nodes ?? []).map((n) => n.type))).map((t) => (
          <span key={t} className="legend-item">
            <i style={{ background: colorFor(t) }} /> {prettyRole(t)}
          </span>
        ))}
        <span className="legend-hint">Click a party to trace its relationships</span>
      </section>

      {graph.provisions?.length > 0 && (
        <section className="provisions">
          <h3>Key provisions</h3>
          <ul>
            {graph.provisions.map((p, i) => (
              <li key={i}>
                <strong>{p.title}</strong>
                {p.article && <span className="article"> · Art. {p.article}</span>}
                <p>{p.summary}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <details className="raw">
        <summary>Raw extraction JSON</summary>
        <pre>{JSON.stringify(graph, null, 2)}</pre>
      </details>
    </div>
  );
}
