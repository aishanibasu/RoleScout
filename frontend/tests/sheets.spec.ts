import { test, expect } from '@playwright/test';

test.beforeEach(async ({ request }) => {
  const response = await request.get('http://127.0.0.1:8011/tracked');
  for (const job of await response.json()) await request.delete(`http://127.0.0.1:8011/tracked/${job.id}`);
});

test('Google Sheets setup is available before connecting', async ({ page }) => {
  await page.goto('/?sheets=cancelled');
  const panel = page.getByRole('region', { name: 'Google Sheets sync' });
  await expect(panel.getByText('Google Sheets needs a one-time connection setup on this computer.')).toBeVisible();
  await expect(panel.getByRole('link', { name: /setup instructions/ })).toBeVisible();
  await expect(panel.getByText(/connection cancelled/)).toBeVisible();
});

test('connected spreadsheet retries and disconnects without removing saved roles', async ({ page }, info) => {
  let connected = true;
  let pending = true;
  let error: string | null = 'Google Sheets is temporarily unavailable. Your roles are saved locally; sync will retry.';
  await page.route('**/api/sheets/status', route => route.fulfill({ json: {
    configured: true, connected, pending, error,
    spreadsheet_url: connected ? 'https://docs.google.com/spreadsheets/d/test-sheet/edit' : null,
    last_synced: pending ? null : '2026-10-21T12:00:00Z',
  } }));
  await page.route('**/api/sheets/retry', route => {
    pending = false; error = null;
    return route.fulfill({ json: { queued: true } });
  });
  await page.route('**/api/sheets/disconnect', route => {
    connected = false;
    return route.fulfill({ json: { disconnected: true } });
  });
  await page.goto('/?q=Research+Analyst+03');
  const save = page.getByRole('button', { name: 'Save role', exact: true });
  await save.click();
  await expect(page.getByRole('button', { name: 'Saved ✓' })).toBeDisabled();
  await page.getByRole('button', { name: /Saved & applications/ }).click();
  const panel = page.getByRole('region', { name: 'Google Sheets sync' });
  await expect(panel.getByRole('alert')).toContainText('saved locally');
  await expect(panel.getByRole('link', { name: /Open spreadsheet/ })).toHaveAttribute('href', 'https://docs.google.com/spreadsheets/d/test-sheet/edit');
  await panel.getByRole('button', { name: 'Sync now' }).click();
  await expect(panel.getByRole('status')).toContainText('Synced');
  await expect(panel.getByRole('alert')).toHaveCount(0);
  await page.screenshot({ path: `test-results/sheets-${info.project.name}.png`, fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await panel.getByRole('button', { name: 'Disconnect', exact: true }).click();
  await expect(panel.getByRole('button', { name: 'Connect Google & create spreadsheet' })).toBeVisible();
  await expect(page.getByLabel('Status for Research Analyst 03')).toBeVisible();
});
