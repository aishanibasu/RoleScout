import { useEffect, useState } from 'react';
type Source = {id: string; name: string; url: string; status: string; job_count: number; scope: string; stale: boolean; error: string | null};
export function SourceCoverage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch('/api/sources', {signal: controller.signal});
        if (!response.ok) throw new Error();
        setSources(await response.json()); setFailed(false);
      } catch { if (!controller.signal.aborted) setFailed(true); }
    }
    void load(); const timer = window.setInterval(load, 60_000);
    return () => {controller.abort(); window.clearInterval(timer);};
  }, []);
  return <details className="source-coverage"><summary>Source coverage · {sources.filter(s => s.job_count > 0).length} connected / {sources.length || '…'} sources</summary>
    {failed && <p>Could not refresh source coverage.</p>}
    <div className="source-grid">{sources.map(source => <div key={source.id} className="source-entry"><strong><a href={source.url} target="_blank" rel="noreferrer">{source.name} ↗</a></strong><span>{source.job_count ? `${source.job_count.toLocaleString()} indexed listings${source.stale ? ' · refresh overdue or failed' : ''}` : source.status === 'manual' ? 'Contact-based recruiting · No public feed' : source.status === 'error' ? 'Connection needs repair' : source.status === 'blocked' ? 'Connection unavailable' : 'Integration in progress'}</span><p>{source.scope}</p>{source.error && source.status === 'error' && <p>Latest collection failed. Only previously verified listings are retained.</p>}</div>)}</div>
  </details>;
}
