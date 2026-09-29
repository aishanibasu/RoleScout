import React, { useCallback, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import { DeadlineFlag } from './DeadlineFlag';
import { Pagination } from './Pagination';
import { RefreshStatus } from './RefreshStatus';
import { SourceCoverage } from './SourceCoverage';
import { LinkedInSearch } from './LinkedInSearch';
import { EligibilityDetails, experienceLabel } from './EligibilityDetails';
import { Tracker, writeTracking } from './Tracking';
import type { TrackedJob } from './Tracking';
import type { EligibilityFields } from './EligibilityDetails';

type Job = EligibilityFields & { application_deadline: string | null; deadline_status: string; deadline_evidence: string | null; first_seen: string; status: string; source: string; details_pending?: boolean; description_note?: string; also_listed_on?: string[]; id: number; company: string; title: string; type: string; interest: string[]; studies: string[]; area: string; city: string; region: string; country: string; arrangement: string; level: string; graduation: number[]; description: string; url: string; locations: {city: string; region: string; country: string; raw: string}[]; last_verified: string; source_experience: string; evidence: Record<string, {status: string; text?: string}> };
type Filters = Record<string, string[]>;
const disciplines = ['Finance', 'Economics', 'Accounting', 'Business', 'Computer Science', 'Data Science', 'Information Technology', 'Architecture', 'Mathematics', 'Statistics', 'Engineering', 'Physics', 'Biology', 'Chemistry'];
const unique = (values: string[]) => [...new Set(values.filter(Boolean))].sort();
const year = new Date().getFullYear();
const options: Record<string, string[]> = {
  deadline: ['Has a deadline', 'Closing within 7 days', 'Deadline passed', 'No date found'],
  company: [],
  type: ['Internship', 'Full-time', 'Part-time', 'Co-op', 'Graduate program', 'Apprenticeship'],
  major: disciplines,
  interest: ['Finance', 'Technology', 'Pharmaceuticals & Biotechnology', 'Healthcare', 'Consulting', 'Research', 'Operations'],
  country: [], region: [],
  arrangement: ['On-site', 'Hybrid', 'Remote', 'Not specified'],
  graduation: ['Already graduated', ...Array.from({ length: 9 }, (_, i) => String(year - 2 + i)), 'Other year', 'Not specified'],
  level: ['Student', 'New graduate', 'Entry level', 'Mid-level', 'Senior', 'Manager / leadership', 'Not specified'],
};
const labels: Record<string, string> = { deadline: 'Application deadline', company: 'Company', type: 'Opportunity type', major: 'Areas of study', interest: 'Field of interest', country: 'Country', region: 'State', arrangement: 'Work arrangement', graduation: 'Graduation year', level: 'Experience level' };
function readSearch() {
  const params = new URLSearchParams(location.search);
  return {
    filters: Object.fromEntries(Object.keys(options).map(k => [k, params.getAll(k)])),
    query: params.get('q') || '', strict: params.get('certainty') === 'confirmed',
    sort: ['company', 'verified'].includes(params.get('sort') || '') ? params.get('sort')! : 'default',
    page: Math.max(1, Number.parseInt(params.get('page') || '1', 10) || 1),
  };
}
const initial = readSearch();
function previousVisit() {
  try { const value = localStorage.getItem('role-searcher-last-visit'); return value && Number.isFinite(Date.parse(value)) ? value : null; }
  catch { return null; }
}
function Dropdown({ name, values, selected, onChange }: { name: string; values: string[]; selected: string[]; onChange: (v: string[]) => void }) {
  const [query, setQuery] = useState('');
  const custom = name === 'major';
  const choices = custom ? [...new Set([...values, ...selected])] : values;
  const candidate = query.trim().replace(/\s+/g, ' ');
  const canAdd = custom && candidate.length > 0 && candidate.length <= 100 && selected.length < 30 && !choices.some(value => value.toLowerCase() === candidate.toLowerCase());
  function addCustom() { if (canAdd) { onChange([...selected, candidate]); setQuery(''); } }
  return <details className="dropdown"><summary><span>{labels[name]}<strong>{selected.length ? selected.join(', ') : 'Any'}</strong></span><span aria-hidden="true">⌄</span></summary><div className="menu">
    {values.length > 6 && <input aria-label={`Search ${labels[name]}`} placeholder={custom ? "Find or add an area…" : "Find an option…"} maxLength={custom ? 100 : undefined} value={query} onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && canAdd) { e.preventDefault(); addCustom(); } }} />}
    {canAdd && <button className="add-study" onClick={addCustom}>Add “{candidate}”</button>}
    {custom && <p className="custom-study-help">Not listed? Type your area and press Enter or choose Add. Select up to 30.</p>}
    <button className="clear-option" onClick={() => onChange([])}>Clear selection</button>
    {choices.filter(v => v.toLowerCase().includes(query.toLowerCase())).map(v => <label className="option" key={v}><input type={['graduation', 'deadline'].includes(name) ? 'radio' : 'checkbox'} name={name} disabled={custom && selected.length >= 30 && !selected.includes(v)} checked={selected.includes(v)} onChange={() => onChange(['graduation', 'deadline'].includes(name) ? [v] : selected.includes(v) ? selected.filter(x => x !== v) : [...selected, v])}/>{v}</label>)}
  </div></details>;
}
function App() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(initial.page);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  const [companies, setCompanies] = useState<string[]>([]);
  const [locations, setLocations] = useState<{city: string; region: string; country: string}[]>([]);
  const [sourceSummary, setSourceSummary] = useState('Checking source coverage…');
  const [filters, setFilters] = useState<Filters>(initial.filters);
  const [query, setQuery] = useState(initial.query);
  const [strict, setStrict] = useState(initial.strict);
  const [sort, setSort] = useState(initial.sort);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [view, setView] = useState('explore');
  const [tracked, setTracked] = useState<TrackedJob[]>([]);
  const [trackingError, setTrackingError] = useState('');
  const [saving, setSaving] = useState<number | null>(null);
  const [lastVisit] = useState(previousVisit);
  const [newOnly, setNewOnly] = useState(false);
  const [applied, setApplied] = useState({ filters: initial.filters, query: initial.query, strict: initial.strict, newOnly: false });
  const pending = JSON.stringify({ filters, query, strict, newOnly }) !== JSON.stringify(applied);
  const refreshTracked = useCallback(async () => {
    const response = await fetch('/api/tracked');
    if (!response.ok) throw new Error('Application tracker is unavailable. Please retry.');
    setTracked(await response.json()); setTrackingError('');
  }, []);
  useEffect(() => { refreshTracked().catch(e => setTrackingError(e.message)); }, [refreshTracked]);
  useEffect(() => {
    try { localStorage.setItem('role-searcher-last-visit', new Date().toISOString()); } catch { /* Browsing works without storage. */ }
    const restore = () => {
      const next = readSearch(); setFilters(next.filters); setQuery(next.query);
      setStrict(next.strict); setSort(next.sort); setPage(next.page); setNewOnly(false);
      setApplied({ filters: next.filters, query: next.query, strict: next.strict, newOnly: false });
    };
    addEventListener('popstate', restore);
    return () => removeEventListener('popstate', restore);
  }, []);
  async function saveJob(job: Job) {
    setSaving(job.id); setTrackingError('');
    try { await writeTracking(job.id, 'Saved'); await refreshTracked(); }
    catch (e) { setTrackingError((e as Error).message); }
    finally { setSaving(null); }
  }
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([fetch('/api/filters', {signal: controller.signal}), fetch('/api/sources', {signal: controller.signal})])
      .then(async ([f, s]) => {
        if (!f.ok || !s.ok) throw new Error('Source information unavailable');
        const facets = await f.json();
        const sources = await s.json() as {name: string; job_count: number; stale: boolean; status: string}[];
        setLocations(facets.locations);
        setCompanies(facets.company);
        const normalize = (current: Filters) => (!current.country.length || current.country.includes('United States'))
          ? { ...current, region: [...new Set(current.region.map(value => facets.state_aliases?.[value.toUpperCase()] || value))] }
          : current;
        setFilters(normalize);
        setApplied(current => {
          const normalized = normalize(current.filters);
          return JSON.stringify(normalized) === JSON.stringify(current.filters) ? current : { ...current, filters: normalized };
        });
        const active = sources.filter(s => s.job_count > 0);
        setSourceSummary(active.length ? `${active.map(s => s.name).join(', ')} · ${active.reduce((n, s) => n + s.job_count, 0)} indexed jobs${active.some(s => s.stale) ? ' · Refresh overdue or failed; some listings may be stale.' : ''}` : 'No jobs collected yet. Source connections are being prepared.');
      }).catch(e => { if (e.name !== 'AbortError') setSourceSummary('Source status unavailable.'); });
    return () => controller.abort();
  }, [reload]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    const timer = setTimeout(() => {
      const p = new URLSearchParams({q: applied.query, certainty: applied.strict ? 'confirmed' : 'all', sort, page: String(page), page_size: '20'});
      if (applied.newOnly && lastVisit) p.set('since', lastVisit);
      Object.entries(applied.filters).forEach(([k, vs]) => vs.forEach(v => p.append(k, v)));
      fetch('/api/jobs?' + p, {signal: controller.signal}).then(async response => {
        if (!response.ok) throw new Error('Could not load jobs. Check that the backend is running.');
        const data = await response.json();
        if (data.total > 0 && page > Math.ceil(data.total / 20)) { setPage(Math.ceil(data.total / 20)); return; }
        setJobs(data.items); setTotal(data.total); setLoading(false);
      }).catch(e => { if (e.name !== 'AbortError') { setError(e.message); setJobs([]); setTotal(0); setLoading(false); } });
    }, 200);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [applied, sort, page, reload, lastVisit]);
  useEffect(() => {
    const p = new URLSearchParams();
    Object.entries(applied.filters).forEach(([k, vs]) => vs.forEach(v => p.append(k, v)));
    if (applied.query) p.set('q', applied.query);
    if (applied.strict) p.set('certainty', 'confirmed');
    if (sort !== 'default') p.set('sort', sort);
    if (page > 1) p.set('page', String(page));
    const target = `${location.pathname}${p.size ? '?' + p.toString() : ''}${location.hash}`;
    if (target !== location.pathname + location.search + location.hash) history.pushState(null, '', target);
  }, [applied, sort, page]);
  function update(key: string, values: string[]) { setFilters(f => ({ ...f, [key]: values, ...(key === 'country' ? { region: [] } : {}) })); }
  function reset() { setNewOnly(false); setFilters(initialEmpty()); setQuery(''); setStrict(false); }
  function applyFilters() { setApplied({ filters, query, strict, newOnly }); setPage(1); setExpanded(null); }
  const chosen = Object.entries(filters).flatMap(([k, vs]) => vs.map(v => ({ k, v })));
  const results = jobs;
  return <><header><a className="brand" href={location.pathname}><span className="brand-icon">r.</span>role searcher<span className="beta">EARLY PREVIEW</span></a><a className="header-link" href="#opportunities">Explore opportunities ↗</a></header>
    <main><section className="hero"><div><div className="eyebrow">YOUR NEXT CHAPTER STARTS HERE</div><h1>Big ambitions.<br/><em>Better possibilities.</em></h1><p>Find a role that fits what you study, what you love,<br className="desktop"/> and where you want to go.</p></div><div className="hero-note"><span className="orbit">↗</span><span>One search.<br/>A world of possibilities.</span></div></section>
    <div className="notice"><span>◉</span><div><strong>Live source coverage.</strong> {sourceSummary} Requirements are shown only where known; review the original listing before applying.</div><span className="sample-tag">LIVE INDEX</span></div>
    <nav className="view-tabs" aria-label="Workspace"><button aria-pressed={view === 'explore'} onClick={() => setView('explore')}>Explore roles</button><button aria-pressed={view === 'tracker'} onClick={() => setView('tracker')}>Saved & applications ({tracked.length})</button></nav>
    {trackingError && <div role="alert" className="notice">{trackingError}<button onClick={() => refreshTracked().catch(e => setTrackingError(e.message))}>Retry tracker</button></div>}
    {view === 'tracker' ? <Tracker jobs={tracked} refresh={refreshTracked}/> : <><SourceCoverage />
    <RefreshStatus />
    <section className="workspace" id="opportunities"><aside><div className="filter-heading"><h2>Your preferences</h2><button onClick={reset}>Reset</button></div><button className="mobile-toggle" onClick={() => setShowFilters(!showFilters)} aria-expanded={showFilters}>Customize filters {showFilters ? '−' : '+'}</button><div className={showFilters ? 'filter-list open' : 'filter-list'}>{Object.entries(options).map(([k, values]) => {
      if (k === 'company') values = companies;
      if (k === 'country') values = unique(locations.map(j => j.country));
      if (k === 'region') values = unique(locations.filter(j => !filters.country.length || filters.country.includes(j.country)).map(j => j.region));
      return <Dropdown key={k} name={k} values={values} selected={filters[k]} onChange={v => update(k, v)}/>;
    })}<label className="certainty">Match certainty<select value={strict ? 'confirmed' : 'all'} onChange={e => { setStrict(e.target.value === 'confirmed'); }}><option value="all">Include unspecified requirements</option><option value="confirmed">Confirmed matches only</option></select></label><p className="filter-help">Choose one or more areas of study, or add your own. A role can match any selected subject. Unspecified requirements are included by default; confirmed matches require stated criteria. Review the original listing for full eligibility.</p></div></aside>
    <div className="results"><label className="search"><span aria-hidden="true">⌕</span><input aria-label="Search roles, companies or skills" placeholder="Search roles, companies or skills" value={query} onChange={e => { setQuery(e.target.value); }}/><span className="search-hint">EXPLORE</span></label>
    <div className="apply-filters"><button onClick={applyFilters}>Show results</button><span role="status">{pending ? 'Filters changed. Click Show results to apply them.' : 'Choose your filters, then click Show results.'}</span></div>
    <LinkedInSearch query={query} filters={filters} locations={locations}/>
    {lastVisit && <label className="new-filter"><input type="checkbox" checked={newOnly} onChange={e => { setNewOnly(e.target.checked); }}/> New since your last visit ({new Date(lastVisit).toLocaleDateString()})</label>}
    <div className="results-heading"><div><h2>Find your next opportunity</h2><p role="status">{loading ? 'Loading jobs…' : `${total} matching roles`}</p></div><label className="sort">Sort by <select value={sort} onChange={e => { setPage(1); setSort(e.target.value); }}><option value="default">First seen: newest</option><option value="company">Company A–Z</option><option value="verified">Most recently verified</option></select></label></div>
    {!!chosen.length && <div className="chips" aria-label="Selected filters">{chosen.map(({ k, v }) => <button key={k + v} onClick={() => update(k, filters[k].filter(x => x !== v))} aria-label={`Remove ${labels[k]}: ${v}`}>{labels[k]}: {v} ×</button>)}</div>}
    {!loading && !error && total > 20 && <Pagination page={page} totalPages={Math.ceil(total / 20)} onChange={setPage} position="top"/>}
    {!loading && !error && results.map(job => <article className="job" key={job.id}><div className="job-top"><div className="company-icon">{job.company.split(' ').slice(0, 2).map(s => s[0]).join('')}</div><div className="company">{job.company}<span>{job.source === 'hft' ? 'Via HFT Jobs · Aggregator' : 'Employer career listing'}</span></div><span className="job-type">{job.type}</span></div><h3>{job.title}</h3><DeadlineFlag job={job}/><div className="listing-freshness">First seen {new Date(job.first_seen).toLocaleDateString()} · Verified {new Date(job.last_verified).toLocaleDateString()}{Date.now() - Date.parse(job.last_verified) > 48 * 60 * 60 * 1000 && <strong> · Verification overdue</strong>}</div><div className="job-meta">{job.locations.map(l => [l.city, l.region, l.country].filter(Boolean).join(', ')).join(' · ') || 'Location not specified'} <span> / </span> {job.arrangement}</div><div className="tags"><span>{job.level}{job.evidence.level?.status === 'inferred' ? ' · inferred' : ''}</span>{job.experience_range && <span>{experienceLabel(job.experience_range)}</span>}{job.interest.map(i => <span key={i}>{i}</span>)}<span>{job.graduation.length ? `${job.graduation_window ? 'Graduation window overlaps' : 'Class of'} ${job.graduation.join(' / ')}` : 'Graduation not extracted'}</span></div><div className="job-bottom"><span>{job.studies.length ? job.studies.join(' · ') : 'Degree subjects not extracted'}</span><button disabled={saving !== null || tracked.some(item => item.id === job.id)} onClick={() => saveJob(job)}>{tracked.some(item => item.id === job.id) ? 'Saved ✓' : saving === job.id ? 'Saving…' : 'Save role'}</button><button aria-expanded={expanded === job.id} onClick={() => setExpanded(expanded === job.id ? null : job.id)}>View details {expanded === job.id ? '−' : '↗'}</button></div>{expanded === job.id && <div className="job-detail"><EligibilityDetails job={job}/><h4>Application deadline</h4><p>{job.deadline_evidence || "No unambiguous application closing date found. Check the original listing."}</p><p>Dates are shown as stated by the employer. Check the original application for its cutoff time and timezone; employers may close roles early.</p><h4>Original description</h4><p className="description">{job.description || (job.details_pending ? 'Full description is being retrieved. Check the original application for requirements.' : job.description_note || 'Full requirements are available on the original employer website.')}</p>{job.also_listed_on?.includes('hft') && <p>Also listed on HFT Jobs.</p>}<p><strong>Matching context:</strong> Finance describes the employer’s industry. Other interests and student level may be inferred from source categories or the title. Unspecified requirements are not confirmation of eligibility. Source experience category: {job.source_experience || 'Not specified'}. Last verified: {new Date(job.last_verified).toLocaleString()}.</p>{/^https?:\/\//i.test(job.url) ? <a href={job.url} target="_blank" rel="noreferrer">View original application ↗</a> : <p>Application link unavailable.</p>}</div>}</article>)}
    {!loading && !error && !results.length && <div className="empty"><span>⌕</span><h3>No roles match these preferences.</h3><p>Try broadening your preferences. More employers will be added as source coverage expands.</p><button onClick={reset}>Clear filters and search</button></div>}
    {loading && <p role="status">Loading current listings…</p>}
    {error && <div className="empty" role="alert"><h3>Jobs are temporarily unavailable.</h3><p>{error}</p><button onClick={() => setReload(x => x + 1)}>Try again</button></div>}
    {!loading && !error && total > 20 && <Pagination page={page} totalPages={Math.ceil(total / 20)} onChange={setPage} position="bottom"/>}
    <p className="results-footer">A little direction for your next big step.</p></div></section></>}</main><footer><span>role searcher</span><span>Built for possibility. · Live job search</span></footer></>;
}
function initialEmpty(): Filters { return Object.fromEntries(Object.keys(options).map(k => [k, []])); }
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
