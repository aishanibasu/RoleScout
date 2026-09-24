export function DeadlineFlag({ job }: { job: { application_deadline: string | null; deadline_status: string } }) {
  if (!job.application_deadline) return null;
  const label = job.deadline_status === 'passed' ? 'Stated deadline passed' : job.deadline_status === 'soon' ? 'Closing soon · Apply by' : 'Apply by';
  const display = new Date(job.application_deadline + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  return <p className={`deadline-flag ${job.deadline_status}`}>{label} <time dateTime={job.application_deadline}>{display}</time></p>;
}
