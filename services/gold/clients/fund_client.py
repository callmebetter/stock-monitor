"""场外联接基金：天天基金 lsjz 确认净值（HTTP-only，PRD §8.4）.

fundgz 盘中估值接口已停用（返回404页），估值改为由对应场内 ETF
当日涨跌幅推导：est_nav = 确认净值 × (1 + 母ETF当日涨跌幅/100)。
"""
import logging

import httpx

import config
from services.gold.catalog import OTC_BY_CODE

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Referer": "http://fund.eastmoney.com/",
}


def _empty_row(code: str, source: str = "tiantian-fund") -> dict:
    meta = OTC_BY_CODE[code]
    return {"code": code, "name": meta["name"], "price": None, "change_pct": None,
            "volume": None, "turnover": None, "nav": None, "est_nav": None,
            "fee": meta["fee"], "cls": meta["cls"], "parent": meta["parent"],
            "source": source}


def fetch_otc_batch(codes: list[str], parent_changes: dict[str, float] | None = None) -> list[dict]:
    """parent_changes: {母ETF代码: 当日涨跌幅%}，用于推导盘中估值。"""
    timeout = config.GOLD_CONFIG.get("timeout", 5)
    parent_changes = parent_changes or {}
    wanted = [c for c in codes if c in OTC_BY_CODE]
    out = []
    with httpx.Client(timeout=timeout, headers=_HEADERS) as client:
        for code in wanted:
            row = _empty_row(code)
            try:
                resp = client.get(
                    "https://api.fund.eastmoney.com/f10/lsjz",
                    params={"fundCode": code, "pageIndex": 1, "pageSize": 1},
                )
                resp.raise_for_status()
                rows = (resp.json().get("Data") or {}).get("LSJZList") or []
                if rows:
                    latest = rows[0]
                    nav = float(latest["DWJZ"]) if latest.get("DWJZ") else None
                    row.update(nav=nav, price=nav)
                    if latest.get("JZZZL"):
                        row["change_pct"] = float(latest["JZZZL"])
            except Exception as e:
                logger.warning("lsjz failed for %s: %s", code, e)
            parent = OTC_BY_CODE[code]["parent"]
            parent_pct = parent_changes.get(parent)
            if row["nav"] and parent_pct is not None:
                row["est_nav"] = round(row["nav"] * (1 + parent_pct / 100), 4)
                row["price"] = row["est_nav"]
                row["change_pct"] = parent_pct
                row["source"] = "lsjz+etf-estimate"
            out.append(row)
    return sorted(out, key=lambda r: wanted.index(r["code"]))
