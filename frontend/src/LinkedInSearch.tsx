import { useState } from 'react';

type Location = { city: string; region: string; country: string };

export function LinkedInSearch({ query, filters, locations }: {
  query: string;
  filters: Record<string, string[]>;
  locations: Location[];
}) {
  const [preferredLocation, setPreferredLocation] = useState('');
  const level = filters.region.length ? 'region' : 'country';
  const choices = [...new Set(filters[level].flatMap(value => {
    const matches = locations.filter(loc => loc[level] === value
      && (!filters.country.length || filters.country.includes(loc.country)));
    if (!matches.length) return [value];
    return matches.map(loc => [...new Set((level === 'region' ? [loc.region, loc.country] : [loc.country]).filter(Boolean))].join(', '));
  }))].sort();
  const selectedLocation = choices.includes(preferredLocation) ? preferredLocation : choices[0] || '';
  const url = new URL('https://www.linkedin.com/jobs/search/');
  if (query.trim()) url.searchParams.set('keywords', query.trim());
  if (selectedLocation) url.searchParams.set('location', selectedLocation);

  return <div className="linkedin-search">
    <div className="linkedin-search-actions">
      <a className="linkedin-search-link" href={url.toString()} target="_blank" rel="noopener noreferrer" aria-describedby="linkedin-search-help">Search LinkedIn ↗</a>
      {choices.length > 1 && <label>LinkedIn location
        <select value={selectedLocation} onChange={event => setPreferredLocation(event.target.value)}>
          {choices.map(choice => <option key={choice} value={choice}>{choice}</option>)}
        </select>
      </label>}
    </div>
    <p id="linkedin-search-help">Opens in a new tab using your search text{selectedLocation ? ` and ${selectedLocation}` : ''}. {selectedLocation ? 'Other filters stay in Role Searcher.' : 'Choose a location on LinkedIn. Other filters stay in Role Searcher.'}</p>
  </div>;
}
