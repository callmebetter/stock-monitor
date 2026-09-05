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

### 2026-09-06
- 新增项目首页（`GET /`，`templates/home.html`）：暗色卡片式导航，4 个入口（截图拼接 / 黄金行情 / Au(T+D) 走势 / API 文档），复用本地 vendor 的 Tailwind + DaisyUI，移动端优先
- 集成截图拼接工具（`GET /web/tools/stitch`，`templates/tools/stitch.html`）：源 screenshot-stitch.html 功能原样迁移（上传≤12张、Cropper 裁剪、纵/横合并、缝隙/背景/PNG·JPG、预览撤销、分享/保存），纯浏览器端 Canvas 处理无后端交互；删除 Express 托管说明块；子页面不加返回链接
- Cropper.js 1.6.2 vendor 入仓 `static/vendor/cropper/`（cropper.min.css/js），模板移除 cdnjs CDN 引用，符合无外部 CDN 约定
- `routes/page_routes.py`：无 prefix 的通用页面 router（区别于 web_routes 的 /web/gold）；`main.py` 注册
- `tests/test_home_stitch.py` 18 用例（首页 200+4 链接、拼接页关键元素/vendor 引用/无 CDN/移动端 viewport、cropper 静态资源 200），全套 62 通过
- docs 整理：root 的 gold/crypto/stitch-invest.md 三份 PRD 移入 `docs/`；同步更新 `config.py`、`services/gold/__init__.py`、AGENTS.md 中的引用为 `docs/gold-invest.md`，文档内部 `AGENTS.md` 相对路径改为 `../AGENTS.md`；项目结构树注释同步更新

### 2026-09-04
- 新增 Au(T+D) 日K线走势（走势子页面，huilvbiao gold_autd_kline 数据源，已验证裸 GET 可用无需认证）
- `models/gold_model.py`：`gold_kline_daily` 表（复合主键 symbol+trade_date 去重；夜市根归属下一交易日，随夜市推进反复 upsert 直至定型）
- `services/gold/clients/kline_client.py`：上游客户端 + 归一化；`services/gold/kline.py`：TTL 节流同步（10min）+ 分批 INSERT..ON DUPLICATE KEY UPDATE + 查询信封（DB 优先；DB 失败降级直读上游并 60s 冷却，避免每请求吃连接超时；`database/__init__.py` engine 加 connect_timeout=3）
- `routes/gold_routes.py`：`GET /api/gold/kline?days=N`（1~730）；`routes/web_routes.py`：`GET /web/gold/trend`（图表数据走前端 fetch JSON，不适用 all-OOB 片段协议）
- 前端：vendor echarts 5.6.1 + `static/js/gold_kline.js`（蜡烛图/MA5~30/日K→周K月K聚合/dataZoom 窗口高低标记，暗色涨红跌绿，逻辑借鉴 huilvbiao gold_charts.min.js 重写为 vanilla JS）+ `templates/gold/trend.html` + 主页头部走势入口
- `services/scheduler_service.py`：K线同步 15:45（当日交易日）/ 02:40（前一自然日为交易日，覆盖周五夜市）
- `tests/test_gold_kline.py` 14 用例，全套 44 通过；实测降级路径 API 0.22s、页面渲染/周月切换正常

### 2026-09-04
- 落实 gold-web-review.md 遗留建议（Review 结论：all-OOB 修复合适，14/14 测试通过）
- `routes/web_routes.py`：删除 6 处死代码 `oob` 上下文参数；`fragment_all` 上游并发化（ThreadPoolExecutor，冷缓存 7.4s → 3.2s，热缓存 22ms）；docstring 固化 all-OOB 约定与 20s 浏览器超时的依据（PRD 5s 指上游单路，由 GOLD_CONFIG 强制）
- 模板清理：4 个片段删无用 `module-btn` class；page.html 删无用 `<body hx-headers>`
- 32/32 测试通过，uvicorn 实测页面 150ms / fragments/all 冷 3.2s 热 22ms

### 2026-09-04
- 新增黄金行情前端页面（docs/gold-invest.md PRD M1/M3，htmx 架构）
- `routes/web_routes.py`：`GET /web/gold` 页面 + 6 个 HTML 片段端点（domestic/international/otc/etf/{tab}/all），直调 services.gold.service 共享 30s 缓存
- 降级协议：上游硬失败返回 HTTP 204 + HX-Trigger gold-error（htmx 不 swap，旧数据保留）；code=2 渲染「缓存」徽标 + gold-stale 事件
- `templates/gold/`：page.html（现代金融暗色 UI：#0d1117 底、涨红跌绿、金色签名溢价条、等宽数字、移动端隐藏次要列）+ 4 个片段模板
- 技术栈：htmx 2.0.4（请求/交换/加载态）+ Alpine 3.17.1（Tab 切换/Toast/懒加载）+ Tailwind + DaisyUI，vendor 库复制入仓 `static/vendor/`，无 setInterval
- Tab 2~4 首次激活自动拉取一次，此后纯前端切换 + 手动刷新（经确认偏离 PRD §5.1 严格纯切换）
- `database/__init__.py`：init_db 失败降级运行（黄金前端不依赖 DB）
- ETF 行补充 scale 字段；OTC 行补充 cls/parent；新增 jinja2 依赖；`tests/test_gold_web.py` 13 个用例

### 2026-09-04
- 新增黄金行情追踪器后端包（docs/gold-invest.md PRD M2）
- `services/gold/`：catalog（锁定的 7 ETF + 8 场外标的与 Tab 分类）、30s TTL 缓存 + last-good 降级、4 个上游客户端、7 个聚合服务函数
- 降级链实测：ETF 走 AkShare → 新浪批量 → 腾讯逐个；伦敦金走新浪 hf_XAU（Yahoo XAUUSD=X 已下架）；场外净值走天天基金 lsjz（fundgz 估值接口已停用，估值改由母 ETF 涨跌推导）
- `models/gold_model.py`：金价/ETF 快照表（混合持久化，每日收盘后快照，非交易日跳过）
- `routes/gold_routes.py`：PRD §9 全部 7 个端点，统一 `{code, ts, stale, msg, data}` 响应
- 新增依赖 httpx、cachetools；新增 dev 组 pytest 与 `[tool.pytest.ini_options]`

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
