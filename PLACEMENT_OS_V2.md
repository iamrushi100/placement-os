# Placement OS V2 Development Notes

V2 development starts from the functional V1 baseline on the `v2` branch. The
goal is to improve maintainability while preserving the current dashboard,
routes, scoring behavior, and stored user data.

## V2 foundation

- Backend: FastAPI with Python's built-in `sqlite3` module.
- Frontend: HTML, CSS, and vanilla JavaScript.
- Database changes use ordered, atomic migrations recorded in SQLite's
  `PRAGMA user_version` value.
- Automated baseline tests use Python's standard-library `unittest`; no test
  dependency is required.

## Database migration rules

1. Add a new, sequential migration function to `MIGRATIONS` in
   `app/database.py` for each schema change.
2. Keep each migration small and safe to run in one transaction.
3. Preserve existing records; do not rebuild or drop user tables without a
   separately reviewed data migration.
4. Do not edit an already released migration. Add a later migration instead.
5. Reject a database whose `user_version` is newer than this code supports.
6. Test migrations against both an empty temporary database and an existing
   unversioned database before using them with personal data.

The first migration records the existing V1 schema. Its `CREATE TABLE IF NOT
EXISTS` statements allow the current unversioned V1 database to be adopted
without replacing its tables or rows.

## Verification

Run these commands from the project root:

```powershell
python -m unittest discover -s tests -v
python -m compileall app tests
node --check static/app.js
git diff --check
```

Before merging V2 work, confirm the existing APIs and dashboard still operate,
and review database changes against a copy of the local SQLite file.

## Scope discipline

V2 changes should solve a defined user need while retaining the existing simple
architecture. Add dependencies, layers, or API behavior changes only when a
specific feature requires them and its impact is documented and tested.
## Module 1 — Placement Opportunities

### Purpose

Capture relevant roles in one place, evaluate them, and promote selected roles
into a serious application pipeline without automating job discovery or
applications.

### Opportunity Inbox and Serious Applications

Every opportunity is stored in the `opportunities` table. New records default to
`is_serious = false` and `Interested`, so they begin in the inbox. Set
`is_serious = true` when the opportunity is worth actively pursuing. The
pipeline status can then move through `Interested`, `Applied`, `Assessment`,
`Interview`, `HR`, `Selected`, or `Rejected`; `Withdrawn`, `Not Eligible`, and
`Expired` are also supported.

Priority is `Low`, `Medium`, or `High`. Company and role are required. Location,
source, link, CTC, deadline, referral, eligibility, requirements, and notes are
optional. CTC is stored as text to support ranges and varied employer formats.

### Database and API

Schema migration version 2 adds one opportunities table with status and priority
constraints, an inbox/serious flag, and creation/update timestamps. It does not
replace or rewrite V1 data.

- `POST /api/opportunities` — create an inbox or serious opportunity.
- `GET /api/opportunities?serious=true&status=Applied` — list, optionally
  filtered by seriousness and status.
- `GET /api/opportunities/{opportunity_id}` — retrieve one record.
- `PUT /api/opportunities/{opportunity_id}` — update supplied fields, including
  status and seriousness.
- `DELETE /api/opportunities/{opportunity_id}` — delete a record.

The API uses Pydantic validation and parameterized SQLite queries. Invalid
status/priority values are rejected; missing records return HTTP 404.

### Design decisions and verification

The inbox and serious application flow share one table, distinguished by
`is_serious`; pipeline stages are represented by a constrained status value.
This keeps the model easy to explain and avoids redundant tables or additional
layers. Standard-library tests cover migration repeatability and preservation,
create/read/list/update, inbox promotion, filtering, delete, invalid input,
missing IDs, and a V1 habit completion/score workflow. All six tests pass.
## Module 2 — Preparation Tracking

Preparation Tracking records what is being studied and whether the topic is
being practiced. It complements V1 habits: a habit records daily effort, while a
topic has a durable status and practice count.

Categories are editable records, seeded with DSA, SQL / DBMS, Python, OOP,
Aptitude, Machine Learning, Deep Learning, GenAI, Cybersecurity, Projects, and
Interview Preparation. Topics belong to one category and use `Not Started`,
`In Progress`, or `Completed`. Each topic stores an independent non-negative
practice count and optional notes; recording practice increments only the count.

Migration version 3 adds `preparation_categories` and `preparation_topics`.
Topics reference their category with a restrictive foreign key. A category
cannot be deleted while it contains topics; move or delete those topics first.
Default names are inserted with `INSERT OR IGNORE`, so existing categories are
not overwritten.

### API

- `POST /api/preparation/categories`, `GET /api/preparation/categories`
- `PUT /api/preparation/categories/{category_id}`
- `DELETE /api/preparation/categories/{category_id}`
- `POST /api/preparation/topics`, `GET /api/preparation/topics`
- `GET /api/preparation/topics/{topic_id}`
- `PUT /api/preparation/topics/{topic_id}`
- `DELETE /api/preparation/topics/{topic_id}`
- `POST /api/preparation/topics/{topic_id}/practice`

Topic lists accept `category_id` and `status` filters. Status and count rules
are validated in Pydantic and constrained in SQLite. The design uses two simple
related tables without practice-session records or extra service layers.

Standard-library tests cover default seeding and repeatability, category and
topic CRUD, filtering, validation, category deletion protection, practice-count
behavior, missing records, and the existing V1/V2 regression workflows. The full suite passes with 11 tests.
## Module 3 — Deep Work

Deep Work tracks completed focus sessions independently of the V1 daily-entry record. A manual session stores a date, duration of at least 30 minutes, one of the supported focus categories, and optional notes. Timer sessions use the same record shape and preserve their start/end timestamps. Only one timer can be active; elapsed time is calculated when it is stopped, and sessions shorter than 30 minutes are discarded.

Migration version 4 adds `deep_work_sessions` and the singleton `deep_work_active_timer` table. The daily summary reports the sum of V2 sessions against a 180-minute target. To preserve older V1 data without double-counting, score, history, and analytics calculations use the V2 session total when sessions exist for a date and otherwise fall back to that date's legacy `daily_entries` value. The score formula and 180-minute cap are unchanged.

### API

- `POST /api/deep-work/sessions`, `GET /api/deep-work/sessions?date=YYYY-MM-DD&category=DSA`
- `GET /api/deep-work/sessions/{session_id}`, `DELETE /api/deep-work/sessions/{session_id}`
- `GET /api/deep-work/daily/{date}`
- `POST /api/deep-work/timer/start`, `GET /api/deep-work/timer`, `POST /api/deep-work/timer/stop`

Standard-library tests cover migration repeatability and table presence, manual session validation and CRUD, filtering and daily totals, timer exclusivity and short/completed stops, and V1 score fallback behavior.

## Module 4 — Placement Dashboard

The Placement Dashboard is a read and aggregation view that answers where placement preparation stands. It reuses the existing V1 and V2 records and does not create a second application, topic, session, or daily-priority tracker. The only editable dashboard values are the placement goal and display-only daily Deep Work target.

### Data and metrics

The dashboard reads serious opportunities for the active application count and status pipeline. Active statuses are Interested, Applied, Assessment, Interview, and HR; Selected, Rejected, Withdrawn, Not Eligible, and Expired do not count as active. The pipeline shows counts for serious opportunities by status. The next deadline is the earliest future deadline across non-terminal opportunities.

Preparation totals, status counts, completion percentage, practice count, and per-category completion percentages come from `preparation_categories` and `preparation_topics`. Daily and weekly Deep Work actuals are sums of `deep_work_sessions`; the week is Monday through today. The weekly target is the configured daily display target multiplied by seven. Today's Focus reads the existing MIT records and incomplete preparation topics.

The daily display target defaults to 180 minutes and can be configured from the dashboard. It is not the scoring target: V1 daily scoring still uses its fixed 180-minute cap regardless of the dashboard setting. The default placement goal is “Get placed in a good software / AI role.”

### Settings and API

Migration version 5 adds only `app_settings`, a key/value table containing the placement goal and daily display target. Dashboard metrics are calculated dynamically; no summaries, snapshots, weekly records, or cached values are stored.

- `GET /api/dashboard` returns goal, application count and pipeline, next deadline, preparation totals and category progress, daily and weekly Deep Work target/actual/progress, today's MITs, and incomplete topics.
- `GET /api/dashboard/settings` returns the two settings.
- `PUT /api/dashboard/settings` updates either or both settings.

The frontend extends the existing page with compact summary cards, pipeline/deadline, preparation progress, Deep Work target versus actual, and Today's Focus. Settings forms update only the goal or display target. Navigation links jump to dashboard sections; module data remains managed through its existing APIs. Everything uses the existing FastAPI, SQLite, HTML, CSS, and vanilla JavaScript stack.

### Testing and design decisions

Standard-library tests cover setting defaults and updates, active versus terminal applications, pipeline counts and deadline selection, empty and populated preparation progress, daily and weekly Deep Work calculations, target/scoring separation, MIT/topic focus, and response validation. This keeps the dashboard explainable as a dynamic view over source records rather than a new tracking subsystem.


## Module 5 — Performance Journal

The Performance Journal records what happened in assessments, coding tests, interviews, and mock interviews, then keeps the user's lessons and action items together. Types are Assessment, Coding Test, Technical Interview, HR Interview, and Mock Interview; performance is Good, Mixed, or Poor. Questions, gaps, lessons, action items, and notes remain plain text so the journal is easy to use without creating a separate question bank or task tracker.

Migration version 6 adds `performance_entries`. Each dated record can optionally link to an opportunity and a preparation topic. These foreign keys use `ON DELETE SET NULL`: deleting a linked opportunity or topic preserves the journal record. When an opportunity is linked, company and role are displayed from that opportunity rather than copied into the journal. Topic links are references only; journal operations do not create topics, change their status, or increment practice counts.

### API and frontend

- `POST /api/performance` creates an entry.
- `GET /api/performance` lists newest first and accepts `type`, `performance`, `company`, `opportunity_id`, and `date` filters.
- `GET /api/performance/{entry_id}`, `PUT /api/performance/{entry_id}`, and `DELETE /api/performance/{entry_id}` read, update, and remove an entry.
- `GET /api/performance/summary` dynamically returns total entries, counts by type and performance, and entries in the latest 30 calendar days (through today).

The dashboard journal form uses the existing opportunity and preparation topic APIs for optional dropdown links. Entries can be reviewed, filtered, edited, and deleted with the existing vanilla JavaScript frontend. The learning loop remains user-directed: journal an experience, choose an action, connect it to a topic if helpful, then practice through Preparation Tracking.

Standard-library tests cover CRUD, filters, validation, missing references, optional and valid relationships, summary counts, no automatic topic changes, and migration from schema version 5 with V1/V2 data preserved. The full suite also exercises existing habit, opportunity, preparation, deep-work, and dashboard workflows. No new runtime or test dependencies were added.
