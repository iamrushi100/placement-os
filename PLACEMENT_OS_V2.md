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