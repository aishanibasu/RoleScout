import { chromium } from '@playwright/test';
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:5173');
  await page.getByText(/\d+ matching roles/).waitFor();
  console.log(await page.getByText(/\d+ matching roles/).innerText());
  console.log('Rendered cards:', await page.locator('article.job').count());
  await page.screenshot({ path: 'test-results/live-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: 'test-results/live-mobile.png', fullPage: true });
  console.log('Mobile overflow:', await page.evaluate(() => document.documentElement.scrollWidth > innerWidth));
  console.log('Browser errors:', errors);
  if (errors.length) process.exitCode = 1;
} finally { await browser.close(); }
