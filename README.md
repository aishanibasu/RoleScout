# Role Searcher

## Product plan

Status: React frontend connected to a FastAPI/SQLite backend; 14 listing sources are connected with daily refresh schedules; all 17 requested sources have visible coverage status.
Created: September 17, 2026.
Project location: `/Users/aishanibasu/Projects/Role Searcher`.

## Run locally

The app now reads real listings from the backend; it no longer falls back to fictional sample jobs.

### Backend (terminal 1)

```bash
cd "/Users/aishanibasu/Projects/Role Searcher/backend"
uv sync
uv run python -m app.collect point72
uv run python -m app.collect ares
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The collector saves jobs in `backend/data/roles.sqlite3`. Set `ROLE_SEARCHER_DB` to override the path. An empty database returns zero listings until collection succeeds. Re-run `python -m app.collect point72` or `python -m app.collect ares` to refresh an individual source. Manual and scheduled refreshes share a process lock, so overlapping runs are rejected. A source-provided retry deadline applies to both.

### Frontend (terminal 2)

```bash
cd "/Users/aishanibasu/Projects/Role Searcher/frontend"
pnpm install --frozen-lockfile
pnpm dev
```

Open the URL printed by Vite. Its `/api` proxy forwards requests to port 8000. The production build needs an equivalent reverse proxy; `pnpm preview` alone does not configure the API connection.

The **Search LinkedIn** button below the search box opens LinkedIn Jobs in a new tab with the current search text and selected location. When multiple locations are selected, choose one in the LinkedIn location dropdown. Without a location selection, choose the location on LinkedIn. Other Role Searcher filters are not transferred, and LinkedIn results are viewed on LinkedIn rather than imported into the local index.

### Automatic refreshes (terminal 3)

```bash
cd "/Users/aishanibasu/Projects/Role Searcher/backend"
uv run python -m app.scheduler
```

Keep this process running for automatic collection every 24 hours. It checks source schedules every 30 seconds and skips sources that are not due. Each source has its own lock, due time, retry deadline, and collection history. A failure in one source does not prevent other sources from refreshing. A failed collection waits until the next daily attempt; source `Retry-After` deadlines can postpone it further. Restarting the worker preserves the due time. After sleep, overdue work runs on the next check. Stop with Ctrl+C.

The app shows whether the worker is active, each source’s last successful refresh, and its next due time. A heartbeat expires after 90 seconds if the worker crashes. `GET /scheduler` exposes the same state. `uv run python -m app.scheduler --once` checks due work once without starting a persistent worker.

A macOS login service is installed for this project and starts the refresh worker automatically. Do not start a second worker manually while it is active. Refreshes pause while logged out, asleep, or powered off; overdue sources are checked after the worker resumes. Process locking supports macOS/Linux. Other machines can run the worker manually using the command above.

### Validation

```bash
# From backend/
uv run pytest -q
# From frontend/
pnpm build
```

### Backend endpoints

Interactive API documentation: <http://127.0.0.1:8000/docs>.

- `GET /health`: local database connectivity.
- `GET /jobs`: repeated dropdown query parameters (including `company=Point72` or `company=Ares%20Management`), `q`, `certainty=all|confirmed`, `sort=default|company|verified`, `page`, and `page_size` (maximum 100).
- `GET /jobs/{id}`: full listing, source text, extraction evidence, and freshness.
- `GET /filters`: available values and normalized locations.
- `GET /sources`: all 17 requested sources, active counts, errors, and freshness status.
- `GET /runs`: recent collection results, including interrupted runs.
- `GET /scheduler`: worker heartbeat, running state, and persisted source schedules.

### Current coverage and limitations

Verified local imports on September 18, 2026; counts change with refresh.

| Source | Listings | Coverage |
| --- | ---: | --- |
| [Apollo](https://www.apollo.com/careers) | 67 | Public career listings; requirements are extracted from available descriptions. |
| [Ares Management](https://www.ares.com/us/careers) | 288 | Public career listings; requirements are extracted from available descriptions. |
| [BNY](https://www.bny.com/corporate/global/en/about-us/careers/work-with-us.html) | 1,399 | Public BNY career index. Full descriptions populate in background; a few unavailable feed records may be excluded. |
| [Balyasny Asset Management](https://www.bamfunds.com/careers) | 140 | Public Balyasny career listings, including internships. Full descriptions populate in background. |
| [Bank of America](https://careers.bankofamerica.com/en-us) | 1991 | US experienced-hire portal; campus and other regional portals are separate. Descriptions populate in background. |
| [Citadel](https://www.citadel.com/careers/) | — | The public careers portal returned an access challenge. |
| [Goldman Sachs](https://www.goldmansachs.com/careers) | 1266 | Goldman Sachs public campus, early-career and professional role index; visit the employer for full requirements. |
| [HFT Jobs](https://www.hft-jobs.com/jobs) | 23453 | Third-party aggregator metadata. Full requirements remain on the original employer website. |
| [Hudson Bay Capital](https://www.hudsonbaycapital.com/careers) | — | The official careers page provides careers@hudsonbaycapital.com for inquiries; no public job listing feed was found. Open the careers page for details. |
| [JPMorgan Chase](https://www.jpmorganchase.com/careers) | — | The linked Oracle portal returned HTTP 403 when checking collection access. |
| [Jefferies](https://www.jefferies.com/careers/) | 58 | Campus opportunities only; the experienced-hire portal is not connected. |
| [Morgan Stanley](https://www.morganstanley.com/people-opportunities) | 123 | Student and graduate programs; experienced-hire feed not returning listings. |
| [Point72](https://careers.point72.com/) | 231 | Public career listings; requirements are extracted from available descriptions. |
| [RBC](https://jobs.rbc.com/) | 1380 | Public RBC global Workday board linked from RBC career listings. Descriptions populate in background. |
| [Susquehanna](https://sig.com/careers/) | 265 | Public career listings; requirements are extracted from available descriptions. |
| [Two Sigma](https://www.twosigma.com/careers/) | 55 | Public Two Sigma open roles, including early careers. |
| [UBS](https://www.ubs.com/global/en/careers.html) | 541 | Public UBS experienced-hire board (site 5012); other campus boards are separate. Full descriptions populate in background. |

31,257 source records produce 30,910 search results after merging matching employer/HFT application URLs and retaining attribution. Different URLs for the same role may still appear separately. Aggregator metadata is labeled. Hudson Bay Capital is included as contact-based recruiting, with no public listing feed found.

Refresh with `python -m app.collect SOURCE_ID`. IDs: `point72`, `ares`, `apollo`, `sig`, `twosigma`, `morganstanley`, `jefferies`, `bofa`, `rbc`, `gs`, `hft`, `ubs`, `bam`, and `bny`. The scheduler refreshes due sources; sources without adapters are not scheduled.

Collectors check robots directives, throttle requests, respect retry deadlines and reject incomplete, empty, duplicate or sharply reduced snapshots. Failed refreshes preserve previous listings. Two successful snapshots omitting a job mark it inactive. A failed refresh or data older than 48 hours is labeled stale.

Bank descriptions populate in batches of 20 between scheduler cycles; initial completion may take hours. Manual batch: `python -m app.hydrate rbc --limit 20` (also `bofa`, `bny`, `ubs` or `bam`). Descriptions survive index refreshes, are rechecked after seven days, and preserve listing verification timestamps. Detail failures back off. Missing descriptions do not confirm education, graduation or experience requirements; review the employer listing.

The UI includes coverage status, dropdown filters, pagination, eligibility evidence, source links and URL-persisted selections. Newest means first discovered by this app. Browser back/forward navigation restores filters, search, sort, and pagination. Search loads the local index into memory; larger deployments should move filtering and deduplication into database queries.

### Education, graduation, and experience matching

Descriptions now pass through a shared, versioned extractor during collection. The job detail view shows the source excerpts and distinguishes stated criteria, preferred qualifications, inferred levels, and provisional matches.

- **Study subjects:** recognized within degree/major statements, not from arbitrary mentions of finance or technology in the description. Each subject maps to a broad study area. Preferred subjects and related-field/equivalent-experience alternatives remain visible. A minor or broad study-area match does not confirm a degree requirement.
- **Graduation:** supports exact graduating-class years and explicit “between Month YYYY and Month YYYY” windows. Program years in titles are ignored. Year selections overlapping only part of a window require month-level review and are excluded from confirmed-only results. Distinct conflicting windows remain unknown.
- **Experience:** extracts numeric year requirements at the beginning of a requirement line, preserving ranges and preferred wording. Corporate biographies are excluded. When one unambiguous stated range is available, minimums of 0–2, 3–5, and 6+ years suggest Entry level, Mid-level, and Senior respectively. These labels are inferred, never confirmed eligibility; bounded ranges spanning categories remain unclassified. Existing student/graduate labels are preserved.
- **Search explanations:** education, graduation, opportunity type, work arrangement, and experience selections receive matching explanations in job details. Confirmed matches mean direct support for the selected criteria, not a guarantee that every qualification is satisfied.

The extractor intentionally misses unsupported phrasing, spelled-out experience numbers, many degree abbreviations, and complex alternative requirements. Degree level, enrollment status, and all other qualifications still need review in the original posting. Unknown locations preserve their original text and may lack country/region normalization. Remote-arrangement extraction is not implemented.

To reprocess stored descriptions after extractor changes without fetching career sites:

```bash
cd "/Users/aishanibasu/Projects/Role Searcher/backend"
uv run python -m app.reindex
```

Reindexing updates derived fields in one transaction and preserves source verification dates, listing status, IDs, and collection history. Use this command to reprocess stored listings.

This is a local development backend. Daily refresh scheduling is implemented. Hosted deployment, broader source adapters, and more complete eligibility extraction are next milestones.


## Daily workflow and development (September 24, 2026)

- **Explore roles:** search, filter, paginate, and sort by first seen, company, or last verification. Search state is kept in the URL and browser back/forward restores it.
- **Save role:** adds a listing to **Saved & applications**. Track Saved, Applied, Interviewing, Offer, or Rejected, and save notes explicitly with **Save changes**.
- The tracker is stored in the local SQLite database and keeps closed listings. It is shared by browsers using this local backend; it is not an account or cloud sync service.
- **New since your last visit** uses a timestamp stored in this browser and compares it with when the app first discovered each role. The toggle becomes available on a subsequent visit. Private browsing or disabled storage may reset this timestamp.
- Listings show first-seen and verification dates. Verification older than 48 hours is marked overdue.
- LinkedIn importing remains on hold; the existing external search link remains available.

Use uv with `backend/pyproject.toml` and `backend/uv.lock`, and pnpm with `frontend/pnpm-lock.yaml`. Install uv and pnpm on your PATH before using the commands above. Python configuration is loaded from `backend/.env`; copy `.env.example` for optional settings. No API secrets are needed by the current app.

Validation:

```bash
# backend/
uv run pytest -q
uv run ruff check app/main.py app/db.py app/tracking.py tests/test_tracking.py tests/serve_e2e.py
uv run ruff format --check app/main.py app/db.py app/tracking.py tests/test_tracking.py tests/serve_e2e.py
# frontend/
pnpm build
pnpm exec playwright install chromium
pnpm test:e2e
```

Playwright starts a real FastAPI server with a disposable seeded database on port 8011 and Vite on port 5174. Tests cover desktop and mobile Chromium, URL navigation, application tracking persistence, new-job filtering, and request failure recovery. They do not modify the real job index or contact employer feeds. Screenshots and failure traces go into ignored `frontend/test-results/`.

New endpoints: `GET /tracked`, `PUT /tracked/{job_id}` with `status` and optional `notes`, and `DELETE /tracked/{job_id}`. `GET /jobs` accepts a timezone-aware `since` timestamp. Keep the server bound to localhost; authentication and multi-user hosting are not implemented.

## 1. Goal

Build a web application that brings jobs and internships from company career pages and selected job boards into one searchable view. Users select dropdown filters to find relevant opportunities and follow the original application link to apply.

Initial source coverage focuses on investment banks, investment managers, hedge funds, and trading firms. The filter design supports other industries, including technology and pharmaceuticals, as sources are added. Industry options must show actual coverage; supporting a filter does not mean that industry already has listings.

## 2. First-version scope

- Collect publicly available listings from the sources in the source registry below, starting with a small working subset and expanding in stages.
- Normalize titles, companies, locations, education requirements, graduation windows, and experience requirements.
- Provide dropdown filters for opportunity type, major, minor, area of study, field of interest, location, graduation year, and experience level.
- Display searchable, paginated results with original application links and freshness information.
- Merge duplicate postings while retaining source attribution.
- Support browsing without an account.

Saved jobs and local application tracking are implemented. Later features: email alerts, resume matching, accounts, and additional industries. Automatic application submission is outside the first version.

## 3. Main user flow

1. Open the search page and browse available listings.
2. Select one or more dropdown filters.
3. See the matching result count and active filter chips.
4. Open a listing to review requirements and why it matched.
5. Select **Apply on company website** to open the original application page.

Filters should persist in the page URL so searches can be bookmarked and shared.

## 4. Dropdown filters

All filters default to **Any**. Long lists are searchable. Multi-select dropdowns include checkboxes, selected values, and a clear control. Controls must work with a keyboard and have accessible labels.

| Dropdown | Selection | Initial options / behavior |
| --- | --- | --- |
| Opportunity type | Multiple | Internship, full-time, part-time, co-op, graduate program, apprenticeship |
| Major | Multiple | Finance, Economics, Accounting, Business, Computer Science, Data Science, Mathematics, Statistics, Engineering, Physics, Biology, Chemistry, other supported disciplines |
| Minor | Multiple | Same discipline taxonomy as major; optional; no minor required |
| Area of study | Multiple | Business & Finance, Computing & Data, Mathematics & Statistics, Engineering, Natural Sciences, Health & Life Sciences, Social Sciences, Arts & Humanities, Interdisciplinary |
| Field of interest | Multiple | Finance, Technology, Pharmaceuticals & Biotechnology, Healthcare, Consulting, Research, Operations; expand with source coverage |
| Country | Multiple | Countries present in indexed listings |
| State / region | Multiple | Options constrained by selected countries |
| City | Multiple | Options constrained by selected countries and regions |
| Work arrangement | Multiple | On-site, hybrid, remote, not specified |
| Graduation year | Single | Already graduated, current year minus two through current year plus six, other year, not specified; year list advances automatically |
| Experience level | Multiple | Student, new graduate, entry level, mid-level, senior, manager / leadership, not specified |

Optional secondary dropdowns: company, employer industry, job function, degree level, and posting age.

### Matching rules

- Use OR between selected values within one dropdown and AND between independent filters.
- Treat major, minor, and broad area of study as a combined education profile: a match to any selected discipline can establish relevance. Selecting a minor must not imply the applicant holds a degree in that subject.
- Distinguish explicit education requirements from inferred relevance. A related major is not proof of eligibility, and a minor cannot satisfy an explicitly required major.
- Field of interest may match employer industry or job function. For example, Technology can surface software engineering at an investment bank. Display which attribute matched.
- Preserve distinctions between employer industry (financial services) and job function (software engineering).
- Compare graduation year with explicit eligibility dates or years. An internship's calendar year is not necessarily the required graduation year.
- Where month-level graduation eligibility exists, a year-only match is provisional; show the exact date window.
- Keep graduation year and experience level independent. Already graduated does not imply professional experience.
- Preserve explicit years-of-experience requirements; inferred seniority labels must be identified as inferred.
- Normalize location aliases such as NYC and New York City. Keep New Jersey separate from New York, and support jobs with multiple locations.
- Remote roles may still have country or state restrictions; remote does not mean worldwide.
- Missing requirements remain unknown rather than being invented. By default, include potentially relevant jobs with unspecified education, graduation, or experience requirements and label them **Requirements not specified**.
- Provide a **Match certainty** dropdown: **Include unspecified requirements** (default) or **Confirmed matches only**. Confirmed matches require explicit evidence for selected eligibility criteria; inferred relevance alone is insufficient.
- For explicit contradictions to a selected eligibility criterion, exclude the listing. For location filters, jobs with unknown location do not qualify as geographic matches.

## 5. Search page and listing details

### Layout

- Header with product name and brief purpose.
- Keyword search for job title, company, or skills.
- Filter sidebar on desktop; collapsible filter panel on mobile.
- Results count, active filter chips, and **Clear all**.
- Sort dropdown: newest first, most recently verified, company A–Z. Use first-seen date when posting date is absent and label it accurately.
- Result cards and pagination.

### Each result shows

- Title and company.
- Location(s) and work arrangement when stated.
- Opportunity type and experience level.
- Relevant study areas and interest tags, with inferred tags distinguished.
- Graduation eligibility or **Not specified**.
- Posting date when available, first seen, and last successfully verified.
- Source and application link.

### Detail view

Show a concise description, skills, explicit eligibility requirements, exact graduation window, years of experience, application deadline if stated, and source attribution. Include the evidence behind education and experience matching. Do not label a job as eligible merely because it is relevant.

### Required states

Loading, no results, source temporarily unavailable, stale listing, closed listing, and application link unavailable. A source failure must not prevent browsing other listings. Show active listings by default and explain when some sources are stale.

## 6. Source registry and coverage

The long-term aim is broad investment-bank coverage. “All investment banks” requires an expandable, maintained registry; it is not a claim of complete initial coverage.

### User-provided sources

| Source | Starting page | Initial status |
| --- | --- | --- |
| HFT Jobs | [User's filtered search](https://www.hft-jobs.com/jobs?exp=student&country=United+States&city=New+York%2CNew+York+City%2CNew+Jersey+%3B+New+York%3B+Palm+Beach) | Research pending; browsing tool could not access the page |
| Apollo Global Management | [Careers](https://www.apollo.com/careers) | Landing page accessible; listing integration pending |
| Ares Management | [Careers](https://www.ares.com/us/careers) | Active Workday collector; 288 listings verified in initial import |
| Balyasny Asset Management | [Careers](https://www.bamfunds.com/careers) | Researching dynamic Salesforce job portal |
| Point72 | [Careers](https://careers.point72.com/) | Active collector; live refresh verified |
| Citadel | [Careers](https://www.citadel.com/careers/) | Direct collection blocked by access challenge |
| Two Sigma | [Careers](https://www.twosigma.com/careers/) | Landing page accessible; listing integration pending |
| Susquehanna / SIG | [Careers](https://sig.com/careers/) | Landing page accessible; listing integration pending |

Page accessibility was checked on September 17, 2026. It does not establish an available feed, permission to collect listings, or a working integration. Inspect each linked job portal before choosing an adapter. The HFT URL is an example search, not a permanent restriction on the application's geography or experience levels.

### Initial bank registry

Official career websites for every bank explicitly named in the request:

| Bank | Official career website |
| --- | --- |
| JPMorgan Chase / J.P. Morgan (JP) | [JPMorganChase Careers](https://www.jpmorganchase.com/careers) |
| Morgan Stanley | [Morgan Stanley Careers](https://www.morganstanley.com/people-opportunities) |
| Bank of America / BofA Securities | [Bank of America Careers](https://careers.bankofamerica.com/en-us) |
| BNY / Bank of New York Mellon (BoNY) | [BNY Careers](https://www.bny.com/corporate/global/en/about-us/careers/work-with-us.html) |
| UBS | [UBS Careers](https://www.ubs.com/global/en/careers.html) |
| RBC / RBC Capital Markets | [RBC Careers](https://jobs.rbc.com/) |
| Goldman Sachs (GS) | [Goldman Sachs Careers](https://www.goldmansachs.com/careers) |
| Jefferies | [Jefferies Careers](https://www.jefferies.com/careers/) |

Career links checked on September 17, 2026. All bank listing integrations remain pending. RBC's root careers URL currently redirects to its Canadian landing page; onboarding must include US opportunities as well.

Expansion candidates: Citi, Barclays, Deutsche Bank, Wells Fargo, HSBC, BNP Paribas, Societe Generale, TD Securities, BMO Capital Markets, Scotiabank, Evercore, Lazard, Moelis, PJT Partners, Houlihan Lokey, and Guggenheim Partners.

Verify official career URLs, regional portals, student-program pages, and listing endpoints during onboarding. Keep company aliases together while preserving distinct employers and business units. This registry includes banking and financial-services employers beyond investment banking alone.

Each source record tracks company, career URL, listing endpoint, adapter type, collection status, supported regions, refresh interval, last attempt, last successful run, and errors. Use explicit states: planned, researching, active, blocked, and paused.

## 7. Collection and refresh design

1. Prefer documented public job feeds or supported applicant-tracking-system interfaces where available.
2. Otherwise inspect public structured job data and permitted HTML extraction.
3. Use browser rendering only for sources that require it and permit that access.
4. Respect source access conditions, robots directives, and rate limits; do not bypass authentication, CAPTCHAs, or access controls. Record inaccessible sources as blocked.
5. Implement a separate adapter per source or shared job platform. One source's layout changes should not break the others.
6. Fetch all listing pages with bounded retries, timeouts, per-domain throttling, and backoff.
7. Normalize fields and retain provenance, extraction evidence, and confidence for inferred values.
8. Deduplicate and upsert records, retaining first-seen and last-seen timestamps.
9. Start with a configurable daily refresh; tune each source's schedule after observing its constraints.
10. Search stored listings through the backend; do not crawl third-party pages on every user search.

### Deduplication and closure

- Prefer employer plus requisition ID. Fall back to canonical application URL; use company/title/location similarity only as a conservative candidate match.
- Prefer the employer's original listing over an aggregator copy, retaining both source references.
- Preserve all locations for a single multi-location role.
- Mark explicitly closed postings closed. If a listing disappears, require two complete successful refreshes before marking it inactive.
- Partial fetches, parser failures, and network failures must not trigger mass closures. Keep affected data and mark its freshness accordingly.

## 8. Minimum data model

| Entity | Main fields |
| --- | --- |
| Company | ID, name, aliases, industry, official career URL |
| Source | ID, company ID (optional for aggregators), URLs, adapter, status, refresh configuration, last attempt/success/error |
| Job | ID, company ID, requisition ID, title, summary, canonical application URL, employment type, program type, functions, study-area tags, degree requirements, graduation window, minimum/maximum experience, experience level, work arrangement, posting date, deadline, first seen, last seen, last verified, status |
| Job location | Job ID, country, region, city, original location text, remote eligibility restrictions |
| Job source | Job ID, source ID, original listing URL, external ID, last observed timestamp |
| Attribute evidence | Job ID, attribute, original text, explicit/inferred/unknown status, confidence, extraction version |
| Collection run | Source ID, start/end time, success/partial/failure, pages fetched, listings observed, errors |

Dates and requirements may be null. Store publication dates separately from discovery timestamps. Taxonomies should use stable identifiers and editable display labels.

## 9. Proposed application structure

Implementation choices remain provisional until the first working source is evaluated.

- Frontend: React with TypeScript for the search page, dropdowns, results, and listing details.
- Backend: Python with FastAPI for search endpoints, normalization, and source adapters.
- Storage: SQLite for a local prototype; PostgreSQL for hosted deployment.
- Collection: a scheduled Python process separate from web requests.
- Testing: fixture-based adapter checks plus focused matching and user-flow tests.

Suggested future folders:

```text
Role Searcher/
  README.md
  frontend/
  backend/
    app/
    collectors/
    tests/
  data/
  docs/
```

Proposed read endpoints: `GET /jobs` (filters, sorting, pagination), `GET /jobs/{id}`, `GET /filters` (available values and counts), and `GET /sources` (coverage and freshness). Collection execution stays separate from public search endpoints.

## 10. Delivery stages

### Stage 1 — Specification

- Establish this product plan, dropdown behavior, source registry, and matching rules.

### Stage 2 — Interface prototype

- Build the responsive search experience using clearly labeled sample listings.
- Implement all requested dropdowns, URL persistence, result cards, and empty states.

### Stage 3 — First live sources

- Evaluate source access and implement two or three feasible adapters.
- Include at least one bank and one investment/trading firm if source access permits.
- Add persistence, refresh history, deduplication, freshness labels, and original application links.

### Stage 4 — Coverage expansion

- Onboard the remaining user-provided firms and initial bank registry.
- Track source coverage visibly; document blocked integrations.
- Add fixtures and failure monitoring for each adapter.

### Stage 5 — Broader industries and optional features

- Add dedicated technology, pharma, and healthcare employers.
- Consider saved jobs, notifications, and application tracking after search quality is reliable.

## 11. Acceptance criteria

- All requested filter categories are available as dropdowns on desktop and mobile.
- Multiple selections and combined filters follow the documented matching rules.
- Graduation windows are extracted from eligibility text, not guessed from program titles.
- Unspecified and inferred requirements are visibly distinguished from explicit matches.
- A technology job at a bank can match Technology; users can see why it matched.
- Multi-location roles match any valid listed location; remote geographic restrictions are respected.
- Duplicate employer/aggregator listings appear once with retained source attribution.
- Original application links work for the first live-source sample.
- Source failures preserve listings and expose stale data rather than falsely reporting closure.
- Search URLs reproduce selections, and dropdowns are usable with a keyboard.
- Sample data is labeled, and live coverage is reported accurately.
- Focused tests cover graduation boundaries, unknown requirements, multi-select behavior, duplicate listings, and incomplete refreshes.

## 12. Working assumptions

- Begin with US-focused source onboarding while preserving international location support; do not silently constrain every search to New York.
- Graduation year is a matching preference, not a guarantee of eligibility.
- The first version helps discover openings and redirects users to employers to apply.
- This is a new standalone project folder. Repository setup and any relationship to JFinder remain separate implementation decisions.

### Integration follow-up — September 18, 2026

- UBS now uses the public experienced-hire board’s anonymous pagination request. All pages must agree on the advertised count and contain distinct IDs. Other UBS campus boards remain outside this integration.
- Balyasny now uses the same anonymous, read-only search action as its public Salesforce careers page. Only job fields are stored; recruiter and employee metadata are discarded. Its public description action supports background enrichment. Browser automation was used for discovery only; routine collection needs no browser or login.
- BNY is connected with 1,399 public jobs from 1,402 advertised feed positions. Offsets count positions, including unavailable records, so the collector advances by its requested window rather than the number of returned jobs. Overlapping windows are deduplicated, count changes still fail validation, and an empty terminal page is required. The allowed discrepancy remains bounded to at most five records and 0.5%. Regression tests cover unavailable positions and prevent repeating the final job. Full descriptions populate in background.
- Citadel and JPMorgan were rechecked and still return HTTP 403 access responses. Hudson Bay Capital still provides recruiting contact details with no public job feed found.

Optional research scripts that use a browser require `pip install playwright` and an installed Google Chrome. They are not required by the app, collectors or scheduler.

## Backups and login services

From `backend/`, run `uv run python -m app.backup` to create a consistent SQLite snapshot, including saved jobs and application notes, under `backend/data/backups/`. The command uses SQLite's online backup API and checks database integrity before publishing the snapshot. It retains the latest 14 snapshots; backups are readable only by their owner. These local copies protect against accidental changes, not disk loss.

To inspect a backup without replacing current data, set `ROLE_SEARCHER_DB` in `backend/.env` to the backup's absolute path and restart the API. Make a copy of the backup first if you intend to run collectors against it. To restore the main database, stop the API and scheduler, preserve the current database and its journal/WAL files, and restore a verified snapshot before restarting. Never copy over an active database.

Generate macOS service definitions with:

```bash
# backend/
uv run python -m app.services --destination data/launchagents
```

The scheduler agent starts at login and restarts after an exit (60-second throttle). The backup agent runs at login and daily at 10 a.m. local time. macOS may defer scheduled runs during sleep. Neither service runs while logged out or powered off. Logs are under `backend/data/logs/`. Regenerate definitions if the project or Python environment moves.

Verified September 24: the project was moved from Downloads to `/Users/aishanibasu/Projects/Role Searcher` to allow background access without changing macOS privacy permissions. The database checksum was unchanged by the move, and the Python environment was rebuilt from `uv.lock`. Both login agents are enabled: the scheduler refreshed Point72 successfully and the backup agent exited successfully after creating a snapshot. The API and frontend remain manually started local development servers; only refreshes and backups start at login.

Service definitions are installed at `~/Library/LaunchAgents/local.rolesearcher.scheduler.plist` and `~/Library/LaunchAgents/local.rolesearcher.backup.plist`. To inspect either service, use `launchctl print gui/$(id -u)/local.rolesearcher.scheduler` or substitute `backup`. The app also shows the scheduler heartbeat under refresh status.

To stop automatic operation, run `launchctl bootout gui/$(id -u)/local.rolesearcher.scheduler` and the equivalent command for `backup`. To also prevent startup at future logins, run `launchctl disable gui/$(id -u)/local.rolesearcher.scheduler` and the equivalent for `backup`. Re-enable with `launchctl enable`, then bootstrap the corresponding plist. Logs retain earlier installation errors as history; inspect current service state and the newest log timestamps when troubleshooting.
