from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query, Request

from . import db
from .coverage import scope
from .dedup import deduplicate
from .scheduling import status as scheduler_status
from .search import eligibility_status, match_explanation, matches
from .tracking import router

FILTER_KEYS = (
    "company",
    "type",
    "major",
    "minor",
    "area",
    "interest",
    "country",
    "region",
    "city",
    "arrangement",
    "graduation",
    "level",
    "deadline",
)


def create_app(path=None):
    @asynccontextmanager
    async def lifespan(app):
        db.initialize(path)
        yield

    app = FastAPI(title="RoleScout API", version="0.1.0", lifespan=lifespan)
    app.include_router(router(path))

    @app.get("/health")
    def health():
        with db.connect(path) as conn:
            conn.execute("SELECT 1")
        return {"status": "ok"}

    @app.get("/scheduler")
    def scheduler():
        return scheduler_status(path)

    @app.get("/jobs")
    def jobs(
        request: Request,
        q: str = Query("", max_length=200),
        certainty: Literal["all", "confirmed"] = "all",
        sort: Literal["default", "company", "verified"] = "default",
        since: Optional[datetime] = None,
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
    ):
        filters = {k: request.query_params.getlist(k) for k in FILTER_KEYS}
        if any(len(v) > 30 or any(len(x) > 100 for x in v) for v in filters.values()):
            raise HTTPException(422, "Filter selections exceed allowed size")
        found = [
            job
            for job in deduplicate(db.active_jobs(path))
            if (job.get("deadline_status") != "passed" or "Deadline passed" in filters["deadline"])
            and matches(job, filters, q, certainty == "confirmed")
        ]
        if since is not None:
            if since.tzinfo is None:
                raise HTTPException(422, "since must include a timezone")
            found = [job for job in found if datetime.fromisoformat(job["first_seen"]) > since]
        if sort == "company":
            found.sort(key=lambda j: (j["company"].casefold(), j["title"].casefold(), j["id"]))
        else:
            found.sort(
                key=lambda j: (j["last_verified" if sort == "verified" else "first_seen"], j["id"]),
                reverse=True,
            )
        start = (page - 1) * page_size
        items = [
            dict(
                job,
                match_reasons=match_explanation(job, filters),
                eligibility_match=eligibility_status(job, filters),
            )
            for job in found[start : start + page_size]
        ]
        return {"items": items, "total": len(found), "page": page, "page_size": page_size}

    @app.get("/jobs/{job_id}")
    def job_detail(job_id: int):
        with db.connect(path) as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Job not found")
        return db.serialize(row)

    @app.get("/filters")
    def filters():
        jobs = deduplicate(db.active_jobs(path))
        result = {}
        for key in ("company", "type", "arrangement", "level"):
            result[key] = sorted({j[key] for j in jobs})
        for key in ("interest", "studies", "graduation"):
            result[key] = sorted({v for j in jobs for v in j[key]})
        locs = {
            tuple(loc.get(k, "") for k in ("city", "region", "country"))
            for j in jobs
            for loc in j.get("locations", [])
        }
        result["locations"] = [
            dict(zip(("city", "region", "country"), loc)) for loc in sorted(locs)
        ]
        for key in ("city", "region", "country"):
            result[key] = sorted({loc[key] for loc in result["locations"] if loc[key]})
        from .geography import STATE_NAMES

        result["state_aliases"] = STATE_NAMES
        return result

    @app.get("/sources")
    def sources():
        with db.connect(path) as conn:
            result = [
                dict(r)
                for r in conn.execute("""SELECT s.*, (SELECT count(*) FROM jobs j
                WHERE j.source_id=s.id AND j.status='active') AS job_count FROM sources s ORDER BY s.name""")
            ]
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        for source in result:
            source["scope"] = scope(source["id"])
            source["stale"] = bool(
                source["last_success"]
                and (datetime.fromisoformat(source["last_success"]) < cutoff or source["error"])
            )
        return result

    @app.get("/runs")
    def runs(limit: int = Query(20, ge=1, le=100)):
        with db.connect(path) as conn:
            return [
                dict(r)
                for r in conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,))
            ]

    return app


app = create_app()
