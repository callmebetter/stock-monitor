# 📊 股票监控系统开发问答文档

## 🧩 1. 项目目标

构建一个基于 Python 的股票筛选系统，使用 [AkShare](https://akshare.xyz/) 获取 A 股市场数据，结合 MySQL 存储历史数据，并通过 FastAPI 提供 RESTful 接口查询符合条件的股票。定时任务使用 APScheduler 实现每日自动采集和筛选。

---

## 🛠️ 2. 技术架构

| 层级 | 技术选型 |
|------|----------|
| 数据采集 | [AkShare](https://akshare.xyz/) |
| 数据存储 | MySQL |
| Web 框架 | FastAPI |
| 定时任务 | APScheduler |
| ORM | SQLAlchemy |
| 日志管理 | logging |
| 异常处理 | try-except + 自定义异常类 |

---

## 📁 3. 目录结构建议

```
stock-monitor/
├── docs/
│   └── faq.md
├── database/
│   ├── __init__.py
│   ├── init_db.py
│   └── models.py
├── services/
│   ├── data_collector.py
│   └── stock_analyzer.py
├── routes/
│   └── api_routes.py
├── config.py
├── main.py
├── requirements.txt
└── README.md
```

---

## 📦 4. 数据库设计

### 表结构：`stock_data`

| 字段名             | 类型     | 描述                     |
|--------------------|----------|--------------------------|
| id                 | BIGINT   | 主键                     |
| symbol             | VARCHAR  | 股票代码                 |
| name               | String   | 股票名称                 |
| date               | DATE     | 交易日期                 |
| open               | FLOAT    | 开盘价                   |
| high               | FLOAT    | 最高价                   |
| low                | FLOAT    | 最低价                   |
| close              | FLOAT    | 收盘价                   |
| volume             | INT      | 成交量（手）             |
| turnover_value     | FLOAT    | 成交金额（元）           |
| amplitude          | FLOAT    | 当日振幅百分比           |
| high_limit         | FLOAT    | 涨停价                   |
| low_limit          | FLOAT    | 跌停价                   |
| open_price         | FLOAT    | 开盘价                   |
| yesterday_close    | FLOAT    | 昨日收盘价               |
| volume_ratio       | FLOAT    | 量比                     |
| turnover_ratio     | FLOAT    | 换手率百分比             |
| pe_ttm             | FLOAT    | 市盈率（TTM）            |
| pb                 | FLOAT    | 市净率                   |
| market_value       | FLOAT    | 总市值（元）             |
| circulation_market_value | FLOAT | 流通市值（元）           |
| rise_speed         | FLOAT    | 涨速百分比               |
| change_from_beginning | FLOAT  | 年初至今涨跌幅百分比     |
| ma5                | FLOAT    | 5日均线                 |
| ma10               | FLOAT    | 10日均线                |
| ma20               | FLOAT    | 20日均线                |
| ma30               | FLOAT    | 30日均线                |
| ma60               | FLOAT    | 60日均线                |
| ma120              | FLOAT    | 120日均线               |
| zhanhe             | FLOAT    | 均线粘合度              |
| created_at         | DATETIME | 创建时间                 |

---

## 🔍 5. 选股逻辑实现（通达信公式转换）

### 条件一：均线粘合
- 计算 MA5, MA10, MA20, MA30, MA60
- 粘合度 = `(MAX(MA5~MA60) / MIN(MA5~MA60) - 1) * 100 < 3%`
- 近15天中至少有10天满足该条件

### 条件二：放量大涨
- 涨幅 > 5%
- 成交量 > 昨日成交量 × 1.5 倍

### 条件三：阳线上穿2~4根均线
- 收盘价上穿 2~4 根均线，且开盘价低于其中至少一根均线

### 条件四：换手率倍增
- 当前换手率是昨日的 2~5 倍

### 条件五：金叉信号
- MA60 上穿 MA120

---

## 🕒 6. 定时任务设计

使用 [APScheduler](file://d:codebasepython-devstock-monitorackend.venvLibsite-packageslask_apschedulerscheduler.py#L32-L377) 配置每日定时任务：
```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

def daily_job():
    collect_data()
    analyze_stocks()
    save_results()

if __name__ == "__main__":
    scheduler.add_job(daily_job, 'cron', hour=15, minute=10)
    scheduler.start()
```

---

## 🌐 7. 接口设计（FastAPI）

| 方法 | 路径             | 功能                     |
|------|------------------|--------------------------|
| GET  | /stocks/today    | 获取今日最新行情           |
| POST | /stocks/update   | 手动更新股票数据         |
| GET  | /stocks/screened | 获取符合选股条件的股票列表 |

---

## 📦 8. 依赖安装

```bash
pip install -r requirements.txt
```

---

## 📌 9. 初始化数据库

```bash
python database/init_db.py
```

---

## 🚀 10. 启动服务

```bash
python main.py
```

The API will be available at `http://localhost:8000`.

---

## 📝 License

This project is licensed under the MIT License.

# Stock Monitoring API 项目常见问题解答 (Q&A)

## 项目设置与配置

### Q1: 如何配置数据库连接？
A1: 在项目根目录下创建 `.env` 文件，并添加以下内容：
```
DATABASE_URL=mysql+pymysql://<username>:<password>@<host>:<port>/<database_name>
DB_USER=<username>
DB_PASSWORD=<password>
DB_HOST=<host>
DB_PORT=<port>
DB_NAME=<database_name>
```
将尖括号中的内容替换为您的实际数据库凭据。

### Q2: 需要安装哪些依赖？
A2: 创建 `requirements.txt` 文件并添加以下依赖：
```
fastapi
uvicorn
akshare
sqlalchemy
pymysql
apscheduler
python-dotenv
mysqlclient
```
然后使用命令 `uv pip install -r requirements.txt` 安装这些依赖。

### Q3: 如何初始化数据库？
A3: 运行以下命令来初始化数据库模式：
```
uv run database/init_db.py
```
这将创建所有需要的数据库表。

## 数据采集与分析

### Q4: 如何手动触发股票数据采集？
A4: 可以通过两种方式手动触发数据采集：
1. 使用 API 端点：发送 POST 请求到 `/api/stocks/update`
2. 运行命令：`uv run services/data_collector.py`

### Q5: 股票数据是如何自动采集的？
A5: 项目使用 APScheduler 设置了定时任务，默认在每个交易日的 15:30 执行。这个任务会调用 `daily_data_collection` 函数来采集和保存股票数据。

### Q6: 如何筛选符合条件的股票？
A6: 可以通过访问 `/api/stocks/screened` 端点获取根据 TDX 公式筛选的股票。筛选基于多个技术指标，包括均线粘合度、成交量变化、价格突破等条件。

## API 使用

### Q7: 有哪些可用的 API 端点？
A7: 当前提供以下 API 端点：
| 方法 | 端点           | 描述                   |
|------|----------------|------------------------|
| GET  | /              | 欢迎信息               |
| GET  | /api/stocks/today | 获取今天的股票数据     |
| POST | /api/stocks/update | 手动更新股票数据      |
| GET  | /api/stocks/screened | 获取筛选后的股票   |

### Q8: 如何测试 API 端点？
A8: 启动应用后，可以通过浏览器或工具如 Postman 访问 `http://localhost:8000/docs` 查看和测试 API 文档。FastAPI 自动生成了交互式文档界面，可以方便地测试各个端点。

## 项目运行

### Q9: 如何启动应用？
A9: 使用以下命令启动 FastAPI 应用：
```
uv run main.py
```
应用将在 `http://localhost:8000` 上运行。

### Q10: 应用启动后如何确保其持续运行？
A10: 应用使用 APScheduler 的 BackgroundScheduler 来管理定时任务。只要应用保持运行，定时任务就会在设定的时间自动执行数据采集。建议将应用部署在服务器上以确保持续运行。

## 已知问题与解决方案

### Q11: 启动应用时遇到 `ModuleNotFoundError` 怎么办？
A11: 这通常表示某些依赖未正确安装。请确保已安装所有必需的依赖包，特别是那些与数据库驱动和定时任务相关的包。例如：
```
uv add tzlocal
```
或者检查 requirements.txt 文件是否包含所有必要的依赖。

### Q12: 数据采集失败可能是什么原因？
A12: 数据采集失败可能有以下原因：
1. AkShare 数据源暂时不可用
2. 数据库连接问题
3. 网络超时
请检查日志文件以获取具体错误信息，并确保网络连接正常和数据库服务正在运行。
