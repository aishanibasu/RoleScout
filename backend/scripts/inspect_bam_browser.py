"""Inspect only the anonymous public careers page in an isolated browser profile."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright
OUT=Path('data/research')
with sync_playwright() as p:
 browser=p.chromium.launch(channel='chrome',headless=True)
 page=browser.new_page();captured=[]
 def response(r):
  if '/aura' in r.url and r.request.method=='POST':
   try:
    text=r.text();index=len(captured)
    (OUT/f'bam_browser_response{index}.txt').write_text(text)
    (OUT/f'bam_browser_request{index}.json').write_text(json.dumps({'url':r.url,'body':r.request.post_data}))
    captured.append((r.status,len(text)))
   except Exception:pass
 page.on('response',response)
 page.goto('https://bambusdev.my.site.com/s/',wait_until='domcontentloaded',timeout=60000)
 page.wait_for_timeout(15000)
 (OUT/'bam_rendered.html').write_text(page.content())
 print(page.locator('body').inner_text()[:6000]);print('public data responses',captured)
 browser.close()
