"""Personal application tracking for the single-user, local application."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import db


class TrackingUpdate(BaseModel):
    status: Literal["Saved", "Applied", "Interviewing", "Offer", "Rejected"]
    notes: str = Field(default="", max_length=5000)


def router(path=None):
    api = APIRouter()

    @api.get("/tracked")
    def tracked():
        with db.connect(path) as conn:
            rows = conn.execute(
                "SELECT j.*, t.stage, t.notes, t.updated_at FROM tracked_jobs t "
                "JOIN jobs j ON j.id=t.job_id ORDER BY t.updated_at DESC, j.id DESC"
            ).fetchall()
        return [
            dict(
                db.serialize(row),
                tracking={
                    "status": row["stage"],
                    "notes": row["notes"],
                    "updated_at": row["updated_at"],
                },
            )
            for row in rows
        ]

    # Browser writes must come from this app, including when served through Vite.
    def check_origin(request):
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(403, "Cross-site writes are not allowed")

    @api.put("/tracked/{job_id}")
    def save(job_id: int, update: TrackingUpdate, request: Request):
        check_origin(request)
        with db.connect(path) as conn:
            if not conn.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone():
                raise HTTPException(404, "Job not found")
            stamp = db.now()
            conn.execute(
                "INSERT INTO tracked_jobs(job_id,stage,notes,updated_at) VALUES (?,?,?,?) "
                "ON CONFLICT(job_id) DO UPDATE SET stage=excluded.stage, "
                "notes=excluded.notes,updated_at=excluded.updated_at",
                (job_id, update.status, update.notes, stamp),
            )
        return {"status": update.status, "notes": update.notes, "updated_at": stamp}

    @api.delete("/tracked/{job_id}")
    def remove(job_id: int, request: Request):
        check_origin(request)
        with db.connect(path) as conn:
            conn.execute("DELETE FROM tracked_jobs WHERE job_id=?", (job_id,))
        return {"removed": True}

    return api
