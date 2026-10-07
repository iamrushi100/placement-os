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