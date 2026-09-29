"""Resolve clear title signals and reject conflicting early-career requirements."""

import re

EARLY = {"Student", "New graduate", "Entry level"}
LEADERSHIP = re.compile(
    r"\b(?:managing director|(?:senior |executive |assistant )?vice president|[ase]?vp|director|head of|chief|manager)\b",
    re.I,
)
SENIOR = re.compile(r"\b(?:senior|sr\.?|principal|staff|lead)\b", re.I)
SUPPORT = re.compile(r"\b(?:assistant|support)\s+(?:to|for)\b", re.I)
JUNIOR = re.compile(r"\b(?:intern(?:ship)?|apprentice(?:ship)?|trainee)\b", re.I)


def title_level(title):
    # Supporting an executive is not the same as being that executive.
    if SUPPORT.search(title) or JUNIOR.search(title):
        return None
    if LEADERSHIP.search(title):
        return "Manager / leadership"
    if SENIOR.search(title):
        return "Senior"
    return None


def normalize_title_level(job):
    level = title_level(job.get("title", ""))
    if not level or job.get("level") == level:
        return job
    evidence = dict(job.get("evidence", {}))
    evidence["level"] = {"status": "inferred", "text": job["title"], "rule": "senior_title"}
    return dict(job, level=level, evidence=evidence)


def conflicts_with_early_career(job, wanted):
    # Broader selections are OR choices; don't restrict a search that includes senior roles.
    selected = set(wanted) - {"Not specified"}
    if not selected or not selected <= EARLY:
        return False
    if title_level(job.get("title", "")):
        return True
    requirements = job.get("experience_requirements", [])
    stated = [e for e in requirements if e.get("preference") == "stated"]
    if not stated and job.get("experience_range"):
        stated = [job["experience_range"]]
    # Entry level uses the existing 0–2 year band. Any required minimum above it
    # is a conflict even when several requirements prevent assigning a single level.
    for requirement in stated:
        if requirement["minimum"] <= 2:
            continue
        return True
    return False
