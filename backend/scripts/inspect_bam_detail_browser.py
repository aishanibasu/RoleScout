import asyncio,json
from urllib.parse import parse_qs
from pathlib import Path
from playwright.async_api import async_playwright
OUT=Path('data/research')
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(channel='chrome',headless=True)
  page=await browser.new_page()
  async def capture(r):
   if '/aura' in r.url and r.request.method=='POST':
    form=parse_qs(r.request.post_data or '')
    for action in json.loads(form.get('message',['{}'])[0]).get('actions',[]):
     params=action.get('params',{})
     if params.get('classname'):
      print('Public read method',params.get('classname'),params.get('method'),params.get('params'),flush=True)
      if 'searchJob' not in params.get('method','') and 'Options' not in params.get('method',''):
       (OUT/'bam_job_detail_response.json').write_text(await r.text())
   if 'auraCmpDef' in r.url:
    try:(OUT/'bam_component.txt').write_text(await r.text())
    except Exception:pass
  page.on('response',capture)
  try:
   await page.goto('https://bambusdev.my.site.com/s/',wait_until='domcontentloaded',timeout=30000)
   link=page.locator('a[data-id="Senior-Legal-Counsel_REQ8247"]');await link.wait_for(timeout=20000)
   await link.click();await page.wait_for_timeout(3000)
   print('job URL',page.url,flush=True)
   (OUT/'bam_detail_rendered.html').write_text(await page.content())
  finally:
   try:await asyncio.wait_for(browser.close(),5)
   except asyncio.TimeoutError:pass
asyncio.run(main())
