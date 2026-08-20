import { useState, useRef } from 'react';
import { ingestPdf, IS_DEMO, type TrustGraph } from './ingest';
import { TrustGraphView } from './TrustGraphView';
import './App.css';

type Phase = 'idle' | 'working' | 'done' | 'error';

export default function App() {
  const [phase, setPhase] = useState<Phase>('idle');
  const [stage, setStage] = useState('');
  const [progress, setProgress] = useState(0);
  const [graph, setGraph] = useState<TrustGraph | null>(null);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  async function run(file: File) {
    setPhase('working');
    setError('');
    setGraph(null);
    setProgress(0);
    setStage('uploading');

    try {
      const result = await ingestPdf(file, (p, s) => {
        setProgress(p);
        setStage(s);
      });
      setGraph(result);
      setPhase('done');
    } catch (e) {
      setError((e as Error).message);
      setPhase('error');
    }
  }

  function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) run(file);
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file) run(file);
  }

  return (
    <div className="app">
      <header className="masthead">
        <h1>TrustGraph</h1>
        <p>Extract parties, roles, and relationships from a trust instrument.</p>
      </header>

      {IS_DEMO && (
        <div className="demo-banner">
          <strong>Demo mode.</strong> This static deploy returns a sample extraction — no
          document leaves your browser and no model is called. The full pipeline (FastAPI,
          Temporal, Claude) runs from the repo:{' '}
          <a href="https://github.com/shraddhaborah/trustgraph" target="_blank" rel="noreferrer">
            github.com/shraddhaborah/trustgraph
          </a>
        </div>
      )}

      {phase === 'idle' && (
        <div
          className="dropzone"
          onDrop={onDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        >
          <p className="dz-title">Drop a trust document here</p>
          <p className="dz-sub">or click to choose a PDF</p>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            onChange={onPick}
            hidden
          />
        </div>
      )}

      {phase === 'working' && (
        <div className="panel">
          <div className="bar">
            <div className="bar-fill" style={{ width: `${Math.round(progress * 100)}%` }} />
          </div>
          <p className="stage">
            {stage} · {Math.round(progress * 100)}%
          </p>
          <p className="hint">
            Extraction runs in the background. Large documents take a minute or two.
          </p>
        </div>
      )}

      {phase === 'error' && (
        <div className="panel error">
          <p className="err-title">Ingestion failed</p>
          <p className="err-body">{error}</p>
          <button onClick={() => setPhase('idle')}>Try another document</button>
        </div>
      )}

      {phase === 'done' && graph && (
        <>
          <div className="toolbar">
            <button onClick={() => setPhase('idle')}>Ingest another document</button>
          </div>
          <TrustGraphView graph={graph} />
        </>
      )}
    </div>
  );
}
