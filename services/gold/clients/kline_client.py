"""黄金日K线客户端：汇率表 gold_autd_kline（Au(T+D) 日线，约 3 年历史）.

无需 Cookie/认证（实测裸 GET 可用）。上游返回 JSON 数组（新→旧），字段
open/high/low/close/price/volume/change/amplitude/day/date_time；首根为
进行中的夜市 K 线（day 归属下一交易日）。本模块只负责拉取与归一化，
缓存与持久化由 services/gold/kline.py 处理。
"""
import logging
from datetime import date

import httpx

import config

logger = logging.getLogger(__name__)

_URL = "https://www.huilvbiao.com/api/gold_autd_kline"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.huilvbiao.com/gold/autd"}

NUMERIC_FIELDS = ("open", "high", "low", "close", "change", "amplitude")


def parse_day(raw) -> date | None:
    """'2026/09/07' -> date；解析失败返回 None。"""
    try:
        y, m, d = (int(x) for x in str(raw).split("/"))
        return date(y, m, d)
    except (ValueError, TypeError):
        return None


def normalize(raw_rows) -> list[dict]:
    """上游行 -> 规范行（trade_date: date，价格类 float，volume int）。

    丢弃缺 day/close 或数值非法的行；保持上游顺序（新→旧）。
    """
    out: list[dict] = []
    for r in raw_rows or []:
        td = parse_day(r.get("day"))
        if td is None:
            continue
        row: dict = {"trade_date": td}
        try:
            for f in NUMERIC_FIELDS:
                row[f] = float(r[f]) if r.get(f) is not None else None
            row["volume"] = int(r["volume"]) if r.get("volume") is not None else None
        except (TypeError, ValueError):
            continue
        if row["close"] is None:
            continue
        out.append(row)
    return out


def fetch_kline() -> list[dict]:
    """拉取 Au(T+D) 日K（新→旧，含进行中夜市根），失败抛异常由上层处理。"""
    timeout = config.GOLD_CONFIG.get("timeout", 5)
    resp = httpx.get(_URL, timeout=timeout, headers=_HEADERS)
    resp.raise_for_status()
    rows = normalize(resp.json())
    if not rows:
        raise RuntimeError("kline upstream returned no valid rows")
    logger.info("kline fetched: %d rows, latest=%s", len(rows), rows[0]["trade_date"])
    return rows
