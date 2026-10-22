import { useEffect, useState } from 'react';

type SheetStatus = { configured: boolean; connected: boolean; spreadsheet_url: string | null; pending: boolean; last_synced: string | null; error: string | null };

// Capture OAuth feedback before search-filter normalization updates the URL.
const callbackResult = new URLSearchParams(window.location.search).get('sheets');

export function GoogleSheets() {
  const [status, setStatus] = useState<SheetStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const response = await fetch('/api/sheets/status');
        if (!response.ok) throw new Error('Could not check Google Sheets sync. Your saved roles are still available.');
        const data = await response.json();
        if (active) setStatus(data);
      } catch (e) { if (active) setError((e as Error).message); }
    };
    void load();
    const timer = setInterval(load, 5000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  async function action(kind: 'connect' | 'retry' | 'disconnect') {
    setBusy(true); setError('');
    try {
      const response = await fetch(`/api/sheets/${kind}`, { method: 'POST' });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Google Sheets could not be updated. Try again.');
      if (kind === 'connect') {
        const url = new URL(data.authorization_url);
        if (url.origin !== 'https://accounts.google.com') throw new Error('Invalid Google connection link.');
        window.location.assign(url.href);
      } else {
        const next = await fetch('/api/sheets/status');
        if (!next.ok) throw new Error('Could not check sync status.');
        setStatus(await next.json());
      }
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  const callback = callbackResult;
  return <section className="sheets-panel" aria-label="Google Sheets sync">
    <h3>Google Sheets</h3>
    <p>Create a “RoleScout Saved Roles” spreadsheet. Your saved roles, application status, and notes will update there automatically while RoleScout is running.</p>
    <p className="filter-help">The Saved Roles tab mirrors this tracker, including removals. Make changes here; app-managed cells in the sheet are overwritten during sync.</p>
    {!status && <p role="status">Checking connection…</p>}
    {status && !status.configured && <>
      <p>Google Sheets needs a one-time connection setup on this computer.</p>
      <a href="https://github.com/aishanibasu/RoleScout#google-sheets-sync" target="_blank" rel="noreferrer">Google Sheets setup instructions ↗</a>
    </>}
    {status?.configured && !status.connected && <button disabled={busy} onClick={() => action('connect')}>Connect Google & create spreadsheet</button>}
    {status?.connected && <>
      <div className="tracking-actions">
        {status.spreadsheet_url && /^https:\/\/docs\.google\.com\/spreadsheets\/d\/[A-Za-z0-9_-]+\/edit$/.test(status.spreadsheet_url) && <a href={status.spreadsheet_url} target="_blank" rel="noreferrer">Open spreadsheet ↗</a>}
        <button disabled={busy} onClick={() => action('retry')}>Sync now</button>
        {status.error && <button disabled={busy} onClick={() => action('connect')}>Reconnect Google</button>}
        <button disabled={busy} onClick={() => action('disconnect')}>Disconnect</button>
      </div>
      <p role="status">{status.pending ? 'Changes are waiting to sync.' : status.last_synced ? `Synced ${new Date(status.last_synced).toLocaleString()}` : 'Preparing your spreadsheet…'}</p>
      <small>Disconnecting keeps your spreadsheet and locally saved roles.</small>
    </>}
    {(error || status?.error) && <p role="alert">{error || status?.error}</p>}
    {callback === 'failed' && !status?.connected && <p role="alert">Google could not be connected. Check the setup instructions and try again.</p>}
    {callback === 'cancelled' && !status?.connected && <p>Google connection cancelled. Your roles are still saved locally.</p>}
  </section>;
}
