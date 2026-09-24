export type EligibilityFields = {
  education_requirements?: { subjects: string[]; text: string; preference: string; alternatives: boolean }[];
  experience_requirements?: { minimum: number; maximum: number | null; text: string; preference: string }[];
  experience_range?: { minimum: number; maximum: number | null } | null;
  graduation_window?: { start: string; end: string; text: string } | null;
  graduation_ambiguous?: boolean;
  graduation_text?: string;
  match_reasons?: { criterion: string; status: string; text: string }[];
};

export function experienceLabel(range: EligibilityFields['experience_range']) {
  if (!range) return '';
  return range.maximum === null ? `${range.minimum}+ years stated` : `${range.minimum}–${range.maximum} years stated`;
}
const month = (value: string) => new Date(value + 'T12:00:00Z').toLocaleDateString([], { month: 'long', year: 'numeric', timeZone: 'UTC' });

export function EligibilityDetails({ job }: { job: EligibilityFields }) {
  const education = job.education_requirements || [];
  const experience = job.experience_requirements || [];
  return <section className="eligibility" aria-label="Extracted requirements">
    <h4>What the listing says</h4>
    <p className="eligibility-note">These excerpts support the filters. A subject match does not confirm every qualification; check the full description.</p>
    {!!job.match_reasons?.length && <div className="match-reasons"><h5>Why this role appears</h5>{job.match_reasons.map((reason, i) => <p key={i}><span className={`evidence-status ${reason.status}`}>{reason.status === 'explicit' ? 'Stated' : reason.status === 'provisional' ? 'Needs review' : reason.status === 'inferred' ? 'Inferred' : 'Unknown'}</span><strong>{reason.criterion}:</strong> {reason.text}</p>)}</div>}
    <h5>Education</h5>
    {education.length ? education.map((e, i) => <div className="requirement" key={i}><span className="evidence-status">{e.preference === 'preferred' ? 'Preferred' : 'Stated subjects'}</span><span>{e.subjects.join(' · ')}</span><blockquote>{e.text}</blockquote>{e.alternatives && <small>Related fields or equivalent experience may be accepted.</small>}</div>) : <p>No specific degree subjects extracted.</p>}
    <h5>Graduation</h5>
    {job.graduation_window ? <div className="requirement"><strong>{month(job.graduation_window.start)} – {month(job.graduation_window.end)}</strong><blockquote>{job.graduation_window.text}</blockquote><small>A year-only selection may overlap only part of this window. Check your graduation month.</small></div> : job.graduation_text ? <div className="requirement"><blockquote>{job.graduation_text}</blockquote></div> : <p>{job.graduation_ambiguous ? 'Multiple graduation criteria need review in the original description.' : 'No unambiguous graduation criteria extracted.'}</p>}
    <h5>Experience</h5>
    {experience.length ? experience.map((e, i) => <div className="requirement" key={i}><span className="evidence-status">{e.preference === 'preferred' ? 'Preferred' : 'Stated'}</span><strong>{experienceLabel(e)}</strong><blockquote>{e.text}</blockquote></div>) : <p>No numeric experience requirement extracted.</p>}
  </section>;
}
