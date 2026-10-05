"""Deterministic, evidence-backed extraction. Unrecognized requirements stay unknown."""

import calendar
import re
from datetime import date

VERSION = 3
SUBJECTS = {
    "Finance": (r"\bfinance\b", "Business & Finance"),
    "Economics": (r"\beconomics\b", "Business & Finance"),
    "Accounting": (r"\baccounting\b", "Business & Finance"),
    "Business": (r"\bbusiness(?: administration| management)?\b", "Business & Finance"),
    "Computer Science": (r"\bcomputer science\b", "Computing & Data"),
    "Data Science": (r"\bdata science\b", "Computing & Data"),
    "Information Technology": (r"\binformation technology\b", "Computing & Data"),
    "Mathematics": (r"\b(?:mathematics|math|maths)\b", "Mathematics & Statistics"),
    "Statistics": (r"\bstatistics\b", "Mathematics & Statistics"),
    "Engineering": (r"\bengineering\b", "Engineering"),
    "Physics": (r"\bphysics\b", "Natural Sciences"),
    "Biology": (r"\bbiology\b", "Natural Sciences"),
    "Chemistry": (r"\bchemistry\b", "Natural Sciences"),
    "Architecture": (r"\barchitecture\b", "Engineering"),
}
PREFERRED = re.compile(
    r"\b(?:prefer\w*|desired|ideally|a plus|nice.to.have|advantageous|given priority)\b", re.I
)
NEGATED = re.compile(
    r"\b(?:not required|no .{0,35}(?:required|necessary)|need not|not eligible|must not|do not|not seeking)\b",
    re.I,
)
DEGREE = re.compile(
    r"\b(?:degree\s+in|major(?:ing)?\s+in|(?:bachelor|master|baccalaureate|undergraduate|graduate|ph\.?d\.?)[’'s.\s]*(?:degree\s+)?in)\s+(.{1,230})",
    re.I,
)
MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTH = "(?:" + "|".join(MONTHS) + ")"
WINDOW = re.compile(
    r"\bbetween\s+(" + MONTH + r")\s+(20\d{2})\s+(?:and|to|[-–—])\s+(" + MONTH + r")\s+(20\d{2})",
    re.I,
)
YEARS = re.compile(
    r"^(?:(?:a minimum(?: of)?|minimum(?: of)?|at least|minimum required experience[: ]*|candidates? (?:must|should) have|you (?:(?:must|should) )?have|must have|requires?)\s+)?(\d{1,2})(?:\s*(?:[-–—]|to)\s*(\d{1,2}))?\s*(?:\+|or more|plus)?\s+years?[’']?\s+(?:of\s+)?(?:(?:[\w/-]+\s+){0,5}experience\b|(?:as|in)\s+)",
    re.I,
)


NUMBER_WORDS = dict(
    zip(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split(),
        range(21),
    )
)


NUMBER_WORD_PATTERN = re.compile(r"\b(?:" + "|".join(NUMBER_WORDS) + r")\b", re.I)


def clean(value):
    return re.sub(r"\s+", " ", value).strip(" \t•-–—")


def extract(description):
    education, experience, windows, classes = [], [], [], []
    preferred_section = False
    for original in description.splitlines():
        text = clean(original)
        if not text:
            continue
        if len(text) < 75 and re.fullmatch(
            r"(?:preferred|desired|additional) (?:qualifications|skills|requirements)[:.]?",
            text,
            re.I,
        ):
            preferred_section = True
            continue
        if len(text) < 75 and re.fullmatch(
            r"(?:requirements|qualifications|education|experience|what you (?:need|bring)|your (?:skills|qualifications)|required (?:skills|qualifications))[:.]?",
            text,
            re.I,
        ):
            preferred_section = False
            continue
        preferred = preferred_section or bool(PREFERRED.search(text))
        if NEGATED.search(text):
            continue
        match = DEGREE.search(text)
        if match:
            clause = re.split(r"[.;]", match.group(1))[0]
            subjects = [
                name for name, (pattern, _) in SUBJECTS.items() if re.search(pattern, clause, re.I)
            ]
            if subjects:
                education.append(
                    {
                        "subjects": subjects,
                        "text": original,
                        "preference": "preferred" if preferred else "stated",
                        "alternatives": bool(
                            re.search(
                                r"related|equivalent|similar|or experience|or work", text, re.I
                            )
                        ),
                    }
                )
        # Avoid corporate biographies by only accepting a requirement at the start of a line.
        years_text = NUMBER_WORD_PATTERN.sub(lambda m: str(NUMBER_WORDS[m[0].lower()]), text)
        years = YEARS.search(years_text)
        if years:
            minimum, maximum = int(years.group(1)), int(years.group(2)) if years.group(2) else None
            if maximum is not None and re.search(r"\d\s*\+\s+years?", years.group(0), re.I):
                maximum = None
            if minimum <= 40 and (maximum is None or minimum <= maximum <= 40):
                experience_preferred = preferred_section or bool(
                    PREFERRED.search(
                        re.split(
                            r";|\.\s+|\s+\((?!prefer|desired|ideally)|,\s*(?:ideally|preferably)|\b(?:ideally|preferably)\s+(?:in|within)\b",
                            text,
                            maxsplit=1,
                            flags=re.I,
                        )[0]
                    )
                )
                experience.append(
                    {
                        "minimum": minimum,
                        "maximum": maximum,
                        "text": original,
                        "preference": "preferred" if experience_preferred else "stated",
                    }
                )
        if not re.search(r"\bgraduat(?:e|es|ing|ion)\b", text, re.I) or preferred:
            continue
        window = WINDOW.search(text)
        if window:
            start_month, start_year = MONTHS[window.group(1).lower()], int(window.group(2))
            end_month, end_year = MONTHS[window.group(3).lower()], int(window.group(4))
            start = date(start_year, start_month, 1)
            end = date(end_year, end_month, calendar.monthrange(end_year, end_month)[1])
            if start <= end and end_year - start_year <= 6:
                windows.append(
                    {"start": start.isoformat(), "end": end.isoformat(), "text": original}
                )
        else:
            exact = re.search(r"\bgraduating class of (20\d{2})\b", text, re.I)
            if exact:
                classes.append({"year": int(exact.group(1)), "text": original})
    # Multiple distinct windows can describe alternative programs. Do not merge them into eligibility.
    window_keys = {(w["start"], w["end"]) for w in windows}
    class_years = {c["year"] for c in classes}
    graduation, confirmed_years, window, grad_text = [], [], None, ""
    if len(window_keys) == 1 and not classes:
        window = windows[0]
        start, end = date.fromisoformat(window["start"]), date.fromisoformat(window["end"])
        graduation = list(range(start.year, end.year + 1))
        confirmed_years = [
            y for y in graduation if start <= date(y, 1, 1) and end >= date(y, 12, 31)
        ]
        grad_text = window["text"]
    elif len(class_years) == 1 and not windows:
        graduation = confirmed_years = sorted(class_years)
        grad_text = classes[0]["text"]
    studies = sorted({s for item in education for s in item["subjects"]})
    areas = sorted({SUBJECTS[s][1] for s in studies})
    stated_experience = [e for e in experience if e["preference"] == "stated"]
    # Distinct experience clauses may refer to different skills/alternatives. Preserve all, but avoid
    # manufacturing a single minimum or seniority from multiple constraints.
    ranges = {(e["minimum"], e["maximum"]) for e in stated_experience}
    experience_range = stated_experience[0] if len(ranges) == 1 else None
    return dict(
        studies=studies,
        areas=areas,
        area=areas[0] if len(areas) == 1 else "",
        education_requirements=education,
        experience_requirements=experience,
        experience_range=experience_range,
        graduation=graduation,
        graduation_confirmed_years=confirmed_years,
        graduation_window=window,
        graduation_text=grad_text,
        graduation_ambiguous=bool((windows or classes) and not graduation),
    )


def enrich(job):
    result = dict(job)
    extracted = extract(job["description"])
    result.update(extracted)
    evidence = dict(job.get("evidence", {}))
    education = extracted["education_requirements"]
    evidence["studies"] = {
        "status": "explicit" if education else "unknown",
        "text": "\n".join(e["text"] for e in education),
    }
    evidence["graduation"] = {
        "status": "explicit" if extracted["graduation"] else "unknown",
        "text": extracted["graduation_text"],
    }
    experience = extracted["experience_range"]
    evidence["experience"] = {
        "status": "explicit" if extracted["experience_requirements"] else "unknown",
        "text": "\n".join(e["text"] for e in extracted["experience_requirements"]),
    }
    # Recompute only levels previously created by this extractor; preserve source adapter labels.
    if evidence.get("level", {}).get("rule") == "experience_range":
        result["level"] = "Not specified"
        evidence["level"] = {"status": "unknown"}
    if result.get("level", "Not specified") == "Not specified" and experience:
        minimum = experience["minimum"]

        def band(years):
            return "Entry level" if years <= 2 else "Mid-level" if years <= 5 else "Senior"

        if experience["maximum"] is None or band(minimum) == band(experience["maximum"]):
            result["level"] = band(minimum)
            evidence["level"] = {
                "status": "inferred",
                "text": experience["text"],
                "rule": "experience_range",
            }
    result["evidence"] = evidence
    result["extraction_version"] = VERSION
    from .seniority import normalize_title_level

    return normalize_title_level(result)
