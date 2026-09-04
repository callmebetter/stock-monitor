"""Au(T+D) 日K线：同步持久化 + 查询服务（走势子页面核心数据源）.

数据流：
- 上游（汇率表，日K新→旧）→ normalize → MySQL gold_kline_daily
  分批 upsert（复合主键 symbol+trade_date 去重；进行中的夜市根随夜市
  推进被反复覆盖直至收盘定型）
- 读取路径（get_kline）：TTL 门控 best-effort 同步（默认 10 分钟一次，
  页面访问即可保持新鲜）→ DB 范围查询；DB 不可用/无数据 → 上游直读
  （30s 缓存 + last-good 降级），msg 标注实际来源

信封协议与 services.gold.service 一致：
- code=0 正常（含 DB 降级直读上游，数据本身是新鲜的）
- code=2 上游 last-good（数据滞后）
- code=1 全部失败
"""
import logging
import threading
import time

import config
from services.gold.cache import GoldCache
from services.gold.clients import kline_client

logger = logging.getLogger(__name__)

SYMBOL = "AUTD"
CHUNK = 300
DEFAULT_DAYS = 250
# 图表友好的紧凑行序：day, open, close, low, high（ECharts 蜡烛图顺序）, change, amplitude, volume
COLUMNS = ["day", "open", "close", "low", "high", "change", "amplitude", "volume"]

# 同步节流门控（日频数据，10 分钟同步一次足够）与上游直读缓存相互独立
_sync_gate = GoldCache(maxsize=4, ttl=config.GOLD_CONFIG.get("kline_ttl", 600))
_upstream = GoldCache(maxsize=4, ttl=30)

# DB 失败冷却：连接不上时 60s 内跳过同步/读取（get_or_fetch 不缓存失败，
# 否则每个请求都要吃一次 DB 连接超时）
FAIL_COOLDOWN = 60
_fail_lock = threading.Lock()
_last_fail_ts = 0.0


def _bar(r: dict) -> list:
    return [r["trade_date"].isoformat(), r["open"], r["close"], r["low"],
            r["high"], r["change"], r["amplitude"], r["volume"]]


def _insert_stmt(rows: list[dict]):
    """单批 INSERT ... ON DUPLICATE KEY UPDATE 语句（测试直接复用）。"""
    from sqlalchemy.dialects.mysql import insert as mysql_insert
    from models.gold_model import GoldKlineDaily

    stmt = mysql_insert(GoldKlineDaily).values([
        {"symbol": SYMBOL, "trade_date": r["trade_date"],
         "open": r["open"], "high": r["high"], "low": r["low"],
         "close": r["close"], "change": r["change"],
         "amplitude": r["amplitude"], "volume": r["volume"],
         "source": "huilvbiao"}
        for r in rows
    ])
    return stmt.on_duplicate_key_update(
        open=stmt.inserted.open, high=stmt.inserted.high,
        low=stmt.inserted.low, close=stmt.inserted.close,
        change=stmt.inserted.change, amplitude=stmt.inserted.amplitude,
        volume=stmt.inserted.volume,
    )


def sync_kline() -> dict:
    """拉上游并分批 upsert 入库。上游或 DB 失败时抛异常，由调用方处理。"""
    from database.database_utils import db_session_scope

    rows = kline_client.fetch_kline()
    with db_session_scope() as db:
        for i in range(0, len(rows), CHUNK):
            db.execute(_insert_stmt(rows[i:i + CHUNK]))
    logger.info("kline synced: %d rows, latest=%s", len(rows), rows[0]["trade_date"])
    return {"status": "success", "rows": len(rows), "latest": rows[0]["trade_date"].isoformat()}


def _ensure_fresh() -> None:
    """TTL 门控的 best-effort 同步：节流窗口内直接返回，超期则尝试 sync。

    任何失败仅告警不阻断——读取路径随后会落到上游直读降级。
    """
    try:
        _sync_gate.get_or_fetch("kline:sync", sync_kline)
    except Exception as e:
        logger.warning("kline sync skipped: %s", e)


def _read_db(days: int) -> list[list]:
    """最近 days 根（旧→新）。无数据或 DB 失败时抛异常/返回空。"""
    from database.database_utils import db_session_scope
    from models.gold_model import GoldKlineDaily

    with db_session_scope() as db:
        rows = (db.query(GoldKlineDaily)
                .filter(GoldKlineDaily.symbol == SYMBOL)
                .order_by(GoldKlineDaily.trade_date.desc())
                .limit(days).all())
    rows.reverse()
    return [[r.trade_date.isoformat(),
             float(r.open) if r.open is not None else None,
             float(r.close) if r.close is not None else None,
             float(r.low) if r.low is not None else None,
             float(r.high) if r.high is not None else None,
             float(r.change) if r.change is not None else None,
             float(r.amplitude) if r.amplitude is not None else None,
             r.volume] for r in rows]


def _db_available() -> bool:
    with _fail_lock:
        return time.time() - _last_fail_ts >= FAIL_COOLDOWN


def _mark_db_fail() -> None:
    global _last_fail_ts
    with _fail_lock:
        _last_fail_ts = time.time()


def get_kline(days: int = DEFAULT_DAYS) -> dict:
    bars = None
    msg = ""
    if _db_available():
        try:
            _ensure_fresh()
            bars = _read_db(days)
            if not bars:
                msg = "数据库暂无K线数据，已直读上游"
        except Exception as e:
            _mark_db_fail()
            logger.warning("kline DB path unavailable: %s", e)
            bars = None
            msg = "数据库不可用，已直读上游"
    else:
        msg = "数据库不可用，已直读上游"

    if not bars:
        try:
            rows, stale = _upstream.get_or_fetch("kline:upstream", kline_client.fetch_kline)
        except Exception as e:
            logger.error("kline fetch failed entirely: %s", e, exc_info=True)
            return {"code": 1, "ts": int(time.time()), "stale": False,
                    "msg": "数据获取失败，请稍后重试",
                    "data": {"symbol": SYMBOL, "columns": COLUMNS, "bars": []}}
        bars = [_bar(r) for r in reversed(rows)][-days:]  # 上游新→旧，转为旧→新
        data = {"symbol": SYMBOL, "columns": COLUMNS, "bars": bars}
        if stale:
            return {"code": 2, "ts": int(time.time()), "stale": True,
                    "msg": "上游超时，已返回上次缓存", "data": data}
        return {"code": 0, "ts": int(time.time()), "stale": False, "msg": msg, "data": data}

    return {"code": 0, "ts": int(time.time()), "stale": False, "msg": msg,
            "data": {"symbol": SYMBOL, "columns": COLUMNS, "bars": bars}}
