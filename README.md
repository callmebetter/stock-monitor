# Stock Monitoring API

This is a FastAPI-based backend service for monitoring stock data, using AkShare for data collection, MySQL for storage, and APScheduler for scheduled tasks.

## 📦 Features

- Fetch real-time stock data using [AkShare](https://akshare.xyz/)
- Store historical stock data in MySQL
- Analyze and screen stocks based on TDX formula logic
- Expose RESTful APIs for querying stock data
- Initialize database schema

## 🛠️ Technology Stack

- **Data Source**: [AkShare](https://akshare.xyz/)
- **Database**: MySQL
- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **ORM**: SQLAlchemy
- **Scheduler**: APScheduler

## 📁 Project Structure

```
stock-monitor/
├── database/
│   ├── __init__.py
│   └── init_db.py
├── models/
│   └── stock_model.py
├── services/
│   ├── data_collector.py
│   └── stock_analyzer.py
├── routes/
│   └── api_routes.py
├── config.py
├── main.py
├── pyproject.toml
└── README.md
```

## 🚀 Getting Started

### 1. Install Dependencies
```bash
uv sync
```

### 2. Set Up Database
- Create a MySQL database named `stock_monitor`
- Update database credentials in `.env` if needed

### 3. Initialize Database Schema
```bash
uv run  database/init_db.py
```

### 4. Start the Application
```bash
uv run  main.py
```

The API will be available at `http://localhost:8000`.

### 5. Available Endpoints

| Method | Endpoint           | Description                   |
|--------|--------------------|-------------------------------|
| GET    | `/`                | Welcome message               |
| GET    | `/api/stocks/today`| Get today's stock data        |
| POST   | `/api/stocks/update`| Manually update stock data   |
| GET    | `/api/stocks/screened`| Get screened stocks      |

## 🌐 Deployment

This project is deployed and managed on Alibaba Cloud VPS via the operations project.

| Item | Value |
|------|-------|
| Source | <https://github.com/callmebetter/stock-monitor.git> |
| VPS Deploy Path | `/var/www/stock-monitor/` |
| Process Manager | PM2 (`stock-monitor`, bash wrapper) |
| Listen | `127.0.0.1:8000` (Uvicorn) |
| Database | MySQL on same VPS |
| Ops Project | `D:\qwen-zone\阿里云VPS运维` (local) — startup scripts, PM2 config, ops logs |

Startup flow on VPS:
```bash
pm2 start /var/www/stock-monitor/start_panel.sh --name stock-monitor --interpreter bash
```

`start_panel.sh` internally runs:
```
exec .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

## 📝 License

This project is licensed under the MIT License.

## TODO
- collect stock data and store in mysql
- implement 选股逻辑（如混线粘连、放量大涨）
- 开发FastAPI接口提供restful api 查询
- 添加定时任务，使用 APScheduler每日自动运行采集和分析流程