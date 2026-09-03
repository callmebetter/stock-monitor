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

---

## Known Issues & TODO

### 🔴 High Priority

#### 1. 选股分析数据前提不足
- **问题**: `screen_stocks()` 需要按 symbol 聚合的多日历史数据来计算 MA 和 rolling 指标
- **现状**: 当前数据模型是"单日快照"入库，无法计算跨日均线和粘合度
- **方案**: 
  - 查询时按 symbol 分组，拉取近 N 日数据计算指标
  - 或新增预计算表存储每日指标

#### 2. `get_screened_stocks()` 性能问题
- **问题**: `pd.read_sql(db.query(StockData).statement, db.bind)` 拉全表
- **方案**: 只查询近期数据，或分页处理

### 🟡 Medium Priority

#### 3. 定时任务缺少交易日判断
- **问题**: `scheduler_service._collect_data` 每日 15:30 执行，不判断是否交易日
- **方案**: 增加 `is_trading_day()` 判断，非交易日跳过

#### 4. Session 管理不统一
- **问题**: 路由层 `Depends(get_db)` 注入的 session 未被使用，service 层各自创建
- **方案**: 二选一：
  - 路由层传入 session，service 函数接受 `db: Session` 参数
  - 移除路由层注入，service 层统一用 `db_session_scope()`

#### 5. 未使用的代码
- `StockUpdateRequest` Pydantic 模型已定义但未使用
- `main.py` 中交易日历定时任务被注释，建议删除或启用

### 🟢 Low Priority

#### 6. 代码风格
- `stock_analyzer.py` 中 `print()` 应改为 `logger.error()`
- `api_routes.py` 中 `StockUpdateRequest` 未使用可删除

---

## Changelog

### 2026-09-03
- 简化依赖管理：删除 `requirements.txt`，统一使用 `pyproject.toml`
- 修复 `pyproject.toml` 行内注释导致 uv 解析失败的问题
- 移除未使用的 `tzlocal` 依赖
- 添加 `.gitattributes` 统一换行符
- 清理 `.gitignore` 重复项
- 添加 `AGENTS.md` 项目规范文档
- 移除 `sys.path` hack，改用正确的包导入
- 删除重复的 `database/init_db.py`
- 升级 SQLAlchemy 2.0 声明式基类 (`DeclarativeBase`)
- 统一数据库会话管理 (`db_session_scope`)
- 重构 `data_collector.py`，按职责分区
- CSV 缓存迁移至 `data/cache/`
- 补充缺失的 `__init__.py`
- 移除 `config.py` 硬编码默认密码
- 降低 `data_cleaner.py` 日志级别
