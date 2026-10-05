"""Conservative matching: absence of eligibility data is not a positive assertion."""

from .geography import country_name, state_name
from .seniority import conflicts_with_early_career


def matches(job, filters, query="", confirmed=False):
    if conflicts_with_early_career(job, filters.get("level", [])):
        return False
    deadline = filters.get("deadline", [])
    status = job.get("deadline_status", "unknown")
    if deadline and not any(
        (choice == "Has a deadline" and status != "unknown")
        or (choice == "Closing within 7 days" and status == "soon")
        or (choice == "Deadline passed" and status == "passed")
        or (choice == "No date found" and status == "unknown")
        for choice in deadline
    ):
        return False
    if filters.get("company") and job["company"] not in filters["company"]:
        return False
    if (
        query.casefold().strip()
        not in " ".join([job["title"], job["company"], job["description"]]).casefold()
    ):
        return False
    for field in ("type", "arrangement", "level"):
        wanted = filters.get(field, [])
        if not wanted:
            continue
        actual = job.get(field, "Not specified")
        evidence = job.get("evidence", {}).get(field, {}).get("status", "unknown")
        if actual == "Not specified":
            if confirmed and "Not specified" not in wanted:
                return False
        elif actual not in wanted:
            return False
        elif confirmed and field == "level" and evidence != "explicit":
            return False
    geo = {f: filters.get(f, []) for f in ("city", "region", "country")}
    if any(geo.values()) and not any(
        all(
            not values
            or (
                any(
                    state_name(v, loc.get("country")) == state_name(loc.get(f), loc.get("country"))
                    for v in values
                )
                if f == "region"
                else country_name(loc.get(f)) in [country_name(v) for v in values]
                if f == "country"
                else loc.get(f) in values
            )
            for f, values in geo.items()
        )
        for loc in job.get("locations", [])
    ):
        return False
    if filters.get("interest") and not set(filters["interest"]).intersection(
        job.get("interest", [])
    ):
        return False
    education_ok, _, _ = education_match(job, filters, confirmed)
    if not education_ok:
        return False
    graduation = filters.get("graduation", [])
    if graduation:
        years = job.get("graduation", [])
        choice = graduation[0]
        if choice == "Not specified":
            return not years
        if not years:
            return not confirmed
        if not choice.isdigit() or int(choice) not in years:
            return False
        if confirmed and (
            job.get("evidence", {}).get("graduation", {}).get("status") != "explicit"
            or int(choice) not in job.get("graduation_confirmed_years", years)
        ):
            return False
    return True


def education_match(job, filters, confirmed=False):
    from .study_match import include_custom_studies

    job, filters = include_custom_studies(job, filters)
    majors, minors, areas = (
        filters.get("major", []),
        filters.get("minor", []),
        filters.get("area", []),
    )
    if not (majors or minors or areas):
        return True, "", "explicit"
    studies = set(job.get("studies", []))
    if not studies:
        return (
            not confirmed,
            "Education requirements could not be extracted; review the original description.",
            "unknown",
        )
    requirements = job.get("education_requirements", [])
    major_match = set(majors) & studies
    if major_match:
        stated = {s for r in requirements if r["preference"] == "stated" for s in r["subjects"]}
        exact = bool(major_match & stated)
        # Compatibility for older records that carry explicit evidence without the new structure.
        if not requirements:
            exact = job.get("evidence", {}).get("studies", {}).get("status") == "explicit"
        return (
            exact or not confirmed,
            "Your area of study appears in the "
            + ("stated" if exact else "preferred")
            + " education criteria: "
            + ", ".join(sorted(major_match))
            + ".",
            "explicit" if exact else "provisional",
        )
    minor_match = set(minors) & studies
    if minor_match:
        return (
            not confirmed,
            "Your minor is relevant, but it does not establish that you meet a degree or major requirement.",
            "provisional",
        )
    if set(areas) & set(job.get("areas", [job.get("area", "")])):
        return (
            not confirmed,
            "Your broad study area is related; check the specific degree subjects in the listing.",
            "provisional",
        )
    if any(r["alternatives"] or r["preference"] == "preferred" for r in requirements):
        return (
            not confirmed,
            "The listing allows related fields or describes preferred subjects; your education needs review.",
            "provisional",
        )
    return False, "Your study selections do not match the extracted degree subjects.", "mismatch"


def match_explanation(job, filters):
    reasons = []
    _, text, status = education_match(job, filters)
    if text:
        reasons.append({"criterion": "Education", "status": status, "text": text})
    graduation = filters.get("graduation", [])
    if graduation:
        choice = graduation[0]
        if not job.get("graduation"):
            reasons.append(
                {
                    "criterion": "Graduation",
                    "status": "unknown",
                    "text": "No unambiguous graduation window was extracted.",
                }
            )
        elif choice.isdigit() and int(choice) not in job.get(
            "graduation_confirmed_years", job["graduation"]
        ):
            reasons.append(
                {
                    "criterion": "Graduation",
                    "status": "provisional",
                    "text": "Your year overlaps the eligibility window; check your graduation month.",
                }
            )
        else:
            reasons.append(
                {
                    "criterion": "Graduation",
                    "status": "explicit",
                    "text": "Your graduation year matches the extracted criteria.",
                }
            )
    for field, label in (
        ("level", "Experience level"),
        ("type", "Opportunity type"),
        ("arrangement", "Work arrangement"),
    ):
        if filters.get(field):
            value = job.get(field, "Not specified")
            evidence = job.get("evidence", {}).get(field, {})
            state = "unknown" if value == "Not specified" else evidence.get("status", "unknown")
            reasons.append(
                {
                    "criterion": label,
                    "status": state,
                    "text": "Not specified; review the listing."
                    if value == "Not specified"
                    else value
                    + (
                        " is inferred; check the source requirements."
                        if state == "inferred"
                        else " matches your selection."
                    ),
                }
            )
    return reasons


def eligibility_status(job, filters):
    criteria = {
        key: filters.get(key, []) for key in ("major", "minor", "area", "graduation", "level")
    }
    reasons = match_explanation(job, criteria)
    if not reasons:
        return "not_assessed"
    return (
        "confirmed" if all(reason["status"] == "explicit" for reason in reasons) else "needs_review"
    )
