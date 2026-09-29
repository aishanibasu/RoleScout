import { DeadlineFlag } from './DeadlineFlag';
import { experienceLabel } from './EligibilityDetails';
import type { EligibilityFields } from './EligibilityDetails';

export type Job = EligibilityFields & {
  id: number; company: string; title: string; url: string;
  studies: string[]; level: string; graduation: number[];
  evidence: Record<string, { status: string }>;
  locations: { city: string; region: string; country: string }[];
  application_deadline: string | null; deadline_status: string;
};

function EligibilitySummary({ job }: { job: Job }) {
  const education = job.education_requirements || [];
  const experience = job.experience_requirements || [];
  const month = (value: string) => new Date(value + 'T12:00:00Z').toLocaleDateString(undefined, { month: 'short', year: 'numeric', timeZone: 'UTC' });
  return <ul className="eligibility-summary">
    <li><strong>Study:</strong> {education.length ? education.map(e => `${e.subjects.join(', ')} (${e.preference === 'preferred' ? 'preferred' : 'stated'}${e.alternatives ? '; alternatives accepted' : ''})`).join('; ') : job.studies.length ? `${job.studies.join(', ')} (check requirements)` : 'Not specified'}</li>
    <li><strong>Experience:</strong> {experience.length ? experience.map(e => `${experienceLabel(e)}${e.preference === 'preferred' ? ' (preferred)' : ''}`).join('; ') : job.experience_range ? experienceLabel(job.experience_range) : job.level !== 'Not specified' ? `${job.level}${job.evidence.level?.status === 'explicit' ? '' : ' (inferred)'}` : 'Not specified'}</li>
    <li><strong>Graduation:</strong> {job.graduation_ambiguous ? 'Check original listing' : job.graduation_window ? `${month(job.graduation_window.start)} – ${month(job.graduation_window.end)}` : job.graduation.length ? `${job.graduation.join(' / ')}${job.evidence.graduation?.status === 'explicit' ? '' : ' (check requirements)'}` : 'Not specified'}</li>
  </ul>;
}

export function JobCard({ job, saved, saving, saveDisabled, onSave }: { job: Job; saved: boolean; saving: boolean; saveDisabled: boolean; onSave: () => void }) {
  return <article className="job concise-job">
    <div className="company"><span className="field-label">Company</span>{job.company}</div>
    <span className="field-label role-label">Role</span><h3>{job.title}</h3>
    <dl className="job-facts">
      <div><dt>Eligibility</dt><dd><EligibilitySummary job={job}/></dd></div>
      <div><dt>Location</dt><dd>{job.locations.map(l => [...new Set([l.city, l.region, l.country].filter(Boolean))].join(', ')).join(' · ') || 'Not specified'}</dd></div>
      <div><dt>Deadline</dt><dd>{job.application_deadline ? <DeadlineFlag job={job}/> : 'Not specified'}</dd></div>
    </dl>
    <div className="card-actions">
      <div className="application-url"><span className="field-label">Application URL</span>{/^https?:\/\//i.test(job.url) ? <a href={job.url} target="_blank" rel="noreferrer" aria-label={`Open application for ${job.title}`}>{job.url} ↗</a> : <span>Unavailable</span>}</div>
      <button disabled={saveDisabled || saved} onClick={onSave}>{saved ? 'Saved ✓' : saving ? 'Saving…' : 'Save role'}</button>
    </div>
  </article>;
}
