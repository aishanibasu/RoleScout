import { useEffect, useState } from 'react';

type Schedule = {
  running: boolean;
  sources: { source: string; name: string; status: string; error: string | null; interval_hours: number; last_success: string | null; next_due: string }[];
};
const date = (value: string) => new Date(value).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });

export function RefreshStatus() {
  const [schedule, setSchedule] = useState<Schedule | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    let pending = false;
    async function load() {
      if (pending) return;
      pending = true;
      try {
        const response = await fetch('/api/scheduler', { signal: controller.signal });
        if (!response.ok) throw new Error('Refresh status unavailable');
        setSchedule(await response.json());
        setFailed(false);
      } catch (error) {
        if (!controller.signal.aborted) setFailed(true);
      } finally {
        pending = false;
      }
    }
    void load();
    const timer = window.setInterval(load, 30_000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, []);
  return <section className="refresh-status" aria-label="Job refresh status">
    <div><span className={`refresh-dot ${schedule?.running && !failed ? 'active' : ''}`} aria-hidden="true"/><strong>{failed ? 'Refresh status unavailable' : !schedule ? 'Checking refresh status…' : schedule.running ? 'Automatic refresh is on' : 'Automatic refresh is paused'}</strong></div>
    {!failed && schedule && <details className="refresh-details"><summary>Refresh schedule</summary><div className="refresh-sources">{schedule.sources.map(source => <div className="refresh-times" key={source.source}><strong>{source.name}</strong><span>Last updated: {source.last_success ? date(source.last_success) : 'Not collected yet'}</span><span>{schedule.running ? `Next check: ${new Date(source.next_due).getTime() <= Date.now() ? 'Due now' : date(source.next_due)}` : 'Stored listings are still available.'}</span><span>Every {source.interval_hours} hours</span>{source.error && <span className="refresh-error">Last refresh failed; keeping previous listings.</span>}</div>)}</div></details>}
  </section>;
}
