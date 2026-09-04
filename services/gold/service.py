"""Aggregation layer: 7 PRD §9 endpoints + 沪伦溢价 (PRD §6.3)."""
import logging
import time
from typing import Any

from services.gold.cache import get_cache
from services.gold.catalog import GRAMS_PER_OUNCE, OTC_BY_CODE, TABS
from services.gold.clients import etf_client, fund_client, intl_client, spot_client

logger = logging.getLogger(__name__)


def _envelope(data: Any, stale: bool = False, msg: str = "") -> dict:
    return {"code": 0 if not stale else 2, "ts": int(time.time()),
            "stale": stale, "msg": msg, "data": data}


def calc_premium(domestic: list[dict], intl: list[dict]) -> dict:
    """沪伦溢价（元/克）= 国内现货 − 国际金价×USD/CNY÷31.1035（Au9999 优先，缺则用 Au99.99）。"""
    domestic_price = None
    for sym in ("Au9999", "Au99.99"):
        domestic_price = next((d["price"] for d in domestic if d["symbol"] == sym and d["price"]), None)
        if domestic_price is not None:
            break
    xau = next((i["price"] for i in intl if i["symbol"] == "XAU" and i["price"]), None)
    usdcny = next((i["price"] for i in intl if i["symbol"] == "USDCNY" and i["price"]), None)
    if domestic_price is None or xau is None or usdcny is None:
        return {"premium": None, "formula": "国内金价 ≈ 国际金价 × USD/CNY ÷ 31.1035 + 境内溢价"}
    implied = float(xau) * float(usdcny) / GRAMS_PER_OUNCE
    return {"premium": round(float(domestic_price) - implied, 2), "implied": round(implied, 2),
            "formula": "国内金价 ≈ 国际金价 × USD/CNY ÷ 31.1035 + 境内溢价"}


def _cached(key: str, fetcher) -> dict:
    try:
        data, stale = get_cache().get_or_fetch(key, fetcher)
    except Exception as e:
        logger.error("gold fetch failed for %s: %s", key, e, exc_info=True)
        return {"code": 1, "ts": int(time.time()), "stale": False,
                "msg": "数据获取失败，请稍后重试", "data": []}
    if stale:
        return {"code": 2, "ts": int(time.time()), "stale": True,
                "msg": "上游超时，已返回上次缓存", "data": data}
    return _envelope(data)


def get_domestic() -> dict:
    return _cached("gold:domestic", spot_client.fetch_domestic)


def get_international() -> dict:
    def _fetch():
        intl = intl_client.fetch_international()
        # 溢价需要国内现货，失败时不阻断国际报价
        try:
            domestic = spot_client.fetch_domestic()
            premium = calc_premium(domestic, intl)
        except Exception as e:
            logger.warning("premium calc skipped: %s", e)
            premium = {"premium": None}
        return {"quotes": intl, "premium": premium}

    return _cached("gold:international", _fetch)


def _etf_group(tab: str) -> dict:
    codes = TABS[tab]["codes"]
    data, stale = get_cache().get_or_fetch(f"etf:{tab}", lambda: etf_client.fetch_etf_batch(codes))
    return data, stale


def _etf_envelope(tab: str) -> dict:
    try:
        data, stale = _etf_group(tab)
    except Exception as e:
        logger.error("gold ETF fetch failed for %s: %s", tab, e, exc_info=True)
        return {"code": 1, "ts": int(time.time()), "stale": False,
                "msg": "数据获取失败，请稍后重试", "data": []}
    if stale:
        return {"code": 2, "ts": int(time.time()), "stale": True,
                "msg": "上游超时，已返回上次缓存", "data": data}
    return _envelope(data)


def get_otc() -> dict:
    def _fetch():
        # 母ETF当日涨跌幅（命中 etf:main 缓存或仅拉 4 只），用于推导场外盘中估值
        parents = sorted({OTC_BY_CODE[c]["parent"] for c in TABS["otc"]["codes"]})
        try:
            etf_rows = etf_client.fetch_etf_batch(parents)
            parent_changes = {r["code"]: r.get("change_pct") for r in etf_rows if r.get("change_pct") is not None}
        except Exception as e:
            logger.warning("parent ETF quotes failed, OTC estimate disabled: %s", e)
            parent_changes = {}
        return fund_client.fetch_otc_batch(TABS["otc"]["codes"], parent_changes=parent_changes)

    return _cached("etf:otc", _fetch)


def get_lowfee() -> dict:
    return _etf_envelope("lowfee")


def get_band() -> dict:
    return _etf_envelope("band")


def get_main() -> dict:
    return _etf_envelope("main")


def get_all() -> dict:
    def _fetch():
        etfs = etf_client.fetch_etf_batch(TABS["main"]["codes"])
        otc = fund_client.fetch_otc_batch(TABS["otc"]["codes"])
        return {"etf": etfs, "otc": otc}

    return _cached("etf:all", _fetch)
