import { test, expect } from '@playwright/test';

test.beforeEach(async ({ request }) => {
  const response = await request.get('http://127.0.0.1:8011/tracked');
  for (const job of await response.json()) await request.delete(`http://127.0.0.1:8011/tracked/${job.id}`);
});

test('search, pagination, URL navigation, details and layout', async ({ page }, info) => {
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('/');
  await expect(page.getByText('240 matching roles', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Next →' }).first().click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page.getByText('Page 2 of 12').first()).toBeVisible();
  await page.goBack();
  await expect(page.getByText('Page 1 of 12').first()).toBeVisible();
  const search = page.getByRole('textbox', { name: 'Search roles, companies or skills' });
  await search.fill('Research Analyst 03');
  await expect(page.getByText('1 matching roles', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'View details' }).click();
  await expect(page.getByRole('heading', { name: 'Original description' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'View original application' })).toHaveAttribute('href', 'https://example.com/jobs/3');
  await page.reload();
  await expect(search).toHaveValue('Research Analyst 03');
  await expect(page.getByText('1 matching roles', { exact: true })).toBeVisible();
  await page.screenshot({ path: `test-results/search-${info.project.name}.png`, fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test('save, update, reload and remove an application', async ({ page }, info) => {
  await page.goto('/?q=Research+Analyst+03');
  await page.getByRole('button', { name: 'Save role', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Saved ✓' })).toBeDisabled();
  await page.getByRole('button', { name: 'Saved & applications (1)' }).click();
  await page.getByLabel('Status for Research Analyst 03').selectOption('Applied');
  await page.getByLabel('Notes for Research Analyst 03').fill('Follow up next Friday');
  await page.getByRole('button', { name: 'Save changes' }).click();
  await expect(page.getByText('Changes saved.')).toBeVisible();
  await page.reload();
  await page.getByRole('button', { name: 'Saved & applications (1)' }).click();
  await expect(page.getByLabel('Status for Research Analyst 03')).toHaveValue('Applied');
  await expect(page.getByLabel('Notes for Research Analyst 03')).toHaveValue('Follow up next Friday');
  await page.screenshot({ path: `test-results/tracker-${info.project.name}.png`, fullPage: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole('button', { name: 'Remove from tracker' }).click();
  await expect(page.getByText('Your shortlist starts here.')).toBeVisible();
});

test('new since visit, empty results and request failure recovery', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('role-searcher-last-visit', new Date(Date.now() + 86400000).toISOString()));
  await page.goto('/');
  await page.getByRole('checkbox', { name: 'New since your last visit' }).check();
  await expect(page.getByText('No roles match these preferences.')).toBeVisible();
  await page.getByRole('button', { name: 'Clear filters and search' }).click();
  await expect(page.getByText('240 matching roles', { exact: true })).toBeVisible();
  await page.route('**/api/jobs?**', route => route.fulfill({ status: 503, body: 'Unavailable' }));
  await page.getByRole('textbox', { name: 'Search roles, companies or skills' }).fill('Research');
  await expect(page.getByRole('heading', { name: 'Jobs are temporarily unavailable.' })).toBeVisible();
  await page.unroute('**/api/jobs?**');
  await page.getByRole('button', { name: 'Try again', exact: true }).click();
  await expect(page.getByText('240 matching roles', { exact: true })).toBeVisible();
});

test('filters work on desktop and mobile, with forward navigation and verified sorting', async ({ page }, info) => {
  await page.goto('/');
  await expect(page.getByText('240 matching roles', { exact: true })).toBeVisible();
  if (info.project.name === 'mobile') await page.getByRole('button', { name: 'Customize filters' }).click();
  const company = page.locator('details.dropdown').filter({ has: page.locator('summary', { hasText: 'Company' }) });
  await company.locator('summary').click();
  await company.getByRole('checkbox', { name: 'Point72', exact: true }).check();
  await expect(page).toHaveURL(/company=Point72/);
  await expect(page.getByRole('button', { name: 'Remove Company: Point72' })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('button', { name: 'Remove Company: Point72' })).toHaveCount(0);
  await page.goForward();
  await expect(page.getByRole('button', { name: 'Remove Company: Point72' })).toBeVisible();
  await page.getByLabel('Sort by').selectOption('verified');
  await page.reload();
  await expect(page.getByLabel('Sort by')).toHaveValue('verified');
  await expect(page.getByText('239 matching roles', { exact: true })).toBeVisible();
});


test('areas of study include Mathematics and clears retired URL filters', async ({ page }, info) => {
  await page.goto('/?minor=Finance&area=Business+%26+Finance');
  await expect(page.getByText('240 matching roles', { exact: true })).toBeVisible();
  await expect(page).not.toHaveURL(/minor=|area=/);
  if (info.project.name === 'mobile') await page.getByRole('button', { name: 'Customize filters' }).click();
  await expect(page.locator('details.dropdown summary').filter({ hasText: /^Minor/ })).toHaveCount(0);
  await expect(page.locator('details.dropdown summary').filter({ hasText: /^Major/ })).toHaveCount(0);
  const major = page.locator('details.dropdown').filter({ has: page.locator('summary', { hasText: /^Areas of study/ }) });
  await major.locator('summary').click();
  await major.getByRole('textbox', { name: 'Search Areas of study', exact: true }).fill('math');
  await major.getByRole('checkbox', { name: 'Mathematics', exact: true }).check();
  await page.getByLabel('Match certainty').selectOption('confirmed');
  await expect(page.getByText('1 matching roles', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Research Analyst 03', exact: true })).toBeVisible();
  await expect(page).toHaveURL(/major=Mathematics/);
  await page.reload();
  await expect(page.getByText('1 matching roles', { exact: true })).toBeVisible();
  if (info.project.name === 'mobile') await page.getByRole('button', { name: 'Customize filters' }).click();
  await major.locator('summary').click();
  await expect(major.getByRole('checkbox', { name: 'Mathematics', exact: true })).toBeChecked();
  await page.screenshot({ path: `test-results/major-${info.project.name}.png`, fullPage: true });
  await major.getByRole('checkbox', { name: 'Economics', exact: true }).check();
  await expect(page.getByText('239 matching roles', { exact: true })).toBeVisible();
});


test('custom study areas can be added, matched, restored and removed', async ({ page }, info) => {
  await page.goto('/');
  if (info.project.name === 'mobile') await page.getByRole('button', { name: 'Customize filters' }).click();
  const studies = page.locator('details.dropdown').filter({ has: page.locator('summary', { hasText: /^Areas of study/ }) });
  await studies.locator('summary').click();
  const input = page.getByRole('textbox', { name: 'Search Areas of study', exact: true });
  await input.fill('  Neuroscience  ');
  await input.press('Enter');
  await page.getByLabel('Match certainty').selectOption('confirmed');
  await expect(page.getByText('1 matching roles', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Research Analyst 04', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Remove Areas of study: Neuroscience', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText('1 matching roles', { exact: true })).toBeVisible();
  if (info.project.name === 'mobile') await page.getByRole('button', { name: 'Customize filters' }).click();
  await studies.locator('summary').click();
  await expect(studies.getByRole('checkbox', { name: 'Neuroscience', exact: true })).toBeChecked();
  await input.fill('neuroscience');
  await expect(studies.getByRole('button', { name: /Add “/ })).toHaveCount(0);
  await input.fill('Actuarial Science');
  await page.screenshot({ path: `test-results/custom-studies-${info.project.name}.png`, fullPage: true });
  await studies.getByRole('button', { name: 'Add “Actuarial Science”' }).click();
  await expect(studies.getByRole('checkbox', { name: 'Actuarial Science', exact: true })).toBeChecked();
  await page.getByRole('button', { name: 'Remove Areas of study: Neuroscience', exact: true }).click();
  await expect(page.getByText('No roles match these preferences.')).toBeVisible();
  await page.getByRole('button', { name: 'Remove Areas of study: Actuarial Science', exact: true }).click();
  await expect(page.getByText('240 matching roles', { exact: true })).toBeVisible();
});


test('location filters use country and state only', async ({ page }, info) => {
  await page.goto('/?city=London');
  await expect(page.getByText('240 matching roles', { exact: true })).toBeVisible();
  await expect(page).not.toHaveURL(/city=/);
  if (info.project.name === 'mobile') await page.getByRole('button', { name: 'Customize filters' }).click();
  await expect(page.locator('details.dropdown summary').filter({ hasText: /^City/ })).toHaveCount(0);
  await expect(page.locator('details.dropdown summary').filter({ hasText: /^State \/ region/ })).toHaveCount(0);
  const country = page.locator('details.dropdown').filter({ has: page.locator('summary', { hasText: /^Country/ }) });
  const state = page.locator('details.dropdown').filter({ has: page.locator('summary', { hasText: /^State/ }) });
  await country.locator('summary').click();
  await country.getByRole('checkbox', { name: 'United States', exact: true }).check();
  await state.locator('summary').click();
  await state.getByRole('checkbox', { name: 'New York', exact: true }).check();
  await expect(page.getByRole('button', { name: 'Remove State: New York', exact: true })).toBeVisible();
  await expect(page.getByText('240 matching roles', { exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Search LinkedIn' })).toHaveAttribute('href', /location=New\+York%2C\+United\+States/);
  await page.screenshot({ path: `test-results/country-state-${info.project.name}.png`, fullPage: true });
  await country.getByRole('button', { name: 'Clear selection', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Remove State: New York', exact: true })).toHaveCount(0);
});


test('jump directly among numbered pages and keep history and filters', async ({ page }, info) => {
  await page.goto('/?country=United+States&region=NY');
  const nav = page.getByRole('navigation', { name: 'Result pages (top)', exact: true });
  await expect(nav.getByText('Page 1 of 12')).toBeVisible();
  await expect(page).toHaveURL(/region=New\+York/);
  for (const value of [4, 7, 3]) {
    await nav.getByRole('button', { name: `Page ${value}`, exact: true }).click();
    await expect(nav.getByText(`Page ${value} of 12`)).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`page=${value}`));
  }
  await page.goBack();
  await expect(nav.getByText('Page 7 of 12')).toBeVisible();
  await nav.getByRole('spinbutton', { name: 'Go to page' }).fill('12');
  await nav.getByRole('button', { name: 'Go', exact: true }).click();
  await expect(nav.getByText('Page 12 of 12')).toBeVisible();
  await expect(nav.getByRole('button', { name: 'Next →' })).toBeDisabled();
  await page.reload();
  await expect(nav.getByRole('button', { name: 'Page 12', exact: true })).toHaveAttribute('aria-current', 'page');
  await nav.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `test-results/pagination-${info.project.name}.png` });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('NY includes other employers and Goldman uses its public link', async ({ page }) => {
  await page.goto('/?country=United+States&region=NY&q=Research+Analyst+05');
  await expect(page.getByText('1 matching roles', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'View details' }).click();
  await expect(page.getByRole('link', { name: 'View original application' })).toHaveAttribute('href', 'https://higher.gs.com/roles/183697');
  await page.getByRole('textbox', { name: 'Search roles, companies or skills' }).fill('Research Analyst 03');
  await expect(page.getByText('1 matching roles', { exact: true })).toBeVisible();
  await expect(page.locator('article.job .company')).toContainText('Point72');
});
