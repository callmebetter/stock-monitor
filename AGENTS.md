# AGENTS.md

## Project Overview

Stock monitoring service: collects A-share market data via AkShare, stores in MySQL, analyzes with TDX-style technical indicators, and exposes RESTful APIs via FastAPI. Scheduled tasks run daily after market close.

## Tech Stack

- **Language**: Python 3.11+
- **Package Manager**: uv (pyproject.toml + uv.lock)
- **Web Framework**: FastAPI + Uvicorn
- **ORM**: SQLAlchemy (declarative models)
- **Database**: MySQL (pymysql driver)
- **Data Source**: AkShare
- **Scheduler**: APScheduler (BackgroundScheduler)
- **Config**: python-dotenv (.env for secrets)

## Project Structure

```
stock-monitor/
├── database/          # DB init & session management
├── models/            # SQLAlchemy ORM models
├── services/          # Business logic (data collection, analysis, scheduling)
├── routes/            # FastAPI route handlers
├── helpers/           # Utility functions (data cleaning)
├── docs/              # Documentation (faq.md)
├── config.py          # App configuration (DB, scheduler, AkShare)
├── main.py            # FastAPI app entry point + lifespan
├── app_logger.py      # Centralized logging setup (rotating file handlers)
└── pyproject.toml     # Dependency declarations (single source of truth)
```

## Conventions

### Dependencies
- Declare all dependencies in `pyproject.toml` only (no requirements.txt).
- Use `uv sync` to install, `uv add <pkg>` to add new packages.
- Do NOT add inline comments after dependency strings (causes uv parse errors).

### Code Style
- Use `logging.getLogger(__name__)` in every module; call `setup_logging()` once in `main.py`.
- Database sessions via `SessionLocal()` from `database/__init__.py`; always close in `finally` blocks.
- Keep business logic in `services/`, route handlers thin (delegate to services).

### Configuration
- Secrets (DB credentials) go in `.env`, never hardcode.
- `config.py` reads from environment variables with safe defaults.

### Git
- LF for all text files; CRLF only for `.bat` scripts.
- Commit messages: conventional format (feat/fix/refactor/docs/chore).

## Key Patterns

### Adding a New API Endpoint
1. Add handler function in `routes/api_routes.py`.
2. If new business logic needed, create/update a function in `services/`.
3. Register route with the `router` instance.

### Adding a Scheduled Task
1. Implement the task function in `services/`.
2. Register it in `services/scheduler_service.py` using `scheduler.add_job()`.

### Stock Analysis Logic
- Technical indicators (MA, convergence, volume) computed in `services/stock_analyzer.py`.
- Uses pandas/numpy for vectorized calculations.
- Screening conditions are combined with boolean masks.
