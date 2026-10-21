"""Direct public employer feeds, with complete snapshots and explicit missing details."""

import re
from urllib.parse import urlsplit

from .ares import location
from .feed_common import job
from .geography import STATE_NAMES
from .html_tree import Tree

# Aggregator copies are not evidence that an employer still advertises a role.
DIRECT_COMPANIES = {"apollo", "schonfeld", "dv trading", "millennium", "gts"}


def locations(raw):
    return [loc for part in re.split(r"\s*[;|]\s*", raw or "") if (loc := location(part))]


class Greenhouse:
    SCOPE = "Direct employer Greenhouse feed, including full job descriptions."

    def __init__(self, name, board):
        self.name, self.board = name, board
        self.URL = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"

    def fetch_snapshot(self, request):
        data = request(self.URL).json()
        rows = data.get("jobs")
        if not isinstance(rows, list) or not rows or data.get("meta", {}).get("total") != len(rows):
            raise ValueError("Incomplete Greenhouse snapshot")
        result = []
        for row in rows:
            url = row["absolute_url"]
            parsed = urlsplit(url)
            identifier = str(row["id"])
            if (
                parsed.netloc not in {"job-boards.greenhouse.io", "boards.greenhouse.io"}
                or parsed.path != f"/{self.board}/jobs/{identifier}"
                or not row.get("content")
            ):
                raise ValueError("Invalid Greenhouse job URL or missing description")
            item = job(
                self.name,
                identifier,
                row["title"],
                url,
                row["content"],
                locs=locations(row.get("location", {}).get("name", "")),
                posted=row.get("first_published"),
            )
            item["source_updated_at"] = row.get("updated_at")
            if row.get("application_deadline"):
                item["description"] += (
                    "\nApplications close on " + str(row["application_deadline"])[:10]
                )
            result.append(item)
        if len({j["external_id"] for j in result}) != len(result):
            raise ValueError("Duplicate Greenhouse jobs")
        return result


schonfeld = Greenhouse("Schonfeld", "schonfeld")
dvtrading = Greenhouse("DV Trading", "dvtrading")


class Millennium:
    URL = "https://career.mlp.com/careers?domain=mlp.com"
    API = "https://career.mlp.com/api/apply/v2/jobs"
    SCOPE = "Direct Millennium careers feed. Full descriptions populate in the background."

    def normalize(self, row):
        identifier = str(row["id"])
        if not identifier.isdigit() or row.get("isPrivate"):
            raise ValueError("Invalid public Millennium posting")
        locs = [loc for raw in row.get("locations", []) for loc in locations(raw)]
        return job(
            "Millennium",
            identifier,
            row["name"],
            f"https://career.mlp.com/careers/job/{identifier}?domain=mlp.com",
            row.get("job_description") or "",
            locs=locs,
            pending=not row.get("job_description"),
        )

    def fetch_snapshot(self, request):
        result, total, offset = [], None, 0
        while total is None or offset < total:
            data = request(f"{self.API}?domain=mlp.com&start={offset}&num=100").json()
            count, rows = data.get("count"), data.get("positions")
            if (
                type(count) is not int
                or not 0 < count < 10000
                or not isinstance(rows, list)
                or not rows
            ):
                raise ValueError("Invalid Millennium snapshot")
            if total is not None and total != count:
                raise ValueError("Millennium index changed during pagination")
            total = count
            result.extend(self.normalize(row) for row in rows)
            offset += len(rows)
            if offset > total or len({j["external_id"] for j in result}) != offset:
                raise ValueError("Duplicate or oversized Millennium page")
        return result

    def fetch_detail(self, request, item):
        row = request(f"{self.API}/{item['external_id']}?domain=mlp.com").json()
        if str(row.get("id")) != item["external_id"] or not row.get("job_description"):
            raise ValueError("Millennium detail missing matching description")
        return self.normalize(row)


millennium = Millennium()


def gts_locations(raw):
    result = []
    for part in raw.split("|"):
        fields = part.strip().split("-")
        country = {
            "US": "United States",
            "UK": "United Kingdom",
            "PL": "Poland",
            "UY": "Uruguay",
            "AR": "Argentina",
        }.get(fields[0], "")
        if not country:
            continue
        region = (
            STATE_NAMES.get(fields[1], fields[1]) if fields[0] == "US" and len(fields) > 2 else ""
        )
        city = "-".join(fields[2:]) if region else "-".join(fields[1:])
        result.append({"city": city, "region": region, "country": country, "raw": part})
    return result


class GTS:
    URL = "https://careers-gtsx.icims.com/jobs/search?ss=1&in_iframe=1"
    SCOPE = "Direct GTS careers listings with full descriptions."

    def fetch_snapshot(self, request):
        result = []
        page, total_pages = 1, None
        while total_pages is None or page <= total_pages:
            url = self.URL if page == 1 else self.URL + f"&pr={page - 1}"
            tree = Tree(request(url).text).root
            headers = tree.find(lambda n: n.has_class("iCIMS_SubHeader_Jobs"))
            match = re.search(r"Page\s+(\d+)\s+of\s+(\d+)", " ".join(n.text() for n in headers))
            if not match or int(match[1]) != page or not 1 <= int(match[2]) <= 100:
                raise ValueError("Invalid GTS pagination")
            if total_pages is not None and total_pages != int(match[2]):
                raise ValueError("GTS page count changed")
            total_pages = int(match[2])
            cards = tree.find(lambda n: n.has_class("iCIMS_JobCardItem"))
            if not cards:
                raise ValueError("GTS page missing jobs")
            for card in cards:
                links = card.find(lambda n: n.tag == "a" and n.has_class("iCIMS_Anchor"))
                if len(links) != 1:
                    raise ValueError("GTS job missing link")
                link = links[0]
                url = link.attrs["href"]
                parsed = urlsplit(url)
                identifier = re.match(r"/jobs/(\d+)/[^/]+/job$", parsed.path)
                if (
                    parsed.scheme != "https"
                    or parsed.netloc != "careers-gtsx.icims.com"
                    or not identifier
                ):
                    raise ValueError("Invalid GTS application link")
                title = re.sub(r"^\d+\s*-\s*", "", link.attrs.get("title", ""))
                locs = [
                    loc
                    for n in card.find(lambda n: n.has_class("iCIMS_JobHeaderData"))
                    for loc in gts_locations(n.text())
                ]
                item = job("GTS", identifier[1], title, url, locs=locs, pending=True)
                result.append(self.fetch_detail(request, item))
            page += 1
        if len({j["external_id"] for j in result}) != len(result):
            raise ValueError("Duplicate GTS jobs")
        return result

    def fetch_detail(self, request, item):
        tree = Tree(request(item["url"]).text).root
        sections = tree.find(lambda n: n.has_class("iCIMS_Expandable_Text"))
        if not sections:
            raise ValueError("GTS full description missing")
        paragraphs = []
        for section in sections:
            blocks = section.find(lambda n: n.tag in {"li", "p"})
            paragraphs.extend(n.text() for n in blocks or [section])
        return dict(
            item, description="\n".join(paragraphs), details_pending=False, details_available=True
        )


gts = GTS()
