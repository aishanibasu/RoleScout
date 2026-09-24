"""Extract only explicit, unambiguous application closing dates."""

import re
from datetime import date, datetime, timezone
from functools import lru_cache

MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
DATE = rf"(?:\d{{4}}-\d{{2}}-\d{{2}}|{MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+\d{{4}}|\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH}\.?[,]?\s+\d{{4}})"
PATTERN = re.compile(
    rf"(?:application(?:s)?\s+(?:deadline|closing date|close(?:s)?(?: on)?|must be (?:received|submitted) by)|closing date|apply by|deadline to apply)\s*[:–—-]?\s*({DATE})\b",
    re.IGNORECASE,
)


@lru_cache(maxsize=40000)
def extract_deadline(description):
    candidates = []
    for match in PATTERN.finditer(description or ""):
        raw = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", match[1], flags=re.I)
        raw = re.sub(r"[,.]", "", raw)
        raw = " ".join(raw.split())
        for fmt in ("%Y-%m-%d", "%B %d %Y", "%b %d %Y", "%d %B %Y", "%d %b %Y"):
            try:
                candidates.append((datetime.strptime(raw, fmt).date().isoformat(), match[0]))
                break
            except ValueError:
                continue
    # Multiple different deadlines may refer to locations or recruiting rounds.
    if len({value for value, _ in candidates}) != 1:
        return None, None
    return candidates[0]


def with_deadline(job, today=None):
    today = today or datetime.now(timezone.utc).date()
    value, evidence = extract_deadline(job.get("description", ""))
    days = (date.fromisoformat(value) - today).days if value else None
    return dict(
        job,
        application_deadline=value,
        deadline_evidence=evidence,
        deadline_status=(
            "unknown"
            if days is None
            else "passed"
            if days < 0
            else "soon"
            if days <= 7
            else "upcoming"
        ),
    )
