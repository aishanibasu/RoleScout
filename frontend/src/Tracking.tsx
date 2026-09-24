import { useState } from 'react';

export type TrackingState = { status: string; notes: string; updated_at: string };
export type TrackedJob = { id: number; title: string; company: string; url: string; status: string; tracking: TrackingState };
export const stages = ['Saved', 'Applied', 'Interviewing', 'Offer', 'Rejected'];

export async function writeTracking(id: number, status: string, notes = '') {
  const response = await fetch(`/api/tracked/${id}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status, notes }),
  });
  if (!response.ok) throw new Error('Could not save changes. Please try again.');
}

function TrackedCard({ job, refresh }: { job: TrackedJob; refresh: () => Promise<void> }) {
  const [status, setStatus] = useState(job.tracking.status);
  const [notes, setNotes] = useState(job.tracking.notes);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  async function save(remove = false) {
    setBusy(true); setMessage('');
    try {
      if (remove) {
        const response = await fetch(`/api/tracked/${job.id}`, { method: 'DELETE' });
        if (!response.ok) throw new Error('Could not remove this job. Please try again.');
      } else await writeTracking(job.id, status, notes);
      await refresh();
      setMessage('Changes saved.');
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }
  return <article className="job tracked-card">
    <p className="eyebrow">{job.company} · {job.status === 'active' ? 'Open listing' : 'Listing closed'}</p>
    <h3>{job.title}</h3>
    <label>Application status<select aria-label={`Status for ${job.title}`} value={status} disabled={busy} onChange={e => setStatus(e.target.value)}>{stages.map(stage => <option key={stage}>{stage}</option>)}</select></label>
    <label>Notes<textarea aria-label={`Notes for ${job.title}`} maxLength={5000} rows={3} value={notes} disabled={busy} onChange={e => setNotes(e.target.value)} placeholder="Next steps, contacts, or interview dates…" /></label>
    <div className="tracking-actions"><button disabled={busy} onClick={() => save()}>Save changes</button><button disabled={busy} onClick={() => save(true)}>Remove from tracker</button>{/^https?:\/\//i.test(job.url) && <a href={job.url} target="_blank" rel="noreferrer">Original listing ↗</a>}</div>
    {message && <p role="status">{message}</p>}
  </article>;
}

export function Tracker({ jobs, refresh }: { jobs: TrackedJob[]; refresh: () => Promise<void> }) {
  const [stage, setStage] = useState('All');
  const filtered = jobs.filter(job => stage === 'All' || job.tracking.status === stage);
  return <section className="tracker" aria-label="Application tracker">
    <div className="results-heading"><div><h2>Your application tracker</h2><p>{jobs.length} saved opportunities · Stored on this computer</p></div><label>Show status<select value={stage} onChange={e => setStage(e.target.value)}>{['All', ...stages].map(value => <option key={value}>{value}</option>)}</select></label></div>
    {filtered.map(job => <TrackedCard key={job.id} job={job} refresh={refresh} />)}
    {!filtered.length && <div className="empty"><h3>{jobs.length ? 'No jobs with this status.' : 'Your shortlist starts here.'}</h3><p>Save a role from Explore, then track your application and next steps here.</p></div>}
  </section>;
}
