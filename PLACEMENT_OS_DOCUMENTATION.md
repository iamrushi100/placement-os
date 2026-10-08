> **Historical V1 documentation:** This document records the original V1 milestones and is retained for project history. For the current implementation, see [PLACEMENT_OS_V2.md](PLACEMENT_OS_V2.md). V1 feature descriptions below may not describe current behavior.

# Placement OS — Project Documentation

> **Personal Placement Streak Tracker / Placement OS**
>
> A deliberately simple full-stack application built to manage a focused placement sprint, track daily discipline, measure progress, and provide a clear daily view.

## 1. Project Overview

Placement OS is a personal placement preparation dashboard designed around a focused sprint.

The core idea is:

> **Do the important work every day, measure it honestly, and maintain consistency.**

The application combines:
- Technical preparation
- Placement preparation
- Deep-work tracking
- Daily MITs (Most Important Tasks)
- Daily reflection
- Habit completion
- Individual habit streaks
- Placement success streak
- Daily placement score
- Sprint history
- Basic analytics

The project intentionally avoids unnecessary complexity. It is not designed to be an AI-agent platform, job scraper, or enterprise-scale system.

### Current sprint
- Start: **6 October 2026**
- End: **5 November 2026**
- Current implementation represents the inclusive period as **31 calendar dates**
- Success threshold: **60/100**

## 2. Why I Built This

Placement preparation can become fragmented across DSA, Python, CS fundamentals, AI/ML, projects, applications, portfolio work, assessments, and interviews.

The problem is not only knowing what to study. The bigger problem is maintaining **consistent daily execution**.

I wanted one simple system that answers:

> **Did I do today's work?**

The project therefore focuses on **execution and consistency** rather than complicated productivity features.

## 3. Project Goals

### Primary goals
1. Track daily placement preparation.
2. Track technical and placement habits.
3. Measure deep-work time.
4. Calculate a daily placement score.
5. Maintain a placement streak.
6. Record daily MITs.
7. Record daily reflection.
8. Visualize the complete sprint.
9. Provide useful analytics.
10. Create a project that can be explained confidently in interviews.

### Secondary goals
- Practice full-stack development.
- Practice REST API design.
- Practice SQL and SQLite.
- Practice frontend/backend integration.
- Practice Git and GitHub workflow.
- Understand derived metrics and data modeling.
- Build something personally useful rather than a tutorial clone.

## 4. Design Philosophy

### 4.1 Simple before sophisticated
A feature is added only when it solves a real problem.

### 4.2 Derived data should be calculated
Metrics such as daily score and streak are calculated from source records rather than unnecessarily stored.

### 4.3 One clear responsibility per layer
- Frontend → user interaction and presentation
- FastAPI → API/business logic
- SQLite → persistence

### 4.4 Build incrementally
**Understand → Implement → Test → Explain → Commit**

### 4.5 Avoid over-engineering
The project intentionally does **not** use:
- Microservices
- RAG
- Vector databases
- LangChain/LangGraph
- Multi-agent systems
- Job scraping
- Automated job applications
- Complex authentication
- Gmail/Calendar integrations

## 5. Technology Stack

| Layer | Technology |
|---|---|
| Language | Python |
| Backend | FastAPI |
| Database | SQLite |
| Database access | Python `sqlite3` |
| Validation | Pydantic |
| Frontend | HTML |
| Styling | CSS |
| Frontend logic | Vanilla JavaScript |
| Server | Uvicorn |
| Version control | Git |
| Remote repository | GitHub |
| Environment | Python virtual environment |

### Why FastAPI?
FastAPI provides simple REST endpoint creation, request validation through Pydantic, automatic API documentation, good Python integration, and a lightweight architecture.

### Why SQLite?
SQLite was selected because this is currently a single-user local application. It provides real SQL persistence, relational tables, constraints, uniqueness, foreign keys, and no separate database server.

If the application became multi-user, PostgreSQL would be a natural next step.

## 6. High-Level Architecture

```text
                    ┌─────────────────────┐
                    │      Browser        │
                    │ HTML + CSS + JS     │
                    └──────────┬──────────┘
                               │
                         HTTP / REST
                               │
                               ▼
                    ┌─────────────────────┐
                    │      FastAPI        │
                    │ API + Business      │
                    │ Logic               │
                    └──────────┬──────────┘
                               │
                         SQL / sqlite3
                               │
                               ▼
                    ┌─────────────────────┐
                    │       SQLite        │
                    │   placement.db      │
                    └─────────────────────┘
```

## 7. Project Structure

```text
Placement_streak_tracker/
│
├── app/
│   ├── main.py
│   ├── database.py
│   └── schemas.py
│
├── static/
│   ├── index.html
│   ├── style.css
│   └── app.js
│
├── placement.db
├── .venv/
└── ...
```

### Responsibilities
- `app/main.py` → FastAPI app, routes, business logic, score/streak/analytics calculations
- `app/database.py` → SQLite connection and table initialization
- `app/schemas.py` → Pydantic request/response models
- `static/index.html` → dashboard structure
- `static/style.css` → dashboard styling
- `static/app.js` → frontend behavior and API communication

## 8. Database Design

The application currently contains five main tables.

### 8.1 `habits`
Stores available habits.

```sql
CREATE TABLE habits (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### 8.2 `habit_completions`
Stores completion of habits for individual dates.

Important constraint:

```sql
UNIQUE(habit_id, date)
```

This prevents the same habit from being completed multiple times on the same date.

### 8.3 `daily_entries`
Stores daily deep-work information. The date is unique, so there is currently one daily deep-work record per day.

### 8.4 `daily_mits`
Stores Most Important Tasks.

Important constraint:

```sql
UNIQUE(date, task)
```

The application currently allows a maximum of three MITs per day.

### 8.5 `daily_reflections`
Stores one daily reflection:
- `went_well`
- `challenges`
- `improvement`

## 9. Current Habits

### Technical
1. DSA
2. Python
3. CS Fundamentals
4. System Design
5. AI/ML

### Placement
6. Assessment Preparation
7. Project Work
8. Portfolio
9. Applications
10. Interview Preparation

**Important design decision:** Deep Work is not a habit. It is measured separately because time spent doing focused work is different from whether a particular category of work was completed.

## 10. Daily Placement Score

The daily score is out of 100.

### Deep Work — 40 points
Target: **180 minutes**

```text
deep_work_score =
    min(deep_work_minutes / 180, 1) × 40
```

| Deep Work | Score |
|---:|---:|
| 0 min | 0 |
| 90 min | 20 |
| 120 min | 27 |
| 180+ min | 40 |

### Important clarification
The application does **not** know whether the user actually worked for 120 minutes.

When the user enters `120`, the application treats that as a self-reported 120 minutes.

A future version could introduce a Start/Stop focus timer, but this is intentionally not part of the current V1.

### Technical Habits — 30 points

```text
technical_score =
    completed_technical_habits / 5 × 30
```

### Placement Habits — 30 points

```text
placement_score =
    completed_placement_habits / 5 × 30
```

### Total

```text
daily_score =
    deep_work_score
    + technical_score
    + placement_score
```

The final value is rounded to the nearest integer.

## 11. Placement Success

A day is successful when:

```text
daily_score >= 60
```

The threshold is currently **60/100**.

## 12. Placement Streak

The placement streak counts consecutive successful days.

The algorithm:
1. Start from today.
2. Calculate today's score.
3. Check whether today's score is at least 60.
4. If successful, count the day.
5. Move to the previous date.
6. Continue until a failed day or sprint boundary is reached.

The streak is calculated dynamically rather than stored separately.

### Why?
A stored streak can become incorrect if historical data changes. Calculating it from source records keeps the metric consistent.

## 13. Individual Habit Streaks

Each habit can have its own streak.

The system looks backward from today and counts consecutive completion dates.

Example:

```text
Oct 5 → completed
Oct 6 → completed
Oct 7 → completed
Oct 8 → not completed
```

Streak = **3 days**

## 14. Daily MITs

The application supports up to three MITs per day.

Example:

```text
1. Solve 5 DSA problems
2. Complete GenAI project module
3. Apply to 3 suitable roles
```

MITs are intentionally separate from the placement score because a task can be personally important without being easy to represent numerically.

## 15. Daily Reflection

The user can record:
- What went well?
- Challenges
- Improvement

This creates a simple feedback loop:

```text
Plan → Execute → Reflect → Improve
```

## 16. Sprint History

The dashboard shows the complete sprint history with:
- Date
- Score
- Deep Work
- Technical completion
- Placement completion
- Status

Statuses:
- **Successful** → past day with score >= 60
- **Needs Work** → past day with score < 60
- **In Progress** → today
- **Upcoming** → future sprint date

## 17. Analytics

The dashboard currently calculates:
- Average Score
- Average Deep Work
- Habit Completion Rate
- Successful Days
- Best Streak

Future dates are excluded from analytics. Elapsed days with zero activity are included so analytics do not artificially inflate performance.

## 18. API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Dashboard |
| POST | `/api/habits` | Create habit |
| GET | `/api/habits` | List habits |
| POST | `/api/habits/{habit_id}/complete` | Complete habit |
| GET | `/api/habits/{habit_id}/streak` | Habit streak |
| GET | `/api/habits/today` | Today's habits |
| POST | `/api/daily-entries` | Save deep work |
| GET | `/api/daily-entries/{date}` | Get deep work |
| GET | `/api/daily-score/{date}` | Calculate score |
| GET | `/api/placement-streak` | Calculate placement streak |
| POST | `/api/mits` | Create MIT |
| GET | `/api/mits/{date}` | Get MITs |
| POST | `/api/reflections` | Save reflection |
| GET | `/api/reflections/{date}` | Get reflection |
| GET | `/api/sprint-history` | Sprint history |
| GET | `/api/analytics` | Sprint analytics |

## 19. Validation and Data Integrity

The backend validates:
- Invalid dates
- Blank MITs
- More than three MITs
- Duplicate MITs
- Duplicate reflections
- Duplicate deep-work entries
- Duplicate habit completion
- Nonexistent habits
- Inactive habits

SQLite also provides database-level constraints.

```text
Application validation
        +
Database constraints
        =
Better data integrity
```

## 20. Frontend ↔ Backend Flow

Example: completing a habit.

```text
User clicks checkbox
        ↓
JavaScript event handler
        ↓
fetch("/api/habits/{id}/complete", POST)
        ↓
FastAPI route
        ↓
Validate habit
        ↓
INSERT completion into SQLite
        ↓
Return response
        ↓
Frontend refreshes score/streak/UI
```

## 21. Important Technical Decisions

### Decision 1 — No ORM
The project uses Python's built-in `sqlite3`.

Reason:
- Small application
- Simple schema
- Direct SQL is easier to understand
- Helps demonstrate actual SQL knowledge
- No need for ORM abstraction at this stage

### Decision 2 — No service/repository layers
The project does not introduce unnecessary Controller/Service/Repository abstractions because the application is small enough that they would add complexity without enough value.

### Decision 3 — Dynamic metrics
Scores, streaks and analytics are derived from source data to avoid redundant values that can become inconsistent.

### Decision 4 — Vanilla JavaScript
The UI is small and does not need a large frontend framework. Vanilla JavaScript also makes browser → API interaction easier to understand.

### Decision 5 — Deep work is self-reported
The application currently records the user's declared deep-work minutes. A timer could be added later, but it is not necessary for V1.

## 22. Development Milestones

### Milestone 1 — Foundation
FastAPI, SQLite, initial schema, basic dashboard.

```text
a0fca7d
feat: create FastAPI and SQLite foundation
```

### Milestone 2 — Habit Tracking

```text
8e36d71
feat: add habit completion and streak tracking
```

### Milestone 3 — Daily Scoring

```text
2ac06f5
feat: add daily scoring and placement streak
```

### Milestone 4 — Interactive Habit UI

```text
cac112f773056b1bc26d1b3ffd5825ed4fba225
feat: make habit tracking interactive
```

### Milestone 5 — Daily MITs

```text
bececfb386dfd690d15d964c248076b1fd4f52d5
feat: add daily MIT tracking
```

### Milestone 6 — Daily Reflection

```text
00dff20cf65191cc11acb29ea57f2324f58bce12
feat: add daily reflection tracking
```

### Milestone 7 — Sprint History

```text
c1b28c3d58ce8cdc7c203c2b6b295ab66a96834f
feat: add 30-day sprint history
```

### Milestone 7.5 — Analytics

```text
5b0b81aaf6b4f2dbedef7f5ec23a9f59806d327c
feat: add sprint analytics
```

### Milestone 8 — Complete Daily Workflow

```text
98d0ed7571659019928a76bc98b64f9054410e13
feat: complete daily placement workflow
```

Added:
- Dynamic sprint day
- Deep-work input
- Deep-work persistence
- Daily score refresh
- Today = In Progress status
- Full daily workflow integration

## 23. Development Environment

- Windows 10
- Python 3.13.0
- Git 2.56.0
- VS Code
- Python virtual environment
- Uvicorn

Run server:

```bash
uvicorn app.main:app --reload
```

Application:

```text
http://127.0.0.1:8000
```

## 24. Git Workflow

Typical workflow:

```bash
git status
git add .
git commit -m "feat: description"
git log --oneline
```

The project uses meaningful feature commits instead of one giant final commit.

## 25. Git Issue Encountered

Git initially reported:

```text
fatal: detected dubious ownership in repository
```

The issue was caused by a Windows ownership mismatch.

The specific repository was added as a safe directory:

```bash
git config --global --add safe.directory "D:/Placement 2026/Projects/Project 2/Placement_streak _tracker"
```

This was a useful real-world Git troubleshooting experience.

## 26. Debugging Experience

At one point, newly created endpoints returned 404 even though the source code was correct.

The cause was an old Uvicorn process still serving the previous application version.

The process was terminated and the application restarted with:

```bash
uvicorn app.main:app --reload
```

### Lesson

When a backend change appears to be ignored:

```text
Browser
   ↓
JavaScript
   ↓
HTTP request
   ↓
Running FastAPI process
   ↓
Source code
```

The source code may be correct while the running process is stale.

## 27. Testing Performed

### Python syntax

```bash
python -m compileall app
```

### JavaScript syntax

```bash
node --check static/app.js
```

### Git whitespace

```bash
git diff --check
```

### Functional testing
Verified:
- Habit completion
- Duplicate habit prevention
- Habit streak
- Daily score
- Placement streak
- MIT creation
- MIT limit
- Reflection creation
- Deep-work saving
- Sprint history
- Analytics
- Dashboard loading

## 28. Current Known Limitation

### Deep-work verification
The application currently trusts the user's input.

```text
User enters: 120
Application stores: 120 minutes
```

The application cannot independently verify whether the user actually focused for 120 minutes.

This is intentional for V1.

## 29. Current Personalization Direction

The daily routine needs a small **Personal Discipline** category, including meditation and a few other personally important habits.

The exact habits should be finalized before modifying the database.

## 30. Motivation Layer — Planned

The dashboard should eventually open with something more meaningful than a standard productivity dashboard.

The goal is not random motivational quotes.

The motivation layer should connect:

```text
Today's work
      ↓
30-day placement goal
      ↓
Career direction
      ↓
Personal identity / discipline
```

The intended feeling is:

> **I know why I am doing this. Now I need to execute.**

The design should remain minimal and should not turn the application into a motivational chatbot.

## 31. Future Roadmap

### V1 — Current
- Habits
- Deep work
- Daily score
- Placement streak
- MITs
- Reflection
- History
- Analytics

### V1.1 — Personal Discipline
Potential addition:
- Meditation
- Selected personal habits
- Personal discipline category

### V1.2 — Motivation Dashboard
Potential addition:
- Personalized mission section
- Progress-focused opening experience
- Strong visual identity

### V1.3 — Documentation & Deployment
- Clean test data
- README
- Project documentation
- GitHub repository
- Deployment

### V2 — Optional AI
Only after the core product is stable.

Possible feature:

**AI Daily Review**

Inputs:
- Score
- Deep work
- Completed habits
- MITs
- Reflection

Output:
- One short observation
- One improvement suggestion
- One priority for tomorrow

This should remain a **small feature**, not an agentic system.

## 32. Features Deliberately Rejected

### RAG
Not needed because the application does not need document retrieval.

### Vector database
Not needed because there is no semantic search requirement.

### Multi-agent architecture
Not needed because the workflow is deterministic.

### Job scraping
Outside the core problem.

### Automated applications
Outside the core problem and introduces significant complexity.

### Complex authentication
Not needed for a personal local application.

### Microservices
The application is small enough for a monolithic FastAPI backend.

### Heavy frontend frameworks
Not necessary for the current dashboard.

## 33. Interview Explanation

> **Placement OS is a personal full-stack placement preparation tracker built using Python, FastAPI, SQLite, HTML, CSS and JavaScript. It allows me to track technical and placement habits, deep-work time, MITs and daily reflection. I calculate a daily placement score from these underlying activities and use the score to determine a placement streak. I intentionally kept the architecture simple and avoided unnecessary technologies like microservices or agentic AI. The project helped me practice REST APIs, SQL, frontend-backend integration, validation, data modeling, Git and debugging.**

## 34. Important Interview Questions

### Q1. Why SQLite?
Because this is a single-user local application. SQLite provides relational persistence without the operational overhead of a separate database server.

### Q2. Why FastAPI?
FastAPI provides simple REST APIs, automatic validation through Pydantic, good Python support and automatic API documentation.

### Q3. Why didn't you use SQLAlchemy?
The project is small and I wanted to understand SQL and database operations directly. Introducing an ORM would add abstraction without much benefit for this scope.

### Q4. Why don't you store the daily score?
The score is derived from deep-work and habit completion records. Storing it would create redundant data and could cause inconsistencies if the underlying records changed.

### Q5. How is the placement streak calculated?
The backend starts from the current day and moves backward through consecutive successful days, where a successful day has a score of at least 60.

### Q6. How does the frontend communicate with the backend?
Vanilla JavaScript uses the browser `fetch()` API to send HTTP requests to FastAPI endpoints and then updates the dashboard using returned JSON.

### Q7. How do you prevent duplicate habit completion?
The database has a unique constraint on `(habit_id, date)`. The API also checks for an existing completion and returns an appropriate error.

### Q8. Why is deep work separate from habits?
A habit represents completion of a category-specific activity, while deep work represents the amount of focused time spent working. They measure different dimensions of productivity.

### Q9. What happens if you scale this application?
I would consider PostgreSQL, authentication, user-specific data ownership, stronger API structure, deployment infrastructure, and potentially a frontend framework — but only when the product requires them.

### Q10. What would you improve next?
First I would improve personal discipline tracking and the dashboard experience, then deploy the stable V1. Only after that would I consider a small AI daily-review feature.

## 35. Lessons Learned

### Technical
- REST API design
- FastAPI routing
- Pydantic validation
- SQLite schema design
- SQL constraints
- Foreign keys
- JavaScript `fetch`
- Frontend/backend integration
- Dynamic calculations
- Error handling
- Git workflow
- Debugging stale server processes

### Engineering

> **A good project is not the project with the most technologies. It is the project where every technology has a reason to exist.**

The project intentionally became simpler as its requirements became clearer.

## 36. Project Status

### Current status
**Core V1 is functional.**

Completed:
- Backend
- Database
- Habit system
- Streak system
- Scoring
- Placement streak
- MITs
- Reflection
- Sprint history
- Analytics
- Deep-work input
- Interactive dashboard
- Git checkpoints

Next:
1. Personal discipline habits
2. Personalized motivation experience
3. End-to-end V1 testing
4. Test-data cleanup
5. README
6. GitHub
7. Deployment
8. Optional V2 AI Daily Review

## 37. Final Project Philosophy

Placement OS is not intended to predict whether I will get placed.

It is intended to make the daily actions required for placement **visible, measurable and consistent**.

The core loop is:

```text
PLAN
  ↓
WORK
  ↓
TRACK
  ↓
REFLECT
  ↓
IMPROVE
  ↓
REPEAT
```

The application exists to make that loop easier to follow every day.

---

## Project Motto

> **Make today count.**
