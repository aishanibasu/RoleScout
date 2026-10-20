import re

from . import ares
from .feed_common import job


class Workday:
    def __init__(self, company, host, tenant, board):
        self.NAME = company
        self.URL = "https://" + host + "/" + board
        self.API = "https://" + host + "/wday/cxs/" + tenant + "/" + board

    def fetch_snapshot(self, request):
        return ares.fetch_snapshot(request, self.API, self.NAME, self.URL)


apollo = Workday("Apollo", "athene.wd5.myworkdayjobs.com", "athene", "Apollo_Careers")


class SnapshotChanged(ValueError):
    """A changing index can be retried without accepting a partial snapshot."""


class WorkdayIndex(Workday):
    def fetch_snapshot(self, request):
        for attempt in range(2):
            try:
                return self._fetch_snapshot(request)
            except SnapshotChanged:
                if attempt:
                    raise

    def _fetch_snapshot(self, request):
        result, total, offset = [], None, 0
        unavailable = 0
        while total is None or offset < total:
            data = request(
                self.API + "/jobs",
                body={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""},
            ).json()
            rows = data.get("jobPostings")
            count = data.get("total")
            if type(count) is not int or not rows or (total is None and count <= 0):
                raise ValueError("Invalid Workday index")
            if total is not None and count not in (0, total):
                raise SnapshotChanged("Workday index changed during pagination")
            total = count if total is None else total
            if total > 20000:
                raise ValueError("Unexpected Workday count")
            for r in rows:
                if not r.get("externalPath"):
                    # Workday sometimes exposes an unavailable record as only its
                    # requisition ID. Count its feed position, but never invent a URL
                    # or reverify an existing listing from this stub.
                    fields = r.get("bulletFields")
                    if (
                        set(r) == {"bulletFields"}
                        and isinstance(fields, list)
                        and len(fields) == 1
                        and isinstance(fields[0], str)
                        and re.fullmatch(r"(?:R-)?[0-9]+", fields[0])
                    ):
                        unavailable += 1
                        continue
                    raise ValueError("Workday listing has no application path: " + repr(r))
                path = ares.listing_path(r["externalPath"])
                # List-only IDs use the exact public posting path, not a title or array index.
                loc = ares.location(r.get("locationsText", ""))
                if loc and re.match(r"^\d+ Locations?$", loc["city"], re.I):
                    loc = None
                item = job(
                    self.NAME,
                    path,
                    r["title"],
                    self.URL + path,
                    locs=[loc] if loc else [],
                    pending=True,
                )
                item["detail_path"] = path
                result.append(item)
            offset += len(rows)
            if len({j["external_id"] for j in result}) != len(result) or offset > total:
                raise SnapshotChanged("Duplicate Workday page")
        if unavailable > min(10, max(1, total // 100)):
            raise ValueError("Too many unavailable Workday records; refusing partial snapshot")
        for item in result:
            item["source_reported_total"] = total
            item["source_unavailable_count"] = unavailable
        return result

    def fetch_detail(self, request, item):
        path = ares.listing_path(item["detail_path"])
        details = ares.normalize(request(self.API + path).json(), path, self.NAME, self.URL)
        details.update(
            external_id=item["external_id"],
            detail_path=path,
            details_pending=False,
            details_available=True,
        )
        return details


bofa = WorkdayIndex("Bank of America", "ghr.wd1.myworkdayjobs.com", "ghr", "Lateral-US")
bofa.SCOPE = "US experienced-hire portal; campus and other regional portals are separate."
rbc = WorkdayIndex("RBC", "rbc.wd3.myworkdayjobs.com", "rbc", "RBCGLOBAL1")
rbc.SCOPE = "Public RBC global Workday board. Records without a title or application link are excluded; descriptions load separately."
