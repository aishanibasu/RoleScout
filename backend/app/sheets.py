"""Single-user Google Sheets sync; credentials stay in ignored local .env files."""

import asyncio
import base64
import hashlib
import json
import os
import re
import secrets
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
from dotenv import dotenv_values
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from . import db

AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
API = "https://sheets.googleapis.com/v4/spreadsheets"
HEADERS = [
    "Company",
    "Role",
    "Eligibility",
    "Location",
    "Deadline",
    "Application URL",
    "Status",
    "Notes",
    "Updated at",
]


def initialize(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS sheets_sync (
        id INTEGER PRIMARY KEY CHECK(id=1), spreadsheet_id TEXT,
        revision INTEGER NOT NULL DEFAULT 0, synced_revision INTEGER NOT NULL DEFAULT -1,
        row_count INTEGER NOT NULL DEFAULT 1, last_synced TEXT, error TEXT,
        retry_at REAL NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0)""")
    conn.execute("INSERT OR IGNORE INTO sheets_sync(id) VALUES (1)")


def changed(conn):
    conn.execute("UPDATE sheets_sync SET revision=revision+1 WHERE id=1")


def export_rows(conn):
    rows = [HEADERS]
    records = conn.execute("""SELECT j.*,t.stage,t.notes,t.updated_at FROM tracked_jobs t
        JOIN jobs j ON j.id=t.job_id ORDER BY j.id""").fetchall()
    for record in records:
        item = db.serialize(record)
        experience = []
        for value in item.get("experience_requirements", []):
            end = value.get("maximum")
            text = f"{value['minimum']}–{end}" if end is not None else f"{value['minimum']}+"
            experience.append(
                text
                + " years"
                + (" (preferred)" if value.get("preference") == "preferred" else " (stated)")
            )
        eligibility = "Study: " + (", ".join(item.get("studies", [])) or "Not specified")
        eligibility += "; Experience: " + (
            "; ".join(experience) or item.get("level", "Not specified")
        )
        eligibility += "; Graduation: " + (
            ", ".join(map(str, item.get("graduation", []))) or "Not specified"
        )
        location = " · ".join(
            ", ".join(dict.fromkeys(loc[k] for k in ("city", "region", "country") if loc.get(k)))
            for loc in item.get("locations", [])
        )
        rows.append(
            [
                item["company"],
                item["title"],
                eligibility,
                location or "Not specified",
                item.get("application_deadline") or "Not specified",
                item["url"],
                record["stage"],
                record["notes"],
                record["updated_at"],
            ]
        )
    return rows


class GoogleSheets:
    def __init__(self, path=None, config_path=None, client_factory=None):
        self.path = path
        self.config_path = Path(config_path or Path(__file__).resolve().parents[1] / ".env")
        self.token_path = db.database_path(path).parent / ".env.google"
        self.client_factory = client_factory or (lambda: httpx.AsyncClient(timeout=25))
        self._lock = None
        self.pending = None

    @property
    def lock(self):
        # Construct on the running server loop (also supports Python 3.9).
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def config(self):
        return dotenv_values(self.config_path) if self.config_path.exists() else {}

    def credentials(self):
        return dotenv_values(self.token_path) if self.token_path.exists() else {}

    def configured(self):
        values = self.config()
        return bool(values.get("GOOGLE_CLIENT_ID") and values.get("GOOGLE_CLIENT_SECRET"))

    def state(self):
        with db.connect(self.path) as conn:
            return dict(conn.execute("SELECT * FROM sheets_sync WHERE id=1").fetchone())

    def status(self):
        state = self.state()
        credentials = self.credentials()
        connected = bool(state["spreadsheet_id"] and credentials.get("GOOGLE_REFRESH_TOKEN"))
        return {
            "configured": self.configured(),
            "connected": connected,
            "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{state['spreadsheet_id']}/edit"
            if state["spreadsheet_id"]
            else None,
            "pending": connected and state["revision"] != state["synced_revision"],
            "last_synced": state["last_synced"],
            "error": state["error"],
        }

    def begin(self):
        if not self.configured():
            raise HTTPException(
                409,
                "Google connection needs one-time setup. See the Google Sheets setup guide in README.md.",
            )
        if self.status()["connected"] and not self.state()["error"]:
            raise HTTPException(409, "A spreadsheet is already connected.")
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
        self.pending = (state, verifier, time.monotonic() + 600)
        config = self.config()
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        url = (
            AUTH
            + "?"
            + urlencode(
                {
                    "client_id": config["GOOGLE_CLIENT_ID"],
                    "redirect_uri": self.redirect_uri(),
                    "response_type": "code",
                    "scope": "https://www.googleapis.com/auth/drive.file",
                    "access_type": "offline",
                    "prompt": "consent",
                    "state": state,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                }
            )
        )
        return state, url

    def redirect_uri(self):
        return (
            self.config().get("GOOGLE_REDIRECT_URI") or "http://localhost:5173/api/sheets/callback"
        )

    async def google(self, method, url, **kwargs):
        async with self.client_factory() as client:
            response = await client.request(method, url, **kwargs)
        if response.status_code >= 400:
            # Do not surface request bodies, credentials, or Google response contents.
            raise RuntimeError(
                "Google authorization expired. Reconnect Google."
                if response.status_code in (400, 401) and url == TOKEN
                else f"Google Sheets request failed (HTTP {response.status_code}). Your roles are saved locally."
            )
        return response.json()

    def store_credentials(self, refresh_token):
        fd, name = tempfile.mkstemp(prefix=".env.google.", dir=self.token_path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "w") as handle:
                handle.write("GOOGLE_REFRESH_TOKEN=" + json.dumps(refresh_token) + "\n")
                handle.write(
                    "GOOGLE_CLIENT_ID=" + json.dumps(self.config()["GOOGLE_CLIENT_ID"]) + "\n"
                )
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.token_path)
        finally:
            temporary.unlink(missing_ok=True)

    async def finish(self, state, cookie, code):
        pending, self.pending = self.pending, None
        if (
            not pending
            or pending[2] < time.monotonic()
            or not secrets.compare_digest(state or "", pending[0])
            or not secrets.compare_digest(cookie or "", pending[0])
        ):
            raise HTTPException(
                400, "Google connection expired or invalid. Start again from RoleScout."
            )
        async with self.lock:
            config = self.config()
            token = await self.google(
                "POST",
                TOKEN,
                data={
                    "code": code,
                    "client_id": config["GOOGLE_CLIENT_ID"],
                    "client_secret": config["GOOGLE_CLIENT_SECRET"],
                    "redirect_uri": self.redirect_uri(),
                    "grant_type": "authorization_code",
                    "code_verifier": pending[1],
                },
            )
            if not token.get("refresh_token") or not token.get("access_token"):
                raise RuntimeError(
                    "Google did not grant background access. Please reconnect and grant permission."
                )
            state = self.state()
            identifier = state["spreadsheet_id"]
            if not identifier:
                sheet = await self.google(
                    "POST",
                    API,
                    headers={"Authorization": "Bearer " + token["access_token"]},
                    json={
                        "properties": {"title": "RoleScout Saved Roles"},
                        "sheets": [
                            {
                                "properties": {
                                    "sheetId": 0,
                                    "title": "Saved Roles",
                                    "gridProperties": {
                                        "rowCount": 1000,
                                        "columnCount": len(HEADERS),
                                        "frozenRowCount": 1,
                                    },
                                }
                            }
                        ],
                    },
                )
                identifier = sheet.get("spreadsheetId", "")
                if not re.fullmatch(r"[A-Za-z0-9_-]+", identifier):
                    raise RuntimeError("Google did not return a valid spreadsheet ID.")
                with db.connect(self.path) as conn:
                    conn.execute(
                        "UPDATE sheets_sync SET spreadsheet_id=? WHERE id=1", (identifier,)
                    )
            self.store_credentials(token["refresh_token"])
            with db.connect(self.path) as conn:
                conn.execute(
                    "UPDATE sheets_sync SET synced_revision=-1,error=NULL,retry_at=0,attempts=0 WHERE id=1"
                )

    async def sync(self):
        async with self.lock:
            state = self.state()
            credentials = self.credentials()
            if (
                not self.configured()
                or not state["spreadsheet_id"]
                or not credentials.get("GOOGLE_REFRESH_TOKEN")
                or state["synced_revision"] == state["revision"]
                or state["retry_at"] > time.time()
            ):
                return
            try:
                config = self.config()
                if credentials.get("GOOGLE_CLIENT_ID") != config["GOOGLE_CLIENT_ID"]:
                    raise RuntimeError("Google client settings changed. Reconnect Google.")
                with db.connect(self.path) as conn:
                    revision = conn.execute(
                        "SELECT revision FROM sheets_sync WHERE id=1"
                    ).fetchone()[0]
                    rows = export_rows(conn)
                token = await self.google(
                    "POST",
                    TOKEN,
                    data={
                        "client_id": config["GOOGLE_CLIENT_ID"],
                        "client_secret": config["GOOGLE_CLIENT_SECRET"],
                        "refresh_token": credentials["GOOGLE_REFRESH_TOKEN"],
                        "grant_type": "refresh_token",
                    },
                )
                # One atomic write, literal strings only: titles/notes cannot execute formulas.
                count = max(len(rows), state["row_count"])
                body = {
                    "requests": [
                        {
                            "updateSheetProperties": {
                                "properties": {
                                    "sheetId": 0,
                                    "gridProperties": {"rowCount": max(1000, count)},
                                },
                                "fields": "gridProperties.rowCount",
                            }
                        },
                        {
                            "updateCells": {
                                "range": {
                                    "sheetId": 0,
                                    "startRowIndex": 0,
                                    "endRowIndex": count,
                                    "startColumnIndex": 0,
                                    "endColumnIndex": len(HEADERS),
                                },
                                "rows": [
                                    {
                                        "values": [
                                            {"userEnteredValue": {"stringValue": str(value)}}
                                            for value in row
                                        ]
                                    }
                                    for row in rows
                                ],
                                "fields": "userEnteredValue",
                            }
                        },
                    ]
                }
                await self.google(
                    "POST",
                    API + "/" + state["spreadsheet_id"] + ":batchUpdate",
                    headers={"Authorization": "Bearer " + token["access_token"]},
                    json=body,
                )
                with db.connect(self.path) as conn:
                    conn.execute(
                        "UPDATE sheets_sync SET synced_revision=?,row_count=?,last_synced=?,error=NULL,retry_at=0,attempts=0 WHERE id=1",
                        (revision, len(rows), db.now()),
                    )
            except Exception as exc:
                message = (
                    str(exc)
                    if isinstance(exc, RuntimeError)
                    else "Google Sheets is temporarily unavailable. Your roles are saved locally; sync will retry."
                )
                delay = min(300, 5 * 2 ** min(state["attempts"], 6))
                with db.connect(self.path) as conn:
                    conn.execute(
                        "UPDATE sheets_sync SET error=?,attempts=attempts+1,retry_at=? WHERE id=1",
                        (message, time.time() + delay),
                    )

    async def worker(self):
        while True:
            try:
                await self.sync()
            except Exception:
                # A transient local DB lock must not stop future attempts.
                pass
            await asyncio.sleep(5)

    def router(self):
        api = APIRouter(prefix="/sheets")

        def local_write(request):
            origin = request.headers.get("origin")
            if request.headers.get("sec-fetch-site") == "cross-site" or (
                origin
                and origin
                not in {
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                    "http://localhost:5174",
                    "http://127.0.0.1:5174",
                }
            ):
                raise HTTPException(403, "Cross-site writes are not allowed")

        @api.get("/status")
        def status():
            return self.status()

        @api.post("/connect")
        async def connect(request: Request):
            local_write(request)
            state, url = self.begin()
            response = JSONResponse({"authorization_url": url})
            response.set_cookie(
                "rolescout_google_state", state, httponly=True, samesite="lax", max_age=600
            )
            return response

        @api.get("/callback")
        async def callback(request: Request, state: str = "", code: str = "", error: str = ""):
            request.scope["query_string"] = b""  # Keep authorization codes out of access logs.
            if error:
                self.pending = None
                return RedirectResponse("/?sheets=cancelled")
            try:
                await self.finish(state, request.cookies.get("rolescout_google_state"), code)
            except HTTPException:
                raise
            except Exception:
                return RedirectResponse("/?sheets=failed")
            response = RedirectResponse("/?sheets=connected")
            response.delete_cookie("rolescout_google_state")
            return response

        @api.post("/retry")
        async def retry(request: Request):
            local_write(request)
            with db.connect(self.path) as conn:
                conn.execute("UPDATE sheets_sync SET retry_at=0,revision=revision+1 WHERE id=1")
            return {"queued": True}

        @api.post("/disconnect")
        async def disconnect(request: Request):
            local_write(request)
            async with self.lock:
                self.pending = None
                self.token_path.unlink(missing_ok=True)
                with db.connect(self.path) as conn:
                    conn.execute(
                        "UPDATE sheets_sync SET spreadsheet_id=NULL,synced_revision=-1,row_count=1,last_synced=NULL,error=NULL,retry_at=0,attempts=0 WHERE id=1"
                    )
            return {"disconnected": True}

        return api
