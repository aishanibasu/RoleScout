import json

from app import db
from app.collect import collect
from app.eligibility import enrich, extract
from app.reindex import reindex
from app.search import matches, match_explanation


def job(description):
    return enrich({'title': '2028 Internship', 'company': 'Example', 'description': description,
                   'external_id': 'EXAMPLE', 'type': 'Internship', 'level': 'Not specified', 'evidence': {}})


def test_education_requires_degree_context_not_job_keywords():
    j = job('Work with our finance and engineering teams.\nBachelor’s degree in computer science or mathematics.')
    assert j['studies'] == ['Computer Science', 'Mathematics']
    assert set(j['areas']) == {'Computing & Data', 'Mathematics & Statistics'}
    assert matches(j, {'major': ['Computer Science']}, confirmed=True)
    assert not matches(j, {'major': ['Finance']})


def test_minor_and_broad_area_do_not_confirm_degree_requirement():
    j = job('Bachelor’s degree in finance.')
    assert matches(j, {'minor': ['Finance']})
    assert not matches(j, {'minor': ['Finance']}, confirmed=True)
    assert matches(j, {'area': ['Business & Finance']})
    assert not matches(j, {'area': ['Business & Finance']}, confirmed=True)
    assert not matches(j, {'major': ['Biology'], 'minor': ['Finance']}, confirmed=True)
    assert match_explanation(j, {'minor': ['Finance']})[0]['status'] == 'provisional'


def test_preferred_and_alternative_education_not_hard_exclusions():
    j = job('Preferred qualifications:\nBachelor’s degree in finance.\nRequirements:\nBachelor’s degree in economics or related fields.')
    assert matches(j, {'major': ['Biology']})
    assert not matches(j, {'major': ['Finance']}, confirmed=True)
    assert matches(j, {'major': ['Economics']}, confirmed=True)


def test_negated_degree_not_extracted():
    assert job('A degree in finance is not required.')['studies'] == []


def test_experience_ignores_company_biography_and_preserves_range():
    j = job('Our firm has over 30 years of investing experience.\n3–5 years of professional experience in software engineering.')
    assert j['experience_range']['minimum'] == 3
    assert j['experience_range']['maximum'] == 5
    assert len(j['experience_requirements']) == 1
    assert j['level'] == 'Mid-level'
    assert matches(j, {'level': ['Mid-level']})
    assert not matches(j, {'level': ['Mid-level']}, confirmed=True)


def test_preferred_experience_does_not_set_seniority():
    j = job('Preferred qualifications:\n10+ years of experience in finance.')
    assert j['experience_range'] is None
    assert j['level'] == 'Not specified'


def test_multiple_distinct_experience_requirements_remain_separate():
    j = job('5+ years of experience in engineering.\n2+ years of experience in Python.')
    assert len(j['experience_requirements']) == 2
    assert j['experience_range'] is None
    assert j['level'] == 'Not specified'


def test_experience_range_crossing_bands_is_not_assigned_one_level():
    assert job('0-10 years of professional experience.')['level'] == 'Not specified'
    assert job('5-7+ years of professional experience.')['experience_range']['maximum'] is None


def test_partial_year_graduation_window_needs_month_review():
    j = job('Expected graduation date between December 2027 and August 2028.')
    assert j['graduation'] == [2027, 2028]
    assert j['graduation_window']['end'] == '2028-08-31'
    assert matches(j, {'graduation': ['2028']})
    assert not matches(j, {'graduation': ['2028']}, confirmed=True)
    assert not matches(j, {'graduation': ['2026']})
    assert match_explanation(j, {'graduation': ['2028']})[0]['status'] == 'provisional'


def test_full_year_inside_window_is_confirmed():
    j = job('Students graduating between December 2026 and July 2028.')
    assert j['graduation_confirmed_years'] == [2027]
    assert matches(j, {'graduation': ['2027']}, confirmed=True)


def test_ambiguous_windows_and_title_year_not_used():
    assert job('Join the summer 2028 program.')['graduation'] == []
    j = job('Graduating between December 2026 and July 2027.\nGraduating between December 2028 and July 2029.')
    assert j['graduation'] == [] and j['graduation_ambiguous']
    assert not matches(j, {'graduation': ['2027']}, confirmed=True)


def test_exact_class_and_repeated_windows():
    assert job('Applicants must be in the graduating class of 2029.')['graduation_confirmed_years'] == [2029]
    assert job(('Students graduating between January 2028 and December 2028.\n') * 2)['graduation_confirmed_years'] == [2028]


def test_reindex_preserves_source_freshness_status_and_is_idempotent(tmp_path):
    path = tmp_path / 'roles.sqlite3'
    collect(path, lambda: [job('Bachelor’s degree in finance.\n5+ years of experience.')])
    with db.connect(path) as conn:
        before = dict(conn.execute('SELECT * FROM jobs').fetchone())
        before_runs = conn.execute('SELECT count(*) FROM runs').fetchone()[0]
    assert reindex(path) == 1
    assert reindex(path) == 1
    with db.connect(path) as conn:
        after = dict(conn.execute('SELECT * FROM jobs').fetchone())
        assert conn.execute('SELECT count(*) FROM runs').fetchone()[0] == before_runs
    for field in ('first_seen', 'last_seen', 'status', 'misses'):
        assert after[field] == before[field]
    assert json.loads(after['payload']) == json.loads(before['payload'])
