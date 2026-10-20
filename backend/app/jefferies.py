"""Import the public campus feed; hydrate descriptions independently."""

import re
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit

from .ares import location
from .feed_common import job
from .html_tree import Tree

URL = "https://jefferies.tal.net/vx/mobile-0/appcentre-1/brand-4/candidate/jobboard/vacancy/2/feed"
SCOPE = "Campus opportunities from the public feed. Descriptions load separately; some detail pages require a browser verification. The experienced-hire portal is not connected."


def fetch_snapshot(request):
    root = ET.fromstring(request(URL).text)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    if root.find('a:link[@rel="next"]', ns) is not None:
        raise ValueError("Jefferies feed now requires pagination")
    entries = root.findall("a:entry", ns)
    if not entries:
        raise ValueError("Jefferies feed empty")
    result = []
    for entry in entries:
        link = entry.find('a:link[@rel="alternate"]', ns)
        url = link.attrib["href"] if link is not None else entry.findtext("a:id", namespaces=ns)
        url = re.sub(r"/xf-[^/]+", "", url or "").split("?")[0]
        parsed = urlsplit(url)
        match = re.search(r"/opp/(\d+)", parsed.path)
        if parsed.scheme != "https" or parsed.netloc != "jefferies.tal.net" or not match:
            raise ValueError("Jefferies application URL missing or invalid")
        item = job(
            "Jefferies", match.group(1), entry.findtext("a:title", namespaces=ns), url, pending=True
        )
        item["source_updated_at"] = entry.findtext("a:updated", namespaces=ns)
        result.append(item)
    return result


def fetch_detail(request, item):
    html = request(item["url"]).text
    if "oleeoProtect" in html or "<title>Quick Check Needed</title>" in html:
        raise ValueError(
            "Jefferies requires browser verification for this description; public feed metadata remains available"
        )
    tree = Tree(html).root
    fields = tree.find(
        lambda n: n.attrs.get("role") == "definition" and n.has_class("hform_value_view")
    )
    if not fields:
        raise ValueError("Jefferies details layout changed")
    description = max((n.text() for n in fields), key=len)
    if len(description) < 200:
        raise ValueError("Jefferies description incomplete")
    city = next((n.text() for n in fields if n.has_class("item78763")), "")
    loc = location(city)
    full = job(
        "Jefferies",
        item["external_id"],
        item["title"],
        item["url"],
        description,
        locs=[loc] if loc else [],
    )
    return {**item, **full}
