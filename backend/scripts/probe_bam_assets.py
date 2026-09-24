from probe_feeds import go,OUT
import re
from urllib.parse import urljoin
s=(OUT/'bam.html').read_text()
for i,url in enumerate(re.findall(r'<script[^>]*src="([^"]+)"',s)):
 if '/sfsites/l/' in url:print(go((f'bam_asset{i}',(urljoin('https://bambusdev.my.site.com',url),None))),flush=True)
