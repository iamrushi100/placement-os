# Placement OS

A personal placement preparation and progress management system built to keep applications, preparation, focused work, and daily progress in one local workspace.

## Why it exists

Placement preparation involves several parallel activities: applications, DSA, Python and CS fundamentals, AI/ML, projects, assessments, interviews, and deep work. Placement OS brings these into one practical tracker so progress and next steps are visible together.

## Features

### Placement Management
- Opportunity Inbox and Serious Applications
- Application pipeline with status tracking
- Deadlines, priorities, and referral details

### Preparation
- Backend-managed categories and topics
- Topic status, practice counts, notes, and progress

### Deep Work
- Persistent focus timer and manual sessions
- Multiple sessions per day, category tracking, and daily totals
- Legacy fallback for historical V1 dates (described below)

### Dashboard
- Placement goal, application count, pipeline, and next deadlines
- Preparation progress and Deep Work daily/weekly totals
- Today's MITs and incomplete preparation topics

### Performance Journal
- Assessments, coding tests, technical interviews, HR interviews, and mock interviews
- Performance notes and action items
- Historical company/role snapshots for linked opportunities

### Productivity
- Daily score, placement streak, MITs, reflections, sprint analytics, and sprint history

MITs and reflections currently support create/read workflows; edit and delete are not part of this release.

## Tech stack

Python, FastAPI, SQLite, Pydantic, HTML, CSS, vanilla JavaScript, Uvicorn, and Git/GitHub.

## Architecture

```text
Browser
   |
   v
HTML / CSS / Vanilla JavaScript
   |
   v
FastAPI (Pydantic request/response validation)
   |
   v
SQLite (versioned migrations)
```

The V2 modules are Opportunities, Preparation Tracking, Deep Work, the Placement Dashboard, and the Performance Journal. Shared Deep Work source-of-truth logic feeds daily totals and score/history/analytics calculations.

New Deep Work is stored as sessions:

```text
New Deep Work -> deep_work_sessions
```

For a date with V2 sessions, the application uses their total. If there are no V2 sessions, it falls back to the historical `daily_entries.deep_work_minutes` value. This keeps V1 history usable without counting legacy minutes and new sessions twice.

## Sprint

The placement sprint runs from 6 October 2026 through 5 November 2026, inclusive: 31 calendar days.

## Setup and run (Windows PowerShell)

```powershell
git clone -b v2 https://github.com/iamrushi100/placement-os.git
cd placement-os
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000/>. Use Python 3.13 for the project's current development setup.

`requirements.txt` lists the runtime packages. The automated tests use Python's standard library and require no test-only package.

## Database and tests

SQLite data is local. `placement.db` is runtime data and is not tracked by Git. Ordered migrations are recorded using SQLite's `user_version`; a fresh database initializes through the migration chain when the app starts.

Run the standard-library test suite from the project root:

```powershell
python -m unittest discover -s tests -v
python -m compileall app tests
node --check static/app.js
```

## What this project demonstrates

- REST API development and Pydantic validation
- SQLite schema design and versioned migrations
- Backend/frontend integration with vanilla JavaScript
- Data integrity and regression testing
- Dashboard design and practical product thinking
