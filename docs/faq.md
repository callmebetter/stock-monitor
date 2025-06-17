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