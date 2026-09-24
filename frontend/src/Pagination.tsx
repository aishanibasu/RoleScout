import { useEffect, useId, useState } from 'react';

export function Pagination({ page, totalPages, onChange, position }: {
  page: number; totalPages: number; onChange: (page: number) => void; position: string;
}) {
  const [target, setTarget] = useState(String(page));
  const inputId = useId();
  useEffect(() => setTarget(String(page)), [page]);
  const pages = totalPages <= 12
    ? Array.from({ length: totalPages }, (_, i) => i + 1)
    : [...new Set([1, ...Array.from({ length: 5 }, (_, i) => page - 2 + i).filter(p => p > 1 && p < totalPages), totalPages])].sort((a, b) => a - b);
  return <nav className="pagination" aria-label={`Result pages (${position})`}>
    <div className="page-buttons">
      <button disabled={page <= 1} onClick={() => onChange(page - 1)}>← Previous</button>
      {pages.map((value, index) => <span className="page-slot" key={value}>
        {index > 0 && value - pages[index - 1] > 1 && <span aria-hidden="true">…</span>}
        <button aria-label={`Page ${value}`} aria-current={value === page ? 'page' : undefined} onClick={() => onChange(value)}>{value}</button>
      </span>)}
      <button disabled={page >= totalPages} onClick={() => onChange(page + 1)}>Next →</button>
    </div>
    <span>Page {page} of {totalPages}</span>
    <form className="page-jump" onSubmit={event => {
      event.preventDefault(); const value = Number(target);
      if (Number.isInteger(value) && value >= 1 && value <= totalPages) onChange(value);
    }}>
      <label htmlFor={inputId}>Go to page</label>
      <input id={inputId} type="number" inputMode="numeric" min={1} max={totalPages} required value={target} onChange={e => setTarget(e.target.value)} />
      <button type="submit">Go</button>
    </form>
  </nav>;
}
