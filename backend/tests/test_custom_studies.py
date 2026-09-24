from app.eligibility import enrich
from app.search import education_match


def listing(text):
    return enrich({"title": "Researcher", "description": text, "evidence": {}})


def test_custom_subject_matches_degree_and_preserves_stored_fields():
    job = listing("Bachelor's degree in Neuroscience required.")
    original = list(job["studies"])
    result = education_match(job, {"major": [" neuroscience "]}, confirmed=True)
    assert result[0] and result[2] == "explicit"
    assert "neuroscience" in result[1]
    assert job["studies"] == original


def test_custom_subject_mentions_do_not_confirm_eligibility():
    assert not education_match(listing("Work in neuroscience."), {"major": ["Neuroscience"]}, True)[
        0
    ]
    assert not education_match(
        listing("Degree in neuroscience not required."), {"major": ["Neuroscience"]}, True
    )[0]
    assert not education_match(
        listing("Degree in Neuroscience preferred."), {"major": ["Neuroscience"]}, True
    )[0]
    assert not education_match(
        listing("Preferred qualifications\nDegree in Neuroscience."),
        {"major": ["Neuroscience"]},
        True,
    )[0]
    assert not education_match(listing("Degree in Neuroscience."), {"major": ["science"]}, True)[0]


def test_presets_and_custom_subjects_match_any_selected_subject():
    assert education_match(
        listing("Degree in Mathematics."), {"major": ["mathematics", "Neuroscience"]}, True
    )[0]
    assert education_match(
        listing("Degree in Neuroscience or Economics."), {"major": ["Neuroscience"]}, True
    )[0]
    assert not education_match(listing("Degree in Economics."), {"major": ["Neuroscience"]}, True)[
        0
    ]
    assert education_match(listing("Education not specified."), {"major": ["Neuroscience"]})[0]
    assert not education_match(listing("Degree in Economics."), {"major": [".*"]}, True)[0]
