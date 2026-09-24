import re

from .feed_common import job
from .geography import normalize_locations

URL = "https://api-higher.gs.com/gateway/api/v1/graphql"
SCOPE = "Goldman Sachs public campus, early-career and professional role index; visit the employer for full requirements."
QUERY = "query GetRoles($searchQueryInput: RoleSearchQueryInput!) { roleSearch(searchQueryInput: $searchQueryInput) { totalCount items { roleId jobTitle jobFunction locations { primary state country city } status division jobType { code description } } } }"


def application_url(role_id):
    match = re.fullmatch(
        r"([0-9]+)(?:_GS_[A-Z_]+)?|([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})",
        str(role_id),
    )
    if not match:
        raise ValueError("Invalid Goldman Sachs role ID")
    return "https://higher.gs.com/roles/" + (match.group(1) or match.group(2))


def fetch_snapshot(request):
    results = []
    total = None
    page = 0
    while total is None or len(results) < total:
        body = {
            "operationName": "GetRoles",
            "query": QUERY,
            "variables": {
                "searchQueryInput": {
                    "page": {"pageSize": 100, "pageNumber": page},
                    "sort": {"sortStrategy": "POSTED_DATE", "sortOrder": "DESC"},
                    "filters": [],
                    "experiences": ["CAMPUS", "EARLY_CAREER", "PROFESSIONAL"],
                    "searchTerm": "",
                }
            },
        }
        response = request(URL, body=body).json()
        if response.get("errors"):
            raise ValueError("Goldman Sachs public query rejected")
        data = response["data"]["roleSearch"]
        rows = data["items"]
        count = data["totalCount"]
        if (
            not rows
            or type(count) is not int
            or not 0 < count < 20000
            or (total is not None and total != count)
        ):
            raise ValueError("Goldman Sachs index incomplete or changed during collection")
        total = count
        for r in rows:
            locations = [
                dict(
                    city=loc.get("city") or "",
                    region=loc.get("state") or "",
                    country=loc.get("country") or "",
                    raw=", ".join(loc[k] for k in ("city", "state", "country") if loc.get(k)),
                )
                for loc in r.get("locations") or []
            ]
            item = job(
                "Goldman Sachs",
                r["roleId"],
                r["jobTitle"],
                application_url(r["roleId"]),
                locs=locations,
                tags=[r.get("jobFunction"), r.get("division")],
            )
            item["description_note"] = "Full requirements are available on the employer’s website."
            results.append(normalize_locations(item))
        if len({r["external_id"] for r in results}) != len(results) or len(results) > total:
            raise ValueError("Duplicate Goldman Sachs page")
        page += 1
    return results
