"""Match user-added subjects against degree clauses without changing stored jobs."""

import re

from .eligibility import DEGREE, NEGATED, PREFERRED, SUBJECTS, clean


def include_custom_studies(job, filters):
    canonical = {name.casefold(): name for name in SUBJECTS}
    selected = [
        canonical.get(clean(value).casefold(), clean(value)) for value in filters.get("major", [])
    ]
    custom = [value for value in selected if value and value not in SUBJECTS]
    filters = {**filters, "major": selected}
    if not custom:
        return job, filters
    requirements = list(job.get("education_requirements", []))
    studies = set(job.get("studies", []))
    preferred_section = False
    for original in job.get("description", "").splitlines():
        text = clean(original)
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
        if NEGATED.search(text):
            continue
        match = DEGREE.search(text)
        if not match:
            continue
        clause = re.split(r"[.;]", match.group(1))[0]
        found = [
            value
            for value in custom
            if re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", clause, re.I)
        ]
        if found:
            studies.update(found)
            requirements.append(
                {
                    "subjects": found,
                    "text": original,
                    "preference": "preferred"
                    if preferred_section or PREFERRED.search(text)
                    else "stated",
                    "alternatives": bool(
                        re.search(r"related|equivalent|similar|or experience|or work", text, re.I)
                    ),
                }
            )
    return {**job, "studies": sorted(studies), "education_requirements": requirements}, filters
